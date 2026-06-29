# 🏠 AI Realitní Radar

Automatizovaný chytrý nástroj pro sledování a oceňování realitního trhu v reálném čase. Pomocí webového scraperu a umělé inteligence (Groq/LLaMA 3.3) prohledává inzeráty, extrahuje z nich klíčová fakta a pomocí vlastní cenové mapy ihned počítá skutečnou hodnotu nemovitosti. Odhalí podhodnocené nabídky ještě předtím, než si jich všimnou ostatní.

![Náhled aplikace](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=for-the-badge&logo=streamlit)
![AI](https://img.shields.io/badge/AI-Groq%20%7C%20LLaMA%203.3-000000?style=for-the-badge&logo=meta)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python)

## 🌟 Hlavní funkce

- **🕵️‍♂️ Skrytý Scraper**: Automaticky stahuje nejnovější inzeráty přímo ze Srealit přes Playwright.
- **🧠 AI Extrakce Dat (JSON Mode)**: Namísto spoléhání se na popisky čte AI celý text a nachází skryté informace. Groq API nově garantuje 100% čistá data díky JSON módu.
- **🧮 Vlastní oceňovací model**: Upravuje cenu za m² podle lokalizace (Cenová mapa), velikosti bytu a konkrétních parametrů.
- **📉 Sledování historie cen**: Scraper automaticky zaznamenává zlevnění bytů a v aplikaci kreslí přehledný čárový graf vývoje ceny v čase.
- **⚡ Extrémní optimalizace**: Playwright plošně blokuje stahování obrázků, videí a reklam, což zaručuje bleskovou rychlost stahování inzerátů.
- **📊 Moderní Dashboard**: Skvěle vypadající tmavé rozhraní postavené na Streamlitu, které vizualizuje TOP 3 Nejlepší nákupy a odchylky v ceně.
- **📱 Telegram Notifikace**: Integrované upozornění, které vás pípne na mobil ve chvíli, kdy AI najde "Férovou nabídku" nebo slevu.

## 🚀 Jak to rozjet (Instalace)

### 1. Požadavky
- Python 3.11 nebo novější
- Prohlížeč (Google Chrome / Edge)
- API klíč od [Groq.com](https://console.groq.com/) (Základní účet je ZDARMA)

### 2. Stažení a Instalace balíčků
Klonujte repozitář nebo stáhněte ZIP a ve složce projektu spusťte terminál:

```bash
# Instalace potřebných knihoven
pip install -r requirements.txt

# Stažení prohlížeče pro scraper
playwright install chromium
```

### 3. Konfigurace (Klíče a Nastavení)
Přejmenujte soubor `.env.example` na `.env` a vložte do něj svůj Groq API klíč.
```env
GROQ_API_KEY=gsk_tvuj_klic_zde
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

V souboru `config.json` si můžete nastavit:
```json
{
    "headless": true, 
    "max_pages": 3,
    "max_bytu_na_stranku": 8
}
```

## 🎮 Použití

Zapnutí hlavního grafického prostředí (Dashboardu):
```bash
streamlit run app.py
```
Aplikace se otevře ve vašem prohlížeči. Odtud můžete scraper spouštět manuálně pomocí tlačítka "Spustit scraper" v postranním panelu.

### Automatický sběrač na pozadí
Pokud chcete aplikaci nechat běžet 24/7 a jen přijímat Telegram notifikace:
```bash
python auto_scraper.py
```

## ⚠️ Upozornění
Tento nástroj používá volně dostupné bezplatné rozhraní umělé inteligence Groq (Llama 3.3). Při velkém objemu dotazů můžete narazit na `Rate Limit` (Omezení počtu slov za den - Error 429). V takovém případě scraper přeskočí nezpracované byty a vyčká na obnovení limitů.

---
*Disclaimer: Tento projekt je vyvíjen pro analytické a vzdělávací účely. Respektujte prosím pravidla webových portálů pro automatizovaný přístup.*
