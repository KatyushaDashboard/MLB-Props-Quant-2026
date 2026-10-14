"""
test_probability.py
===================
Uji coba probability engine dengan contoh nyata.
"""
from utils.probability_engine import (
    prob_pitcher_strikeouts,
    prob_pitcher_outs,
    prob_hitter_home_runs,
    prob_hitter_hits,
    prob_hitter_total_bases,
)

print("=" * 60)
print("🎲 UJI COBA PROBABILITY ENGINE")
print("=" * 60)

# --- PITCHER PROPS ---
# Contoh: Pitcher dengan expected_BF=17.8, K-rate=0.236
# Line dari bandar: OVER 4.5 K

bf = 17.8
k_rate = 0.236

prob_over_k = prob_pitcher_strikeouts(bf, k_rate, 4.5, "over")
prob_under_k = prob_pitcher_strikeouts(bf, k_rate, 4.5, "under")

print(f"\n⚾ PITCHER STRIKEOUTS (Line: 4.5)")
print(f"   Expected BF: {bf}, K-Rate: {k_rate}")
print(f"   Expected K:  {bf * k_rate:.2f}")
print(f"   P(OVER 4.5):  {prob_over_k:.1f}%")
print(f"   P(UNDER 4.5): {prob_under_k:.1f}%")
print(f"   Total:        {prob_over_k + prob_under_k:.1f}%")  # Harus ~100%

# --- PITCHER OUTS ---
out_rate = 0.679
prob_over_outs = prob_pitcher_outs(bf, out_rate, 11.5, "over")
prob_under_outs = prob_pitcher_outs(bf, out_rate, 11.5, "under")

print(f"\n⚾ PITCHER OUTS (Line: 11.5)")
print(f"   Expected BF: {bf}, Out-Rate: {out_rate}")
print(f"   Expected Outs: {bf * out_rate:.2f}")
print(f"   P(OVER 11.5):  {prob_over_outs:.1f}%")
print(f"   P(UNDER 11.5): {prob_under_outs:.1f}%")

# --- HITTER PROPS ---
# Contoh: Hitter dengan expected_PA=4.0, xBA=0.280, xSLG=0.480
pa = 4.0
xba = 0.280
xslg = 0.480
hr_rate = 0.045  # 4.5% HR per PA

print(f"\n🏏 HITTER HITS (Line: 0.5)")
print(f"   Expected PA: {pa}, xBA: {xba}")
print(f"   Expected Hits: {pa * xba:.2f}")
print(f"   P(OVER 0.5): {prob_hitter_hits(pa, xba, 0.5, 'over'):.1f}%")

print(f"\n🏏 HITTER HR (Line: 0.5)")
print(f"   Expected PA: {pa}, HR-Rate: {hr_rate}")
print(f"   Expected HR: {pa * hr_rate:.3f}")
print(f"   P(OVER 0.5): {prob_hitter_home_runs(pa, hr_rate, 0.5, 'over'):.1f}%")

print(f"\n🏏 HITTER TOTAL BASES (Line: 1.5)")
print(f"   Expected PA: {pa}, xSLG: {xslg}")
print(f"   Expected TB: {pa * xslg:.2f}")
print(f"   P(OVER 1.5): {prob_hitter_total_bases(pa, xba, xslg, 1.5, 'over'):.1f}%")

print("\n" + "=" * 60)
print("✅ Selesai!")