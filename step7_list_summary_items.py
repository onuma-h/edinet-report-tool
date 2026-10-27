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
    if "SummaryOfBusinessResults" in element_id and "CurrentYearDuration" in context_id or (
        "SummaryOfBusinessResults" in element_id and "CurrentYearInstant" in context_id
    ):
        seen[element_id] = item_name

print(f"項目数: {len(seen)}\n")
for element_id, item_name in seen.items():
    print(f"{element_id}: {item_name}")
