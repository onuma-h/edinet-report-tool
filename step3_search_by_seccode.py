import sys
import time
import requests
from pathlib import Path
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")


def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


env = load_env(Path(__file__).parent / ".env")
api_key = env["EDINET_API_KEY"]

sec_code = "7203"  # トヨタ自動車の証券コード
days_to_check = 90  # 何日さかのぼって調べるか

url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
today = date.today()
found = []

for i in range(days_to_check):
    target_date = today - timedelta(days=i)
    params = {
        "date": target_date.isoformat(),
        "type": "2",
        "Subscription-Key": api_key,
    }
    response = requests.get(url, params=params)
    data = response.json()

    for doc in data.get("results", []):
        if doc.get("secCode") and doc["secCode"].startswith(sec_code):
            found.append(doc)
            print(f"{target_date}: {doc.get('filerName')} - {doc.get('docDescription')} (docID={doc.get('docID')})")

    time.sleep(1)  # APIへの負荷を抑えるための待機

print(f"\n見つかった書類: {len(found)}件")
