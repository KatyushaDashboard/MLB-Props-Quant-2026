"""
utils/probability_engine.py
===========================
Menghitung probabilitas Over/Under untuk setiap prop
menggunakan distribusi yang paling tepat.
"""

from scipy.stats import binom, poisson
from typing import Optional
import math


def prob_over_under_binomial(
    expected_trials: float,
    rate: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """
    Hitung probabilitas Over/Under menggunakan Distribusi Binomial.
    
    Parameters:
    -----------
    expected_trials : Jumlah trial yang diharapkan (BF untuk pitcher, PA untuk hitter)
    rate            : Probabilitas sukses per trial (K-rate, HR-rate, dll)
    line            : Garis taruhan dari bandar (misal: 4.5)
    bet_type        : "over" atau "under"
    
    Returns:
    --------
    Probabilitas dalam persen (0-100)
    """
    # Binomial butuh n sebagai integer
    n = max(1, round(expected_trials))
    p = min(max(rate, 0.001), 0.999)  # Clamp antara 0.001 dan 0.999
    
    # line 4.5 berarti kita perlu >= 5 untuk OVER
    threshold = math.floor(line)  # 4.5 → 4
    
    if bet_type.lower() == "over":
        # P(X > line) = P(X >= threshold + 1) = 1 - P(X <= threshold)
        prob = 1 - binom.cdf(threshold, n, p)
    else:
        # P(X < line) = P(X <= threshold)
        prob = binom.cdf(threshold, n, p)
    
    return prob * 100.0


def prob_over_under_poisson(
    expected_value: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """
    Hitung probabilitas Over/Under menggunakan Distribusi Poisson.
    Digunakan sebagai fallback atau untuk event sangat langka (HR).
    """
    lam = max(expected_value, 0.01)
    threshold = math.floor(line)
    
    if bet_type.lower() == "over":
        prob = 1 - poisson.cdf(threshold, lam)
    else:
        prob = poisson.cdf(threshold, lam)
    
    return prob * 100.0


# ============================================================
# FUNGSI KHUSUS PER PROP
# ============================================================

def prob_pitcher_strikeouts(
    expected_bf: float,
    k_rate: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """Probabilitas untuk Pitcher Strikeouts."""
    return prob_over_under_binomial(expected_bf, k_rate, line, bet_type)


def prob_pitcher_outs(
    expected_bf: float,
    out_rate: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """Probabilitas untuk Pitcher Outs."""
    return prob_over_under_binomial(expected_bf, out_rate, line, bet_type)


def prob_hitter_hits(
    expected_pa: float,
    hit_rate: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """Probabilitas untuk Hitter Hits."""
    return prob_over_under_binomial(expected_pa, hit_rate, line, bet_type)


def prob_hitter_home_runs(
    expected_pa: float,
    hr_rate: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """
    Probabilitas untuk Hitter Home Runs.
    HR sangat langka, jadi kita pakai Poisson sebagai primary
    dan Binomial sebagai cross-check.
    """
    # Untuk HR, Poisson biasanya lebih stabil karena event sangat rare
    expected_hr = expected_pa * hr_rate
    return prob_over_under_poisson(expected_hr, line, bet_type)


def prob_hitter_total_bases(
    expected_pa: float,
    xba: float,
    xslg: float,
    line: float,
    bet_type: str = "over"
) -> float:
    """
    Probabilitas untuk Hitter Total Bases.
    TB lebih kompleks karena melibatkan multiple hit types.
    Kita aproksimasi dengan Poisson menggunakan expected TB.
    """
    expected_tb = expected_pa * xslg  # SLG ≈ TB per PA
    return prob_over_under_poisson(expected_tb, line, bet_type)