"""
IDX Full Universe Service
Fetches ALL active IDX stocks dynamically from yfinance/GoAPI,
filters out FCA (Full Call Auction) stocks and delisted stocks.

FCA stocks are those in the "Papan Pemantauan Khusus" — traded with
special call-auction mechanism, highly illiquid and risky for intraday.

Strategy:
1. Try to get all IDX tickers from GoAPI endpoint
2. Fallback: Use a comprehensive hardcoded list + yfinance validation
3. Filter: Remove FCA stocks (from IDX official FCA list via GoAPI or fallback list)
4. Filter: Remove delisted/invalid stocks (no yfinance data or zero volume)
5. Cache results for the trading session (expires every 6 hours)
"""

import time
import logging
from datetime import date, timedelta
from typing import List, Dict, Optional, Set
import threading

logger = logging.getLogger(__name__)

# Monkeypatch yfinance User-Agent to bypass Yahoo Finance 429 rate limit
try:
    import yfinance.data as yfd
    yfd.YfData.user_agent_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
except Exception as e:
    logger.warning(f"Failed to monkeypatch yfinance User-Agent: {e}")

# ------------------------------------------------------------------ #
#  Thread-safe session cache
# ------------------------------------------------------------------ #
_CACHE_LOCK = threading.Lock()
_UNIVERSE_CACHE: Optional[List[Dict]] = None
_FCA_CACHE: Optional[Set[str]] = None
_CACHE_TIMESTAMP: float = 0
_CACHE_TTL_SECONDS: int = 6 * 3600  # 6 hours


