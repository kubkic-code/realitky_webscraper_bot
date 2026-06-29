import time
import subprocess
import os
import sys

def main():
    # Save PID so app.py can manage it
    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".auto_scraper.pid")
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
        
    print(f"Auto-scraper spustěn (PID {os.getpid()}). Poběží každých 15 minut.")
    
    python_exe = sys.executable
    scraper_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.py")
    
    # CREATE_NO_WINDOW na Windows pro skryté spouštění scraperu
    creation_flags = 0x08000000 if sys.platform == "win32" else 0
    env_utf8 = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    
    try:
        while True:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Spouštím scraper.py...")
            try:
                subprocess.run(
                    [python_exe, scraper_path],
                    cwd=os.path.dirname(scraper_path),
                    env=env_utf8,
                    creationflags=creation_flags
                )
            except Exception as e:
                print(f"Chyba při spouštění scraperu: {e}")
                
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scraper dokončil běh. Čekám 15 minut...")
            time.sleep(15 * 60) # 15 minutes
    except KeyboardInterrupt:
        print("Auto-scraper byl ukončen.")
    finally:
        # Odstranit PID soubor při ukončení
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except:
                pass

if __name__ == "__main__":
    main()
