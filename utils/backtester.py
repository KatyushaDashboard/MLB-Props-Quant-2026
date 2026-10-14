"""
utils/backtester.py
===================
Walk-Forward Validation Framework untuk MLB Props.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Callable  # noqa: UP035
from utils.hitter_engine import enrich_batted_ball_data, calculate_hitter_projection
from utils.statcast_fetcher import fetch_statcast_data


def walk_forward_validate(
    full_data: pd.DataFrame,
    train_window_days: int = 30,
    gap_days: int = 2,
    test_days: int = 1,
    model_function: Callable = None,
) -> pd.DataFrame:
    """
    Walk-Forward Validation dengan gap untuk mencegah data leakage.
    
    Skema:
    ┌────────────────────────────────────────────────────────────────────┐
    │ Fold 1:                                                            │
    │   Train: [Day 1 ─────── Day 30]                                  │
    │   Gap:   [Day 31 ─ Day 32]  ← TIDAK dipakai (mencegah leakage)  │
    │   Test:  [Day 33]           ← Prediksi untuk hari ini            │
    │                                                                    │
    │ Fold 2: (geser 1 hari)                                           │
    │   Train: [Day 2 ─────── Day 31]                                  │
    │   Gap:   [Day 32 ─ Day 33]                                       │
    │   Test:  [Day 34]                                                │
    │                                                                    │
    │ Fold 3: (geser 1 hari lagi)                                      │
    │   Train: [Day 3 ─────── Day 32]                                  │
    │   Gap:   [Day 33 ─ Day 34]                                       │
    │   Test:  [Day 35]                                                │
    │   ...                                                              │
    └────────────────────────────────────────────────────────────────────┘
    
    Parameters:
    -----------
    full_data : DataFrame Statcast lengkap (misal 45 hari)
    train_window_days : Ukuran window training (default 30)
    gap_days : Jarak antara akhir training dan test (mencegah leakage)
    test_days : Berapa hari test per fold (default 1)
    model_function : Fungsi model yang akan dievaluasi
    
    Returns:
    --------
    DataFrame berisi hasil evaluasi per fold.
    """
    
    # Ambil semua tanggal unik dari data
    all_dates = sorted(full_data['game_date'].unique())
    total_days = len(all_dates)
    
    # Hitung jumlah fold yang mungkin
    min_days_needed = train_window_days + gap_days + test_days
    if total_days < min_days_needed:
        raise ValueError(
            f"Data hanya {total_days} hari. "
            f"Butuh minimal {min_days_needed} hari "
            f"(train={train_window_days} + gap={gap_days} + test={test_days})"
        )
    
    num_folds = total_days - min_days_needed + 1
    print(f"📊 Walk-Forward Validation")
    print(f"   Total hari data: {total_days}")
    print(f"   Train window: {train_window_days} hari")
    print(f"   Gap: {gap_days} hari (anti-leakage)")
    print(f"   Test: {test_days} hari")
    print(f"   Jumlah fold: {num_folds}")
    print("=" * 60)
    
    all_results = []
    
    for fold in range(num_folds):
        # Hitung index tanggal untuk fold ini
        train_start_idx = fold
        train_end_idx = fold + train_window_days
        gap_end_idx = train_end_idx + gap_days
        test_end_idx = gap_end_idx + test_days
        
        # Ambil tanggal-tanggalnya
        train_dates = all_dates[train_start_idx:train_end_idx]
        test_dates = all_dates[gap_end_idx:test_end_idx]
        
        if len(test_dates) == 0:
            break
        
        # Filter data
        train_data = full_data[full_data['game_date'].isin(train_dates)]
        test_data = full_data[full_data['game_date'].isin(test_dates)]
        
        # Enrich training data
        train_bbe = enrich_batted_ball_data(train_data)
        test_bbe = enrich_batted_ball_data(test_data)
        
        # Evaluasi model di test data
        # (Di sini Anda memanggil hitter_engine atau pitcher_engine)
        fold_results = evaluate_fold(
            train_bbe=train_bbe,
            test_bbe=test_bbe,
            test_dates=test_dates,
        )
        
        fold_results['fold'] = fold + 1
        fold_results['train_start'] = train_dates[0]
        fold_results['train_end'] = train_dates[-1]
        fold_results['test_date'] = test_dates[0]
        
        all_results.append(fold_results)
        
        print(f"   Fold {fold+1}/{num_folds}: "
              f"Train [{train_dates[0]} → {train_dates[-1]}] | "
              f"Gap [{all_dates[train_end_idx]} → {all_dates[gap_end_idx-1]}] | "
              f"Test [{test_dates[0]}]")
    
    return pd.DataFrame(all_results)


def evaluate_fold(
    train_bbe: pd.DataFrame,
    test_bbe: pd.DataFrame,
    test_dates: list,
) -> Dict:
    """
    Evaluasi satu fold: bandingkan prediksi vs aktual.
    
    Di sinilah kita hitung:
    - Mean Absolute Error (MAE) untuk xHits
    - Calibration untuk probabilitas O/U
    - Brier Score
    """
    
    # Dapatkan semua batter yang ada di test data
    test_batters = test_bbe['batter'].unique()
    
    predictions = []
    actuals = []
    
    for batter_id in test_batters:
        # PREDIKSI: gunakan data training untuk memproyeksikan
        # (simulasi: kita memprediksi sebelum game dimulai)
        venue = test_bbe[test_bbe['batter'] == batter_id]['venue'].iloc[0] \
                if 'venue' in test_bbe.columns else 'Neutral Site'
        
        projection = calculate_hitter_projection(
            df_batted_balls=train_bbe,  # ← PAKAI DATA TRAINING!
            batter_id=batter_id,
            venue_name=venue,
            batting_order_position=0,  # TODO: ambil dari lineup
        )
        
        if projection['status'] != 'OK':
            continue
        
        # AKTUAL: apa yang benar-benar terjadi di test day
        batter_test_data = test_bbe[test_bbe['batter'] == batter_id]
        
        # Hitung actual hits (single, double, triple, home_run)
        hit_events = ['single', 'double', 'triple', 'home_run']
        actual_hits = len(batter_test_data[batter_test_data['events'].isin(hit_events)])
        
        # Hitung actual total bases
        tb_map = {'single': 1, 'double': 2, 'triple': 3, 'home_run': 4}
        actual_tb = batter_test_data[batter_test_data['events'].isin(hit_events)]['events'].map(tb_map).sum()
        
        predictions.append({
            'batter_id': batter_id,
            'pred_hits': projection['xHits'],
            'pred_tb': projection['xTotalBases'],
            'pred_hr': projection['xHR'],
        })
        
        actuals.append({
            'batter_id': batter_id,
            'actual_hits': actual_hits,
            'actual_tb': actual_tb,
            'actual_hr': len(batter_test_data[batter_test_data['events'] == 'home_run']),
        })
    
    # Hitung metrik evaluasi
    if not predictions:
        return {
            'mae_hits': np.nan,
            'mae_tb': np.nan,
            'mae_hr': np.nan,
            'n_predictions': 0,
        }
    
    pred_df = pd.DataFrame(predictions)
    actual_df = pd.DataFrame(actuals)
    merged = pred_df.merge(actual_df, on='batter_id')
    
    mae_hits = (merged['pred_hits'] - merged['actual_hits']).abs().mean()
    mae_tb = (merged['pred_tb'] - merged['actual_tb']).abs().mean()
    mae_hr = (merged['pred_hr'] - merged['actual_hr']).abs().mean()
    
    return {
        'mae_hits': round(mae_hits, 4),
        'mae_tb': round(mae_tb, 4),
        'mae_hr': round(mae_hr, 4),
        'n_predictions': len(merged),
        'avg_pred_hits': round(merged['pred_hits'].mean(), 3),
        'avg_actual_hits': round(merged['actual_hits'].mean(), 3),
    }


# ============================================================
# FUNGSI UNTUK MENJALANKAN BACKTEST POSTSEASON
# ============================================================

def run_postseason_backtest():
    """
    Backtest khusus postseason:
    1. Tarik data postseason 2023-2025 untuk tune parameter postseason
    2. Tarik data postseason 2026 yang sudah berjalan untuk validasi
    3. Walk-forward validation di postseason 2026
    """
    
    print("=" * 60)
    print("🏆 POSTSEASON BACKTESTING FRAMEWORK")
    print("=" * 60)
    
    # --- FASE 1: Tarik data postseason sebelumnya ---
    print("\n[FASE 1] Menarik data postseason 2023-2025...")
    postseason_ranges = [
        ('2023-10-03', '2023-11-01'),  # Postseason 2023
        ('2024-10-01', '2024-10-30'),  # Postseason 2024
        ('2025-09-30', '2025-10-28'),  # Postseason 2025
    ]
    
    postseason_dfs = []
    for start, end in postseason_ranges:
        print(f"  📥 {start} → {end}")
        df = fetch_statcast_data(start, end, cache=True)
        if df is not None:
            postseason_dfs.append(df)
    
    if postseason_dfs:
        df_postseason_hist = pd.concat(postseason_dfs, ignore_index=True)
        print(f"✅ Total data postseason historis: {len(df_postseason_hist):,} pitches")
        
        # Di sini kita tune parameter postseason
        # Misal: hitung HR rate di postseason vs regular season
        postseason_hr_rate = len(df_postseason_hist[df_postseason_hist['events'] == 'home_run']) / len(df_postseason_hist)
        print(f"   HR Rate Postseason 2023-2025: {postseason_hr_rate:.4f}")
    
    # --- FASE 2: Tarik data postseason 2026 yang sudah berjalan ---
    print("\n[FASE 2] Menarik data postseason 2026 (Wild Card + Division Series)...")
    df_postseason_2026 = fetch_statcast_data('2026-10-01', '2026-10-10', cache=True)
    
    if df_postseason_2026 is not None:
        print(f"✅ Data postseason 2026: {len(df_postseason_2026):,} pitches")
    
    # --- FASE 3: Walk-Forward Validation di postseason 2026 ---
    print("\n[FASE 3] Walk-Forward Validation di postseason 2026...")
    # Note: Karena postseason 2026 baru ~10 hari, kita pakai window lebih kecil
    # Train: 5 hari, Gap: 1 hari, Test: 1 hari
    
    if df_postseason_2026 is not None and len(df_postseason_2026) > 0:
        results = walk_forward_validate(
            full_data=df_postseason_2026,
            train_window_days=5,    # Lebih kecil karena data postseason terbatas
            gap_days=1,             # Gap 1 hari untuk anti-leakage
            test_days=1,            # Prediksi per hari
        )
        
        if not results.empty:
            print("\n" + "=" * 60)
            print("📊 HASIL WALK-FORWARD VALIDATION")
            print("=" * 60)
            print(f"   Rata-rata MAE Hits:  {results['mae_hits'].mean():.4f}")
            print(f"   Rata-rata MAE TB:    {results['mae_tb'].mean():.4f}")
            print(f"   Rata-rata MAE HR:    {results['mae_hr'].mean():.4f}")
            print(f"   Total fold:          {len(results)}")
            
            return results
    
    return pd.DataFrame()


if __name__ == "__main__":
    results = run_postseason_backtest()
    
    if not results.empty:
        print("\n✅ Backtesting selesai!")
        print(results.to_string(index=False))