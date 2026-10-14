"""
utils/hitter_engine.py
======================
Engine untuk menghitung proyeksi Hitter Props: Hits, Total Bases, Home Runs.
Versi produksi - siap dipanggil oleh bot_updater.py
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple  # noqa: UP035

# ============================================================
# KONFIGURASI & KONSTANTA
# ============================================================

# Park Factors 2026 (akan di-update via backtesting nanti)
# Format: {nama_stadion: (hit_factor, hr_factor)}
# hit_factor: multiplier untuk xBA/xHits
# hr_factor: multiplier untuk xHR (biasanya lebih ekstrem dari hit_factor)
PARK_FACTORS: Dict[str, Tuple[float, float]] = {
    "Coors Field":                (1.18, 1.30),
    "Great American Ball Park":   (1.08, 1.15),
    "Yankee Stadium":             (1.05, 1.12),
    "Dodger Stadium":             (1.03, 1.05),
    "Wrigley Field":              (1.04, 1.08),
    "Guaranteed Rate Field":      (1.02, 1.06),
    "Fenway Park":                (1.06, 1.02),
    "Globe Life Field":           (1.00, 1.00),
    "Chase Field":                (1.03, 1.05),
    "Oracle Park":                (0.92, 0.85),
    "T-Mobile Park":              (0.93, 0.88),
    "Oakland Coliseum":           (0.95, 0.92),
    "PNC Park":                   (0.96, 0.94),
    "Progressive Field":          (0.97, 0.98),
    "Neutral Site":               (1.00, 1.00),
}

# ============================================================
# POSTSEASON ADJUSTMENTS
# ============================================================

# Penyesuaian Expected PA (Plate Appearance) untuk postseason.
# Di postseason, starter ditarik lebih cepat, lebih banyak bullpen,
# dan lebih banyak pinch hitter → rata-rata PA per batter turun.
# Regular season: ~4.0 PA/batter/game
# Postseason:     ~3.1 PA/batter/game (turun ~22%)
POSTSEASON_PA_MULTIPLIER = 0.980

# Penyesuaian hit/TB/HR untuk postseason (dari backtest 2023-2025)
POSTSEASON_HIT_MULTIPLIER = 0.926   # Akan diisi dari hasil tuning
POSTSEASON_TB_MULTIPLIER = 0.882
POSTSEASON_HR_MULTIPLIER = 0.809

# Konstanta konversi Barrel → HR (default, akan di-tune via backtesting)
BARREL_TO_HR_RATE = 0.449
BARREL_TO_HR_RATE_POSTSEASON = 0.402

# Default expected Plate Appearances per batter per game
DEFAULT_EXPECTED_PA = 3.70

# Posisi batting order mempengaruhi expected PA
# Leadoff & 2nd slot dapat lebih banyak PA, 8th & 9th lebih sedikit
PA_BY_BATTING_ORDER = {
    1: 4.6,  # Leadoff
    2: 4.4,
    3: 4.2,
    4: 4.1,  # Cleanup
    5: 4.0,
    6: 3.9,
    7: 3.8,
    8: 3.7,
    9: 3.6,  # Biasanya pitcher (NL) atau weak hitter
}


# ============================================================
# FUNGSI UTAMA
# ============================================================

def get_park_factor(venue_name: str) -> Tuple[float, float]:
    """
    Ambil Park Factor berdasarkan nama stadion.
    Return: (hit_factor, hr_factor)
    """
    return PARK_FACTORS.get(venue_name, (1.00, 1.00))


def get_expected_pa(batting_order_position: int = 0) -> float:
    """
    Hitung expected PA berdasarkan posisi batting order.
    """
    if 1 <= batting_order_position <= 9:
        return PA_BY_BATTING_ORDER[batting_order_position]
    return DEFAULT_EXPECTED_PA


def calculate_barrel_flag(launch_speed: float, launch_angle: float) -> int:
    """
    Tentukan apakah sebuah batted ball adalah Barrel.
    Berdasarkan definisi resmi MLB Statcast.
    
    Returns: 1 jika Barrel, 0 jika bukan.
    """
    if pd.isna(launch_speed) or pd.isna(launch_angle):
        return 0
    
    if launch_speed >= 98:
        max_la = 30 + (launch_speed - 98)
        min_la = 26 - (launch_speed - 98)
        
        if min_la <= launch_angle <= max_la:
            return 1
    
    return 0


def enrich_batted_ball_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tambahkan kolom-kolom turunan ke DataFrame Statcast.
    Dipanggil setelah pull data mentah.
    """
    df = df.copy()
    
    # Pastikan kolom numerik bertipe float
    numeric_cols = ['launch_speed', 'launch_angle', 
                    'estimated_ba_using_speedangle', 
                    'estimated_slg_using_speedangle']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Filter hanya Batted Ball Events (bola yang masuk permainan)
    df_bbe = df[df['launch_speed'].notna()].copy()
    
    if len(df_bbe) == 0:
        return df_bbe
    
    # Hitung Barrel flag
    df_bbe['is_barrel'] = df_bbe.apply(
        lambda row: calculate_barrel_flag(row['launch_speed'], row['launch_angle']),
        axis=1
    )
    
    # Hitung Hard Hit flag (Exit Velocity >= 95 mph)
    df_bbe['is_hard_hit'] = (df_bbe['launch_speed'] >= 95).astype(int)
    
    return df_bbe


