"""
utils/pitcher_engine.py
=======================
Engine untuk menghitung proyeksi Pitcher Props: Strikeouts (xK) dan Outs (xOuts).
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional  # noqa: UP035

# ============================================================
# KONFIGURASI & KONSTANTA
# ============================================================

# Rata-rata jumlah batter yang dihadapi (Batters Faced / PA) per game
# Starter di regular season biasanya menghadapi 20-24 batter.
# Di postseason, karena "short leash" (cepat ditarik), ini turun drastis.
REGULAR_SEASON_AVG_BF = 20.9
POSTSEASON_AVG_BF = 17.8  # Estimasi awal, akan kita tune via backtest nanti!

# Multiplier Postseason untuk Strikeout
# Di postseason, umpire cenderung memberi strike zone lebih lebar, 
# dan batter lebih agresif -> K% pitcher biasanya naik.
POSTSEASON_K_MULTIPLIER = 1.058 # Estimasi awal
# Multiplier Postseason untuk Outs
# Di postseason, defense lebih rapat dan pitcher lebih fokus -> out rate naik sedikit
POSTSEASON_OUT_MULTIPLIER = 1.004 # Hipotesis awal, akan kita tune nanti


# ============================================================
# FUNGSI UTAMA
# ============================================================

def calculate_pitcher_projection(
    df_statcast: pd.DataFrame,
    pitcher_id: int,
    is_postseason: bool = False,
    dynamic_expected_bf: Optional[float] = None  # <-- TAMBAHAN BARU
) -> Dict:
    """
    Hitung proyeksi Pitcher Props untuk satu pertandingan.
    """
    # 1. Filter data khusus untuk pitcher ini
    df_pitcher = df_statcast[df_statcast['pitcher'] == pitcher_id].copy()
    
    if len(df_pitcher) < 20:
        return {
            "pitcher_id": pitcher_id,
            "status": "INSUFFICIENT_DATA",
            "xK": None,
        }
    
    # 2. Hitung Batters Faced (BF) dengan BENAR
    # Gunakan kombinasi (game_pk, at_bat_number) untuk menghitung PA unik
    if 'game_pk' in df_pitcher.columns and 'at_bat_number' in df_pitcher.columns:
        total_bf = df_pitcher[['game_pk', 'at_bat_number']].drop_duplicates().shape[0]
    else:
        # Fallback: hitung baris di mana 'events' terisi (akhir dari satu PA)
        pa_events = [
            'strikeout', 'strikeout_call', 'strikeout_swinging',
            'walk', 'hit_by_pitch',
            'single', 'double', 'triple', 'home_run',
            'field_out', 'grounded_into_double_play', 'force_out',
            'sac_fly', 'sac_bunt', 'fielders_choice',
            'fielders_choice_out', 'double_play', 'triple_play',
            'caught_stealing_2b', 'caught_stealing_3b',
            'pickoff_caught_stealing_2b', 'pickoff_caught_stealing_1b'
        ]
        total_bf = len(df_pitcher[df_pitcher['events'].isin(pa_events)])
    
    # 3. Hitung jumlah Strikeout dengan BENAR
    # Di Statcast, 'events' = 'strikeout' hanya muncul di 1 baris per PA
    # (yaitu di pitch terakhir yang mengakhiri PA tersebut)
    strikeout_events = ['strikeout', 'strikeout_call', 'strikeout_swinging',
                        'strikeout_double_play', 'strikeout_triple_play']
    
    strikeouts = len(df_pitcher[
        df_pitcher['events'].astype(str).str.strip().isin(strikeout_events)
    ])

        # 4. HITUNG OUTS (TAMBAHAN BARU)
    # Daftar event di Statcast yang menghasilkan Out
    out_events = [
        'field_out', 'force_out', 'grounded_into_double_play', 
        'double_play', 'sac_fly', 'sac_bunt',
        'strikeout', 'strikeout_call', 'strikeout_swinging', 
        'strikeout_double_play', 'strikeout_triple_play'
    ]
    
    total_outs = len(df_pitcher[df_pitcher['events'].astype(str).str.strip().isin(out_events)])
    
    # Hitung Out Rate (Outs per Batters Faced)
    if total_bf > 0:
        out_rate = total_outs / total_bf
    else:
        out_rate = 0.65  # Default MLB average jika data kosong
    
    # 4. Hitung K-Rate
    if total_bf == 0:
        k_rate = 0.20
    else:
        k_rate = strikeouts / total_bf
    
    # Sanity check: K-rate tidak boleh > 0.50 (50% sudah sangat ekstrem)
    if k_rate > 0.50:
        k_rate = 0.50
    
        # 5. Tentukan Expected BF & K-Rate Adjusted
    if dynamic_expected_bf is not None:
        expected_bf = dynamic_expected_bf
        if is_postseason:
            postseason_bf_ratio = POSTSEASON_AVG_BF / REGULAR_SEASON_AVG_BF
            expected_bf = expected_bf * postseason_bf_ratio
    elif is_postseason:
        expected_bf = POSTSEASON_AVG_BF
    else:
        expected_bf = REGULAR_SEASON_AVG_BF
    
    # K-Rate adjustment tetap berlaku untuk postseason
    if is_postseason:
        k_rate_adjusted = k_rate * POSTSEASON_K_MULTIPLIER
    else:
        k_rate_adjusted = k_rate
    
    # 6. Hitung xK
    x_k = expected_bf * k_rate_adjusted
        # 6. HITUNG EXPECTED OUTS (xOuts)
    if is_postseason:
        expected_outs = expected_bf * out_rate * POSTSEASON_OUT_MULTIPLIER
    else:
        expected_outs = expected_bf * out_rate
    
    return {
        "pitcher_id": pitcher_id,
        "total_bf": total_bf,
        "total_k": strikeouts,
        "total_outs": total_outs,       # <-- Tambahan
        "k_rate": round(k_rate, 3),
        "k_rate_adjusted": round(k_rate_adjusted, 3),
        "out_rate": round(out_rate, 3), # <-- Tambahan
        "expected_bf": expected_bf,
        "xK": round(x_k, 2),
        "xOuts": round(expected_outs, 2), # <-- Tambahan
        "status": "OK"
    
    }