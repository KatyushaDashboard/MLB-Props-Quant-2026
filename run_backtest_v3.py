"""
run_backtest_v3.py
==================
Step 1: Tune postseason multiplier dari data 2023-2025.
Step 2: Validasi di postseason 2026.
"""

import pandas as pd
import numpy as np
from utils.statcast_fetcher import fetch_statcast_data
from utils.hitter_engine import enrich_batted_ball_data, calculate_hitter_projection


def hitung_rate_per_batter(df_all):
    """Hitung hits/PA, TB/PA, HR/PA untuk setiap batter."""
    hit_events = ['single', 'double', 'triple', 'home_run']
    tb_map = {'single': 1, 'double': 2, 'triple': 3, 'home_run': 4}
    
    pa = df_all.groupby('batter').size().reset_index(name='pa')
    
    hits = df_all[df_all['events'].isin(hit_events)] \
                 .groupby('batter').size().reset_index(name='hits')
    
    df_tb = df_all[df_all['events'].isin(hit_events)].copy()
    df_tb['tb'] = df_tb['events'].map(tb_map)
    tb = df_tb.groupby('batter')['tb'].sum().reset_index(name='tb')
    
    hr = df_all[df_all['events'] == 'home_run'] \
                .groupby('batter').size().reset_index(name='hr')
    
    m = pa.merge(hits, on='batter', how='left') \
          .merge(tb, on='batter', how='left') \
          .merge(hr, on='batter', how='left').fillna(0)
    
    m['hits_pa'] = m['hits'] / m['pa']
    m['tb_pa'] = m['tb'] / m['pa']
    m['hr_pa'] = m['hr'] / m['pa']
    
    return m


def step1_tune_multiplier():
    """Tune multiplier dari postseason 2023-2025."""
    print("=" * 60)
    print("🔬 STEP 1: TUNE MULTIPLIER (Postseason 2023-2025)")
    print("=" * 60)
    
    # Regular season akhir
    print("\n📥 Menarik regular season Sep 2023-2025...")
    reg_list = []
    for tahun in ['2023', '2024', '2025']:
        df = fetch_statcast_data(f'{tahun}-09-01', f'{tahun}-09-30', cache=True)
        if df is not None:
            reg_list.append(df)
            print(f"   ✅ Sep {tahun}: {len(df):,} pitches")
    df_reg = pd.concat(reg_list, ignore_index=True)
    
    # Postseason
    print("\n📥 Menarik postseason 2023-2025...")
    post_list = []
    post_ranges = [
        ('2023-10-03', '2023-11-01'),
        ('2024-10-01', '2024-10-30'),
        ('2025-09-30', '2025-10-28'),
    ]
    for start, end in post_ranges:
        df = fetch_statcast_data(start, end, cache=True)
        if df is not None:
            post_list.append(df)
            print(f"   ✅ {start} → {end}: {len(df):,} pitches")
    df_post = pd.concat(post_list, ignore_index=True)
    
    # Hitung metrik
    reg_m = hitung_rate_per_batter(df_reg)
    post_m = hitung_rate_per_batter(df_post)
    
    # Filter sample cukup
    reg_avg = reg_m[reg_m['pa'] >= 20]
    post_avg = post_m[post_m['pa'] >= 10]
    
    hit_mult = post_avg['hits_pa'].mean() / reg_avg['hits_pa'].mean()
    tb_mult = post_avg['tb_pa'].mean() / reg_avg['tb_pa'].mean()
    hr_mult = post_avg['hr_pa'].mean() / reg_avg['hr_pa'].mean()
    
    print("\n" + "=" * 60)
    print("📊 HASIL MULTIPLIER POSTSEASON")
    print("=" * 60)
    print(f"   Hit Multiplier:  {hit_mult:.3f}")
    print(f"   TB Multiplier:   {tb_mult:.3f}")
    print(f"   HR Multiplier:   {hr_mult:.3f}")
    
    return {
        'hit': round(hit_mult, 3),
        'tb': round(tb_mult, 3),
        'hr': round(hr_mult, 3),
    }


