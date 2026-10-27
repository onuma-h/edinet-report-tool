"""ステップ1-A: J-Quants APIから上場銘柄一覧を取得し、CSVに保存する。

出力: screening/output/master.csv
列: code, company_name, company_name_en, market_code, market_name,
    sector33_code, sector33_name, sector17_code, sector17_name
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent.parent
OUT_DIR = Path(__file__).parent / "output"
OUT_PATH = OUT_DIR / "master.csv"

COLUMNS = [
    ("Code", "code"),
    ("CoName", "company_name"),
    ("CoNameEn", "company_name_en"),
    ("Mkt", "market_code"),
    ("MktNm", "market_name"),
    ("S33", "sector33_code"),
    ("S33Nm", "sector33_name"),
    ("S17", "sector17_code"),
    ("S17Nm", "sector17_name"),
]


def main():
    env = load_env(BASE_DIR / ".env")
    api_key = env.get("JQUANTS_API_KEY")
    if not api_key:
        print("エラー: .env に JQUANTS_API_KEY がありません")
        return

    import jquantsapi

    print("J-Quantsから上場銘柄一覧を取得中...")
    cli = jquantsapi.ClientV2(api_key=api_key)
    df = cli.get_eq_master()
    print(f"取得件数: {len(df)}件")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src_cols = [src for src, _ in COLUMNS]
    out_cols = [dst for _, dst in COLUMNS]

    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(out_cols)
        for _, row in df.iterrows():
            writer.writerow([row[c] for c in src_cols])

    print(f"保存しました: {OUT_PATH}")


if __name__ == "__main__":
    main()
