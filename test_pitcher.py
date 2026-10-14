"""
test_pitcher.py (v2 - dengan diagnosa detail)
"""
import pandas as pd
import os
from utils.pitcher_engine import calculate_pitcher_projection

def test_pitcher():
    data_files = [f for f in os.listdir('data') 
                  if f.startswith('statcast_') and f.endswith('.csv')]
    if not data_files:
        print("❌ Tidak ada data cache.")
        return
    
    # Gunakan file pertama
    filepath = os.path.join('data', data_files[0])
    print(f"📂 Menggunakan: {data_files[0]}")
    df = pd.read_csv(filepath, low_memory=False)
    
    # Cari pitcher dengan data terbanyak
    top_pitchers = df['pitcher'].value_counts().head(3)
    print(f"\n🔍 3 Pitcher terbanyak di file ini:")
    print(top_pitchers.to_string())
    
    pitcher_id = top_pitchers.index[0]
    df_p = df[df['pitcher'] == pitcher_id]
    
    # --- DIAGNOSA MENTAH ---
    print(f"\n{'='*60}")
    print(f"🔬 DIAGNOSA MENTAH untuk Pitcher ID: {pitcher_id}")
    print(f"{'='*60}")
    print(f"   Total baris (pitches):  {len(df_p)}")
    
    if 'game_pk' in df_p.columns:
        n_games = df_p['game_pk'].nunique()
        print(f"   Jumlah game:            {n_games}")
    
    if 'game_pk' in df_p.columns and 'at_bat_number' in df_p.columns:
        total_bf = df_p[['game_pk', 'at_bat_number']].drop_duplicates().shape[0]
        print(f"   Total BF (benar):       {total_bf}")
    
    # Hitung strikeout
    so = df_p[df_p['events'].astype(str).str.contains('strikeout', case=False, na=False)]
    print(f"   Total Strikeout events: {len(so)}")
    print(f"   K-Rate (mentah):        {len(so)/total_bf:.3f}" if total_bf > 0 else "   K-Rate: N/A")
    
    # Tampilkan unique events untuk verifikasi
    print(f"\n   Distribusi 'events' (10 teratas):")
    print(df_p['events'].value_counts().head(10).to_string())
    
    # --- UJI ENGINE ---
    print(f"\n{'='*60}")
    print(f"🧪 HASIL PITCHER ENGINE")
    print(f"{'='*60}")
    
    res_reg = calculate_pitcher_projection(df, pitcher_id, is_postseason=False)
    res_post = calculate_pitcher_projection(df, pitcher_id, is_postseason=True)
    
    print(f"\n   [Regular Season]")
    for k, v in res_reg.items():
        print(f"      {k}: {v}")
    
    print(f"\n   [Postseason]")
    for k, v in res_post.items():
        print(f"      {k}: {v}")

if __name__ == "__main__":
    test_pitcher()