def step2_validate(mult):
    """Validasi multiplier di postseason 2026."""
    print("\n" + "=" * 60)
    print("🏆 STEP 2: VALIDASI DI POSTSEASON 2026")
    print("=" * 60)
    
    print("\n📥 Menarik regular season Sep 2026 (baseline)...")
    df_train = fetch_statcast_data('2026-09-01', '2026-09-30', cache=True)
    
    print("📥 Menarik postseason 2026 (validation)...")
    df_test = fetch_statcast_data('2026-10-01', '2026-10-10', cache=True)
    
    if df_train is None or df_test is None:
        print("❌ Data tidak lengkap.")
        return None

        # --- MUAT VENUE MAPPING ---
    try:
        venue_map = pd.read_csv('data/venue_mapping.csv')
        # Ubah jadi dictionary agar pencarian super cepat: {game_pk: 'Nama Stadion'}
        venue_dict = dict(zip(venue_map['game_pk'], venue_map['venue']))
        print(f"✅ Venue mapping dimuat ({len(venue_dict)} stadion).")
    except FileNotFoundError:
        print("❌ data/venue_mapping.csv tidak ditemukan. Jalankan build_venue_map.py dulu!")
        return None
    
    train_bbe = enrich_batted_ball_data(df_train)
    
    hit_events = ['single', 'double', 'triple', 'home_run']
    tb_map = {'single': 1, 'double': 2, 'triple': 3, 'home_run': 4}
    
    results = []
    dates = sorted(df_test['game_date'].unique())
    print(f"\n📅 Validasi {len(dates)} hari postseason 2026...")
    
    for tgl in dates:
        day = df_test[df_test['game_date'] == tgl]
        
        # Groupby by game_pk dan batter untuk mengantisipasi doubleheader (2 game di hari yang sama)
        for (game_pk, bid), batter_day_data in day.groupby(['game_pk', 'batter']):
            
            # Cari nama stadion berdasarkan game_pk
            venue_name = venue_dict.get(game_pk, 'Neutral Site')
            
            proj = calculate_hitter_projection(
                df_batted_balls=train_bbe,
                batter_id=bid,
                venue_name=venue_name,  # <-- SEKARANG BERISI NAMA STADION ASLI!
                is_postseason=True,
            )
            
            if proj['status'] != 'OK':
                continue
            
            # ... (kode di bawahnya biarkan sama: raw_h, adj_h, dll) ...
            
            raw_h = proj['xHits']
            raw_t = proj['xTotalBases']
            raw_r = proj['xHR']
            
            adj_h = raw_h * mult['hit']
            adj_t = raw_t * mult['tb']
            adj_r = raw_r * mult['hr']
            
            b = day[day['batter'] == bid]
            
            # FILTER: Hanya evaluasi batter yang mendapat minimal 3 PA (Plate Appearance)
            # Ini menyaring Starter dan membuang Pinch Hitter/Bench Player.
            # PA dihitung dari jumlah baris di mana batter ini menghadapi pitcher (termasuk K, BB, HBP).
            # Di Statcast, setiap baris adalah satu pitch. Kita butuh unique 'at_bat_number'.
            if 'at_bat_number' in b.columns:
                total_pa = b['at_bat_number'].nunique()
            else:
                # Fallback jika kolom tidak ada
                total_pa = len(b) 
            
            if total_pa < 3:
                continue  # Lewati pemain ini (kemungkinan besar pinch hitter)
            
            act_h = len(b[b['events'].isin(hit_events)])
            act_t = b[b['events'].isin(hit_events)]['events'].map(tb_map).sum()
            act_r = len(b[b['events'] == 'home_run'])
            
            results.append({
                'date': tgl, 'batter': bid,
                'raw_h': raw_h, 'adj_h': adj_h, 'act_h': act_h,
                'raw_t': raw_t, 'adj_t': adj_t, 'act_t': act_t,
                'raw_r': raw_r, 'adj_r': adj_r, 'act_r': act_r,
            })
    
    if not results:
        print("⚠️ Tidak ada hasil.")
        return None
    
    df = pd.DataFrame(results)
    
    mae_rh = (df['raw_h'] - df['act_h']).abs().mean()
    mae_ah = (df['adj_h'] - df['act_h']).abs().mean()
    mae_rt = (df['raw_t'] - df['act_t']).abs().mean()
    mae_at = (df['adj_t'] - df['act_t']).abs().mean()
    mae_rr = (df['raw_r'] - df['act_r']).abs().mean()
    mae_ar = (df['adj_r'] - df['act_r']).abs().mean()
    
    print("\n" + "=" * 60)
    print("📊 HASIL VALIDASI")
    print("=" * 60)
    print(f"{'':20} {'Raw':>10} {'Adjusted':>10} {'Improve':>10}")
    print("-" * 52)
    print(f"{'MAE Hits':20} {mae_rh:>10.4f} {mae_ah:>10.4f} {((mae_rh-mae_ah)/mae_rh*100):>+9.1f}%")
    print(f"{'MAE Total Bases':20} {mae_rt:>10.4f} {mae_at:>10.4f} {((mae_rt-mae_at)/mae_rt*100):>+9.1f}%")
    print(f"{'MAE HR':20} {mae_rr:>10.4f} {mae_ar:>10.4f} {((mae_rr-mae_ar)/mae_rr*100):>+9.1f}%")
    print("-" * 52)
    print(f"{'Avg Pred (Raw)':20} {df['raw_h'].mean():>10.3f}")
    print(f"{'Avg Pred (Adj)':20} {df['adj_h'].mean():>10.3f}")
    print(f"{'Avg Actual':20} {df['act_h'].mean():>10.3f}")
    print(f"{'Total predictions':20} {len(df):>10}")
    
    df.to_csv('data/backtest_v3_results.csv', index=False)
    print(f"\n💾 Hasil disimpan ke data/backtest_v3_results.csv")
    
    return df


if __name__ == "__main__":
    mult = step1_tune_multiplier()
    step2_validate(mult)