"""
tune_constants.py v2 (FIXED)
=============================
Menghitung POSTSEASON_PA_MULTIPLIER dan BARREL_TO_HR_RATE
secara empiris dari data yang sudah di-cache.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from utils.hitter_engine import enrich_batted_ball_data


def parse_dates_from_filename(fname):
    """
    Ambil tanggal mulai dari nama file cache.
    Format: statcast_2023-09-01_to_2023-09-30.csv
    """
    parts = fname.replace('statcast_', '').replace('.csv', '')
    start_str = parts.split('_to_')[0]  # '2023-09-01'
    return datetime.strptime(start_str, '%Y-%m-%d')


def is_postseason_date(dt):
    """
    Postseason MLB = Oktober dan November.
    Regular season = April - September.
    """
    return dt.month >= 10


def hitung_konstanta():
    print("=" * 60)
    print("🔬 MENGHITUNG KONSTANTA DARI DATA EMPIRIS (v2 FIXED)")
    print("=" * 60)
    
    data_files = [f for f in os.listdir('data') 
                  if f.startswith('statcast_') and f.endswith('.csv')]
    
    if not data_files:
        print("❌ Tidak ada file cache. Jalankan run_backtest_v3.py dulu.")
        return
    
    # Print deteksi file untuk verifikasi
    print("\n📂 DETEKSI FILE:")
    for fname in sorted(data_files):
        dt = parse_dates_from_filename(fname)
        label = "POSTSEASON" if is_postseason_date(dt) else "REGULAR"
        print(f"   [{label:>10}] {fname}")
    
    # ========================================
    # 1. HITUNG BARREL → HR RATE
    # ========================================
    print("\n📊 [1/2] Menghitung Barrel → HR Rate...")
    
    barrels_reg = 0
    hr_from_barrel_reg = 0
    barrels_post = 0
    hr_from_barrel_post = 0
    
    for fname in data_files:
        filepath = os.path.join('data', fname)
        df = pd.read_csv(filepath, low_memory=False)
        
        dt = parse_dates_from_filename(fname)
        is_post = is_postseason_date(dt)
        
        df_bbe = enrich_batted_ball_data(df)
        if len(df_bbe) == 0:
            continue
        
        barrels = df_bbe[df_bbe['is_barrel'] == 1]
        hr_barrels = barrels[barrels['events'] == 'home_run']
        
        if is_post:
            barrels_post += len(barrels)
            hr_from_barrel_post += len(hr_barrels)
        else:
            barrels_reg += len(barrels)
            hr_from_barrel_reg += len(hr_barrels)
    
    barrel_hr_reg = hr_from_barrel_reg / barrels_reg if barrels_reg > 0 else None
    barrel_hr_post = hr_from_barrel_post / barrels_post if barrels_post > 0 else None
    
    print(f"\n   Regular Season:")
    print(f"     Total Barrels:    {barrels_reg:,}")
    print(f"     HR dari Barrels:  {hr_from_barrel_reg:,}")
    if barrel_hr_reg:
        print(f"     Barrel → HR Rate: {barrel_hr_reg:.3f}")
    
    print(f"\n   Postseason:")
    print(f"     Total Barrels:    {barrels_post:,}")
    print(f"     HR dari Barrels:  {hr_from_barrel_post:,}")
    if barrel_hr_post:
        print(f"     Barrel → HR Rate: {barrel_hr_post:.3f}")
    
    # ========================================
    # 2. HITUNG PA MULTIPLIER (FIXED)
    # ========================================
    print("\n📊 [2/2] Menghitung PA Multiplier...")
    
    # PA dihitung dari unique at_bat_number per game per batter
    # (bukan jumlah baris/pitches)
    pa_reg_per_game = []
    pa_post_per_game = []
    
    for fname in data_files:
        filepath = os.path.join('data', fname)
        df = pd.read_csv(filepath, low_memory=False)
        
        dt = parse_dates_from_filename(fname)
        is_post = is_postseason_date(dt)
        
        # Pastikan kolom yang dibutuhkan ada
        if 'at_bat_number' not in df.columns or 'game_pk' not in df.columns:
            print(f"   ⚠️ {fname} tidak punya kolom at_bat_number/game_pk, skip.")
            continue
        
        # Hitung unique PA per batter per game
        pa_counts = df.groupby(['game_pk', 'batter'])['at_bat_number'].nunique()
        
        # Rata-rata PA per batter per game untuk file ini
        avg_pa = pa_counts.mean()
        
        if is_post:
            pa_post_per_game.append(avg_pa)
        else:
            pa_reg_per_game.append(avg_pa)
    
    if pa_reg_per_game and pa_post_per_game:
        avg_pa_reg = np.mean(pa_reg_per_game)
        avg_pa_post = np.mean(pa_post_per_game)
        pa_multiplier = avg_pa_post / avg_pa_reg
    else:
        avg_pa_reg = avg_pa_post = pa_multiplier = None
    
    print(f"\n   Rata-rata PA/batter/game Regular Season: {avg_pa_reg:.2f}")
    print(f"   Rata-rata PA/batter/game Postseason:     {avg_pa_post:.2f}")
    print(f"   PA Multiplier (Post/Reg):                {pa_multiplier:.3f}")
    
    # ========================================
    # HASIL AKHIR
    # ========================================
    print("\n" + "=" * 60)
    print("📋 KONSTANTA EMPIRIS UNTUK HITTER_ENGINE.PY")
    print("=" * 60)
    if barrel_hr_reg:
        print(f"   BARREL_TO_HR_RATE          = {barrel_hr_reg:.3f}")
    if barrel_hr_post:
        print(f"   BARREL_TO_HR_RATE_POSTSEASON = {barrel_hr_post:.3f}")
    if pa_multiplier:
        print(f"   POSTSEASON_PA_MULTIPLIER   = {pa_multiplier:.3f}")
    print("=" * 60)


if __name__ == "__main__":
    hitung_konstanta()