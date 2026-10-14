"""
bot_updater.py
==============
Pipeline FINAL: Schedule -> Odds -> Projections -> Value Bets.
Terintegrasi dengan jadwal MLB, venue dinamis, dan safety checks.
"""
import json
import argparse
import pandas as pd
from datetime import datetime, timedelta

from utils.odds_fetcher import fetch_all_props, find_value_bets
from utils.statcast_fetcher import (
    fetch_statcast_data, get_today_schedule, extract_game_info,
    get_player_mlbam_id, fetch_recent_statcast, get_game_rosters
)
from utils.pitcher_engine import calculate_pitcher_projection
from utils.hitter_engine import calculate_hitter_projection, enrich_batted_ball_data
from utils.probability_engine import (
    prob_pitcher_strikeouts, prob_pitcher_outs,
    prob_hitter_hits, prob_hitter_home_runs, prob_hitter_total_bases
)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ============================================================
# KONFIGURASI
# ============================================================
MIN_PITCHES_FOR_PITCHER = 50
MIN_BBE_FOR_HITTER = 10
EDGE_THRESHOLD = 3.0
IS_POSTSEASON = True


def name_to_id(full_name: str):
    """Ubah 'FREDDY PERALTA' menjadi MLBAM ID."""
    parts = full_name.strip().split()
    if len(parts) < 2:
        return None
    first = parts[0].lower()
    last = parts[-1].lower()
    return get_player_mlbam_id(last, first)


def get_target_date(date_arg: str = None) -> str:
    """Tentukan tanggal target untuk prediksi."""
    if date_arg:
        try:
            datetime.strptime(date_arg, '%Y-%m-%d')
            return date_arg
        except ValueError:
            print(f"❌ Format tanggal salah: '{date_arg}'. Gunakan YYYY-MM-DD.")
            exit(1)
    et_tz = ZoneInfo("America/New_York")
    now_et = datetime.now(et_tz)
    return now_et.strftime('%Y-%m-%d')


