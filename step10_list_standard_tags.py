import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

csv_path = Path(__file__).parent / "data" / "S100Y8NY" / "XBRL_TO_CSV" / "jpcrp030000-asr-001_E02144-000_2026-03-31_01_2026-06-10.csv"

with open(csv_path, encoding="utf-16", newline="") as f:
    reader = csv.reader(f, delimiter="\t")
    rows = list(reader)

keywords = ["Assets", "Equity", "NetAssets", "CashAndCashEquivalents",
            "CashFlowsFromUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivities",
            "ProfitLoss", "NetIncomeLoss"]

seen = {}
for row in rows[1:]:
    element_id, item_name, context_id = row[0], row[1], row[2]
    if not (element_id.startswith("jpigp_cor:") or element_id.startswith("jppfs_cor:")):
        continue
    if any(k in element_id for k in keywords):
        if context_id in ("CurrentYearDuration", "CurrentYearInstant"):
            seen[element_id] = (item_name, context_id)

for element_id, (item_name, context_id) in sorted(seen.items()):
    print(f"{element_id} [{context_id}]: {item_name}")

print(f"\n該当項目数: {len(seen)}")
