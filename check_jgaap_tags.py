import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import load_csv_rows

sys.stdout.reconfigure(encoding="utf-8")

rows = load_csv_rows(Path(__file__).parent / "data", "S100XTWY")

keywords = ["NonControlling", "Noncontrolling", "SubscriptionRights", "OwnersEquity",
            "ShareholdersEquity", "CurrentPeriodEndDate", "NetAssets"]

seen = set()
for row in rows:
    element_id, item_name, context_id = row[0], row[1], row[2]
    if any(k in element_id for k in keywords) and context_id in ("CurrentYearInstant", "FilingDateInstant"):
        key = (element_id, context_id)
        if key not in seen:
            seen.add(key)
            print(f"{element_id} | {item_name} | context={context_id} | value={row[-1]}")
