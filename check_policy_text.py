import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = list(Path("data/S100Y8NY/XBRL_TO_CSV").glob("jpcrp*-asr-*.csv"))[0]
with open(p, encoding="utf-16", newline="") as f:
    rows = list(csv.reader(f, delimiter="\t"))

keywords = ["経営方針", "経営環境", "対処すべき課題", "事業等のリスク", "MDA", "BusinessPolicy",
            "BusinessRisk", "ManagementPolicy"]

for row in rows[1:]:
    element_id, item_name = row[0], row[1]
    if any(k in element_id or k in item_name for k in keywords):
        value_preview = (row[-1] or "")[:80]
        print(f"{element_id} | {item_name} | context={row[2]} | len={len(row[-1] or '')} | preview={value_preview}")
