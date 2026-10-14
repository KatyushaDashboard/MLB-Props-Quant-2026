"""
utils/statcast_fetcher.py
=========================
Module untuk menarik data dari Statcast (pybaseball) dan MLB Stats API.
Menyediakan fungsi-fungsi yang akan dipanggil oleh bot_updater.py
"""
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple  # noqa: UP035
from pybaseball import statcast, playerid_lookup

# ============================================================
# KONFIGURASI
# ============================================================
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
DATA_DIR = "data"
CACHE_DAYS = 3  # Data statcast di-cache, tidak perlu pull ulang jika < 3 hari


# ============================================================
# FUNGSI: MLB STATS API
# ============================================================

def get_today_schedule(target_date: Optional[str] = None) -> list:
    """
    Tarik jadwal MLB untuk tanggal tertentu.

    Parameters:
    -----------
    target_date : Format 'YYYY-MM-DD'. Default: hari ini.

    Returns:
    --------
    List of game dicts dari MLB API.
    """
    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')

    url = f"{MLB_API_BASE}/schedule"
    params = {
        "sportId": 1,
        "date": target_date,
        "hydrate": "probablePitcher(note),linescore,venue,team"
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if 'dates' not in data or len(data['dates']) == 0:
            print(f"⚠️ Tidak ada jadwal MLB untuk {target_date}")
            return []

        games = data['dates'][0].get('games', [])
        print(f"✅ Ditemukan {len(games)} pertandingan untuk {target_date}")
        return games
    except requests.exceptions.RequestException as e:
        print(f"❌ Error menarik jadwal MLB: {e}")
        return []


def extract_game_info(game: dict) -> dict:
    """Ekstrak informasi penting dari satu game object MLB API."""
    venue = game.get('venue', {})
    away_team = game.get('teams', {}).get('away', {})
    home_team = game.get('teams', {}).get('home', {})

    return {
        "game_pk": game.get('gamePk'),
        "game_date": game.get('gameDate', '')[:10],
        "venue_name": venue.get('name', 'Neutral Site'),
        "away_team_name": away_team.get('team', {}).get('name', 'TBD'),
        "away_team_id": away_team.get('team', {}).get('id'),
        "home_team_name": home_team.get('team', {}).get('name', 'TBD'),
        "home_team_id": home_team.get('team', {}).get('id'),
        "away_probable_pitcher": away_team.get('probablePitcher', {}).get('fullName', 'TBD'),
        "home_probable_pitcher": home_team.get('probablePitcher', {}).get('fullName', 'TBD'),
        "away_probable_pitcher_id": away_team.get('probablePitcher', {}).get('id'),
        "home_probable_pitcher_id": home_team.get('probablePitcher', {}).get('id'),
    }


def get_boxscore_lineup(game_pk: int, team_type: str) -> list:
    """
    Tarik lineup (batting order) dari boxscore.

    Parameters:
    -----------
    game_pk : Game ID dari MLB API
    team_type : 'away' atau 'home'

    Returns:
    --------
    List of dicts: [{"player_id": 12345, "full_name": "Aaron Judge", "order": 1}, ...]
    """
    url = f"{MLB_API_BASE}/game/{game_pk}/boxscore"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        batting_order = data.get('teams', {}).get(team_type, {}).get('battingOrder', [])
        players = data.get('teams', {}).get(team_type, {}).get('players', {})

        lineup = []
        for i, pid in enumerate(batting_order, start=1):
            player_key = f"ID{pid}"
            player_data = players.get(player_key, {})
            person = player_data.get('person', {})
            lineup.append({
                "player_id": pid,
                "full_name": person.get('fullName', 'Unknown'),
                "order": i,
                "bat_side": person.get('batSide', {}).get('code', 'R'),
            })
        return lineup
    except Exception as e:
        print(f"⚠️ Gagal tarik lineup game {game_pk} ({team_type}): {e}")
        return []


def get_game_rosters(game_pk: int) -> dict:
    """
    Tarik roster kedua tim dari boxscore MLB API.

    Returns:
    --------
    dict: {'away': [player_ids], 'home': [player_ids]}
    """
    url = f"{MLB_API_BASE}/game/{game_pk}/boxscore"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        rosters = {}
        for side in ['away', 'home']:
            players = data.get('teams', {}).get(side, {}).get('players', {})
            player_ids = []
            for key, pdata in players.items():
                person = pdata.get('person', {})
                if person.get('id'):
                    player_ids.append(person['id'])
            rosters[side] = player_ids

        return rosters
    except Exception as e:
        print(f"⚠️ Gagal tarik roster game {game_pk}: {e}")
        return {'away': [], 'home': []}


# ============================================================
# FUNGSI: PLAYER ID LOOKUP (dengan caching)
# ============================================================

_PLAYER_LOOKUP_CACHE = None


def _ensure_lookup_table():
    """
    Pastikan lookup table pybaseball sudah ter-download.
    pybaseball menyimpan cache internal setelah download pertama,
    sehingga semua panggilan berikutnya sangat cepat.
    """
    global _PLAYER_LOOKUP_CACHE
    if _PLAYER_LOOKUP_CACHE is not None:
        return  # Sudah di-trigger, tidak perlu lagi

    print("   📥 Triggering player lookup table download (first time only)...")
    try:
        # playerid_lookup WAJIB punya minimal 1 argumen (last name).
        # Kita pakai nama umum untuk trigger download cache internal pybaseball.
        _PLAYER_LOOKUP_CACHE = playerid_lookup("smith")
        print(f"   ✅ Lookup table ready ({len(_PLAYER_LOOKUP_CACHE)} rows sample)")
    except Exception as e:
        print(f"   ⚠️ Gagal trigger lookup table: {e}")
        _PLAYER_LOOKUP_CACHE = pd.DataFrame()


def get_player_mlbam_id(last_name: str, first_name: Optional[str] = None) -> Optional[int]:
    """
    Cari MLBAM ID menggunakan playerid_lookup dari pybaseball.
    Robust terhadap perbedaan nama kolom antar versi pybaseball.
    """
    _ensure_lookup_table()

    def _extract_id(df: pd.DataFrame) -> Optional[int]:
        """Ekstrak ID dari DataFrame hasil lookup, handle berbagai nama kolom."""
        if df is None or len(df) == 0:
            return None

        # Cari kolom ID (berbagai kemungkinan nama)
        id_col = None
        for col_name in ['key_mlbam', 'id', 'mlbam_id', 'player_id']:
            if col_name in df.columns:
                id_col = col_name
                break

        if id_col is None:
            print(f"      ⚠️ Kolom ID tidak ditemukan. Kolom tersedia: {df.columns.tolist()}")
            return None

        # Sort berdasarkan tahun debut/main terakhir (jika ada)
        sort_col = None
        for col_name in ['debut_year', 'mlb_played_first', 'mlb_played_last', 'year']:
            if col_name in df.columns:
                sort_col = col_name
                break

        if sort_col is not None:
            try:
                df = df.sort_values(sort_col, ascending=False)
            except Exception:  # noqa: S110
                pass  # Jika sorting gagal, ambil baris pertama saja

        return int(df.iloc[0][id_col])

    # Coba 1: dengan first name (paling akurat)
    if first_name:
        try:
            results = playerid_lookup(last_name, first_name)
            player_id = _extract_id(results)
            if player_id is not None:
                return player_id
        except Exception as e:
            print(f"      ⚠️ Lookup error '{first_name} {last_name}': {e}")

    # Coba 2: hanya last name (fallback)
    try:
        results = playerid_lookup(last_name)
        player_id = _extract_id(results)
        if player_id is not None:
            return player_id
    except Exception as e:
        print(f"      ⚠️ Lookup fallback error '{last_name}': {e}")

    return None


# ============================================================
# FUNGSI: STATCAST / PYBASEBALL
# ============================================================

def fetch_statcast_data(
    start_date: str,
    end_date: str,
    cache: bool = True
) -> Optional[pd.DataFrame]:
    """
    Tarik data Statcast pitch-by-pitch untuk rentang tanggal.

    Parameters:
    -----------
    start_date : Format 'YYYY-MM-DD'
    end_date : Format 'YYYY-MM-DD'
    cache : Jika True, simpan ke CSV agar tidak pull ulang

    Returns:
    --------
    DataFrame Statcast atau None jika gagal.
    """
    cache_filename = os.path.join(
        DATA_DIR,
        f"statcast_{start_date}_to_{end_date}.csv"
    )

    # Cek cache
    if cache and os.path.exists(cache_filename):
        file_age_days = (datetime.now() - datetime.fromtimestamp(
            os.path.getmtime(cache_filename)
        )).days
        if file_age_days < CACHE_DAYS:
            print(f"📦 Menggunakan cache: {cache_filename}")
            return pd.read_csv(cache_filename)

    # Tarik data baru
    print(f"📥 Menarik data Statcast: {start_date} → {end_date}...")
    print("   (Ini bisa memakan waktu 1-5 menit tergantung rentang tanggal)")

    try:
        df = statcast(start_date, end_date)
        if df is None or df.empty:
            print("⚠️ Tidak ada data Statcast untuk rentang tersebut.")
            return None

        print(f"✅ Berhasil! {len(df):,} baris data pitch-by-pitch.")

        # Simpan ke cache
        if cache:
            os.makedirs(DATA_DIR, exist_ok=True)
            df.to_csv(cache_filename, index=False)
            print(f"💾 Disimpan ke cache: {cache_filename}")

        return df
    except Exception as e:
        print(f"❌ Error menarik Statcast: {e}")
        return None


def get_pitcher_recent_bf(
    pitcher_id: int,
    df_statcast: pd.DataFrame,
    n_starts: int = 5
) -> Optional[float]:
    """
    Hitung rata-rata Batters Faced (BF) per game untuk N start terakhir.

    Returns:
    --------
    Rata-rata BF (float). Jika data kurang, kembalikan None.
    """
    df_p = df_statcast[df_statcast['pitcher'] == pitcher_id]

    if 'game_pk' not in df_p.columns or 'at_bat_number' not in df_p.columns:
        return None

    # Hitung BF per game
    bf_per_game = (
        df_p
        .dropna(subset=['game_pk', 'at_bat_number'])
        .groupby('game_pk')['at_bat_number']
        .nunique()
    )

    if len(bf_per_game) == 0:
        return None

    # Urutkan dari game_pk terbesar ke terkecil = start terbaru ke terlama
    recent_starts = bf_per_game.sort_index(ascending=False).head(n_starts)
    return float(recent_starts.mean())


def fetch_recent_statcast(days_back: int = 7, cache: bool = True) -> Optional[pd.DataFrame]:
    """
    Tarik data Statcast untuk N hari terakhir.
    Convenience wrapper untuk fetch_statcast_data.

    Parameters:
    -----------
    days_back : Jumlah hari ke belakang (default 7)
    """
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    return fetch_statcast_data(start_date, end_date, cache=cache)