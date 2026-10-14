"""
tune_pitcher_v2.py
==================
Menghitung konstanta Pitcher Engine KHUSUS STARTING PITCHER.
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime

strikeout_events = ['strikeout', 'strikeout_call', 'strikeout_swinging',
                    'strikeout_double_play', 'strikeout_triple_play']
out_events = [
    'field_out', 'force_out', 'grounded_into_double_play', 
    'double_play', 'sac_fly', 'sac_bunt'
] + strikeout_events

def parse_date(fname):
    parts = fname.replace('statcast_', '').replace('.csv', '')
    return datetime.strptime(parts.split('_to_')[0], '%Y-%m-%d')

def is_postseason(dt):
    return dt.month >= 10

def tune():
    print("=" * 60)
    print("⚾ TUNE PITCHER CONSTANTS (STARTING PITCHERS ONLY)")
    print("=" * 60)

    data_files = [f for f in os.listdir('data') 
                  if f.startswith('statcast_') and f.endswith('.csv')]
    
    reg_bf_per_game = []
    post_bf_per_game = []
    
    reg_k_total, reg_bf_total, reg_out_total = 0, 0, 0
    post_k_total, post_bf_total, post_out_total = 0, 0, 0

    for fname in data_files:
        dt = parse_date(fname)
        is_post = is_postseason(dt)
        label = "POSTSEASON" if is_post else "REGULAR"
        
        print(f"   📂 Membaca {fname} [{label}]...")
        df = pd.read_csv(os.path.join('data', fname), low_memory=False)

        if 'inning' not in df.columns or 'pitcher' not in df.columns:
            continue
            
        # ==========================================
        # 🚨 FILTER: HANYA STARTING PITCHERS
        # Starting Pitcher pasti melempar di inning 1
        # ==========================================
        inning1_data = df[df['inning'] == 1]
        
        # Dapatkan daftar unique (game_pk, pitcher) yang tampil di inning 1
        starters = inning1_data.groupby(['game_pk', 'pitcher']).size().reset_index()[['game_pk', 'pitcher']]
        
        # Filter df utama hanya untuk pitcher-pitcher starter tersebut
        df_clean = df.merge(starters, on=['game_pk', 'pitcher'], how='inner')
        df_clean = df_clean.dropna(subset=['pitcher', 'at_bat_number'])
        # ==========================================
        
        # Hitung BF per Starter per Game
        bf_counts = df_clean.groupby(['game_pk', 'pitcher'])['at_bat_number'].nunique()
        
        if is_post:
            post_bf_per_game.extend(bf_counts.tolist())
        else:
            reg_bf_per_game.extend(bf_counts.tolist())
            
        file_bf = bf_counts.sum()
        
        # Hitung K dan Outs
        df_events = df_clean[df_clean['events'].notna()]
        k_count = len(df_events[df_events['events'].isin(strikeout_events)])
        out_count = len(df_events[df_events['events'].isin(out_events)])
        
        if is_post:
            post_bf_total += file_bf
            post_k_total += k_count
            post_out_total += out_count
        else:
            reg_bf_total += file_bf
            reg_k_total += k_count
            reg_out_total += out_count

    avg_bf_reg = np.mean(reg_bf_per_game)
    avg_bf_post = np.mean(post_bf_per_game)
    k_rate_reg = reg_k_total / reg_bf_total if reg_bf_total > 0 else 0
    k_rate_post = post_k_total / post_bf_total if post_bf_total > 0 else 0
    out_rate_reg = reg_out_total / reg_bf_total if reg_bf_total > 0 else 0
    out_rate_post = post_out_total / post_bf_total if post_bf_total > 0 else 0

    k_mult = k_rate_post / k_rate_reg if k_rate_reg > 0 else 1.0
    out_mult = out_rate_post / out_rate_reg if out_rate_reg > 0 else 1.0

    print("\n" + "=" * 60)
    print("📊 HASIL (KHUSUS STARTING PITCHERS)")
    print("=" * 60)
    print(f"{'Metrik':<25} {'Regular':<15} {'Postseason':<15}")
    print("-" * 55)
    print(f"{'Avg BF / Game':<25} {avg_bf_reg:<15.2f} {avg_bf_post:<15.2f}")
    print(f"{'K-Rate':<25} {k_rate_reg:<15.3f} {k_rate_post:<15.3f}")
    print(f"{'Out-Rate':<25} {out_rate_reg:<15.3f} {out_rate_post:<15.3f}")

    print("\n🎯 KONSTANTA FINAL:")
    print(f"   REGULAR_SEASON_AVG_BF      = {avg_bf_reg:.1f}")
    print(f"   POSTSEASON_AVG_BF          = {avg_bf_post:.1f}")
    print(f"   POSTSEASON_K_MULTIPLIER    = {k_mult:.3f}")
    print(f"   POSTSEASON_OUT_MULTIPLIER  = {out_mult:.3f}")
    print("=" * 60)

if __name__ == "__main__":
    tune()