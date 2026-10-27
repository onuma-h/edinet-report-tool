"""連結→単体フォールバック修正の検証。
 1) 4970 東洋合成工業を再取得し、5期分の自己資本比率・ROE・営業利益率を確認
 2) 従業員欠損だった8社で従業員数が取れるようになったか確認(キャッシュ済み有報を使用)
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import (load_env, find_annual_report_docs, download_and_extract_csv,
                        build_results, load_csv_rows)
from step1c_extract_edinet import extract_employees

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).parent.parent
DATA = BASE / "data"


def pct(x):
    return "N/A" if x is None else f"{x*100:.1f}%"


def oku(x):
    return "N/A" if x is None else f"{x/1e8:.1f}"


def verify_4970():
    env = load_env(BASE / ".env")
    api_key = env["EDINET_API_KEY"]
    print("[1] 4970 東洋合成工業を再取得(5期)...")
    found = find_annual_report_docs("4970", api_key, num_periods=5, sleep_sec=0.5)
    filings = []
    for target_date, doc in found:
        doc_id = doc["docID"]
        download_and_extract_csv(doc_id, api_key, DATA)
        time.sleep(0.3)
        filings.append((doc.get("docDescription", ""),
                        f"{doc.get('periodStart','')} - {doc.get('periodEnd','')}", doc_id))
    results = build_results(DATA, filings)
    doc_ids = [d for _, _, d in filings]
    print(f"  {len(doc_ids)}期取得")
    print(f"  {'期末':<12}{'単体?':<6}{'売上億':>8}{'営利益億':>9}{'営利率':>8}{'純利益億':>9}{'自己資本億':>10}{'自己資本比率':>11}{'ROE':>8}")
    for did in doc_ids:
        r = results[did]
        print(f"  {str(r.get('period_end_date')):<12}"
              f"{('単体' if r.get('is_non_consolidated') else '連結'):<6}"
              f"{oku(r.get('revenue')):>8}{oku(r.get('operating_income')):>9}"
              f"{pct(r.get('operating_margin')):>8}{oku(r.get('net_income')):>9}"
              f"{oku(r.get('self_capital')):>10}{pct(r.get('equity_ratio')):>11}"
              f"{pct(r.get('roe')):>8}  {r.get('roe_flag') or ''}")


def verify_employees():
    print("\n[2] 従業員欠損8社の再抽出(キャッシュ済み有報を使用)...")
    with open(BASE / "screening" / "output" / "screened_with_edinet.csv",
              encoding="utf-8-sig", newline="") as f:
        m = {r["code"][:4]: r for r in csv.DictReader(f)}
    codes = ["247A", "4970", "6226", "6231", "6485", "6613", "6648", "7711"]
    ok = 0
    for c in codes:
        info = m.get(c, {})
        doc_id = info.get("edinet_doc_id", "")
        name = info.get("company_name", "?")
        if not doc_id or not (DATA / doc_id).exists():
            print(f"  {c} {name}: キャッシュ無し(スキップ)")
            continue
        rows = load_csv_rows(DATA, doc_id)
        emp, nc = extract_employees(rows)
        if emp is not None:
            ok += 1
            print(f"  {c} {name}: {emp}人 ({'単体' if nc else '連結'})")
        else:
            print(f"  {c} {name}: 依然取得不可")
    print(f"  → 8社中 {ok}社が取得できるようになった")


if __name__ == "__main__":
    verify_4970()
    verify_employees()
