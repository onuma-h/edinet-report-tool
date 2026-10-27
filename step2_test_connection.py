import sys
import requests
from pathlib import Path

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

date = "2026-07-17"  # 確認したい提出日(YYYY-MM-DD)。変更すれば別の日を調べられます

url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
params = {
    "date": date,
    "type": "2",
    "Subscription-Key": api_key,
}

response = requests.get(url, params=params)
data = response.json()

count = data["metadata"]["resultset"]["count"]
print(f"{date} に提出された書類の件数: {count}件")

for doc in data.get("results", [])[:5]:
    print(f"- {doc.get('filerName')}: {doc.get('docDescription')}")