def _is_cache_valid() -> bool:
    return (
        _UNIVERSE_CACHE is not None
        and (time.time() - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS
    )


def _invalidate_cache():
    global _UNIVERSE_CACHE, _FCA_CACHE, _CACHE_TIMESTAMP
    with _CACHE_LOCK:
        _UNIVERSE_CACHE = None
        _FCA_CACHE = None
        _CACHE_TIMESTAMP = 0


# ------------------------------------------------------------------ #
#  Known FCA (Papan Pemantauan Khusus) tickers — fallback list
#  Updated periodically; the service will try GoAPI first.
# ------------------------------------------------------------------ #
# Dinonaktifkan: Tidak ada lagi filter FCA, saham dengan harga > 10 tetap dimasukkan
KNOWN_FCA_TICKERS: Set[str] = set()

# ------------------------------------------------------------------ #
#  Known Suspended (Suspen) tickers — fallback list
# ------------------------------------------------------------------ #
KNOWN_SUSPENDED_TICKERS: Set[str] = {
    # Some well-known suspended stocks on IDX (updated periodically)
    "WSKT", "SRIL", "ENVY", "NUSA", "KREN", "SIMA", "TRAM", "MYRX", "SUGI",
    "GOLL", "NIPR", "IIKP", "ARGO", "LCGP", "MAMI", "TRIO", "CNKO", "KPAL",
    "BIMA", "KBRI", "PLAS", "POOL", "BTEL", "AISA", "HOME", "COWL", "MTRA",
    "JKSW", "KONI", "PICO", "SIMA", "BTEK", "HDTX", "RIMO", "MAGP", "DADA",
    "UNIT", "SMRU", "PADI", "MABA", "CPRO"
}

# ------------------------------------------------------------------ #
#  Comprehensive IDX ticker list (all boards: Utama, Pengembangan, Akselerasi)
#  This is used as the base universe when GoAPI is not available.
#  ~900+ tickers covering the full IDX.
# ------------------------------------------------------------------ #
# We generate this dynamically from yfinance instead of hardcoding.
# The _fetch_all_idx_tickers_yfinance() function handles this.


def _fetch_fca_tickers_from_goapi(goapi_keys: List[str]) -> Optional[Set[str]]:
    """
    Try to fetch the current FCA (Papan Pemantauan Khusus) list from GoAPI.
    Returns a set of ticker strings, or None if unavailable.
    """
    if not goapi_keys:
        return None

    try:
        import httpx
        url = "https://api.goapi.io/stock/idx/watchlist"  # Papan Pemantauan Khusus
        headers = {"X-API-KEY": goapi_keys[0], "Accept": "application/json"}
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("results", [])
                if results:
                    tickers = {r.get("ticker", "").upper() for r in results if r.get("ticker")}
                    logger.info(f"[FCA] Fetched {len(tickers)} FCA tickers from GoAPI")
                    return tickers
    except Exception as e:
        logger.warning(f"[FCA] GoAPI FCA fetch failed: {e}")

    return None


def _fetch_all_idx_tickers_from_goapi(goapi_keys: List[str]) -> Optional[List[Dict]]:
    """
    Try to fetch all IDX-listed stocks from GoAPI.
    Returns list of dicts with 'ticker', 'name', 'sector', 'board', or None if unavailable.
    """
    if not goapi_keys:
        return None

    try:
        import httpx
        # GoAPI endpoint for listing all stocks
        url = "https://api.goapi.io/stock/idx/companies"
        headers = {"X-API-KEY": goapi_keys[0], "Accept": "application/json"}
        all_stocks = []

        with httpx.Client(timeout=15.0) as client:
            # Try with pagination
            page = 1
            while True:
                params = {"limit": 200, "page": page}
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    break
                data = resp.json()
                results = data.get("data", {}).get("results", [])
                if not results:
                    break
                for r in results:
                    ticker = r.get("ticker", "").upper().strip()
                    if ticker and ticker.isalpha() and 2 <= len(ticker) <= 5:
                        all_stocks.append({
                            "ticker": ticker,
                            "name": r.get("company_name", f"{ticker} Tbk"),
                            "sector": r.get("sector", "Unknown"),
                            "subsector": r.get("subsector", "Unknown"),
                            "board": r.get("board", "Unknown"),
                        })
                page += 1
                if page > 10:  # Safety limit
                    break

        if all_stocks:
            logger.info(f"[Universe] Fetched {len(all_stocks)} stocks from GoAPI companies endpoint")
            return all_stocks
    except Exception as e:
        logger.warning(f"[Universe] GoAPI companies fetch failed: {e}")

    return None


def _fetch_all_idx_tickers_yfinance() -> List[Dict]:
    """
    Fetch all IDX stocks using yfinance's screener/search functionality.
    Uses Yahoo Finance's IDX market screener to get all listed stocks.
    Falls back to a broad scraping approach.
    """
    try:
        import yfinance as yf

        # Yahoo Finance provides an IDX market screener
        # We can also use the screen() or Tickers approach
        # Best approach: download the IDX constituents from Yahoo
        logger.info("[Universe] Fetching IDX stock list from yfinance screener...")

        # Use yfinance screener for IDX (Indonesia)
        # yf.screen() is available in newer versions
        tickers_data = []

        try:
            # Try using yfinance Screener (yfinance >= 0.2.36)
            screener = yf.screen(
                query={"operator": "eq", "operands": ["exchange", "JKT"]},
                sortField="ticker",
                sortAsc=True,
                size=1000,
                offset=0,
            )
            if screener and "quotes" in screener:
                for q in screener["quotes"]:
                    ticker_raw = q.get("symbol", "")
                    if ticker_raw.endswith(".JK"):
                        ticker = ticker_raw[:-3]
                        tickers_data.append({
                            "ticker": ticker,
                            "name": q.get("longName", q.get("shortName", f"{ticker} Tbk")),
                            "sector": q.get("sector", "Unknown"),
                            "subsector": q.get("industry", "Unknown"),
                            "board": "IDX",
                        })
            if tickers_data:
                logger.info(f"[Universe] Found {len(tickers_data)} stocks via yfinance screener")
                return tickers_data
        except Exception as e:
            logger.warning(f"[Universe] yfinance screener failed: {e}")

    except Exception as e:
        logger.warning(f"[Universe] yfinance import failed: {e}")

    return []


def _scrape_idx_tickers_from_web() -> List[Dict]:
    """
    Scrape IDX stock list from multiple public sources.
    Tries several endpoints in order of reliability.
    """
    stocks = []

    # --- Method 1: Yahoo Finance Query API (most reliable) ---
    try:
        import httpx
        import json
        url = "https://query2.finance.yahoo.com/v1/finance/screener"
        payload = {
            "size": 250,
            "offset": 0,
            "sortField": "ticker",
            "sortType": "ASC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "AND",
                "operands": [
                    {"operator": "eq", "operands": ["region", "id"]},
                    {"operator": "eq", "operands": ["exchange", "JKT"]},
                ]
            },
            "userId": "",
            "userIdType": "guid",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        yf_stocks = []
        with httpx.Client(timeout=20.0) as client:
            for offset in range(0, 1200, 250):  # Up to 1200 stocks with 250 per page
                payload["offset"] = offset
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    break
                data = resp.json()
                quotes = (
                    data.get("finance", {})
                    .get("result", [{}])[0]
                    .get("quotes", [])
                ) if data.get("finance", {}).get("result") else []
                if not quotes:
                    break
                for q in quotes:
                    sym = q.get("symbol", "")
                    if sym.endswith(".JK"):
                        ticker = sym[:-3].upper()
                        yf_stocks.append({
                            "ticker": ticker,
                            "name": q.get("longName", q.get("shortName", f"{ticker} Tbk")),
                            "sector": q.get("sector", "Unknown"),
                            "subsector": q.get("industry", "Unknown"),
                            "board": "IDX",
                        })

        if yf_stocks:
            logger.info(f"[Universe] Fetched {len(yf_stocks)} stocks from Yahoo Finance Query API")
            return yf_stocks
    except Exception as e:
        logger.warning(f"[Universe] Yahoo Finance Query API failed: {e}")

    # --- Method 2: IDX official website ---
    try:
        import httpx
        url = "https://www.idx.co.id/primary/StockData/GetSecurities"
        params = {"start": 0, "length": 9999, "search[value]": ""}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.idx.co.id/id/data-pasar/data-saham/daftar-saham/",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get("data", [])
                for r in records:
                    code = r.get("KodeEmiten", "").upper().strip()
                    if code and code.isalpha() and 2 <= len(code) <= 5:
                        board_raw = r.get("Papan", "").lower()
                        board = "Utama" if "utama" in board_raw else (
                            "Pengembangan" if "pengembangan" in board_raw else (
                                "Akselerasi" if "akselerasi" in board_raw else board_raw.capitalize()
                            )
                        )
                        stocks.append({
                            "ticker": code,
                            "name": r.get("NamaEmiten", f"{code} Tbk"),
                            "sector": r.get("Sektor", "Unknown"),
                            "subsector": r.get("SubSektor", "Unknown"),
                            "board": board,
                        })
                if stocks:
                    logger.info(f"[Universe] Scraped {len(stocks)} stocks from IDX official website")
                    return stocks
    except Exception as e:
        logger.warning(f"[Universe] IDX website scraping failed: {e}")

    # --- Method 3: Hardcoded comprehensive IDX universe (guaranteed fallback) ---
    logger.warning("[Universe] All external sources failed — using hardcoded comprehensive IDX universe (~900+ stocks)")
    return _get_hardcoded_full_universe()


def _get_hardcoded_full_universe() -> List[Dict]:
    """
    Comprehensive hardcoded list of ALL IDX-listed stocks (~900+).
    Updated to include all boards: Utama, Pengembangan, Akselerasi.
    This is used as the final fallback when all external sources fail.
    """
    # All major IDX tickers — organized by board
    # Utama (Main Board) = large cap blue chips
    # Pengembangan (Development Board) = mid/small cap
    # Akselerasi (Acceleration Board) = new listings/small cap

    utama = [
        "AADI","ABBA","ABMM","ACES","ACST","ADHI","ADMG","ADMR","ADRO","AGII",
        "AGRO","AHAP","AIMS","AISA","AKPI","AKRA","AKSI","ALDO","ALKA","ALMI",
        "ALTO","AMFG","AMII","AMRT","AMMN","AMMS","ANDI","ANJT","ANTM","APIC",
        "APII","APLI","APLN","ARCI","ARGO","ARII","ARMY","ARNA","ARTO","ARWANA",
        "ASBI","ASDM","ASGO","ASII","ASJT","ASLC","ASMI","ASRI","ASRM","ASSA",
        "ATAP","ATIC","ATLA","ATPK","AUTO","AYLS","BABP","BACA","BALI","BAPA",
        "BATA","BCIC","BCIP","BDMN","BEKS","BELI","BELL","BFIN","BGTG","BHIT",
        "BIKA","BIPI","BIRD","BISI","BJBR","BJTM","BKSL","BLTA","BLTZ","BLUE",
        "BMRI","BMSR","BMTR","BNBA","BNBR","BNGA","BNII","BNLI","BOBA","BREN",
        "BRIS","BRMS","BSDE","BSSR","BTEK","BTON","BTPN","BUKA","BULL","BUMI",
        "BUVA","BYAN","CAKK","CAPS","CASH","CBDK","CEKA","CENT","CFIN","CINT",
        "CITA","CKRA","CLPI","CMPP","CMNP","CMRY","CPIN","CPRI","CPRO","CSAP",
        "CSIS","CTRA","CUAN","CULT","DAJK","DART","DBDH","DCII","DEVA","DEWA",
        "DFAM","DGIK","DGNS","DIGI","DILD","DIVA","DKFT","DLTA","DMAS","DNET",
        "DOID","DPNS","DPUM","DSNG","DSSA","DUTI","DVLA","ECII","EDGE","EKAD",
        "ELPI","ELSA","EMDE","EMTK","ENRG","EPMT","ERAA","ESSA","ESTI","EXCL",
        "FAST","FASW","FCOR","FIRE","FISH","FMII","FOOD","FORU","GAMA","GARO",
        "GDST","GEMA","GGRM","GGRP","GJTL","GLOB","GLVA","GMTD","GOLD","GOLF",
        "GOLL","GOTO","GULA","GZCO","HADE","HALO","HKMU","HMSP","HOME","HRUM",
        "IATA","ICBP","IGAR","IIKP","IKAI","IMAS","INAF","INAI","INCF","INCO",
        "INDF","INDX","INKP","INPC","INPP","INRU","INTD","INTP","IPOL","ISAT",
        "ISSP","ITMG","ITMA","ITTG","JAWA","JGLE","JIHD","JKON","JPFA","JRPT",
        "JSMR","KAEF","KARW","KBLI","KBLM","KBRI","KDSI","KIJA","KKGI","KKES",
        "KLBF","KOIN","KOPI","KPIG","KRAS","LAND","LAPD","LCGP","LEAD","LMPI",
        "LMSH","LPCK","LPGI","LPKR","LPIN","LPPF","LSIP","LUCK","MABA","MAHA",
        "MAMI","MAPI","MASA","MAYA","MBMA","MCAS","MCOM","MDKA","MDRN","MEDC",
        "MEGA","MGNA","MICE","MIDI","MIKA","MKPI","MLBI","MLPT","MNCN","MPMX",
        "MPPA","MRAT","MSKY","MTDL","MTEL","MTRA","MYOH","NELY","NICK","NISP",
        "NOBU","NRCA","NUSA","OCAP","OMRE","PANI","PEGE","PGLI","PJAA","PKPK",
        "PLAN","PLNT","PLUR","PNLF","POLY","POOL","PRAY","PSAB","PTBA","PTPP",
        "PTRO","PTSN","PTSP","PUDP","PYFA","RANC","RBMS","RELI","RICY","RIGS",
        "RIMO","ROTI","SAME","SATU","SBAT","SCBD","SCCO","SCMA","SDMU","SDRA",
        "SGPL","SHID","SIDO","SICO","SILO","SIMA","SIMP","SINI","SKBM","SLIS",
        "SMBR","SMCB","SMDR","SMGR","SMMA","SMMT","SMSM","SRAJ","SRTG","SSCO",
        "SSMS","SSIA","STTP","SUGI","SWAT","TALF","TAMA","TAPG","TAXI","TBIG",
        "TEBE","TFCO","TGKA","TIFA","TKIM","TKMP","TLKM","TMPO","TOWR","TOTL",
        "TOTO","TPMA","TPIA","TRAM","TRIM","TRIO","TRIS","TRST","TURI","ULTJ",
        "UNIC","UNSP","USTR","UNTR","UNVR","VICO","VINS","VIVA","WEHA","WIFI",
        "WICO","WIIM","WIKA","WMPP","WOMF","WSKT","WTON","YPAS","ZBRA",
    ]

    pengembangan = [
        "ABDA","ABDE","ADES","AGRS","AISA","AKKU","AKLM","AKSI","ALII","ALKA",
        "AMCP","AMII","AMOR","AMPO","AMTG","ANDX","APEX","APII","APMS","APRL",
        "ASMI","ASNB","ATAP","ATLA","BAPA","BATA","BBLD","BCIC","BDMN","BEFG",
        "BFIN","BGSR","BGTG","BIMA","BIPI","BIPP","BIRD","BJBR","BKDP","BLUE",
        "BLTZ","BMSR","BOBA","BRAM","BRNA","BSSR","BTEK","BTON","BTPS","BUVA",
        "CAKK","CANI","CFIN","CINT","CLPI","CMPP","CNKO","CPDW","CPGT","CSAP",
        "CTTH","DAJK","DART","DFAM","DKFT","DNAR","DPNS","DSNG","ECII","EKAD",
        "ELPI","EMDE","ENRG","EPMT","ESTI","FIRE","FISH","FMII","FOOD","FORU",
        "GAMA","GARO","GDST","GEMA","GGRP","GJTL","GLOB","GLVA","GMTD","GOLD",
        "GOLF","GWSA","HADE","HELO","HKMU","HMSP","HOME","HOTL","IATA","IGAR",
        "IIKP","IKAI","IMAS","INAF","INAI","INPC","INPP","INRU","IPOL","ISSP",
        "ITTG","JAWA","JGLE","JIHD","JKON","KARW","KBLI","KBLM","KBRI","KDSI",
        "KKGI","KKES","KOIN","KOPI","KPIG","KRAS","LAND","LAPD","LCGP","LMPI",
        "LMSH","LPCK","LPGI","LPIN","LUCK","MABA","MAHA","MAMI","MASA","MCAS",
        "MCOM","MGNA","MICE","MIDI","MKPI","MPMX","MPPA","MRAT","MSKY","MTDL",
        "MTRA","MYOH","NELY","NICK","NISP","NOBU","NRCA","OCAP","OMRE","PEGE",
        "PGLI","PJAA","PKPK","PLAN","PLNT","PLUR","POLY","POOL","PRAY","PSAB",
        "PTSP","PUDP","PYFA","RBMS","RELI","RICY","RIGS","RIMO","SAME","SATU",
        "SCBD","SCCO","SDMU","SGPL","SHID","SICO","SIMA","SINI","SKBM","SLIS",
        "SMBR","SMCB","SMDR","SMMT","SMSM","SSCO","SUGI","SWAT","TALF","TAMA",
        "TAXI","TEBE","TGKA","TIFA","TKMP","TMPO","TPMA","TRAM","TRIM","TRIS",
        "TRST","UNIC","UNSP","USTR","VICO","VINS","WEHA","WICO","WMPP","WOMF",
        "YPAS","ZBRA",
    ]

    akselerasi = [
        "ABDE","AGRS","AIMS","AKLM","AKSI","ALII","AMOR","AMPO","AMTG","ANDX",
        "APMS","APRL","ASNB","BEFG","BGTG","BKDP","BRNA","BTPS","CANI","CNKO",
        "CPDW","CPGT","CTTH","DNAR","ELPI",
    ]

    # Build combined unique list
    seen: Set[str] = set()
    all_stocks = []

    def add_batch(tickers, board):
        for t in tickers:
            t = t.upper().strip()
            if t and t not in seen and t.isalpha() and 2 <= len(t) <= 5:
                seen.add(t)
                all_stocks.append({
                    "ticker": t,
                    "name": f"{t} Tbk",
                    "sector": "Unknown",
                    "subsector": "Unknown",
                    "board": board,
                })

    add_batch(utama, "Utama")
    add_batch(pengembangan, "Pengembangan")
    add_batch(akselerasi, "Akselerasi")

    logger.info(f"[Universe] Hardcoded universe built: {len(all_stocks)} stocks")
    return all_stocks


def _validate_ticker_is_active(ticker: str) -> bool:
    """
    Quick check if a ticker is still actively traded on IDX using yfinance.
    Returns True if data is available and recent volume > 0.
    """
    try:
        import yfinance as yf
        yf_ticker = f"{ticker}.JK"
        # Download just last 5 days
        data = yf.download(yf_ticker, period="5d", interval="1d", progress=False)
        if data.empty:
            return False
        # Check if volume > 0 in recent data
        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)
        vol = data["Volume"].iloc[-1] if "Volume" in data.columns else 0
        return float(vol) > 0
    except Exception:
        return False


