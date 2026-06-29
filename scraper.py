import traceback
from time import sleep
import re
import time
import random
import sys
from datetime import datetime
import json
import sqlite3
import requests
import os
from dotenv import load_dotenv

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from groq import Groq

# ==========================================
# 1. NASTAVENÍ A PŘIPOJENÍ
# ==========================================
# Vynucení UTF-8 výstupu na Windows (prevence UnicodeEncodeError)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("[CHYBA] Chybi GROQ_API_KEY! Vytvor .env soubor podle .env.example a vloz svuj klic.")
    sys.exit(1)

# Telegram konfigurace (volitelné)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
except FileNotFoundError:
    print("[WARNING] Chybi config.json, pouzivam vychozi nastaveni.")
    config = {}

HEADLESS            = config.get("headless", True)
MAX_PAGES           = config.get("max_pages", 3)
MAX_BYTU_NA_STRANKU = config.get("max_bytu_na_stranku", 8)

client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# 2. DATABÁZE — Inicializace se schématem v3
# ==========================================
def init_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zakazky.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS nalezene_byty (
            id          INTEGER PRIMARY KEY,
            nazev       TEXT,
            cena        INTEGER,
            url         TEXT,
            odhad_ai    INTEGER,
            lokalita    TEXT,
            plusy       TEXT,
            minusy      TEXT,
            zduvodneni  TEXT,
            timestamp   TEXT DEFAULT (datetime('now','localtime')),
            puvodni_cena INTEGER DEFAULT 0
        )
    ''')
    
    # Nová tabulka pro sledování historie cen
    c.execute('''
        CREATE TABLE IF NOT EXISTS historie_cen (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            byt_id      INTEGER,
            cena        INTEGER,
            timestamp   TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    
    # Migrace: přidej timestamp sloupec pokud chybí (zpětná kompatibilita)
    for col_sql in [
        "ALTER TABLE nalezene_byty ADD COLUMN timestamp TEXT DEFAULT (datetime('now','localtime'))",
        "ALTER TABLE nalezene_byty ADD COLUMN puvodni_cena INTEGER DEFAULT 0",
    ]:
        try:
            c.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # Sloupec už existuje
            
    # Pokud je historie cen prázdná, ale máme už nějaké byty, naimportujeme jejich aktuální ceny jako první bod do grafu
    c.execute("SELECT COUNT(*) FROM historie_cen")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO historie_cen (byt_id, cena, timestamp) SELECT id, cena, timestamp FROM nalezene_byty")
        
    conn.commit()
    return conn

# ==========================================
# 3. CENOVÁ MAPA — Načítání z externího JSON
# ==========================================
def nacti_cenovou_mapu() -> dict:
    """Načte cenovou mapu z cenova_mapa.json. Fallback na prázdný dict."""
    try:
        with open('cenova_mapa.json', 'r', encoding='utf-8') as f:
            mapa = json.load(f)
        # Odstraníme komentářové klíče
        return {k: v for k, v in mapa.items() if not k.startswith("_")}
    except FileNotFoundError:
        print("[WARNING] Chybi cenova_mapa.json, pouzivam fallback 55 000 Kc/m2.")
        return {}

CENOVA_MAPA = nacti_cenovou_mapu()
DEFAULT_CENA_M2 = CENOVA_MAPA.pop("_default", 55000) if "_default" in CENOVA_MAPA else 55000

def ziskej_cenu_za_m2(nazev_lokality: str) -> int:
    """Vyhledá cenu za m² v cenové mapě. Hledá od nejdelšího klíče (nejpřesnější shoda)."""
    lokalita = nazev_lokality.lower()
    # Seřadíme klíče od nejdelšího po nejkratší → specifičtější shoda má přednost
    for klic in sorted(CENOVA_MAPA.keys(), key=len, reverse=True):
        if klic in lokalita:
            return CENOVA_MAPA[klic]
    return DEFAULT_CENA_M2

# ==========================================
# 4. TELEGRAM NOTIFIKACE
# ==========================================
def posli_telegram(zprava: str):
    """Odešle zprávu přes Telegram Bot API. Pokud Telegram není nakonfigurován, nic neudělá."""
    if not TELEGRAM_ENABLED:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": zprava,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("    [TELEGRAM] Notifikace odeslana.")
        else:
            print(f"    [TELEGRAM] Chyba: HTTP {resp.status_code} — {resp.text[:120]}")
    except Exception as e:
        print(f"    [TELEGRAM] Chyba odeslani: {e}")

def formatuj_telegram_zpravu(typ: str, nazev: str, lokalita: str, cena: int, odhad: int, odchylka: float, url: str, puvodni_cena: int = 0) -> str:
    """Sestaví HTML zprávu pro Telegram."""
    cena_fmt = f"{cena:,}".replace(",", " ")
    odhad_fmt = f"{odhad:,}".replace(",", " ")

    dispozice_m = re.search(r'(\d+\+(?:1|kk|KK))', nazev, re.IGNORECASE)
    dispozice = dispozice_m.group(1) if dispozice_m else "Byt"
    m2_m = re.search(r'(\d+)\s*m', nazev)
    m2 = f"{m2_m.group(1)} m²" if m2_m else ""

    if typ == "nova":
        emoji = "🟢"
        titulek = "NOVÁ LEVNÁ KOUPĚ"
    else:
        emoji = "🔥"
        titulek = "ZLEVNĚNÝ INZERÁT"

    zprava = f"{emoji} <b>{titulek}</b>\n\n"
    zprava += f"🏠 {dispozice} · {m2}\n"
    zprava += f"📍 {lokalita}\n\n"
    zprava += f"💰 Cena: <b>{cena_fmt} Kč</b>\n"
    zprava += f"🧠 AI Odhad: <b>{odhad_fmt} Kč</b>\n"
    zprava += f"📊 Odchylka: <b>{odchylka:+.1f} %</b>\n"

    if typ == "zlevneno" and puvodni_cena > 0:
        sleva = puvodni_cena - cena
        sleva_fmt = f"{sleva:,}".replace(",", " ")
        puvodni_fmt = f"{puvodni_cena:,}".replace(",", " ")
        zprava += f"\n⬇️ Sleva: <b>-{sleva_fmt} Kč</b> (z {puvodni_fmt} Kč)\n"

    zprava += f"\n🔗 <a href=\"{url}\">Otevřít na Sreality</a>"
    return zprava

# ==========================================
# 5. GROQ AI EXTRAKTOR  ← NEDOTKNUTELNÁ FUNKCE
# ==========================================
def analyzuj_inzerat_groq(nazev: str, popis: str) -> dict | None:
    prompt = f"""
    Jsi nemilosrdný analytik dat z realitních inzerátů. NEPOČÍTEJ CENU (cenu inzerátu ignoruj, nesnaž se ji odhadovat). Extrahuj pouze fakta.
    Pečlivě si přečti i informace o garáži, zahradě nebo dalších nákladech (často se platí zvlášť).
    
    Inzerát: {nazev} | {popis}
    
    Pravidla pro parametry:
    - rozloha_m2: podlahová plocha bytu v m2 (pouze číslo). Hledej v textu i názvu.
    - dispozice: např. "1+kk", "3+1", "atypicky"
    - stav: "luxus" (pouze pokud je po NAPROSTÉ kompletní rekonstrukci na míru nebo novostavba), "dobry" (udržovaný, částečná rekonstrukce), "spatny" (před rekonstrukcí, původní stav), "neznamo"
    - material: "cihla", "skelet", "panel", "neznamo"
    - patro: "prizemi_podkrovi" (i suterén), "vyssi_s_vytahem", "standard" (všechno ostatní, např. 2. patro bez výtahu), "neznamo"
    - penb: "a", "b", "c", "g", "ostatni", "neznamo"
    - garaz_stani: true (pokud je v ceně nebo lze dokoupit), false
    - sklep_m2: plocha sklepa v m2 (číslo, 0 pokud není)
    - balkon_m2: plocha balkonu/terasy v m2 (číslo, 0 pokud není)
    
    KRITICKÉ PRAVIDLO:
    I když něco není výslovně napsáno v odrážkách, přečti si celý text! Pokud ani tam informace není, napiš "neznamo" (nebo 0) a dej to do "chybejici_data".
    ZAKAZUJI TI SI DATA VYMÝŠLET NEBO HÁDAT!
    
    HODNOCENÍ INVESTICE:
    Vyplň dvě věty. Do "investicni_riziko" napiš hlavní hrozbu (např. 'nutná rekonstrukce', 'přirážka za garáž', 'rušná ulice'). Do "investicni_potencial" napiš hlavní technické plus. Buď maximálně stručný a kritický.
    
    Vrať POUZE tento JSON objekt a NIC JINÉHO:
    {{
        "rozloha_m2": 0,
        "dispozice": "neznamo",
        "stav": "dobry",
        "material": "neznamo",
        "patro": "standard",
        "penb": "neznamo",
        "garaz_stani": false,
        "sklep_m2": 0,
        "balkon_m2": 0,
        "chybejici_data": ["material", "penb"],
        "investicni_riziko": "Riziko...",
        "investicni_potencial": "Potenciál..."
    }}
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        odpoved = chat_completion.choices[0].message.content.strip()
        return json.loads(odpoved)
    except Exception as e:
        print(f"[WARNING] Chyba AI extraktoru (JSON): {e}")
        return None

# ==========================================
# 6. VÝPOČET ODHADU CENY  ← NEDOTKNUTELNÁ FUNKCE
# ==========================================
def vypocitej_odhad(m2: int, data_ai: dict, cena_m2_lokalita: int) -> tuple:
    historie_uprav = []

    # 1. VELIKOSTNÍ DEGRESE
    korekce_m2 = 1.0
    if m2 <= 35:
        korekce_m2 = 1.20
        historie_uprav.append("Velikostní přirážka (Mikro byt ≤ 35 m²): +20 % k základní ceně za m²")
    elif m2 <= 50:
        korekce_m2 = 1.10
        historie_uprav.append("Velikostní přirážka (Malý byt ≤ 50 m²): +10 % k základní ceně za m²")
    elif m2 >= 100:
        korekce_m2 = 0.90
        historie_uprav.append("Velikostní sleva (Velkometrážní byt ≥ 100 m²): -10 % ze základní ceny za m²")
    elif m2 >= 80:
        korekce_m2 = 0.95
        historie_uprav.append("Velikostní sleva (Větší byt ≥ 80 m²): -5 % ze základní ceny za m²")

    upravena_cena_m2 = cena_m2_lokalita * korekce_m2
    zakladni_cena   = m2 * upravena_cena_m2

    # 2. KVALITATIVNÍ KOEFICIENTY
    koeficient = 1.0
    stav     = str(data_ai.get('stav',     'neznamo')).lower()
    material = str(data_ai.get('material', 'neznamo')).lower()

    if stav == 'luxus':
        koeficient += 0.20
        historie_uprav.append("Stav (Novostavba/Luxusní reko): +20 %")
    elif stav in ['spatny', 'neznamo']:
        koeficient -= 0.20
        historie_uprav.append("Stav (Špatný nebo Neznámý): -20 %")
    else:
        historie_uprav.append("Stav (Dobrý/Standardní): 0 %")

    if material in ['cihla', 'skelet']:
        koeficient += 0.05
        historie_uprav.append("Materiál (Cihla/Skelet): +5 %")
    elif material == 'panel':
        koeficient -= 0.10
        historie_uprav.append("Materiál (Panel): -10 %")
    elif material == 'neznamo':
        if stav == 'luxus':
            koeficient += 0.05
            historie_uprav.append("Materiál (Neznámý, Luxusní stav → Předpoklad Skelet/Cihla): +5 %")
        else:
            koeficient -= 0.10
            historie_uprav.append("Materiál (Neznámý → Pesimistický předpoklad Panel): -10 %")

    patro = str(data_ai.get('patro', 'neznamo')).lower()
    if patro == 'vyssi_s_vytahem':
        koeficient += 0.03
        historie_uprav.append("Patro (Vyšší s výtahem): +3 %")
    elif patro in ['prizemi_podkrovi', 'neznamo']:
        koeficient -= 0.05
        historie_uprav.append("Patro (Přízemí/Podkroví/Neznámé): -5 %")
    else:
        historie_uprav.append("Patro (Standardní střední patro): 0 %")

    penb = str(data_ai.get('penb', 'neznamo')).lower()
    if penb in ['a', 'b']:
        koeficient += 0.05
        historie_uprav.append("PENB (A/B - Úsporná): +5 %")
    elif penb in ['g', 'neznamo']:
        koeficient -= 0.10
        historie_uprav.append("PENB (G nebo Neznámý): -10 %")
    else:
        historie_uprav.append("PENB (Standard C-F): 0 %")

    upravena_cena   = zakladni_cena * koeficient
    uprava_proc_czk = round(upravena_cena - zakladni_cena, -4)

    # 3. FIXNÍ BONUSY
    bonusy = 0
    if str(data_ai.get('garaz_stani', False)).lower() == 'true':
        cena_garaz = round(cena_m2_lokalita * 6, -4)
        bonusy += cena_garaz
        historie_uprav.append(f"Garážové stání (Lokalizovaná cena): +{int(cena_garaz):,} Kč".replace(',', ' '))

    try:    sklep = float(data_ai.get('sklep_m2', 0))
    except: sklep = 0.0
    if sklep > 0:
        cena_sklep = round(sklep * (cena_m2_lokalita * 0.3), -3)
        bonusy += cena_sklep
        historie_uprav.append(f"Sklep ({sklep} m²): +{int(cena_sklep):,} Kč".replace(',', ' '))

    try:    balkon = float(data_ai.get('balkon_m2', 0))
    except: balkon = 0.0
    if balkon > 0:
        cena_balkon = round(balkon * (cena_m2_lokalita * 0.25), -3)
        bonusy += cena_balkon
        historie_uprav.append(f"Balkon/Terasa ({balkon} m²): +{int(cena_balkon):,} Kč".replace(',', ' '))

    finalni_cena = round(upravena_cena + bonusy, -4)

    # 4. SPOLEHLIVOST
    chybejici = data_ai.get('chybejici_data', [])
    if not isinstance(chybejici, list):
        chybejici = [chybejici]
    chybejici = [p for p in chybejici if str(p).lower() not in ["nic", "všechna data nalezena", "vse", "none", "[]"]]

    confidence = max(0, 100 - (len(chybejici) * 15))
    if confidence < 40:
        historie_uprav.insert(0, "**⚠️ POZOR: Extrémní nedostatek dat. Algoritmus uplatnil maximální pesimistické srážky.**")

    return int(finalni_cena), int(uprava_proc_czk), int(bonusy), confidence, chybejici, historie_uprav, upravena_cena_m2

# ==========================================
# 7. JAVASCRIPT PRO VÝBĚR BYTŮ ZE STRÁNKY
# ==========================================
JS_SEZNAM = """
() => {
    const nalezene = {};
    const odkazy = document.querySelectorAll('a[href*="/detail/prodej/byt"]');
    odkazy.forEach(odkaz => {
        const url = odkaz.href;
        const idMatch = url.match(/(\\d+)$/);
        if (!idMatch) return;
        const id = parseInt(idMatch[1]);
        let karta = odkaz.parentElement;
        let pokusy = 7;
        let maCenu = false;
        while (karta && pokusy > 0) {
            if (karta.innerText && karta.innerText.includes("Kč")) { maCenu = true; break; }
            karta = karta.parentElement; pokusy--;
        }
        if (maCenu) {
            let radkyVsechny = karta.innerText.split('\\n').map(r => r.trim()).filter(r => r.length > 0);
            let radky = radkyVsechny.filter(r => !r.toLowerCase().includes("fotografi") && !r.toLowerCase().includes("zobrazit"));
            const cenaRadek = radky.find(r => r.includes("Kč")) || "0";
            const cenaCislo = parseInt(cenaRadek.replace(/\\D/g, '')) || 0;
            let nazevCisty = radky.length > 0 ? radky[0] : "Neznámý název";
            let lokalitaCista = radky.length > 1 && !radky[1].includes("Kč") ? radky[1] : "Neznámá Lokalita";
            nalezene[id] = { id, nazev: nazevCisty, lokalita: lokalitaCista, cena: cenaCislo, url };
        }
    });
    return Object.values(nalezene);
}
"""

# ==========================================
# 8. EXTRAKCE POPISU Z DETAIL STRÁNKY
#    Sbírá VŠE: popis + parametrové tabulky + štítky PENB
#    BEZ předčasného ukončování cyklu přes break
# ==========================================
JS_DETAIL = """
() => {
    const casti = [];
    const videnePrvky = new Set();

    // --- ČÁST 1: Textový popis inzerátu ---
    const popisSelektory = [
        '[class*="description"]',
        '[class*="Description"]',
        '[data-testid*="description"]',
        '[class*="PropertyDescription"]',
        '[class*="property-description"]',
        '[class*="perex"]',
        'section[class*="desc"]'
    ];
    const popisTexty = [];
    for (const sel of popisSelektory) {
        Array.from(document.querySelectorAll(sel))
            .filter(e => e.innerText && e.innerText.length > 80 && !videnePrvky.has(e))
            .forEach(e => {
                videnePrvky.add(e);
                popisTexty.push(e.innerText.trim());
            });
    }
    // Fallback: všechny odstavce
    if (popisTexty.length === 0) {
        Array.from(document.querySelectorAll('p'))
            .filter(e => e.innerText && e.innerText.length > 40 && !videnePrvky.has(e))
            .forEach(e => {
                videnePrvky.add(e);
                popisTexty.push(e.innerText.trim());
            });
    }
    if (popisTexty.length > 0) {
        casti.push('=== POPIS INZERÁTU ===\\n' + popisTexty.join('\\n'));
    }

    // --- ČÁST 2: Parametrové tabulky (PENB, patro, materiál atd.) ---
    const paramSelektory = [
        '[class*="param"]',
        '[class*="Param"]',
        '[class*="parameter"]',
        '[class*="Parameter"]',
        '[class*="detail-item"]',
        '[class*="DetailItem"]',
        '[class*="property-item"]',
        '[class*="PropertyItem"]',
        '[class*="property-feature"]',
        'table',
        'dl',
        'ul[class*="feature"]',
        'ul[class*="list"]',
        '[class*="info-list"]',
        '[class*="attributes"]'
    ];
    const paramTexty = [];
    const klicovaSlova = /PENB|patro|podlaží|podlaz|materiál|material|stav|výtah|vytah|balkon|terasa|sklep|garáž|garaz|energetick|plocha|dispozice|typ|novostavba|rekonstrukce|cihla|panel|skelet/i;
    for (const sel of paramSelektory) {
        Array.from(document.querySelectorAll(sel))
            .filter(e => {
                if (videnePrvky.has(e)) return false;
                const t = e.innerText || '';
                return t.length > 3 && t.length < 3000 && klicovaSlova.test(t);
            })
            .forEach(e => {
                videnePrvky.add(e);
                const t = e.innerText.trim();
                if (t) paramTexty.push(t);
            });
    }
    if (paramTexty.length > 0) {
        casti.push('=== PARAMETRY A TABULKY ===\\n' + paramTexty.join('\\n---\\n'));
    }

    // --- ČÁST 3: Štítky PENB a energetické třídy ---
    const stitkySelektory = [
        '[class*="energy"]', '[class*="Energy"]',
        '[class*="penb"]',   '[class*="PENB"]',
        '[class*="badge"]',  '[class*="Badge"]',
        '[class*="label"]',  '[class*="Label"]',
        '[class*="tag"]',    '[class*="Tag"]',
        '[class*="certif"]'
    ];
    const stitkyTexty = [];
    for (const sel of stitkySelektory) {
        Array.from(document.querySelectorAll(sel))
            .filter(e => {
                if (videnePrvky.has(e)) return false;
                const t = e.innerText || '';
                return t.length > 0 && t.length < 300;
            })
            .forEach(e => {
                videnePrvky.add(e);
                const t = e.innerText.trim();
                if (t) stitkyTexty.push(t);
            });
    }
    if (stitkyTexty.length > 0) {
        casti.push('=== ŠTÍTKY A TŘÍDY ===\\n' + stitkyTexty.join(' | '));
    }

    const vysledek = casti.join('\\n\\n');
    return vysledek.substring(0, 5000) || 'Bližší informace chybí.';
}
"""

# ==========================================
# 9. STAŽENÍ DETAILU S PLNOU OCHRANOU CHYB
# ==========================================
def stahni_detail_stranky(context, byt_url: str) -> str:
    """
    Otevře stránku detailu inzerátu a vrátí extrahovaný text.
    Jakýkoliv pád (Timeout, Network, JS chyba) je zachycen — vrátí fallback string.
    Volající smyčka nikdy nespadne.
    """
    detail_page = None
    try:
        detail_page = context.new_page()
        detail_page.goto(byt_url, wait_until="domcontentloaded", timeout=20000)

        # Čekání na React render — zkusíme specifické parametrové selektory
        try:
            detail_page.wait_for_selector(
                '[class*="param"], [class*="description"], [class*="Description"], '
                '[class*="detail-item"], [class*="property-title"], table, dl',
                timeout=10000,
                state='attached'
            )
        except PlaywrightTimeoutError:
            # Selektor nenašel → počkáme fixně, React mohl být pomalejší
            detail_page.wait_for_timeout(4000)

        popis = detail_page.evaluate(JS_DETAIL)

        # Druhý pokus pokud první vrátil málo textu
        if not popis or len(popis) < 50:
            detail_page.wait_for_timeout(2500)
            popis = detail_page.evaluate(JS_DETAIL)

        popis = popis or "Bližší informace chybí."
        print(f"    [INFO] Stazeno {len(popis)} znaku z detailu.")
        return popis

    except PlaywrightTimeoutError as e:
        print(f"    [TIMEOUT] Timeout pri nacitani detailu: {type(e).__name__} -- preskakuji.")
        return "Bližší informace chybí."
    except Exception as e:
        print(f"    [CHYBA] Chyba detailu ({type(e).__name__}): {str(e)[:120]} -- preskakuji.")
        return "Bližší informace chybí."
    finally:
        if detail_page:
            try:
                detail_page.close()
            except Exception:
                pass  # Stránka již mohla být zavřena

# ==========================================
# 10. STEALTH HELPER — lidská simulace
# ==========================================
def lidska_pauza(min_s: float = 1.5, max_s: float = 4.0):
    """Náhodná pauza simulující lidské chování."""
    time.sleep(random.uniform(min_s, max_s))

def simuluj_scroll(page, min_scrolls: int = 2, max_scrolls: int = 5):
    """Simuluje postupné scrollování po stránce jako běžný uživatel."""
    pocet = random.randint(min_scrolls, max_scrolls)
    for _ in range(pocet):
        scroll_px = random.randint(300, 800)
        page.mouse.wheel(0, scroll_px)
        time.sleep(random.uniform(0.3, 1.0))

# ==========================================
# 11. HLAVNÍ SCRAPING ENGINE
# ==========================================
def zkontroluj_sreality():
    print(f"\n[START] AI Realitni Radar v4 (Stealth + Slevy + Telegram)")
    print(f"  Headless: {HEADLESS} | Stranky: {MAX_PAGES} | Bytu/stranka: {MAX_BYTU_NA_STRANKU}")
    print(f"  Telegram: {'AKTIVNÍ' if TELEGRAM_ENABLED else 'VYPNUTÝ (chybí token nebo chat_id v .env)'}")
    print(f"  Cenova mapa: {len(CENOVA_MAPA)} lokalit načteno")
    print("=" * 60)

    conn = init_db()
    cursor = conn.cursor()
    celkem_nove = 0
    celkem_zlevnene = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                )
            )
            
            # Blokování zbytečných datových náloží pro zrychlení a šetření paměti
            context.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            page = context.new_page()

            for cislo_stranky in range(1, MAX_PAGES + 1):
                url_stranky = (
                    "https://www.sreality.cz/hledani/prodej/byty"
                    if cislo_stranky == 1
                    else f"https://www.sreality.cz/hledani/prodej/byty?strana={cislo_stranky}"
                )

                print(f"\n[STRANKA {cislo_stranky}/{MAX_PAGES}] Nacitam: {url_stranky}")

                try:
                    page.goto(url_stranky, wait_until="domcontentloaded", timeout=20000)
                except Exception as e:
                    print(f"[CHYBA] Stránka {cislo_stranky} se nenacetla: {e} -- preskakuji.")
                    continue

                page.wait_for_timeout(2000)

                # Souhlas s cookies (pouze na první stránce)
                if cislo_stranky == 1:
                    try:
                        btn = page.locator("button:has-text('Souhlasím')")
                        if btn.is_visible(timeout=4000):
                            btn.click(timeout=3000)
                            page.wait_for_timeout(3000)
                    except Exception:
                        pass

                # Počkáme na načtení cen
                try:
                    page.locator("text=Kč").first.wait_for(timeout=12000)
                    page.wait_for_timeout(1500)
                except Exception as e:
                    page.screenshot(path="debug_sreality.png")
                    print(f"[CHYBA] Stránka {cislo_stranky} nenacetla inzeráty (ulozeno debug_sreality.png) -- preskakuji.")
                    continue

                # Simulace scrollování po stránce
                simuluj_scroll(page)

                print(f"[INFO] Extrahuji byty ze stranky {cislo_stranky}...")
                try:
                    byty = page.evaluate(JS_SEZNAM)
                except Exception as e:
                    print(f"[CHYBA] JS extrakce: {e} -- preskakuji stranku.")
                    continue

                if not byty:
                    print("[INFO] Na strance nebyla nalezena zadna data.")
                    continue

                print(f"[OK] Nalezeno {len(byty)} nabidek, zpracovavam prvnich {MAX_BYTU_NA_STRANKU}...")
                print("-" * 60)

                nove_na_strance = 0

                for i, byt in enumerate(byty[:MAX_BYTU_NA_STRANKU]):
                    # --- Celý blok jednoho bytu je v try/except → pád = continue ---
                    try:
                        byt_id       = byt['id']
                        nazev        = byt['nazev']
                        lokalita_txt = byt['lokalita']
                        cena_inzerat = byt['cena']
                        byt_url      = byt['url']

                        # ==============================
                        # KONTROLA: Známý inzerát → detekce slevy
                        # ==============================
                        cursor.execute("SELECT id, cena FROM nalezene_byty WHERE id=?", (byt_id,))
                        existujici = cursor.fetchone()

                        if existujici:
                            stara_cena = existujici[1]
                            if cena_inzerat < stara_cena:
                                # ZLEVNĚNO! Aktualizujeme databázi
                                print(f"[{i+1}/{MAX_BYTU_NA_STRANKU}] [SLEVA] {nazev[:55]}...")
                                print(f"    Stará cena: {stara_cena:,} Kč → Nová cena: {cena_inzerat:,} Kč".replace(',', ' '))

                                now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cursor.execute(
                                    "UPDATE nalezene_byty SET cena=?, puvodni_cena=?, timestamp=? WHERE id=?",
                                    (cena_inzerat, stara_cena, now_ts, byt_id)
                                )
                                cursor.execute(
                                    "INSERT INTO historie_cen (byt_id, cena, timestamp) VALUES (?, ?, ?)",
                                    (byt_id, cena_inzerat, now_ts)
                                )
                                conn.commit()
                                celkem_zlevnene += 1

                                # Přepočteme odhad pro kontrolu statusu
                                cursor.execute("SELECT odhad_ai FROM nalezene_byty WHERE id=?", (byt_id,))
                                row = cursor.fetchone()
                                if row and row[0] > 0:
                                    odchylka_sleva = ((cena_inzerat - row[0]) / row[0]) * 100
                                    # Telegram: zlevněný inzerát, pokud se dostal na Levnou koupě nebo Férovou nabídku
                                    if odchylka_sleva <= 3:
                                        zprava = formatuj_telegram_zpravu(
                                            "zlevneno", nazev, lokalita_txt,
                                            cena_inzerat, row[0], odchylka_sleva,
                                            byt_url, puvodni_cena=stara_cena
                                        )
                                        posli_telegram(zprava)
                            else:
                                print(f"[{i+1}/{MAX_BYTU_NA_STRANKU}] [SKIP] Znam: {nazev[:55]}...")
                            continue

                        # ==============================
                        # NOVÝ INZERÁT — plné zpracování
                        # ==============================
                        print(f"[{i+1}/{MAX_BYTU_NA_STRANKU}] [NOVA] Zpracovavam: {nazev[:55]}...")

                        # Vylepšený RegEx pro m² — zachytí i "52m²", "52 m2", "52m2"
                        m2_match = re.search(r'(\d+)\s*m[²2]', nazev, re.IGNORECASE)
                        m2_z_nazvu = int(m2_match.group(1)) if m2_match else 0

                        if cena_inzerat == 0:
                            print("    [SKIP] Chybi cena -- preskakuji.")
                            continue

                        # Stáhnout detail (nikdy nespadne — má vlastní ochranu)
                        popis = stahni_detail_stranky(context, byt_url)

                        # Lidská pauza mezi detaily
                        lidska_pauza(1.5, 3.5)

                        # AI analýza
                        data_ai = analyzuj_inzerat_groq(nazev, popis)
                        if not data_ai:
                            print("    [SKIP] AI nevratila data -- preskakuji.")
                            continue

                        # Fallback na metry z AI
                        m2 = m2_z_nazvu
                        if m2 == 0 and data_ai.get('rozloha_m2'):
                            try:
                                m2 = int(data_ai['rozloha_m2'])
                            except (ValueError, TypeError):
                                pass

                        if m2 == 0:
                            print("    [SKIP] Nepodarilo se ziskat metry ani z nazvu ani z AI -- preskakuji.")
                            continue

                        # Výpočet odhadu
                        cena_za_m2_lokalita = ziskej_cenu_za_m2(lokalita_txt)
                        (
                            finalni_cena, uprava_proc, uprava_fix,
                            confidence, chybejici, historie, final_m2_base
                        ) = vypocitej_odhad(m2, data_ai, cena_za_m2_lokalita)

                        odchylka = ((cena_inzerat - finalni_cena) / finalni_cena * 100) if finalni_cena > 0 else 0.0

                        if odchylka < -3:   status = "🟢 Levná koupě"
                        elif odchylka <= 3: status = "🟡 Férová nabídka"
                        else:               status = "🔴 Předraženo"

                        # Formátování pro výpis
                        cena_m2_fmt    = f"{cena_za_m2_lokalita:,}".replace(',', ' ')
                        final_m2_fmt   = f"{int(final_m2_base):,}".replace(',', ' ')
                        mezisoucet_fmt = f"{int(m2 * final_m2_base):,}".replace(',', ' ')
                        uprava_fmt     = f"{uprava_proc:+,}".replace(',', ' ')
                        final_fmt      = f"{finalni_cena:,}".replace(',', ' ')
                        chybejici_str  = ', '.join(str(c) for c in chybejici) if chybejici else 'Všechna data nalezena'
                        upravy_md      = "\n".join(f"* {u}" for u in historie) if historie else "* Žádné úpravy"

                        print(f"    [AI] Duvera: {confidence} % | Odhad: {final_fmt} Kc | {status} ({odchylka:+.1f} %)")

                        zduvodneni_txt = f"""
**🧮 Přesný rozpad výpočtu (Algoritmus):**
* **Spolehlivost dat:** {confidence} % (Chybějící data: {chybejici_str})
* **Základní ceník lokality:** {cena_m2_fmt} Kč/m²
* **Upravená cena za metr** (dle velikosti bytu): **{final_m2_fmt} Kč/m²**
* **Mezisoučet základu** ({m2} m² × {final_m2_fmt} Kč): **{mezisoucet_fmt} Kč**

**Aplikované úpravy ceny (Koeficienty a bonusy):**
{upravy_md}
* **Celkový vliv procentuálních koeficientů:** **{uprava_fmt} Kč**

* **Finální vypočtená cena:** **{final_fmt} Kč**
* **Výsledek:** {status} (Odchylka {odchylka:+.1f} %)

---
> **⚠️ Hlavní investiční riziko:**
> {data_ai.get('investicni_riziko', 'Bez detekovaného rizika.')}
>
> **📈 Investiční potenciál:**
> {data_ai.get('investicni_potencial', 'Bez zjevného potenciálu.')}
"""
                        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cursor.execute(
                            "INSERT INTO nalezene_byty "
                            "(id, nazev, cena, url, odhad_ai, lokalita, plusy, minusy, zduvodneni, timestamp, puvodni_cena) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (byt_id, nazev, cena_inzerat, byt_url, finalni_cena,
                             lokalita_txt, "AI Analýza", chybejici_str, zduvodneni_txt, now_ts, 0)
                        )
                        cursor.execute(
                            "INSERT INTO historie_cen (byt_id, cena, timestamp) VALUES (?, ?, ?)",
                            (byt_id, cena_inzerat, now_ts)
                        )
                        conn.commit()
                        nove_na_strance += 1
                        celkem_nove += 1

                        # Telegram: nová levná koupě
                        if odchylka < -3:
                            zprava = formatuj_telegram_zpravu(
                                "nova", nazev, lokalita_txt,
                                cena_inzerat, finalni_cena, odchylka, byt_url
                            )
                            posli_telegram(zprava)

                        lidska_pauza(1.5, 3.0)
                        print("-" * 55)

                    except Exception as byt_err:
                        # Zachytíme JAKOUKOLIV neočekávanou chybu u jednoho bytu
                        # a pokračujeme dalším -- smyčka nesmi padnout
                        print(f"    [CHYBA] Byt #{i+1}: {type(byt_err).__name__}: {str(byt_err)[:150]}")
                        print("    [INFO] Preskakuji na dalsi inzerat...")
                        continue

                print(f"[OK] Stranka {cislo_stranky} hotova | Nove zaznamy: {nove_na_strance}")

                # Pauza mezi stránkami
                if cislo_stranky < MAX_PAGES:
                    lidska_pauza(3.0, 6.0)

            browser.close()

    except Exception as fatal_err:
        print(f"\n[FATAL] KRITICKA CHYBA SCRAPERU: {type(fatal_err).__name__}: {fatal_err}")
    finally:
        conn.close()
        print(f"\n[KONEC] Hotovo! Novych: {celkem_nove} | Zlevnenych: {celkem_zlevnene}")

# ==========================================
# 12. SPUŠTĚNÍ
# ==========================================
if __name__ == "__main__":
    zkontroluj_sreality()