def run_pipeline(target_date: str):
    print("=" * 60)
    print("🤖 DAILY PIPELINE v2 (SCHEDULE-INTEGRATED)")
    print(f"📅 Target Date: {target_date} (Eastern Time)")
    print(f"🏆 Mode: {'POSTSEASON' if IS_POSTSEASON else 'REGULAR SEASON'}")
    print("=" * 60)

    # ── STEP 1: Tarik Jadwal ──
    print(f"\n📥 [1/5] Menarik jadwal MLB untuk {target_date} (ET)...")
    games = get_today_schedule(target_date)
    if not games:
        print("❌ Tidak ada game untuk tanggal ini.")
        return None

    game_infos = []
    for g in games:
        info = extract_game_info(g)
        game_infos.append(info)
        print(f"   🏟️ {info['away_team_name']} @ {info['home_team_name']}")
        print(f"      Venue: {info['venue_name']}")
        print(f"      SP Away: {info['away_probable_pitcher']}")
        print(f"      SP Home: {info['home_probable_pitcher']}")

    # ── STEP 2: Tarik Odds ──
    print("\n📥 [2/5] Menarik odds dari The Odds API...")
    odds_data = fetch_all_props()
    if not odds_data:
        print("❌ Tidak ada odds.")
        return None

    # ── STEP 3: Tarik Statcast ──
    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
    end_date = (target_dt - timedelta(days=1)).strftime('%Y-%m-%d')

    if IS_POSTSEASON:
        start_date = f"{target_dt.year}-09-30"
    else:
        start_date = (target_dt - timedelta(days=14)).strftime('%Y-%m-%d')

    print(f"\n📥 [3/5] Menarik Statcast: {start_date} → {end_date}...")
    df_statcast = fetch_statcast_data(start_date, end_date, cache=True)
    if df_statcast is None:
        print("❌ Gagal tarik Statcast.")
        return None
    df_bbe = enrich_batted_ball_data(df_statcast)
    print(f"   ✅ {len(df_statcast):,} pitches | {len(df_bbe):,} BBE")

    # ── STEP 3.5: Tarik Roster SEMUA Game (SEKALI SAJA) ──
    print("\n👥 [3.5/5] Menarik roster pemain dari MLB API...")
    all_player_ids_today = set()
    for info in game_infos:
        rosters = get_game_rosters(info['game_pk'])
        game_ids = set(rosters['away'] + rosters['home'])
        all_player_ids_today.update(game_ids)
        print(f"   Game {info['game_pk']}: {len(game_ids)} pemain")
    print(f"   ✅ Total pemain unik hari ini: {len(all_player_ids_today)}")

    # ── STEP 4: Hitung Proyeksi ──
    print("\n⚙️ [4/5] Menghitung proyeksi per game...")
    projections = {}
    all_results = []

    # ── 4a. Proses STARTING PITCHERS (per game) ──
    for info in game_infos:
        venue = info['venue_name']
        game_pk = info['game_pk']
        print(f"\n   🏟️ Game {game_pk}: {info['away_team_name']} @ {info['home_team_name']} ({venue})")

        for side in ['away', 'home']:
            sp_name = info.get(f'{side}_probable_pitcher', 'TBD')
            sp_id = info.get(f'{side}_probable_pitcher_id')

            if sp_name == 'TBD' or sp_id is None:
                print(f"      ⚠️ SP {side} belum diumumkan.")
                continue

            sp_data = df_statcast[df_statcast['pitcher'] == sp_id]
            n_pitches = len(sp_data)
            if n_pitches < MIN_PITCHES_FOR_PITCHER:
                print(f"      ⚠️ {sp_name}: hanya {n_pitches} pitches (min {MIN_PITCHES_FOR_PITCHER}). SKIP.")
                continue

            proj = calculate_pitcher_projection(
                df_statcast, sp_id,
                is_postseason=IS_POSTSEASON
            )
            if proj['status'] != 'OK':
                print(f"      ⚠️ {sp_name}: {proj['status']}. SKIP.")
                continue

            sp_name_lower = sp_name.lower()
            sp_odds = odds_data.get(sp_name_lower, {})

            print(f"      ⚾ SP {side.upper()}: {sp_name} (ID: {sp_id})")
            print(f"         xK: {proj['xK']} | xOuts: {proj['xOuts']} | BF: {proj['expected_bf']:.1f}")

            if 'pitcher_strikeouts' in sp_odds:
                line_k = sp_odds['pitcher_strikeouts']['line']
                p_over_k = prob_pitcher_strikeouts(proj['expected_bf'], proj['k_rate'], line_k, "over")
                p_under_k = 100.0 - p_over_k
                if sp_name_lower not in projections:
                    projections[sp_name_lower] = {}
                projections[sp_name_lower]['pitcher_strikeouts'] = {
                    'prob_over': p_over_k, 'prob_under': p_under_k
                }
                all_results.append({
                    'game': f"{info['away_team_name']} @ {info['home_team_name']}",
                    'player': sp_name, 'type': 'SP',
                    'market': 'pitcher_strikeouts',
                    'line': line_k, 'projection': proj['xK'],
                    'prob_over': p_over_k
                })

            if 'pitcher_outs' in sp_odds:
                line_o = sp_odds['pitcher_outs']['line']
                p_over_o = prob_pitcher_outs(proj['expected_bf'], proj['out_rate'], line_o, "over")
                p_under_o = 100.0 - p_over_o
                if sp_name_lower not in projections:
                    projections[sp_name_lower] = {}
                projections[sp_name_lower]['pitcher_outs'] = {
                    'prob_over': p_over_o, 'prob_under': p_under_o
                }
                all_results.append({
                    'game': f"{info['away_team_name']} @ {info['home_team_name']}",
                    'player': sp_name, 'type': 'SP',
                    'market': 'pitcher_outs',
                    'line': line_o, 'projection': proj['xOuts'],
                    'prob_over': p_over_o
                })

    # ── 4b. Proses HITTERS (DI LUAR game loop, cukup sekali) ──
    print(f"\n   🏏 Memproses hitters...")
    hitter_markets = ['batter_hits', 'batter_home_runs', 'batter_total_bases']
    processed_hitters = set()
    skipped_hitters = 0

    total_hitters = len([p for p, m in odds_data.items()
                        if any(k in m for k in hitter_markets)])
    processed_count = 0

    # Ambil venue dari game pertama sebagai default
    default_venue = game_infos[0]['venue_name'] if game_infos else 'Neutral Site'

    for player_name, markets in odds_data.items():
        has_hitter_market = any(m in markets for m in hitter_markets)
        if not has_hitter_market:
            continue
        if player_name in processed_hitters:
            continue

        player_id = name_to_id(player_name)
        if not player_id:
            continue

        if player_id not in all_player_ids_today:
            skipped_hitters += 1
            continue

        batter_bbe = df_bbe[df_bbe['batter'] == player_id]
        if len(batter_bbe) < MIN_BBE_FOR_HITTER:
            skipped_hitters += 1
            continue

        proj_h = calculate_hitter_projection(
            df_bbe, player_id,
            venue_name=default_venue,
            is_postseason=IS_POSTSEASON
        )
        if proj_h['status'] != 'OK':
            skipped_hitters += 1
            continue

        processed_hitters.add(player_name)
        processed_count += 1
        if processed_count % 5 == 0:
            print(f"      🏏 Proses hitter {processed_count}/{total_hitters}...")

        if player_name not in projections:
            projections[player_name] = {}

        for market_key in hitter_markets:
            if market_key not in markets:
                continue
            line = markets[market_key]['line']

            if market_key == 'batter_hits':
                p_over = prob_hitter_hits(proj_h['expected_pa'], proj_h['avg_xba'], line, "over")
            elif market_key == 'batter_home_runs':
                hr_rate = proj_h['barrel_rate'] * 0.449
                p_over = prob_hitter_home_runs(proj_h['expected_pa'], hr_rate, line, "over")
            else:
                p_over = prob_hitter_total_bases(
                    proj_h['expected_pa'], proj_h['avg_xba'],
                    proj_h['avg_xslg'], line, "over"
                )

            p_under = 100.0 - p_over
            projections[player_name][market_key] = {
                'prob_over': p_over, 'prob_under': p_under
            }

    print(f"      🏏 Hitters diproses: {len(processed_hitters)} | Skipped: {skipped_hitters}")

    # ── STEP 5: Cari Value Bets ──
    print(f"\n🎯 [5/5] Mencari Value Bets (Edge > {EDGE_THRESHOLD}%)...")
    value_bets = find_value_bets(odds_data, projections)

    sane_bets = [b for b in value_bets if b['edge'] <= 25.0]
    suspicious_bets = [b for b in value_bets if b['edge'] > 25.0]

    print("\n" + "=" * 60)
    print("🏆 TOP PICKS HARI INI")
    print("=" * 60)
    if sane_bets:
        for i, bet in enumerate(sane_bets[:10]):
            print(f"\n   #{i+1} {bet['player'].upper()} — {bet['market']} {bet['side']} {bet['line']}")
            print(f"      Odds: {bet['odds']:+} | Implied: {bet['implied_prob']:.1f}% | Model: {bet['model_prob']:.1f}%")
            print(f"      💰 EDGE: +{bet['edge']:.1f}%")
    else:
        print("\n   Tidak ada value bet yang memenuhi kriteria.")

    if suspicious_bets:
        print(f"\n   ⚠️ {len(suspicious_bets)} bet dengan edge > 25% DIBUANG:")
        for bet in suspicious_bets:
            print(f"      ❌ {bet['player']} — {bet['market']} {bet['side']} (Edge: +{bet['edge']:.1f}%)")

    print(f"\n{'=' * 60}")
    print(f"📊 SUMMARY")
    print(f"   Games hari ini:       {len(game_infos)}")
    print(f"   Pemain diproses:      {len(projections)}")
    print(f"   Value bets (sane):    {len(sane_bets)}")
    print(f"   Bets dibuang (bias):  {len(suspicious_bets)}")
    print(f"{'=' * 60}")

    # ── SIMPAN HASIL ──
    output_data = {
        "run_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "mode": "POSTSEASON" if IS_POSTSEASON else "REGULAR SEASON",
        "games_today": len(game_infos),
        "players_processed": len(projections),
        "top_picks": sane_bets,
        "suspicious_bets": suspicious_bets
    }

    with open('data/todays_picks.json', 'w') as f:
        json.dump(output_data, f, indent=4)

    print("\n💾 Hasil disimpan ke data/todays_picks.json")
    return output_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="MLB Props Quant Pipeline"
    )
    parser.add_argument(
        '--date', type=str, default=None,
        help='Tanggal target (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--tomorrow', action='store_true',
        help='Prediksi jadwal besok (ET + 1 hari)'
    )
    args = parser.parse_args()

    if args.tomorrow:
        et_tz = ZoneInfo("America/New_York")
        tomorrow_et = datetime.now(et_tz) + timedelta(days=1)
        target_date = tomorrow_et.strftime('%Y-%m-%d')
    else:
        target_date = get_target_date(args.date)

    run_pipeline(target_date)