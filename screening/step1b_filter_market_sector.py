"""ステップ1-B(前半): 市場区分・業種で絞り込む(APIは使わない)。

入力: screening/output/master.csv
出力: screening/output/filtered_market_sector.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).parent / "output"
IN_PATH = OUT_DIR / "master.csv"
OUT_PATH = OUT_DIR / "filtered_market_sector.csv"


def main():
    with open(IN_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"入力: {len(rows)}件")

    kept = []
    for row in rows:
        if row["market_name"] not in config.TARGET_MARKETS:
            continue
        if row["sector33_name"] not in config.TARGET_SECTORS33:
            continue
        kept.append(row)

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(kept)

    print(f"絞り込み後: {len(kept)}件")
    print(f"  対象市場: {config.TARGET_MARKETS}")
    print(f"  対象33業種: {config.TARGET_SECTORS33}")

    # 業種別・市場別の内訳を表示
    print("\n--- 市場別内訳 ---")
    by_mkt = {}
    for r in kept:
        by_mkt[r["market_name"]] = by_mkt.get(r["market_name"], 0) + 1
    for k, v in sorted(by_mkt.items()):
        print(f"  {k}: {v}件")

    print("\n--- 33業種別内訳 ---")
    by_sec = {}
    for r in kept:
        by_sec[r["sector33_name"]] = by_sec.get(r["sector33_name"], 0) + 1
    for k, v in sorted(by_sec.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}件")

    print(f"\n保存しました: {OUT_PATH}")


if __name__ == "__main__":
    main()
