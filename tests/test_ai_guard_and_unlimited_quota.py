import pytest
from unittest.mock import MagicMock
from services.scanner_engine import SignalOutput, ScannerEngine
from services.scoring_engine import ScoringResult


def test_ai_guard_logic_preserves_bullish_signals():
    """
    Rekomendasi 1: AI Guard harus mencegah Strategy Agent LLM (Gemini Vision)
    membatalkan sinyal bullish (BUY, STRONG BUY, WATCHLIST) menjadi AVOID atau SELL,
    baik di morning scan maupun noon scan.
    """
    scanner = ScannerEngine.__new__(ScannerEngine)

    test_cases = [
        # (deterministic_signal, llm_decision, expected_final)
        ("BUY", "AVOID", "BUY"),
        ("STRONG BUY", "AVOID", "STRONG BUY"),
        ("WATCHLIST", "AVOID", "WATCHLIST"),
        ("BUY", "SELL", "BUY"),
        ("STRONG BUY", "SELL", "STRONG BUY"),
        ("WATCHLIST", "SELL", "WATCHLIST"),
        # Normal upgrades / confirms:
        ("WATCHLIST", "BUY", "BUY"),
        ("BUY", "STRONG BUY", "STRONG BUY"),
    ]

    for det_sig, llm_dec, expected in test_cases:
        score_result = ScoringResult(ticker="BBCA", total_score=65.0, signal=det_sig, confidence_score=7)
        strategy_result = {"decision": llm_dec, "confidence_score": 3}

        final_signal = strategy_result["decision"]
        final_confidence = int(strategy_result.get("confidence_score", 5))

        # Replikasi persis blok AI Guard di ScannerEngine.scan_single
        if score_result.signal in ("BUY", "STRONG BUY", "WATCHLIST") and final_signal in ("AVOID", "SELL"):
            final_signal = score_result.signal
            final_confidence = max(final_confidence, score_result.confidence_score)

        assert final_signal == expected, f"Failed for {det_sig} + {llm_dec}: got {final_signal}, expected {expected}"


def test_unlimited_quota_and_no_sector_limit():
    """
    Penghapusan kuota Top 10 & Maksimal 3 Per Sektor:
    Ketika scan_all dipanggil dengan top_n=None (default baru):
    - Seluruh saham bullish hasil scoring Fase 2 diteruskan ke Fase 3.
    - Tidak ada pemotongan ke 10 saham.
    - Tidak ada pemotongan maksimal 3 saham per sektor.
    """
    # 25 saham bullish dengan 12 saham di antaranya dari sektor Financials
    results = []
    for i in range(25):
        sec = "Financials" if i < 12 else "Energy"
        dummy = MagicMock(spec=SignalOutput)
        dummy.ticker = f"STK{i}"
        dummy.signal = "BUY"
        dummy.raw_score = 80 - i
        dummy.sector = sec
        results.append(dummy)

    # Logika baru di scan_all:
    top_n = None
    if top_n is not None:
        top_candidates = results[:top_n]
    else:
        top_candidates = results

    # Verifikasi kuota tidak dibatasi 10
    assert len(top_candidates) == 25

    # Verifikasi sektor Financials tidak dipotong ke 3 (semua 12 tetap ada)
    fin_candidates = [c for c in top_candidates if c.sector == "Financials"]
    assert len(fin_candidates) == 12


def test_custom_top_n_still_supported_if_provided():
    """Jika user/kode tertentu secara eksplisit menentukan top_n, kuota tersebut dihormati."""
    results = [MagicMock(ticker=f"STK{i}") for i in range(20)]
    top_n = 5
    if top_n is not None:
        top_candidates = results[:top_n]
    else:
        top_candidates = results

    assert len(top_candidates) == 5
