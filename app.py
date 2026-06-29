import streamlit as st
import sqlite3
import pandas as pd
import re
import subprocess
import sys
import os
import time
from datetime import datetime, timedelta
# ==========================================
# KONFIGURACE STRÁNKY
# ==========================================
st.set_page_config(
    page_title="AI Realitní Radar",
    layout="wide",
    page_icon="🏠",
    initial_sidebar_state="expanded"
)

# ==========================================
# GLOBÁLNÍ CSS — Moderní tmavý design v2
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Hlavní pozadí */
    .stApp {
        background: linear-gradient(135deg, #0d1117 0%, #161b27 50%, #0d1117 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161b27 0%, #1a2035 100%);
        border-right: 1px solid rgba(99,102,241,0.2);
    }
    
    /* Vlastní typography a barvy */
    .hero-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: #94a3b8;
        font-weight: 400;
        margin-bottom: 2rem;
    }

    /* KPI Karty */
    .kpi-card {
        background: rgba(30,41,59,0.5);
        border: 1px solid rgba(99,102,241,0.15);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(99,102,241,0.15);
        background: rgba(30,41,59,0.8);
    }
    .kpi-icon { font-size: 1.8rem; margin-bottom: 0.5rem; display: block; }
    .kpi-value { font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
    .kpi-label { font-size: 0.75rem; font-weight: 500; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.2rem; }

    /* Hlavní karta bytu */
    .byt-card {
        background: rgba(15,23,42,0.6);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .byt-card:hover {
        background: rgba(15,23,42,0.9);
        border-color: rgba(99,102,241,0.4);
        box-shadow: 0 8px 30px rgba(0,0,0,0.5);
    }
    /* Zelený okraj pro top nabídky */
    .byt-card-levna { border-left: 5px solid #22c55e; }
    .byt-card-ferova { border-left: 5px solid #eab308; }
    .byt-card-predra { border-left: 5px solid #ef4444; border-color: rgba(239,68,68,0.2); }
    
    .byt-nazev { font-size: 1.35rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.3rem; }
    .byt-lokalita { font-size: 0.95rem; color: #94a3b8; margin-bottom: 1rem; display:flex; align-items:center; gap:0.3rem; }
    
    /* Ceny */
    .cena-label { font-size: 0.75rem; text-transform: uppercase; color: #64748b; font-weight: 600; letter-spacing: 0.05em; }
    .cena-inzerat { font-size: 1.8rem; font-weight: 800; color: #f8fafc; }
    .cena-odhad { font-size: 1.4rem; font-weight: 600; color: #a5b4fc; }

    /* Odznaky (Badges) */
    .status-badge {
        display: inline-block;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge-levna { background: rgba(34,197,94,0.15); color: #4ade80; border: 1px solid rgba(34,197,94,0.3); }
    .badge-ferova { background: rgba(234,179,8,0.15); color: #fde047; border: 1px solid rgba(234,179,8,0.3); }
    .badge-predra { background: rgba(239,68,68,0.15); color: #f87171; border: 1px solid rgba(239,68,68,0.3); }
    
    /* Odznaky pro nové a zlevněné (menší a pulzující) */
    @keyframes pulse-new {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    .badge-nove {
        display: inline-block; padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.75rem; font-weight: 800;
        background: linear-gradient(135deg, #ef4444, #dc2626); color: white; margin-left: 0.5rem;
        animation: pulse-new 2s infinite; vertical-align: middle;
    }
    .badge-zlevneno {
        display: inline-block; padding: 0.2rem 0.5rem; border-radius: 6px; font-size: 0.75rem; font-weight: 800;
        background: linear-gradient(135deg, #10b981, #059669); color: white; margin-left: 0.5rem;
        vertical-align: middle; border: 1px solid rgba(255,255,255,0.2);
    }

    /* Důvěra ProgressBar */
    .duvera-bar-bg {
        background: rgba(15,23,42,0.8);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 4px;
        height: 6px;
        width: 100%;
        margin-top: 0.3rem;
        overflow: hidden;
    }
    .duvera-bar-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, #818cf8, #c084fc);
    }

    /* Tlačítka */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 15px rgba(99,102,241,0.3) !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(99,102,241,0.5) !important;
    }

    /* Oddělovač */
    hr { border-color: rgba(99,102,241,0.15) !important; margin: 1.5rem 0 !important; }

    /* Divider nadpis sekce */
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #a5b4fc;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 1.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .section-title::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(99,102,241,0.3), transparent);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# DATABÁZOVÉ FUNKCE
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zakazky.db')

def nacti_data(pouze_zajimave: bool = False) -> pd.DataFrame:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        if pouze_zajimave:
            df = pd.read_sql_query(
                """
                SELECT * FROM nalezene_byty 
                WHERE odhad_ai > 0 AND ((cena - odhad_ai) * 100.0 / odhad_ai) <= 3.0
                ORDER BY id DESC LIMIT 10
                """, conn
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM nalezene_byty ORDER BY id DESC LIMIT 10", conn
            )
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def nacti_top_3() -> pd.DataFrame:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            """
            SELECT * FROM nalezene_byty 
            WHERE odhad_ai > 0 AND (cena - odhad_ai) < 0
            ORDER BY ((cena - odhad_ai) * 100.0 / odhad_ai) ASC 
            LIMIT 3
            """, conn
        )
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def nacti_kpi() -> dict:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM nalezene_byty")
        celkem = cur.fetchone()[0]
        return {"celkem": celkem}
    except Exception:
        return {"celkem": 0}
    finally:
        if conn:
            conn.close()

def nacti_historii_cen(byt_id: int) -> pd.DataFrame:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT cena, timestamp FROM historie_cen WHERE byt_id=? ORDER BY timestamp ASC",
            conn, params=(byt_id,)
        )
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def vypocitej_odchylku(row) -> float:
    if row['odhad_ai'] > 0:
        return ((row['cena'] - row['odhad_ai']) / row['odhad_ai']) * 100
    return 0.0

def urcit_status(odchylka: float) -> tuple[str, str, str]:
    if odchylka < -3:
        return "🟢 Levná koupě", "levna", "badge-levna"
    elif odchylka <= 3:
        return "🟡 Férová nabídka", "ferova", "badge-ferova"
    else:
        return "🔴 Předraženo", "predra", "badge-predra"

def extrahuj_dispozici(nazev: str) -> str:
    m = re.search(r'(\d+\+(?:1|kk|KK))', nazev, re.IGNORECASE)
    return m.group(1) if m else "Byt"

def extrahuj_m2(nazev: str) -> str:
    m = re.search(r'(\d+)\s*m[²2]', nazev, re.IGNORECASE)
    return f"{m.group(1)} m²" if m else "? m²"

def extrahuj_duveru(zduvodneni: str) -> int:
    m = re.search(r'Spolehlivost dat:\*\* (\d+)', zduvodneni or '')
    return int(m.group(1)) if m else 0

def je_novy(timestamp_str: str, hodin: int = 24) -> bool:
    try:
        ts = datetime.strptime(timestamp_str[:19], "%Y-%m-%d %H:%M:%S")
        return datetime.now() - ts < timedelta(hours=hodin)
    except (ValueError, TypeError):
        return False

def je_zlevneny(puvodni_cena) -> bool:
    try:
        return int(puvodni_cena) > 0
    except (ValueError, TypeError):
        return False

# ==========================================
# AUTO-SCRAPER OVLÁDÁNÍ
# ==========================================
PROJEKT_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(PROJEKT_DIR, ".auto_scraper.pid")

def is_auto_scraper_running():
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        if sys.platform == "win32":
            output = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True, text=True)
            return str(pid) in output
        else:
            # Simple check for linux (if user switches OS)
            os.kill(pid, 0)
            return True
    except:
        return False

def toggle_auto_scraper(zapnout: bool):
    if zapnout and not is_auto_scraper_running():
        python_exe = sys.executable
        auto_script = os.path.join(PROJEKT_DIR, "auto_scraper.py")
        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        subprocess.Popen([python_exe, auto_script], creationflags=creation_flags)
        time.sleep(1) # Počkat, než se vytvoří PID soubor
    elif not zapnout and is_auto_scraper_running():
        try:
            with open(PID_FILE, "r") as f:
                pid = int(f.read().strip())
            if sys.platform == "win32":
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass

# ==========================================
# SCRAPER — SKRYTÉ SPUŠTĚNÍ S ST.STATUS A LIVE LOGEM
# ==========================================
def spust_scraper_a_zobraz_log(scraper_dir: str):
    python_exe = sys.executable
    scraper_path = os.path.join(scraper_dir, "scraper.py")
    creation_flags = 0x08000000 if sys.platform == "win32" else 0
    env_utf8 = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

    with st.status("Scraper prave bezi. Prosim cekejte, muze to trvat nekolik minut...", expanded=True) as status:
        st.write("Spoustim scraper.py na pozadi...")
        try:
            result = subprocess.run(
                [python_exe, scraper_path],
                cwd=scraper_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env_utf8,
                creationflags=creation_flags,
            )
        except Exception as e:
            status.update(label=f"Chyba: scraper se nepodarilo spustit.", state="error")
            st.error(f"Nelze spustit scraper.py: {e}")
            return

        vystup = (result.stdout or "") + (result.stderr or "")
        if vystup.strip():
            st.code(vystup, language="text")

        if result.returncode == 0:
            status.update(label="Hotovo! Scraper uspesne dokoncil stazeni.", state="complete", expanded=False)
            st.rerun() # Automaticky obnoví stránku a ukáže nové byty!
        else:
            status.update(label=f"Scraper skoncil s chybou (kod {result.returncode}). Viz log nize.", state="error", expanded=True)
            st.error("Scraper neskončil úspěšně. Zkopíruj mi log výše.")
            return

# ==========================================
# SIDEBAR — Ovládání a filtry
# ==========================================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 1.5rem 0;">
        <div style="font-size:2.5rem;">🏠</div>
        <div style="font-size:1.1rem; font-weight:700; color:#e2e8f0;">AI Realitní Radar</div>
        <div style="font-size:0.75rem; color:#64748b;">powered by Groq + LLaMA 3.3</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 🔍 Chytrý Filtr")
    filtr_nejlepsi = st.toggle("Nejlepší nákupy", value=False, help="Zobrazí 10 nejnovějších bytů se statusem Levná koupě nebo Férová nabídka napříč databází.")
    
    st.divider()

    st.markdown("## 🤖 Automatizace")
    is_running = is_auto_scraper_running()
    auto_run = st.toggle("Auto-Scraper (15 min)", value=is_running, help="Poběží na pozadí a pošle zprávu na Telegram, když najde slevu.")
    if auto_run != is_running:
        toggle_auto_scraper(auto_run)
        st.rerun()

    st.divider()
    
    st.markdown("## 🚀 Manuální Scraper")
    st.caption("Jednorázové spuštění kontroly novinek.")
    spustit = st.button("▶ Spustit scraper", use_container_width=True, key="btn_scraper")

    if st.button("🔄 Obnovit data", use_container_width=True, key="btn_refresh"):
        st.rerun()

    st.divider()
    kpi = nacti_kpi()
    st.caption(f"🏢 Bytů v DB: **{kpi['celkem']}**")

# ==========================================
# HERO SEKCE
# ==========================================
st.markdown('<div class="hero-title">🏠 AI Realitní Radar</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Inteligentní analýza trhu — AI odhad ceny každého bytu v reálném čase</div>', unsafe_allow_html=True)

# ==========================================
# LIVE SCRAPER SEKCE (priorita nad vším ostatním)
# ==========================================
if spustit:
    st.markdown('<div class="section-title">🔄 Průběh scraperu</div>', unsafe_allow_html=True)
    spust_scraper_a_zobraz_log(PROJEKT_DIR)
    st.stop()

# ==========================================
# TOP DEALS (Načtení 3 nejlepších z celé DB)
# ==========================================
df_top3 = nacti_top_3()
if not df_top3.empty:
    df_top3['odchylka'] = df_top3.apply(vypocitej_odchylku, axis=1)
    
    st.markdown('<div class="section-title">🏆 Top 3 Deals vůbec</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    
    for rank, (_, trow) in enumerate(df_top3.iterrows()):
        disp_t     = extrahuj_dispozici(str(trow['nazev']))
        m2_t       = extrahuj_m2(str(trow['nazev']))
        cena_t     = int(trow['cena'])
        odhad_t    = int(trow['odhad_ai'])
        odch_t     = float(trow['odchylka'])
        lok_t      = str(trow['lokalita'])
        url_t      = str(trow['url'])
        usp_czk    = odhad_t - cena_t
        medal      = ["🥇", "🥈", "🥉"][rank]
        cena_fmt_t = f"{cena_t:,}".replace(',', ' ')
        usp_fmt_t  = f"{usp_czk:,}".replace(',', ' ')

        extra_badges = ""
        if 'puvodni_cena' in trow.index and je_zlevneny(trow.get('puvodni_cena', 0)):
            extra_badges += '<span class="badge-zlevneno">⬇️ ZLEVNĚNO</span> '

        with cols[rank]:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(15,23,42,0.9) 100%);
                border: 1px solid rgba(34,197,94,0.25); border-left: 4px solid #22c55e; border-radius: 14px;
                padding: 0.9rem 1.2rem; margin-bottom: 0.6rem;
                display: flex; flex-direction: column; justify-content: space-between; gap: 0.5rem; height: 100%;
            ">
                <div>
                    <span style="font-size:1.3rem;">{medal}</span>
                    <strong style="color:#e2e8f0; font-size:1rem;">&nbsp;{disp_t} · {m2_t}</strong> {extra_badges}
                    <div style="color:#64748b; font-size:0.82rem; margin-top:0.2rem;">📍 {lok_t}</div>
                </div>
                <div style="display:flex; justify-content: space-between; align-items: flex-end; margin-top:0.5rem;">
                    <div>
                        <div style="color:#94a3b8; font-size:0.72rem; text-transform:uppercase;">Cena</div>
                        <div style="color:#e2e8f0; font-weight:700;">{cena_fmt_t} Kč</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#22c55e; font-size:1.4rem; font-weight:800;">{odch_t:.1f} %</div>
                    </div>
                </div>
                <a href="{url_t}" target="_blank" style="
                    background: linear-gradient(135deg,#22c55e,#16a34a); color:white; text-decoration:none;
                    padding:0.45rem 1rem; border-radius:8px; font-size:0.82rem; font-weight:600; text-align:center; display:block; margin-top: 0.3rem;
                ">🔗 Otevřít na Sreality</a>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# SEZNAM BYTŮ (10 nejnovějších)
# ==========================================
df = nacti_data(filtr_nejlepsi)

if filtr_nejlepsi:
    st.markdown(f'<div class="section-title">✨ Nejnovější Zajímavé Nabídky (Top 10)</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="section-title">🏢 Absolutně Nejnovější Nabídky (Top 10)</div>', unsafe_allow_html=True)

if df.empty:
    st.warning("📭 Nebyly nalezeny žádné byty. Spusť scraper.")
else:
    df['odchylka']   = df.apply(vypocitej_odchylku, axis=1)
    df['status_txt'] = df['odchylka'].apply(lambda x: urcit_status(x)[0])
    df['dispozice']  = df['nazev'].apply(extrahuj_dispozici)
    df['m2_txt']     = df['nazev'].apply(extrahuj_m2)
    df['duvera']     = df.apply(lambda r: extrahuj_duveru(str(r.get('zduvodneni', ''))), axis=1)

    df['je_novy'] = df.apply(lambda r: je_novy(str(r.get('timestamp', '')), hodin=24), axis=1)
    if 'puvodni_cena' in df.columns:
        df['je_zlevneny'] = df['puvodni_cena'].apply(je_zlevneny)
    else:
        df['je_zlevneny'] = False

    for _, row in df.iterrows():
        nazev        = str(row['nazev'])
        cena         = int(row['cena'])
        odhad        = int(row['odhad_ai'])
        url          = str(row['url'])
        lokalita     = str(row['lokalita'])
        zduvodneni   = str(row.get('zduvodneni', ''))
        odchylka_val = float(row['odchylka'])
        dispozice    = str(row['dispozice'])
        m2_txt       = str(row['m2_txt'])
        duvera_val   = int(row['duvera'])
        timestamp    = str(row.get('timestamp', ''))
        je_novy_flag = bool(row.get('je_novy', False))
        je_zlev_flag = bool(row.get('je_zlevneny', False))
        puvodni_c    = int(row.get('puvodni_cena', 0)) if 'puvodni_cena' in row.index else 0

        status_txt, status_cls, badge_cls = urcit_status(odchylka_val)

        cena_fmt  = f"{cena:,}".replace(',', ' ')
        odhad_fmt = f"{odhad:,}".replace(',', ' ')
        sleva_czk = cena - odhad
        sleva_fmt = f"{sleva_czk:+,}".replace(',', ' ')
        ts_display = timestamp[:16] if (timestamp and timestamp != 'nan' and len(timestamp) >= 16) else ''
        sleva_color = '#ef4444' if sleva_czk > 0 else '#22c55e'

        extra_badges_html = ""
        if je_novy_flag:
            extra_badges_html += ' <span class="badge-nove">🔥 NOVÉ</span>'
        if je_zlev_flag:
            sleva_abs = puvodni_c - cena
            sleva_abs_fmt = f"{sleva_abs:,}".replace(',', ' ')
            extra_badges_html += f' <span class="badge-zlevneno">⬇️ ZLEVNĚNO −{sleva_abs_fmt} Kč</span>'

        st.markdown(f"""
        <div class="byt-card byt-card-{status_cls}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:1rem;">
                <div style="flex:2; min-width:200px;">
                    <div class="byt-nazev">🏠 {dispozice} &nbsp;·&nbsp; {m2_txt}{extra_badges_html}</div>
                    <div class="byt-lokalita">📍 {lokalita}</div>
                    <span class="status-badge {badge_cls}">{status_txt} &nbsp; {odchylka_val:+.1f} %</span>
                </div>
                <div style="flex:1; min-width:130px; text-align:center;">
                    <div class="cena-label">Cena inzerátu</div>
                    <div class="cena-inzerat">{cena_fmt} Kč</div>
                    <div style="font-size:0.75rem; color:{sleva_color};">{sleva_fmt} Kč vs. odhad</div>
                </div>
                <div style="flex:1; min-width:130px; text-align:center;">
                    <div class="cena-label">🧠 AI Odhad</div>
                    <div class="cena-odhad">{odhad_fmt} Kč</div>
                    <div style="font-size:0.75rem; color:#64748b;">Důvěra: {duvera_val} %</div>
                    <div class="duvera-bar-bg">
                        <div class="duvera-bar-fill" style="width:{duvera_val}%;"></div>
                    </div>
                </div>
                <div style="min-width:120px; text-align:right; display:flex; flex-direction:column; gap:0.4rem; align-items:flex-end;">
                    <a href="{url}" target="_blank" style="
                        background: linear-gradient(135deg,#6366f1,#8b5cf6);
                        color:white; text-decoration:none;
                        padding:0.5rem 1.2rem; border-radius:10px;
                        font-size:0.85rem; font-weight:600;
                        white-space:nowrap;
                    ">🔗 Otevřít</a>
                    <span style="font-size:0.7rem; color:#475569;">📅 {ts_display}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🤖 Rozbalit AI analýzu a matematický rozpad výpočtu"):
            hist_df = nacti_historii_cen(row['id'])
            if len(hist_df) > 1:
                st.markdown("**📉 Vývoj ceny v čase**")
                st.line_chart(hist_df['cena'], use_container_width=True)
                st.markdown("---")
            st.markdown(zduvodneni)

# ==========================================
# FOOTER
# ==========================================
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#334155; font-size:0.8rem; padding:1rem 0;">
    AI Realitní Radar v2.0 &nbsp;·&nbsp; Powered by <strong style="color:#818cf8">Groq LLaMA 3.3 70B</strong>
    &nbsp;·&nbsp; Data ze <strong style="color:#818cf8">sreality.cz</strong>
    <br>Odhady AI jsou pouze orientační a nemohou nahradit odborné posouzení.
</div>
""", unsafe_allow_html=True)