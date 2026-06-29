import requests

CURRENT = "1.0.0"
REPO = "Soyibjon1/maktab"
BRANCH = "master"
FILES = ["Talaba.py", "client_agent.py", "updater.py"]

def check_and_update():
    try:
        r = requests.get(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.txt", timeout=5)
        if r.text.strip() == CURRENT:
            return False

        for filename in FILES:
            r = requests.get(f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{filename}", timeout=10)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(r.text)

        return True
    except Exception:
        return False