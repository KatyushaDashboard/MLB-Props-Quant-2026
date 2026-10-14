"""
build_venue_map.py
==================
Membuat data/venue_mapping.csv yang memetakan game_pk ke nama stadion.
Menggunakan MLB Stats API langsung (bukan pybaseball.schedule).
"""
import pandas as pd
import requests
import os
from datetime import datetime, timedelta

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"

def fetch_schedule_range(start_date, end_date):
    """Tarik jadwal dari MLB API untuk rentang tanggal tertentu."""
    url = f"{MLB_API_BASE}/schedule"
    params = {
        "sportId": 1,
        "startDate": start_date,
        "endDate": end_date,
        "hydrate": "venue"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        games = []
        if 'dates' in data:
            for date_entry in data['dates']:
                for game in date_entry.get('games', []):
                    game_pk = game.get('gamePk')
                    venue_name = game.get('venue', {}).get('name', 'Unknown')
                    if game_pk and venue_name != 'Unknown':
                        games.append({
                            'game_pk': game_pk,
                            'venue': venue_name
                        })
        return games
    except Exception as e:
        print(f"   ⚠️ Gagal menarik {start_date} - {end_date}: {e}")
        return []


def build_venue_map():
    print("📅 Membangun Peta Stadion (Venue Mapping) via MLB API...")
    
    # Rentang tanggal yang sesuai dengan data cache backtest kita
    date_ranges = [
        ('2023-09-01', '2023-11-01'),  # Reg Sep + Post 2023
        ('2024-09-01', '2024-10-30'),  # Reg Sep + Post 2024
        ('2025-09-01', '2025-10-28'),  # Reg Sep + Post 2025
        ('2026-08-17', '2026-10-10'),  # L60 Reg + Post 2026
    ]
    
    all_games = []
    
    for start, end in date_ranges:
        print(f"   Menarik jadwal {start} sampai {end}...")
        games = fetch_schedule_range(start, end)
        print(f"   ✅ Ditemukan {len(games)} pertandingan")
        all_games.extend(games)
    
    if not all_games:
        print("❌ Tidak ada jadwal yang berhasil ditarik.")
        return
    
    # Buat DataFrame dan hapus duplikat
    df_map = pd.DataFrame(all_games).drop_duplicates(subset=['game_pk'])
    
    # Simpan
    os.makedirs('data', exist_ok=True)
    df_map.to_csv('data/venue_mapping.csv', index=False)
    
    print(f"\n✅ Berhasil! {len(df_map)} game dipetakan ke stadionnya.")
    print("   Disimpan ke data/venue_mapping.csv")
    
    # Tampilkan statistik stadion
    print(f"\n   Daftar stadion unik ({df_map['venue'].nunique()} stadion):")
    for v in sorted(df_map['venue'].unique()):
        print(f"   - {v}")
    
    print(f"\n   Contoh mapping (5 baris pertama):")
    print(df_map.head().to_string(index=False))


if __name__ == "__main__":
    build_venue_map()