"""
utils/odds_fetcher.py
=====================
Menarik odds dan lines dari The Odds API untuk MLB player props.
"""
import streamlit as st
import requests
from typing import Dict, List, Optional  # noqa: UP035
from datetime import datetime

# ============================================================
# KONFIGURASI
# ============================================================
# Coba ambil dari Streamlit secrets, fallback ke hardcoded
try:
    ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
except:
    ODDS_API_KEY = "YOUR_API_KEY_HERE"  # Fallback untuk local  # Ganti dengan API key Anda dari the-odds-api.com
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/baseball_mlb"

# Market yang kita targetkan (sesuai project Anda)
PITCHER_MARKETS = "pitcher_strikeouts,pitcher_outs"
HITTER_MARKETS = "batter_hits,batter_home_runs,batter_total_bases"


# ============================================================
# FUNGSI UTAMA
# ============================================================

def get_implied_probability(american_odds: int) -> float:
    """
    Konversi odds Amerika ke probabilitas persentase (0-100).
    
    -110 → 52.38%
    +150 → 40.00%
    -200 → 66.67%
    """
    if american_odds > 0:
        return 100.0 / (american_odds + 100.0) * 100.0
    else:
        return (-american_odds) / (-american_odds + 100.0) * 100.0


def fetch_all_props() -> Dict:
    """
    Tarik semua player props (pitcher & hitter) untuk semua game hari ini.
    
    Returns:
        Nested dict: {player_name: {market_key: {line, over_odds, under_odds}}}
    """
    if ODDS_API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️ ODDS_API_KEY belum diatur di odds_fetcher.py")
        return {}
    
    # Step 1: Dapatkan daftar events hari ini
    events_url = f"{ODDS_API_BASE}/events"
    events_response = requests.get(events_url, params={"apiKey": ODDS_API_KEY})
    
    if events_response.status_code != 200:
        print(f"❌ Gagal menarik events: {events_response.status_code}")
        return {}
    
    events = events_response.json()
    props_dict = {}
    
    # Step 2: Untuk setiap event, tarik odds
    for event in events:
        event_id = event['id']
        
        # Gabungkan pitcher dan hitter markets
        all_markets = f"{PITCHER_MARKETS},{HITTER_MARKETS}"
        
        odds_url = f"{ODDS_API_BASE}/events/{event_id}/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": all_markets,
            "oddsFormat": "american",
            "bookmakers": "draftkings,fanduel"
        }
        
        try:
            odds_response = requests.get(odds_url, params=params)
            if odds_response.status_code != 200:
                continue
                
            event_data = odds_response.json()
            
            # Parse odds dari response
            for bookmaker in event_data.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    market_key = market["key"]
                    
                    for outcome in market.get("outcomes", []):
                        player_name = outcome.get("description", "Unknown").lower().strip()
                        side = outcome.get("name")  # "Over" atau "Under"
                        line = outcome.get("point")
                        odds = outcome.get("price")
                        
                        if player_name not in props_dict:
                            props_dict[player_name] = {}
                        if market_key not in props_dict[player_name]:
                            props_dict[player_name][market_key] = {
                                "line": line,
                                "over_odds": -110,  # Default
                                "under_odds": -110  # Default
                            }
                        
                        if side == "Over":
                            props_dict[player_name][market_key]["over_odds"] = odds
                        elif side == "Under":
                            props_dict[player_name][market_key]["under_odds"] = odds
                            
        except Exception as e:
            print(f"⚠️ Error parsing event {event_id}: {e}")
            continue
    
    print(f"✅ Ditemukan odds untuk {len(props_dict)} pemain")
    return props_dict


def find_value_bets(
    player_props: Dict,
    projections: Dict
) -> List[Dict]:
    """
    Membandingkan proyeksi model kita dengan odds bandar untuk menemukan value.
    
    Parameters:
    -----------
    player_props : Dict dari fetch_all_props()
        {player_name: {market_key: {line, over_odds, under_odds}}}
    projections : Dict dari engine
        {player_name: {market_key: {prob_over, prob_under}}}
    
    Returns:
        List of value bets dengan Edge > threshold
    """
    EDGE_THRESHOLD = 3.0  # Minimal 3% edge untuk dianggap value bet
    
    value_bets = []
    
    for player_name, markets in player_props.items():
        if player_name not in projections:
            continue
            
        for market_key, odds_data in markets.items():
            if market_key not in projections[player_name]:
                continue
                
            line = odds_data["line"]
            over_odds = odds_data["over_odds"]
            under_odds = odds_data["under_odds"]
            
            prob_data = projections[player_name][market_key]
            model_over_prob = prob_data["prob_over"]
            model_under_prob = prob_data["prob_under"]
            
            # Hitung implied probability dari odds
            implied_over = get_implied_probability(over_odds)
            implied_under = get_implied_probability(under_odds)
            
            # Hitung Edge
            edge_over = model_over_prob - implied_over
            edge_under = model_under_prob - implied_under
            
            # Cek OVER
            if edge_over >= EDGE_THRESHOLD:
                value_bets.append({
                    "player": player_name,
                    "market": market_key,
                    "side": "OVER",
                    "line": line,
                    "odds": over_odds,
                    "model_prob": model_over_prob,
                    "implied_prob": implied_over,
                    "edge": edge_over
                })
            
            # Cek UNDER
            if edge_under >= EDGE_THRESHOLD:
                value_bets.append({
                    "player": player_name,
                    "market": market_key,
                    "side": "UNDER",
                    "line": line,
                    "odds": under_odds,
                    "model_prob": model_under_prob,
                    "implied_prob": implied_under,
                    "edge": edge_under
                })
    
    # Urutkan berdasarkan edge tertinggi
    value_bets.sort(key=lambda x: x['edge'], reverse=True)
    
    return value_bets