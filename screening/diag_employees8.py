"""8社の従業員数を現行コード(空値スキップ入り)で再確認。キャッシュ利用・API無し。"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import load_csv_rows
from step1c_extract_edinet import extract_employees

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).parent.parent
DATA = BASE / "data"

with open(BASE / "screening" / "output" / "screened_with_edinet.csv",
          encoding="utf-8-sig", newline="") as f:
    m = {r["code"][:4]: r for r in csv.DictReader(f)}

codes = ["247A", "4970", "6226", "6231", "6485", "6613", "6648", "7711"]
ok = 0
for c in codes:
    info = m.get(c, {})
    doc_id = info.get("edinet_doc_id", "")
    name = info.get("company_name", "?")
    if not doc_id or not (DATA / doc_id).exists():
        print(f"  {c} {name}: キャッシュ無し(スキップ)")
        continue
    rows = load_csv_rows(DATA, doc_id)
    emp, nc = extract_employees(rows)
    if emp is not None:
        ok += 1
        print(f"  {c} {name}: {emp}人 ({'単体' if nc else '連結'})")
    else:
        print(f"  {c} {name}: 依然取得不可")
print(f"  → 8社中 {ok}社が取得できた")
