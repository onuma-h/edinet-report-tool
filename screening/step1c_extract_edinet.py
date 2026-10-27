"""ステップ1-C(全件): 51社の有報をEDINETから取得し、外国人株主比率・従業員数・
セグメント名を抽出してCSVに追加する。

効率化: EDINETの日次一覧を直近から1日ずつ走査し、51社全ての最新有報をまとめて探す。

入力: screening/output/filtered_marketcap.csv
出力: screening/output/screened_with_edinet.csv
"""
import csv
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import (load_env, fetch_documents, is_annual_report,
                        download_and_extract_csv, load_csv_rows, to_number)

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
OUT_DIR = Path(__file__).parent / "output"
IN_PATH = OUT_DIR / "filtered_marketcap.csv"
OUT_PATH = OUT_DIR / "screened_with_edinet.csv"

SCAN_DAYS = 400
SLEEP = 0.5

FOREIGN_TAGS = [
    "jpcrp_cor:PercentageOfShareholdingsForeignersOtherThanIndividuals",
    "jpcrp_cor:PercentageOfShareholdingsForeignIndividuals",
]
SEG_PAT = re.compile(r"E\d+-\d+([A-Za-z0-9]+?)ReportableSegments?Member")


def camel_split(s):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)


def extract_foreign_ratio(rows):
    total, found = 0.0, False
    for r in rows:
        if r[0] in FOREIGN_TAGS and "CurrentYear" in r[2]:
            v = to_number(r[-1])
            if v is not None:
                total += v
                found = True
    return total if found else None


def extract_employees(rows):
    """連結の当期従業員数。値が空(「－」等でNone)なら単体(NonConsolidatedMember)に
    フォールバックする。戻り値: (人数 or None, 単体を採用したか bool)"""
    for r in rows:
        if r[0] == "jpcrp_cor:NumberOfEmployees" and r[2] == "CurrentYearInstant":
            v = to_number(r[-1])
            if v is not None:
                return v, False
    for r in rows:
        if r[0] == "jpcrp_cor:NumberOfEmployees" and r[2] == "CurrentYearInstant_NonConsolidatedMember":
            v = to_number(r[-1])
            if v is not None:
                return v, True
    return None, False


def extract_segments(rows):
    segs = []
    for r in rows:
        for m in SEG_PAT.finditer(r[2]):
            t = camel_split(m.group(1))
            if t and t not in segs:
                segs.append(t)
    return segs


def sweep_annual_reports(codes, api_key):
    """直近から日次一覧を走査し、各コードの最新有報 {code4: (date, doc)} を返す。"""
    today = date.today()
    remaining = set(codes)
    found = {}
    for i in range(SCAN_DAYS):
        if not remaining:
            break
        d = today - timedelta(days=i)
        docs = fetch_documents(d, api_key)
        for doc in docs:
            sec = (doc.get("secCode") or "")
            for code4 in list(remaining):
                if sec.startswith(code4) and is_annual_report(doc, code4):
                    found[code4] = (d, doc)
                    remaining.discard(code4)
        time.sleep(SLEEP)
        if i % 20 == 0:
            print(f"  ...直近{i}日走査済み、発見{len(found)}/{len(codes)}社 (残{len(remaining)})")
    print(f"  走査完了: 発見{len(found)}/{len(codes)}社")
    if remaining:
        print(f"  未発見コード: {sorted(remaining)}")
    return found


def main():
    env = load_env(BASE / ".env")
    api_key = env["EDINET_API_KEY"]

    with open(IN_PATH, encoding="utf-8-sig", newline="") as f:
        targets = list(csv.DictReader(f))
    code_map = {t["code"][:4]: t for t in targets}
    codes = list(code_map.keys())
    print(f"対象: {len(codes)}社")

    print("\n[1/2] EDINET日次一覧を走査して有報をまとめて検索...")
    found = sweep_annual_reports(codes, api_key)

    print("\n[2/2] 各社の有報をダウンロードして抽出...")
    out_rows = []
    for code4, t in code_map.items():
        row = dict(t)
        if code4 not in found:
            row.update({"edinet_doc_id": "", "filing_date": "", "foreign_ratio_pct": "",
                        "employees": "", "employees_basis": "", "segments": "",
                        "edinet_status": "有報未発見"})
            out_rows.append(row)
            continue
        fdate, doc = found[code4]
        doc_id = doc["docID"]
        try:
            download_and_extract_csv(doc_id, api_key, DATA_DIR)
            time.sleep(SLEEP)
            rows = load_csv_rows(DATA_DIR, doc_id)
            fr = extract_foreign_ratio(rows)
            emp, emp_nc = extract_employees(rows)
            segs = extract_segments(rows)
            row.update({
                "edinet_doc_id": doc_id,
                "filing_date": fdate.isoformat(),
                "foreign_ratio_pct": "" if fr is None else f"{fr*100:.2f}",
                "employees": "" if emp is None else str(emp),
                "employees_basis": "単体" if emp_nc else ("連結" if emp is not None else ""),
                "segments": " / ".join(segs) if segs else "Single segment",
                "edinet_status": "OK",
            })
            print(f"  {code4} {t['company_name'][:16]}: 外国人{row['foreign_ratio_pct']}% "
                  f"従業員{row['employees']} セグ[{row['segments']}]")
        except Exception as e:
            row.update({"edinet_doc_id": doc_id, "filing_date": fdate.isoformat(),
                        "foreign_ratio_pct": "", "employees": "", "employees_basis": "",
                        "segments": "", "edinet_status": f"ERROR:{type(e).__name__}"})
            print(f"  {code4} {t['company_name'][:16]}: エラー {e}")
        out_rows.append(row)

    fieldnames = list(out_rows[0].keys())
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    ok = sum(1 for r in out_rows if r["edinet_status"] == "OK")
    print(f"\n完了: 抽出成功{ok}/{len(out_rows)}社  保存: {OUT_PATH}")


if __name__ == "__main__":
    main()
