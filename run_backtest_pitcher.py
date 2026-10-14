"""
run_backtest_pitcher.py
=======================
Validasi Pitcher Engine (xK dan xOuts) di Postseason 2026.
Baseline: Regular Season Sep 2026
Validation: Postseason 2026
"""
import pandas as pd
from utils.statcast_fetcher import fetch_statcast_data, get_pitcher_recent_bf
from utils.pitcher_engine import calculate_pitcher_projection

def run():
    print("=" * 60)
    print("⚾ PITCHER ENGINE BACKTEST (Postseason 2026)")
    print("=" * 60)

    print("\n📥 Menarik baseline (Regular Season Sep 2026)...")
    df_train = fetch_statcast_data('2026-09-01', '2026-09-30', cache=True)
    
    print("📥 Menarik validation (Postseason 2026)...")
    df_test = fetch_statcast_data('2026-10-01', '2026-10-10', cache=True)
    
    if df_train is None or df_test is None:
        print("❌ Data tidak lengkap.")
        return
        
    # Daftar event di Statcast
    strikeout_events = ['strikeout', 'strikeout_call', 'strikeout_swinging',
                        'strikeout_double_play', 'strikeout_triple_play']
    out_events = [
        'field_out', 'force_out', 'grounded_into_double_play', 
        'double_play', 'sac_fly', 'sac_bunt'
    ] + strikeout_events
    
    results = []
    dates = sorted(df_test['game_date'].unique())
    
    print(f"\n📅 Menguji {len(dates)} hari postseason...")
    
    for tgl in dates:
        day_data = df_test[df_test['game_date'] == tgl]
        
        # CARI STARTING PITCHERS HARI INI
        # (Pitcher yang melempar di inning 1)
        if 'inning' not in day_data.columns:
            continue
            
        inning1 = day_data[day_data['inning'] == 1]
        starters_today = inning1.groupby(['game_pk', 'pitcher']).size().reset_index()[['game_pk', 'pitcher']]
        
        for _, row in starters_today.iterrows():
            game_pk = row['game_pk']
            pitcher_id = row['pitcher']
            
            # 1. HITUNG EXPECTED BF DINAMIS dari data training (3 start terakhir di bulan Sep)
            dynamic_bf = get_pitcher_recent_bf(pitcher_id, df_train, n_starts=3)
            
            # 2. PREDIKSI (pakai baseline df_train, mode postseason, dengan BF dinamis)
            proj = calculate_pitcher_projection(
                df_train, 
                pitcher_id, 
                is_postseason=True,
                dynamic_expected_bf=dynamic_bf  # <-- TERAPKAN DI SINI
            )
            
            if proj['status'] != 'OK':
                continue
                
            # 2. AKTUAL (apa yang terjadi di game postseason ini)
            pitcher_game_data = day_data[day_data['pitcher'] == pitcher_id]
            
            act_k = len(pitcher_game_data[pitcher_game_data['events'].isin(strikeout_events)])
            act_outs = len(pitcher_game_data[pitcher_game_data['events'].isin(out_events)])
            
            results.append({
                'date': tgl,
                'game_pk': game_pk,
                'pitcher_id': pitcher_id,
                'pred_k': proj['xK'],
                'pred_outs': proj['xOuts'],
                'act_k': act_k,
                'act_outs': act_outs
            })
            
    if not results:
        print("⚠️ Tidak ada data starter yang bisa diuji.")
        return
        
    df_res = pd.DataFrame(results)
    
    # Hitung MAE (Mean Absolute Error)
    mae_k = (df_res['pred_k'] - df_res['act_k']).abs().mean()
    mae_outs = (df_res['pred_outs'] - df_res['act_outs']).abs().mean()
    
    print("\n" + "=" * 60)
    print("📊 HASIL VALIDASI PITCHER")
    print("=" * 60)
    print(f"   Total Starting Pitchers diuji: {len(df_res)}")
    print(f"   MAE Strikeouts (xK):  {mae_k:.3f}")
    print(f"   MAE Outs (xOuts):     {mae_outs:.3f}")
    print("-" * 45)
    print(f"   Avg Pred K:           {df_res['pred_k'].mean():.2f}")
    print(f"   Avg Actual K:         {df_res['act_k'].mean():.2f}")
    print(f"   Avg Pred Outs:        {df_res['pred_outs'].mean():.2f}")
    print(f"   Avg Actual Outs:      {df_res['act_outs'].mean():.2f}")
    
    df_res.to_csv('data/backtest_pitcher_results.csv', index=False)
    print(f"\n💾 Detail hasil disimpan ke data/backtest_pitcher_results.csv")

if __name__ == "__main__":
    run()