import sys
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

doc_id = "S100Y8NY"  # トヨタ自動車 第122期 有価証券報告書

url = f"https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"
params = {
    "type": "5",  # CSV(XBRLをタブ区切りに変換したもの)
    "Subscription-Key": api_key,
}

response = requests.get(url, params=params)
print("HTTPステータス:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))

data_dir = Path(__file__).parent / "data" / doc_id
data_dir.mkdir(parents=True, exist_ok=True)
zip_path = data_dir / "csv.zip"
zip_path.write_bytes(response.content)
print(f"保存先: {zip_path}")

with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
    print(f"\nZIP内のファイル数: {len(names)}")
    for n in names[:20]:
        print("-", n)
    z.extractall(data_dir)

print(f"\n展開先フォルダ: {data_dir}")
