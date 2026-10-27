"""ステップ1-Cテスト: 3社で外国人株主比率・従業員数・セグメント名を抽出できるか試す。

EDINETから直近の有価証券報告書を探してダウンロードし、抽出する。
"""
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import (load_env, find_annual_report_docs, download_and_extract_csv,
                        load_csv_rows, to_number)

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"

# テスト対象3社(51社リストから、黒字・老舗中心に選定)
TEST_CODES = ["6524", "6855", "6824"]  # 湖北工業 / 日本電子材料 / 新コスモス電機

FOREIGN_TAGS = [
    "jpcrp_cor:PercentageOfShareholdingsForeignersOtherThanIndividuals",
    "jpcrp_cor:PercentageOfShareholdingsForeignIndividuals",
]


def extract_foreign_ratio(rows):
    """外国法人等(個人以外+個人)の所有株式数割合を合計して返す(小数, 例0.19)。"""
    total = 0.0
    found = False
    detail = {}
    for r in rows:
        if r[0] in FOREIGN_TAGS and "CurrentYear" in r[2]:
            v = to_number(r[-1])
            if v is not None:
                total += v
                found = True
                detail[r[1]] = v
    return (total if found else None), detail


def extract_employees(rows):
    """連結の当期従業員数。ctx=CurrentYearInstant(メンバー修飾なし)。"""
    for r in rows:
        if r[0] == "jpcrp_cor:NumberOfEmployees" and r[2] == "CurrentYearInstant":
            return to_number(r[-1])
    return None


def extract_segments(rows):
    """コンテキストIDから ...XxxxReportableSegmentMember を拾い、セグメント識別子を集める。"""
    pat = re.compile(r"[:_]([A-Za-z0-9]+?)ReportableSegmentMember")
    segs = []
    for r in rows:
        for m in pat.finditer(r[2]):
            name = m.group(1)
            if name and name not in segs:
                segs.append(name)
    return segs


def main():
    env = load_env(BASE / ".env")
    api_key = env["EDINET_API_KEY"]

    with open(BASE / "screening" / "output" / "filtered_marketcap.csv",
              encoding="utf-8-sig", newline="") as f:
        by_code = {r["code"][:4]: r for r in csv.DictReader(f)}

    for code4 in TEST_CODES:
        info = by_code.get(code4, {})
        name = info.get("company_name", "?")
        print(f"\n===== {code4} {name} =====")
        print("  EDINETで有報を検索中...")
        docs = find_annual_report_docs(code4, api_key, num_periods=1,
                                       initial_scan_days=400, sleep_sec=0.5)
        if not docs:
            print("  有報が見つかりませんでした")
            continue
        target_date, doc = docs[-1]
        doc_id = doc["docID"]
        print(f"  提出日={target_date} docID={doc_id} desc={doc.get('docDescription')}")
        download_and_extract_csv(doc_id, api_key, DATA_DIR)
        rows = load_csv_rows(DATA_DIR, doc_id)

        fr, detail = extract_foreign_ratio(rows)
        emp = extract_employees(rows)
        segs = extract_segments(rows)

        print(f"  外国人株主比率: {'N/A' if fr is None else f'{fr*100:.2f}%'}")
        for k, v in detail.items():
            print(f"      - {k} = {v}")
        print(f"  従業員数(連結): {emp}")
        print(f"  セグメント: {segs if segs else '(抽出なし=単一セグメント等の可能性)'}")


if __name__ == "__main__":
    main()
