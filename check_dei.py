import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

p = list(Path("data/S100Y8NY/XBRL_TO_CSV").glob("jpcrp*-asr-*.csv"))[0]
with open(p, encoding="utf-16", newline="") as f:
    rows = list(csv.reader(f, delimiter="\t"))

for row in rows[1:]:
    element_id, item_name = row[0], row[1]
    if "jpdei_cor" in element_id or "English" in element_id or "CompanyName" in element_id or "会社名" in item_name or "英" in item_name:
        print(f"{element_id} | {item_name} | {row[2]} | {row[-1]}")
