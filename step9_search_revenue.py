import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

csv_path = Path(__file__).parent / "data" / "S100Y8NY" / "XBRL_TO_CSV" / "jpcrp030000-asr-001_E02144-000_2026-03-31_01_2026-06-10.csv"

with open(csv_path, encoding="utf-16", newline="") as f:
    reader = csv.reader(f, delimiter="\t")
    rows = list(reader)

seen = {}
for row in rows[1:]:
    element_id, item_name, context_id = row[0], row[1], row[2]
    if "Revenue" in element_id or "売上高" in item_name or "営業収益" in item_name:
        key = (element_id, item_name)
        if key not in seen:
            seen[key] = context_id

for (element_id, item_name), context_id in seen.items():
    print(f"{element_id}: {item_name}  [例context: {context_id}]")

print(f"\n該当項目数: {len(seen)}")
