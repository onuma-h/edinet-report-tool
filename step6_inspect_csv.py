import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

csv_path = Path(__file__).parent / "data" / "S100Y8NY" / "XBRL_TO_CSV" / "jpcrp030000-asr-001_E02144-000_2026-03-31_01_2026-06-10.csv"

with open(csv_path, encoding="utf-16", newline="") as f:
    reader = csv.reader(f, delimiter="\t")
    rows = list(reader)

print(f"行数: {len(rows)}")
print("\n--- ヘッダー ---")
print(rows[0])

print("\n--- 先頭5行(ヘッダー除く) ---")
for row in rows[1:6]:
    print(row)

keywords = ["NetSales", "OperatingIncome", "ProfitLoss", "Assets", "NetAssets",
            "CashAndCashEquivalents", "売上高", "営業利益", "当期純利益", "純資産", "総資産"]

print("\n--- キーワードを含む行(最初の30件) ---")
count = 0
for row in rows[1:]:
    if any(k in cell for cell in row for k in keywords):
        print(row)
        count += 1
        if count >= 30:
            break
