"""確認A: 4970 東洋合成工業の各期CSVで、純利益タグが本当に無いのか、
抽出経路の問題かを切り分ける。キャッシュ済みCSVを直接走査する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_csv_rows, extract_period_end_date, to_number

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).parent.parent / "data"

# 純利益に関係するタグ
NI_TAGS = [
    "jppfs_cor:ProfitLoss",
    "jppfs_cor:ProfitLossAttributableToOwnersOfParent",
    "jpigp_cor:ProfitLossAttributableToOwnersOfParentIFRS",
]


def is_4970(rows):
    for r in rows:
        if r[0] == "jpdei_cor:SecurityCodeDEI" and (r[-1] or "").startswith("4970"):
            return True
    return False


def main():
    hits = []
    for folder in DATA.iterdir():
        if not folder.is_dir():
            continue
        try:
            rows = load_csv_rows(DATA, folder.name)
        except Exception:
            continue
        if not is_4970(rows):
            continue
        ped = extract_period_end_date(rows)
        hits.append((ped, folder.name, rows))

    hits.sort()
    print(f"4970の書類 {len(hits)}件 発見")
    for ped, doc_id, rows in hits:
        print(f"\n=== 期末 {ped}  doc={doc_id} ===")
        found_any = False
        for r in rows:
            if r[0] in NI_TAGS:
                ctx = r[2]
                # 当期の時点/期間のみ（比較用の前期などは除外して見やすく）
                if ctx.startswith("CurrentYearDuration") or ctx.startswith("Prior1YearDuration"):
                    val = to_number(r[-1])
                    oku = "N/A" if val is None else f"{val/1e8:.2f}億"
                    print(f"  {r[0]:<52} ctx={ctx:<45} 値={r[-1]}  ({oku})")
                    found_any = True
        if not found_any:
            print("  → 純利益系タグ(CurrentYear/Prior1Year Duration)が1件も無い")


if __name__ == "__main__":
    main()
