"""
test_odds.py
============
Test Odds Fetcher & Value Bet Finder.
"""
from utils.odds_fetcher import fetch_all_props, get_implied_probability, find_value_bets

print("=" * 60)
print("🎰 UJI COBA ODDS FETCHER")
print("=" * 60)

# Test konversi odds
print("\n📊 Test Konversi Odds:")
for odds in [-110, +150, -200, +220]:
    impl = get_implied_probability(odds)
    print(f"   {odds:+5} → {impl:.1f}%")

# Tarik odds real-time
print("\n📥 Menarik odds dari The Odds API...")
props = fetch_all_props()

if props:
    # Tampilkan 5 pemain pertama
    print("\n📋 Contoh Data Odds (5 pemain pertama):")
    for i, (player, markets) in enumerate(list(props.items())[:5]):
        print(f"\n   {i+1}. {player.upper()}")
        for market, data in markets.items():
            print(f"      {market}: Line={data['line']} | OVER {data['over_odds']:+} | UNDER {data['under_odds']:+}")
    
    # Simulasi value bet dengan proyeksi dummy
    print("\n🎯 Simulasi Value Bet (dengan proyeksi dummy):")
    dummy_projections = {
        list(props.keys())[0]: {
            "pitcher_strikeouts": {"prob_over": 60.0, "prob_under": 40.0}
        }
    }
    
    # Ganti dengan nama pemain aktual dari data
    if props:
        first_player = list(props.keys())[0]
        if "pitcher_strikeouts" in props[first_player]:
            dummy_projections = {
                first_player: {
                    "pitcher_strikeouts": {"prob_over": 60.0, "prob_under": 40.0}
                }
            }
            
            value_bets = find_value_bets(props, dummy_projections)
            
            if value_bets:
                print(f"\n   ✅ Ditemukan {len(value_bets)} value bet(s):")
                for bet in value_bets[:5]:
                    print(f"      {bet['player']} - {bet['market']} {bet['side']} {bet['line']}")
                    print(f"      Odds: {bet['odds']:+} | Model: {bet['model_prob']:.1f}% | Implied: {bet['implied_prob']:.1f}%")
                    print(f"      🎯 EDGE: +{bet['edge']:.1f}%")
                    print()
            else:
                print("   ⚠️ Tidak ada value bet dengan dummy projection ini.")
else:
    print("❌ Tidak ada odds yang berhasil ditarik.")

print("=" * 60)