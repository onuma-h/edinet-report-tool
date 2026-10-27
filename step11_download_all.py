import sys
import time
import zipfile
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

filings = [
    ("第118期", "S100OC13"),
    ("第119期", "S100QZHY"),
    ("第120期", "S100TR7I"),
    ("第121期", "S100VWVY"),
    ("第122期", "S100Y8NY"),
]

url_template = "https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
base_dir = Path(__file__).parent / "data"

for label, doc_id in filings:
    data_dir = base_dir / doc_id
    zip_path = data_dir / "csv.zip"

    if zip_path.exists():
        print(f"{label} ({doc_id}): すでにダウンロード済み、スキップ")
        continue

    data_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(url_template.format(doc_id=doc_id), params={"type": "5", "Subscription-Key": api_key})
    zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(data_dir)

    print(f"{label} ({doc_id}): ダウンロード完了 (status={response.status_code})")
    time.sleep(1)

print("\n全件ダウンロード完了")