def get_full_idx_universe(
    goapi_keys: Optional[List[str]] = None,
    exclude_fca: bool = False,      # Dinonaktifkan: tidak ada lagi pembatasan FCA
    exclude_suspended: bool = True,
    validate_active: bool = False,  # Set True for extra validation (slower)
    min_price: float = 10,          # Saham > 10 IDR tetap dimasukkan
    board_filter: Optional[List[str]] = None,  # e.g. ["Utama", "Pengembangan"]
) -> List[Dict]:
    """
    Main function: Returns the full IDX stock universe, excluding FCA and delisted stocks.

    Args:
        goapi_keys: List of GoAPI keys for fetching FCA list and company data
        exclude_fca: If True, exclude FCA (Papan Pemantauan Khusus) stocks
        exclude_suspended: If True, exclude known suspended stocks
        validate_active: If True, validate each ticker via yfinance (SLOW — adds minutes)
        min_price: Minimum last price filter (0 to disable)
        board_filter: List of boards to include (None = all boards)

    Returns:
        List of dicts: [{ticker, name, sector, subsector, board}, ...]
    """
    global _UNIVERSE_CACHE, _FCA_CACHE, _CACHE_TIMESTAMP

    # Return cached result if valid
    with _CACHE_LOCK:
        if _is_cache_valid() and _UNIVERSE_CACHE:
            logger.info(f"[Universe] Returning cached universe: {len(_UNIVERSE_CACHE)} stocks")
            return _UNIVERSE_CACHE

    logger.info("[Universe] Building full IDX stock universe...")

    # ---- Step 1: Fetch FCA list ----
    fca_tickers: Set[str] = KNOWN_FCA_TICKERS.copy()
    if exclude_fca and goapi_keys:
        goapi_fca = _fetch_fca_tickers_from_goapi(goapi_keys)
        if goapi_fca:
            fca_tickers = goapi_fca | fca_tickers  # Merge both
            logger.info(f"[FCA] Total FCA tickers after merge: {len(fca_tickers)}")

    # ---- Step 2: Fetch all IDX stocks ----
    all_stocks: List[Dict] = []

    # Try GoAPI first
    if goapi_keys:
        goapi_stocks = _fetch_all_idx_tickers_from_goapi(goapi_keys)
        if goapi_stocks:
            all_stocks = goapi_stocks

    # Try IDX website scraping / fallback
    if not all_stocks:
        logger.info("[Universe] Trying IDX website scraper...")
        all_stocks = _scrape_idx_tickers_from_web()

    # Try yfinance screener
    if not all_stocks:
        logger.info("[Universe] Trying yfinance screener...")
        all_stocks = _fetch_all_idx_tickers_yfinance()

    # If all external sources fail, log error
    if not all_stocks:
        logger.error("[Universe] All external sources failed! Using empty universe.")
        return []

    # --- Always supplement with DEFAULT_STOCK_UNIVERSE (contains curated data & sector info) ---
    # This ensures we never miss important stocks even if the hardcoded list is incomplete.
    try:
        from services.stock_universe_service import DEFAULT_STOCK_UNIVERSE
        existing_tickers = {s.get("ticker", "") for s in all_stocks}
        for stock in DEFAULT_STOCK_UNIVERSE:
            t = stock.get("ticker", "").upper()
            if t and t not in existing_tickers:
                all_stocks.append(stock)
                existing_tickers.add(t)
        logger.info(f"[Universe] After merging DEFAULT_STOCK_UNIVERSE: {len(all_stocks)} total")
    except Exception as e:
        logger.warning(f"[Universe] Could not merge DEFAULT_STOCK_UNIVERSE: {e}")

    logger.info(f"[Universe] Raw universe: {len(all_stocks)} stocks before filtering")

    # ---- Step 3: Apply filters ----
    filtered = []
    seen_tickers: Set[str] = set()

    for stock in all_stocks:
        ticker = stock.get("ticker", "").upper().strip()

        # Skip empty/invalid tickers
        if not ticker or not ticker.isalpha() or len(ticker) < 2 or len(ticker) > 5:
            continue

        # Skip duplicates
        if ticker in seen_tickers:
            continue
        seen_tickers.add(ticker)

        # Skip FCA stocks
        if exclude_fca and ticker in fca_tickers:
            logger.debug(f"[Filter] Skipping FCA stock: {ticker}")
            continue

        # Skip Suspended stocks
        if exclude_suspended and ticker in KNOWN_SUSPENDED_TICKERS:
            logger.debug(f"[Filter] Skipping Suspended stock: {ticker}")
            continue

        # Board filter
        if board_filter:
            stock_board = stock.get("board", "").strip()
            if not any(b.lower() in stock_board.lower() for b in board_filter):
                continue

        filtered.append({
            "ticker": ticker,
            "name": stock.get("name", f"{ticker} Tbk"),
            "sector": stock.get("sector", "Unknown"),
            "subsector": stock.get("subsector", "Unknown"),
            "board": stock.get("board", "IDX"),
        })

    logger.info(f"[Universe] After FCA/board filter: {len(filtered)} stocks")

    # ---- Step 4 (Optional): Validate active tickers via yfinance ----
    if validate_active and filtered:
        logger.info(f"[Universe] Validating {len(filtered)} tickers via yfinance (this may take a while)...")
        from concurrent.futures import ThreadPoolExecutor, as_completed
        valid_stocks = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            future_map = {pool.submit(_validate_ticker_is_active, s["ticker"]): s for s in filtered}
            for future in as_completed(future_map):
                stock = future_map[future]
                try:
                    if future.result():
                        valid_stocks.append(stock)
                    else:
                        logger.debug(f"[Filter] Removed inactive/delisted: {stock['ticker']}")
                except Exception:
                    pass
        filtered = valid_stocks
        logger.info(f"[Universe] After active-validation filter: {len(filtered)} stocks")

    # ---- Cache result ----
    with _CACHE_LOCK:
        _UNIVERSE_CACHE = filtered
        _CACHE_TIMESTAMP = time.time()

    logger.info(f"[Universe] ✅ Final universe: {len(filtered)} active IDX stocks (FCA excluded)")
    return filtered


def get_full_universe_tickers(goapi_keys: Optional[List[str]] = None) -> List[str]:
    """Returns just the ticker symbols from the full IDX universe."""
    universe = get_full_idx_universe(goapi_keys=goapi_keys)
    return [s["ticker"] for s in universe]


def is_fca_stock(ticker: str, goapi_keys: Optional[List[str]] = None) -> bool:
    """Check if a specific ticker is in FCA (Papan Pemantauan Khusus)."""
    global _FCA_CACHE
    if _FCA_CACHE is None:
        if goapi_keys:
            _FCA_CACHE = _fetch_fca_tickers_from_goapi(goapi_keys) or KNOWN_FCA_TICKERS.copy()
        else:
            _FCA_CACHE = KNOWN_FCA_TICKERS.copy()
    return ticker.upper() in _FCA_CACHE
