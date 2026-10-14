"""
app.py
======
Dashboard Streamlit untuk MLB Props Quant Engine.
Jalankan: streamlit run app.py
"""
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Import pipeline kita
from bot_updater import run_pipeline, get_target_date

# ============================================================
# KONFIGURASI HALAMAN
# ============================================================
st.set_page_config(
    page_title="MLB Props Quant 2026",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS (agar tabel lebih cantik)
# ============================================================
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .edge-positive { color: #00c853; font-weight: bold; }
    .edge-warning { color: #ff6d00; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================
st.title("⚾ MLB Props Quant Engine 2026")
st.markdown("""
Sistem prediksi kuantitatif berbasis **Statcast xBA/xSLG**, **Distribusi Binomial**, 
dan **Value Bet Detection** dengan safety checks otomatis.
""")

# ============================================================
# SIDEBAR: KONTROL
# ============================================================
with st.sidebar:
    st.header("⚙️ Kontrol Analisis")
    
    # Pilih mode tanggal
    date_mode = st.radio(
        "Pilih Target Prediksi:",
        ["Hari Ini (ET)", "Besok (ET)", "Tanggal Spesifik"],
        index=1  # Default: Besok
    )
    
    target_date = None
    if date_mode == "Tanggal Spesifik":
        # Default: besok
        default_date = datetime.now() + timedelta(days=1)
        target_date = st.date_input(
            "Pilih tanggal:",
            value=default_date
        ).strftime('%Y-%m-%d')
    elif date_mode == "Besok (ET)":
        try:
            from zoneinfo import ZoneInfo
            et_tz = ZoneInfo("America/New_York")
            tomorrow_et = datetime.now(et_tz) + timedelta(days=1)
            target_date = tomorrow_et.strftime('%Y-%m-%d')
        except ImportError:
            target_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        target_date = get_target_date()
    
    st.info(f"📅 Target Date: **{target_date}** (Eastern Time)")
    
    st.divider()
    
    # Tombol Run Analysis
    run_button = st.button(
        "🚀 Run Analysis",
        type="primary",
        use_container_width=True
    )
    
    # Pengaturan tambahan
    st.divider()
    st.subheader("⚙️ Parameter")
    edge_threshold = st.slider("Min Edge (%)", 1.0, 10.0, 3.0, 0.5)
    show_suspicious = st.checkbox("Tampilkan Bets Anomali", value=True)

# ============================================================
# JALANKAN ANALISIS (jika tombol diklik)
# ============================================================
if run_button:
    with st.spinner("🔄 Menjalankan analisis... Ini bisa memakan waktu 1-3 menit."):
        try:
            # Jalankan pipeline
            result = run_pipeline(target_date)
            
            # Simpan ke session_state agar tidak hilang saat refresh
            st.session_state['result'] = result
            st.session_state['last_run'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.success("✅ Analisis selesai!")
        except Exception as e:
            st.error(f"❌ Error saat menjalankan analisis: {str(e)}")
            st.exception(e)

# ============================================================
# TAMPILKAN HASIL
# ============================================================
if 'result' in st.session_state:
    data = st.session_state['result']
    
    # ── HEADER HASIL ──
    st.divider()
    st.header(f"📊 Hasil Analisis: {target_date}")
    st.caption(f"Terakhir dijalankan: {st.session_state.get('last_run', 'N/A')} | Mode: {data['mode']}")
    
    # ── METRICS ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Games Hari Ini", data['games_today'])
    col2.metric("Pemain Diproses", data['players_processed'])
    col3.metric("Value Bets", len(data['top_picks']))
    col4.metric("Bets Anomali", len(data['suspicious_bets']))
    
    st.divider()
    
    # ── TABS ──
    tab1, tab2, tab3 = st.tabs(["🏆 Top Picks", "⚠️ Bets Anomali", "📥 Export"])
    
    with tab1:
        if data['top_picks']:
            df_picks = pd.DataFrame(data['top_picks'])
            
            # Filter berdasarkan edge threshold dari sidebar
            df_picks = df_picks[df_picks['edge'] >= edge_threshold]
            
            if len(df_picks) == 0:
                st.warning(f"Tidak ada bets dengan edge >= {edge_threshold}%. Coba turunkan threshold di sidebar.")
            else:
                # Rename kolom
                df_display = df_picks.rename(columns={
                    'player': 'Pemain',
                    'market': 'Market',
                    'side': 'Arah',
                    'line': 'Line',
                    'odds': 'Odds',
                    'implied_prob': 'Prob. Bandar (%)',
                    'model_prob': 'Prob. Model (%)',
                    'edge': 'EDGE (%)'
                })
                
                # Format angka
                df_display['Prob. Bandar (%)'] = df_display['Prob. Bandar (%)'].round(1)
                df_display['Prob. Model (%)'] = df_display['Prob. Model (%)'].round(1)
                df_display['EDGE (%)'] = df_display['EDGE (%)'].round(1)
                
                # Styling: highlight edge tinggi
                def highlight_edge(val):
                    if val >= 10:
                        return 'background-color: #c8e6c9; font-weight: bold'
                    elif val >= 5:
                        return 'background-color: #f0f4c3'
                    return ''
                
                styled_df = df_display.style.map(
                    highlight_edge,
                    subset=['EDGE (%)']
                )
                
                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Tips
                st.info("💡 **Tips:** Edge > 10% = Strong Value | Edge 5-10% = Good Value | Edge 3-5% = Marginal Value")
        else:
            st.info("Tidak ada value bet yang memenuhi kriteria hari ini. Tetap disiplin!")
    
    with tab2:
        if show_suspicious and data['suspicious_bets']:
            st.warning("⚠️ Bets berikut memiliki Edge > 25% dan **DITOLAK** oleh sistem karena kemungkinan besar ada anomali data.")
            
            df_susp = pd.DataFrame(data['suspicious_bets'])
            df_susp = df_susp.rename(columns={
                'player': 'Pemain',
                'market': 'Market',
                'side': 'Arah',
                'edge': 'Edge Anomali (%)'
            })
            df_susp['Edge Anomali (%)'] = df_susp['Edge Anomali (%)'].round(1)
            
            st.dataframe(
                df_susp[['Pemain', 'Market', 'Arah', 'Edge Anomali (%)']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("✅ Tidak ada anomali yang terdeteksi.")
    
    with tab3:
        st.subheader("📥 Export Data")
        
        if data['top_picks']:
            df_export = pd.DataFrame(data['top_picks'])
            
            # CSV Export
            csv = df_export.to_csv(index=False)
            st.download_button(
                label="📄 Download Top Picks (CSV)",
                data=csv,
                file_name=f"mlb_picks_{target_date}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # JSON Export
            json_str = json.dumps(data, indent=2)
            st.download_button(
                label="📄 Download Full Report (JSON)",
                data=json_str,
                file_name=f"mlb_report_{target_date}.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.info("Tidak ada data untuk di-export.")
    
    # ── RIWAYAT PREDIKSI ──
    st.divider()
    st.subheader("📜 Riwayat Prediksi")
    
    # Coba baca file history
    history_file = 'data/prediction_history.csv'
    if os.path.exists(history_file):
        df_history = pd.read_csv(history_file)
        st.dataframe(df_history.tail(10), use_container_width=True, hide_index=True)
    else:
        st.caption("Belum ada riwayat. Riwayat akan otomatis tersimpan setelah beberapa kali run.")
    
    # Simpan ke history
    if data['top_picks']:
        df_new = pd.DataFrame(data['top_picks'])
        df_new['run_date'] = datetime.now().strftime('%Y-%m-%d')
        df_new['target_date'] = target_date
        
        if os.path.exists(history_file):
            df_history = pd.read_csv(history_file)
            df_combined = pd.concat([df_history, df_new], ignore_index=True)
        else:
            df_combined = df_new
        
        os.makedirs('data', exist_ok=True)
        df_combined.to_csv(history_file, index=False)

else:
    # Belum ada hasil
    st.info("👈 Klik tombol **Run Analysis** di sidebar untuk memulai analisis.")
    
    # Tampilkan panduan
    with st.expander("📖 Cara Menggunakan Dashboard Ini"):
        st.markdown("""
        1. **Pilih Target Prediksi** di sidebar:
           - **Hari Ini (ET)**: Untuk game yang sedang berlangsung hari ini waktu Amerika
           - **Besok (ET)**: Untuk game besok pagi WIB (= malam ini ET)
           - **Tanggal Spesifik**: Untuk backtest atau perencanaan
        
        2. **Klik "Run Analysis"** dan tunggu 1-3 menit.
        
        3. **Lihat hasil** di tab Top Picks:
           - 🟢 Hijau = Strong Value (Edge > 10%)
           - 🟡 Kuning = Good Value (Edge 5-10%)
        
        4. **Cross-check manual** sebelum taruhan:
           - Cek cedera pemain
           - Cek cuaca
           - Cek lineup final (1 jam sebelum game)
        
        5. **Export** hasil ke CSV untuk jurnal taruhan Anda.
        """)
    
    # Coba load dari JSON jika ada
    if os.path.exists('data/todays_picks.json'):
        st.divider()
        st.subheader("📂 Hasil Terakhir (dari file cache)")
        try:
            with open('data/todays_picks.json', 'r') as f:
                cached_data = json.load(f)
            st.json(cached_data)
        except:
            pass

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption("""
⚾ **MLB Props Quant Engine 2026** | 
Dibangun dengan Python, Statcast, dan The Odds API | 
⚠️ Selalu gunakan manajemen bankroll yang baik (1-2% per bet). 
Tidak ada jaminan keuntungan. Bertaruhlah dengan bertanggung jawab.
""")