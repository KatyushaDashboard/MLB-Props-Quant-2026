"""
test_engine.py
==============
Test sederhana untuk memastikan hitter_engine dan statcast_fetcher bekerja.
Jalankan: python test_engine.py
"""

from utils.statcast_fetcher import fetch_recent_statcast
from utils.hitter_engine import enrich_batted_ball_data, calculate_hitter_projection

def main():
    print("=" * 60)
    print("🧪 TEST: Hitter Engine + Statcast Fetcher")
    print("=" * 60)
    
    # 1. Tarik data 3 hari terakhir (lebih cepat untuk test)
    print("\n[1/4] Menarik data Statcast 3 hari terakhir...")
    df_raw = fetch_recent_statcast(days_back=3, cache=True)
    
    if df_raw is None or df_raw.empty:
        print("❌ Gagal tarik data. Coba lagi atau cek koneksi internet.")
        return
    
    print(f"   Raw data: {len(df_raw):,} pitches")
    
    # 2. Enrich data (tambah is_barrel, is_hard_hit)
    print("\n[2/4] Enriching data (menghitung Barrel, Hard Hit)...")
    df_bbe = enrich_batted_ball_data(df_raw)
    print(f"   Batted Ball Events: {len(df_bbe):,}")
    print(f"   Total Barrels: {df_bbe['is_barrel'].sum():,}")
    
    # 3. Pilih satu batter random untuk test
    if len(df_bbe) > 0:
        sample_batter_id = df_bbe['batter'].value_counts().index[0]
        print(f"\n[3/4] Test proyeksi untuk batter ID: {sample_batter_id}")
        
        result = calculate_hitter_projection(
            df_batted_balls=df_bbe,
            batter_id=sample_batter_id,
            venue_name="Yankee Stadium",
            batting_order_position=3
        )
        
        # 4. Print hasil
        print("\n[4/4] Hasil Proyeksi:")
        print("-" * 40)
        for key, value in result.items():
            print(f"   {key}: {value}")
    else:
        print("⚠️ Tidak ada BBE data untuk test.")
    
    print("\n" + "=" * 60)
    print("✅ TEST SELESAI!")
    print("=" * 60)


if __name__ == "__main__":
    main()