"""
check_venue.py
==============
Mengecek apakah data Statcast memiliki kolom venue dan apa isinya.
"""
import pandas as pd
import os

data_files = [f for f in os.listdir('data') if f.startswith('statcast_') and f.endswith('.csv')]

if data_files:
    filepath = os.path.join('data', data_files[0])
    df = pd.read_csv(filepath, low_memory=False, nrows=10)
    
    print("=" * 60)
    print("🔍 DIAGNOSA KOLOM STATCAST")
    print("=" * 60)
    
    if 'venue' in df.columns:
        print("✅ Kolom 'venue' ADA di dalam data!")
        
        # Baca full data untuk lihat variasi nama stadion
        print("   Membaca data penuh untuk melihat variasi nama stadion...")
        df_full = pd.read_csv(filepath, low_memory=False)
        
        unique_venues = df_full['venue'].dropna().unique()
        print(f"\n   Ditemukan {len(unique_venues)} nama stadion unik:")
        for v in unique_venues[:10]: # Tampilkan 10 contoh
            print(f"   - '{v}'")
            
    else:
        print("❌ Kolom 'venue' TIDAK ADA di data Statcast mentah.")
        print("   (pybaseball.statcast() secara default tidak menarik nama stadion)")
        print("\n   Kolom-kolom yang ada di data saat ini:")
        print(f"   {df.columns.tolist()[:15]}... (dan {len(df.columns)-15} lainnya)")
else:
    print("❌ Tidak ada file cache CSV di folder data/.")