def calculate_hitter_projection(
    df_batted_balls: pd.DataFrame,
    batter_id: int,
    venue_name: str,
    batting_order_position: int = 0,
    expected_pa_override: Optional[float] = None,
    is_postseason: bool = False
) -> Dict:
    """
    Hitung proyeksi Hitter Props untuk satu pemain di satu pertandingan.
    
    Parameters:
    -----------
    df_batted_balls : DataFrame yang sudah di-enrich (punya kolom is_barrel, dll)
    batter_id : MLBAM ID si batter
    venue_name : Nama stadion tempat bermain
    batting_order_position : Posisi di batting order (1-9)
    expected_pa_override : Override manual untuk expected PA (opsional)
    
    Returns:
    --------
    Dict berisi proyeksi xHits, xTB, xHR + metrik pendukung
    """
    
    # 1. Filter data untuk batter ini saja
    df_batter = df_batted_balls[df_batted_balls['batter'] == batter_id]
    
    if len(df_batter) < 5:  # Butuh minimal 5 BBE untuk proyeksi valid
        return {
            "batter_id": batter_id,
            "status": "INSUFFICIENT_DATA",
            "sample_size": len(df_batter),
            "xHits": None,
            "xTotalBases": None,
            "xHR": None,
        }
    
    # 2. Hitung metrik baseline dari data historis
    avg_xba = df_batter['estimated_ba_using_speedangle'].mean()
    avg_xslg = df_batter['estimated_slg_using_speedangle'].mean()
    barrel_rate = df_batter['is_barrel'].mean()
    hard_hit_rate = df_batter['is_hard_hit'].mean()
    avg_exit_velo = df_batter['launch_speed'].mean()
    sample_size = len(df_batter)
    
    # Handle NaN
    avg_xba = avg_xba if not np.isnan(avg_xba) else 0.250
    avg_xslg = avg_xslg if not np.isnan(avg_xslg) else 0.400
    barrel_rate = barrel_rate if not np.isnan(barrel_rate) else 0.05
    
    # 3. Ambil Park Factor
    hit_factor, hr_factor = get_park_factor(venue_name)
    
    # 4. Tentukan Expected PA
    if expected_pa_override:
        expected_pa = expected_pa_override
    else:
        expected_pa = get_expected_pa(batting_order_position)
    # Terapkan penyesuaian PA untuk postseason
    if is_postseason:
        expected_pa = expected_pa * POSTSEASON_PA_MULTIPLIER
    # 5. KALKULASI PROYEKSI
    # -----------------------------------------------
    
    # xHits = xBA × PA × hit_park_factor
    x_hits = avg_xba * expected_pa * hit_factor
    
    # xTotalBases = xSLG × PA × hit_park_factor
    # (SLG pada dasarnya = Total Bases per At-Bat)
    x_total_bases = avg_xslg * expected_pa * hit_factor
    
    # xHR = Barrel_Rate × PA × Barrel→HR_Rate × hr_park_factor
    expected_barrels = barrel_rate * expected_pa
    if is_postseason:
        x_hr = expected_barrels * BARREL_TO_HR_RATE_POSTSEASON * hr_factor
    else:
        x_hr = expected_barrels * BARREL_TO_HR_RATE * hr_factor
    # 6. TERAPKAN POSTSEASON ADJUSTMENT
    if is_postseason:
        x_hits = x_hits * POSTSEASON_HIT_MULTIPLIER
        x_total_bases = x_total_bases * POSTSEASON_TB_MULTIPLIER
        x_hr = x_hr * POSTSEASON_HR_MULTIPLIER
    
    # 6. Return hasil
    return {
        "batter_id": batter_id,
        "venue": venue_name,
        "expected_pa": round(expected_pa, 2),
        "sample_size": sample_size,
        "is_postseason": is_postseason,

        
        # Metrik Baseline
        "avg_xba": round(avg_xba, 3),
        "avg_xslg": round(avg_xslg, 3),
        "barrel_rate": round(barrel_rate, 3),
        "hard_hit_rate": round(hard_hit_rate, 3),
        "avg_exit_velo": round(avg_exit_velo, 1),
        
        # Park Factors yang diterapkan
        "hit_factor": hit_factor,
        "hr_factor": hr_factor,
        
        # PROYEKSI UTAMA
        "xHits": round(x_hits, 3),
        "xTotalBases": round(x_total_bases, 3),
        "xHR": round(x_hr, 3),
        
        "status": "OK",
    }


# ============================================================
# FUNGSI HELPER: Batch Processing
# ============================================================

def calculate_batch_projections(
    df_batted_balls: pd.DataFrame,
    batter_list: list,
    venue_name: str
) -> list:
    """
    Hitung proyeksi untuk banyak batter sekaligus (satu lineup).
    
    Parameters:
    -----------
    batter_list : List of dicts, format:
        [{"batter_id": 592450, "order": 3}, {"batter_id": 518792, "order": 4}, ...]
    venue_name : Stadion tempat mereka bermain
    """
    results = []
    
    for batter_info in batter_list:
        projection = calculate_hitter_projection(
            df_batted_balls=df_batted_balls,
            batter_id=batter_info["batter_id"],
            venue_name=venue_name,
            batting_order_position=batter_info.get("order", 0)
        )
        results.append(projection)
    
    return results