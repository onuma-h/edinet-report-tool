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

sec_code = "7203"
target_years = [2022, 2023, 2024, 2025, 2026]  # 調べたい事業年度末を含む年(3月決算を想定)
window_start = (5, 15)  # 5月15日から
window_end = (7, 15)  # 7月15日まで

url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
found = []

for year in target_years:
    start = date(year, *window_start)
    end = date(year, *window_end)
    days = (end - start).days + 1

    for i in range(days):
        target_date = start + timedelta(days=i)
        if target_date > date.today():
            continue
        params = {
            "date": target_date.isoformat(),
            "type": "2",
            "Subscription-Key": api_key,
        }
        response = requests.get(url, params=params)
        data = response.json()

        for doc in data.get("results", []):
            if not (doc.get("secCode") or "").startswith(sec_code):
                continue
            desc = doc.get("docDescription", "")
            if desc.startswith("有価証券報告書") or desc.startswith("半期報告書") or desc.startswith("四半期報告書"):
                found.append(doc)
                print(f"{target_date}: {doc.get('filerName')} - {desc} (docID={doc.get('docID')})")

        time.sleep(1)  # APIへの負荷を抑えるための待機

print(f"\n見つかった書類: {len(found)}件")
