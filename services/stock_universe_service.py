"""
IDX AI Signal Bot - Stock Universe Service
Manages the master list of IDX stocks.
"""

import pandas as pd
from typing import List, Dict, Optional
from loguru import logger


# Default IDX stock universe (top ~50 liquid stocks for MVP)
# In production, this should be fetched from IDX API or database
DEFAULT_STOCK_UNIVERSE = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "BMRI", "name": "Bank Mandiri Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "TLKM", "name": "Telkom Indonesia Tbk", "sector": "Infrastructures", "subsector": "Telecommunication", "board": "Utama"},
    {"ticker": "ASII", "name": "Astra International Tbk", "sector": "Consumer Cyclicals", "subsector": "Automobiles", "board": "Utama"},
    {"ticker": "UNVR", "name": "Unilever Indonesia Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Consumer Goods", "board": "Utama"},
    {"ticker": "HMSP", "name": "HM Sampoerna Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Tobacco", "board": "Utama"},
    {"ticker": "GGRM", "name": "Gudang Garam Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Tobacco", "board": "Utama"},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Food & Beverages", "board": "Utama"},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Food & Beverages", "board": "Utama"},
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk", "sector": "Healthcare", "subsector": "Pharmaceuticals", "board": "Utama"},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "ANTM", "name": "Aneka Tambang Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "INCO", "name": "Vale Indonesia Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "ITMG", "name": "Indo Tambangraya Megah Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk", "sector": "Energy", "subsector": "Oil & Gas", "board": "Utama"},
    {"ticker": "SMGR", "name": "Semen Indonesia Tbk", "sector": "Basic Materials", "subsector": "Cement", "board": "Utama"},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Food & Beverages", "board": "Utama"},
    {"ticker": "EMTK", "name": "Elang Mahkota Teknologi Tbk", "sector": "Technology", "subsector": "Media", "board": "Utama"},
    {"ticker": "TOWR", "name": "Sarana Menara Nusantara Tbk", "sector": "Infrastructures", "subsector": "Telecommunication", "board": "Utama"},
    {"ticker": "TBIG", "name": "Tower Bersama Infrastructure Tbk", "sector": "Infrastructures", "subsector": "Telecommunication", "board": "Utama"},
    {"ticker": "MAPI", "name": "Mitra Adiperkasa Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "ERAA", "name": "Erajaya Swasembada Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "ACES", "name": "Ace Hardware Indonesia Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Food & Beverages", "board": "Utama"},
    {"ticker": "SSMS", "name": "Sawit Sumbermas Sarana Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "LSIP", "name": "PP London Sumatra Indonesia Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "AALI", "name": "Astra Agro Lestari Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "BSDE", "name": "Bumi Serpong Damai Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "CTRA", "name": "Ciputra Development Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "SMRA", "name": "Summarecon Agung Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "EXCL", "name": "XL Axiata Tbk", "sector": "Infrastructures", "subsector": "Telecommunication", "board": "Utama"},
    {"ticker": "ISAT", "name": "Indosat Tbk", "sector": "Infrastructures", "subsector": "Telecommunication", "board": "Utama"},
    {"ticker": "JSMR", "name": "Jasa Marga Tbk", "sector": "Infrastructures", "subsector": "Toll Roads", "board": "Utama"},
    {"ticker": "WIKA", "name": "Wijaya Karya Tbk", "sector": "Infrastructures", "subsector": "Construction", "board": "Utama"},
    {"ticker": "WSKT", "name": "Waskita Karya Tbk", "sector": "Infrastructures", "subsector": "Construction", "board": "Utama"},
    {"ticker": "PTPP", "name": "PP (Persero) Tbk", "sector": "Infrastructures", "subsector": "Construction", "board": "Utama"},
    {"ticker": "UNTR", "name": "United Tractors Tbk", "sector": "Consumer Cyclicals", "subsector": "Heavy Equipment", "board": "Utama"},
    {"ticker": "INKP", "name": "Indah Kiat Pulp & Paper Tbk", "sector": "Basic Materials", "subsector": "Pulp & Paper", "board": "Utama"},
    {"ticker": "TKIM", "name": "Pabrik Kertas Tjiwi Kimia Tbk", "sector": "Basic Materials", "subsector": "Pulp & Paper", "board": "Utama"},
    {"ticker": "BRPT", "name": "Barito Pacific Tbk", "sector": "Basic Materials", "subsector": "Petrochemicals", "board": "Utama"},
    {"ticker": "ESSA", "name": "Surya Esa Perkasa Tbk", "sector": "Energy", "subsector": "Oil & Gas", "board": "Utama"},
    {"ticker": "BUKA", "name": "Bukalapak.com Tbk", "sector": "Technology", "subsector": "E-Commerce", "board": "Utama"},
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk", "sector": "Technology", "subsector": "E-Commerce", "board": "Utama"},
    {"ticker": "BRIS", "name": "Bank Syariah Indonesia Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "ARTO", "name": "Bank Jago Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "AMMN", "name": "Amman Mineral Internasional Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    
    # --- Konglomerasi Prajogo Pangestu ---
    {"ticker": "TPIA", "name": "Chandra Asri Pacific Tbk", "sector": "Basic Materials", "subsector": "Chemicals", "board": "Utama"},
    {"ticker": "BREN", "name": "Barito Renewables Energy Tbk", "sector": "Infrastructures", "subsector": "Utilities", "board": "Utama"},
    {"ticker": "CUAN", "name": "Petrindo Jaya Kreasi Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "PTRO", "name": "Petrosea Tbk", "sector": "Energy", "subsector": "Oil & Gas Equipment", "board": "Utama"},

    # --- Konglomerasi Bakrie ---
    {"ticker": "BUMI", "name": "Bumi Resources Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "BRMS", "name": "Bumi Resources Minerals Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "ENRG", "name": "Energi Mega Persada Tbk", "sector": "Energy", "subsector": "Oil & Gas", "board": "Utama"},
    {"ticker": "DEWA", "name": "Darma Henwa Tbk", "sector": "Energy", "subsector": "Oil & Gas Equipment", "board": "Utama"},
    {"ticker": "BNBR", "name": "Bakrie & Brothers Tbk", "sector": "Industrials", "subsector": "Holding Company", "board": "Utama"},

    # --- Konglomerasi Salim ---
    {"ticker": "SIMP", "name": "Salim Ivomas Pratama Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "DNET", "name": "Indoritel Makmur Internasional Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},

    # --- Konglomerasi Sinar Mas ---
    {"ticker": "SMMA", "name": "Sinar Mas Multiartha Tbk", "sector": "Financials", "subsector": "Financial Services", "board": "Utama"},
    {"ticker": "DSSA", "name": "Dian Swastatika Sentosa Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "DUTI", "name": "Duta Pertiwi Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},

    # --- Konglomerasi Hary Tanoe (MNC) ---
    {"ticker": "BHIT", "name": "MNC Asia Holding Tbk", "sector": "Financials", "subsector": "Holding Company", "board": "Utama"},
    {"ticker": "BMTR", "name": "Global Mediacom Tbk", "sector": "Technology", "subsector": "Media", "board": "Utama"},
    {"ticker": "MNCN", "name": "Media Nusantara Citra Tbk", "sector": "Technology", "subsector": "Media", "board": "Utama"},
    {"ticker": "MSIN", "name": "MNC Digital Entertainment Tbk", "sector": "Technology", "subsector": "Media", "board": "Utama"},
    {"ticker": "BABP", "name": "Bank MNC Internasional Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},

    # --- Konglomerasi Lippo ---
    {"ticker": "LPKR", "name": "Lippo Karawaci Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "LPPF", "name": "Matahari Department Store Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "SILO", "name": "Siloam International Hospitals Tbk", "sector": "Healthcare", "subsector": "Hospitals", "board": "Utama"},
    {"ticker": "MLPT", "name": "Multipolar Technology Tbk", "sector": "Technology", "subsector": "IT Services", "board": "Utama"},

    # --- Konglomerasi CT Corp & Lainnya ---
    {"ticker": "MEGA", "name": "Bank Mega Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "BBHI", "name": "Allo Bank Indonesia Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "MEDC", "name": "Medco Energi Internasional Tbk", "sector": "Energy", "subsector": "Oil & Gas", "board": "Utama"},
    {"ticker": "BYAN", "name": "Bayan Resources Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},

    # --- Tambahan Konglomerat 9 Naga & Tokoh Kunci ---
    {"ticker": "PANI", "name": "Pantai Indah Kapuk Dua Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "SRTG", "name": "Saratoga Investama Sedaya Tbk", "sector": "Financials", "subsector": "Investment Service", "board": "Utama"},
    {"ticker": "BELI", "name": "Global Digital Niaga Tbk", "sector": "Technology", "subsector": "E-Commerce", "board": "Utama"},
    {"ticker": "MAYA", "name": "Bank Mayapada Internasional Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "SRAJ", "name": "Sejahtera Anugrahjaya Tbk", "sector": "Healthcare", "subsector": "Hospitals", "board": "Utama"},
    {"ticker": "RANC", "name": "Supra Boga Lestari Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},

    # --- Saham Pilihan Lainnya / Kebutuhan User ---
    {"ticker": "INET", "name": "Sinergi Inti Andalan Prima Tbk", "sector": "Technology", "subsector": "Telecommunication", "board": "Utama"},

    # --- Tambahan Konstituen IDX80 ---
    {"ticker": "AADI", "name": "Adaro Andalan Indonesia Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "ADMR", "name": "Adaro Minerals Indonesia Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "AKRA", "name": "AKR Corporindo Tbk", "sector": "Energy", "subsector": "Oil & Gas", "board": "Utama"},
    {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "BBTN", "name": "Bank Tabungan Negara Tbk", "sector": "Financials", "subsector": "Banks", "board": "Utama"},
    {"ticker": "BKSL", "name": "Sentul City Tbk", "sector": "Properties & Real Estate", "subsector": "Property", "board": "Utama"},
    {"ticker": "CBDK", "name": "Citra Borneo Utama Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "CMRY", "name": "Cisarua Mountain Dairy Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Food & Beverages", "board": "Utama"},
    {"ticker": "DSNG", "name": "Dharma Satya Nusantara Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "ELSA", "name": "Elnusa Tbk", "sector": "Energy", "subsector": "Oil & Gas Equipment", "board": "Utama"},
    {"ticker": "HRTA", "name": "Hartadinata Abadi Tbk", "sector": "Consumer Cyclicals", "subsector": "Retail", "board": "Utama"},
    {"ticker": "HUMI", "name": "Humpuss Maritim Internasional Tbk", "sector": "Infrastructures", "subsector": "Transportation", "board": "Utama"},
    {"ticker": "HYGN", "name": "Ecofirst Pestindo Tbk", "sector": "Industrials", "subsector": "Commercial Services", "board": "Utama"},
    {"ticker": "INDY", "name": "Indika Energy Tbk", "sector": "Energy", "subsector": "Coal", "board": "Utama"},
    {"ticker": "MBMA", "name": "Merdeka Battery Materials Tbk", "sector": "Basic Materials", "subsector": "Mining", "board": "Utama"},
    {"ticker": "MIKA", "name": "Mitra Keluarga Karyasehat Tbk", "sector": "Healthcare", "subsector": "Hospitals", "board": "Utama"},
    {"ticker": "PNLF", "name": "Panin Financial Tbk", "sector": "Financials", "subsector": "Investment Service", "board": "Utama"},
    {"ticker": "SCMA", "name": "Surya Citra Media Tbk", "sector": "Technology", "subsector": "Media", "board": "Utama"},
    {"ticker": "SIDO", "name": "Industri Jamu dan Farmasi Sido Muncul Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Pharmaceuticals", "board": "Utama"},
    {"ticker": "SSIA", "name": "Surya Semesta Internusa Tbk", "sector": "Infrastructures", "subsector": "Construction", "board": "Utama"},
    {"ticker": "TAPG", "name": "Triputra Agro Persada Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Utama"},
    {"ticker": "WIFI", "name": "Solusi Sinergi Digital Tbk", "sector": "Technology", "subsector": "IT Services", "board": "Utama"},
    {"ticker": "GZCO", "name": "Gozco Plantations Tbk", "sector": "Consumer Non-Cyclicals", "subsector": "Plantations", "board": "Pengembangan"},
]



def get_stock_universe() -> List[Dict]:
    """
    Get the list of all active IDX stocks.
    For MVP: returns hardcoded universe.
    For production: fetch from IDX API or database.
    """
    logger.info(f"Loading stock universe: {len(DEFAULT_STOCK_UNIVERSE)} stocks")
    return [s for s in DEFAULT_STOCK_UNIVERSE if True]  # All active


def get_stock_by_ticker(ticker: str) -> Optional[Dict]:
    """Get stock info by ticker symbol. Allows ALL valid IDX tickers."""
    ticker = ticker.upper().strip()
    for stock in DEFAULT_STOCK_UNIVERSE:
        if stock["ticker"] == ticker:
            return stock
    
    # If not in the pre-defined universe but is a valid IDX ticker format
    if ticker.isalpha() and 3 <= len(ticker) <= 5:
        return {
            "ticker": ticker,
            "name": f"{ticker} (IDX Stock)",
            "sector": "Unknown",
            "subsector": "Unknown",
            "board": "Unknown"
        }
    return None


def get_stocks_by_sector(sector: str) -> List[Dict]:
    """Get all stocks in a specific sector."""
    sector_lower = sector.lower()
    return [s for s in DEFAULT_STOCK_UNIVERSE if s["sector"].lower() == sector_lower]


def get_all_sectors() -> List[str]:
    """Get list of unique sectors."""
    return list(set(s["sector"] for s in DEFAULT_STOCK_UNIVERSE))


def validate_ticker(ticker: str) -> bool:
    """Validate if ticker exists or is a valid IDX format."""
    return get_stock_by_ticker(ticker) is not None


# Known non-syariah stocks on IDX (conventional finance/banks, tobacco, alcohol)
NON_SYARIAH_TICKERS = {
    # Conventional Banks
    "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BDMN", "BNGA", "BNII", "BBHI",
    "MAYA", "BABP", "MEGA", "AGRO", "NOBU", "BACA", "BCIC", "BJBR", "BJTM",
    "BNLI", "PNBN", "MCOR", "AMAR", "ARTO", "BNBA", "BSWD", "DNAR", "INPC",
    "MASB", "NISP", "SDRA", "BVIC", "BGTG", "BEKS",
    # Tobacco
    "HMSP", "GGRM", "WIIM", "ITIC",
    # Alcoholic Beverages
    "MLBI", "DLTA",
    # Conventional Finance & Insurance
    "BFIN", "CFIN", "WOMF", "MFIN", "ADMF", "PNLF", "SMMA", "SRTG",
}


def is_syariah_stock(ticker: str) -> bool:
    """
    Check if ticker is Syariah compliant (Daftar Efek Syariah / ISSI constituent).
    By default in IDX, non-financial/non-tobacco/non-alcohol stocks are Syariah.
    """
    if not ticker:
        return True
    ticker_clean = ticker.upper().strip()
    if ticker_clean in NON_SYARIAH_TICKERS:
        return False
    stock_info = get_stock_by_ticker(ticker_clean)
    if stock_info:
        subsector = (stock_info.get("subsector") or "").lower()
        sector = (stock_info.get("sector") or "").lower()
        if "bank" in subsector and ticker_clean not in {"BRIS", "BTPS", "PNBS"}:
            return False
        if "tobacco" in subsector or "rokok" in subsector:
            return False
        if "alcohol" in subsector or "liquor" in subsector:
            return False
    return True

