"""ステップ1-D: スコアリングと最終出力。
 - 外国人保有比率が高い順に並べ替え
 - 直近期が営業赤字の企業に警告フラグを立てる

入力: screening/output/screened_with_edinet.csv
出力: screening/output/candidates_final.csv (+ コンソールに要約表)
"""
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).parent / "output"
IN_PATH = OUT_DIR / "screened_with_edinet.csv"
OUT_PATH = OUT_DIR / "candidates_final.csv"


def to_f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    with open(IN_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        op = to_f(r.get("operating_income"))
        if op is None:
            r["_loss_flag"] = "不明"
        elif op < 0:
            r["_loss_flag"] = "★営業赤字"
        else:
            r["_loss_flag"] = ""
        r["_op_oku"] = "" if op is None else f"{op/100_000_000:.1f}"
        fr = to_f(r.get("foreign_ratio_pct"))
        r["_fr"] = fr if fr is not None else -1.0  # 空欄は末尾へ

    rows.sort(key=lambda r: r["_fr"], reverse=True)

    out_cols = ["rank", "code", "company_name", "company_name_en", "market_name",
                "sector33_name", "market_cap_oku", "foreign_ratio_pct",
                "operating_income_oku", "loss_warning", "employees", "segments",
                "filing_date", "edinet_status"]

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_cols)
        w.writeheader()
        for i, r in enumerate(rows, 1):
            w.writerow({
                "rank": i,
                "code": r["code"],
                "company_name": r["company_name"],
                "company_name_en": r["company_name_en"],
                "market_name": r["market_name"],
                "sector33_name": r["sector33_name"],
                "market_cap_oku": r["market_cap_oku"],
                "foreign_ratio_pct": r["foreign_ratio_pct"],
                "operating_income_oku": r["_op_oku"],
                "loss_warning": r["_loss_flag"],
                "employees": r["employees"],
                "segments": r["segments"],
                "filing_date": r["filing_date"],
                "edinet_status": r["edinet_status"],
            })

    n_loss = sum(1 for r in rows if r["_loss_flag"] == "★営業赤字")
    print(f"最終候補: {len(rows)}社  (うち営業赤字警告: {n_loss}社)")
    print(f"保存: {OUT_PATH}\n")

    print("=== 外国人保有比率ランキング(上位20社) ===")
    print(f"{'順':>2} {'コード':<5} {'社名':<20} {'外国人%':>7} {'時価総額億':>8} {'営業利益億':>9} {'警告':<8}")
    for i, r in enumerate(rows[:20], 1):
        name = r["company_name"][:18]
        pad = "　" * (18 - len(name))
        print(f"{i:>2} {r['code']:<5} {name}{pad} {r['foreign_ratio_pct'] or 'N/A':>7} "
              f"{r['market_cap_oku']:>8} {r['_op_oku'] or 'N/A':>9} {r['_loss_flag']:<8}")


if __name__ == "__main__":
    main()
