"""半導体関連8社の最終選定用: 5期分の財務 + 研究開発費 + 主要顧客 + 決算期 + 会計基準。
既存の edinet_lib を使うだけ(コード変更なし)。結果を JSON で保存する。
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import (load_env, find_annual_report_docs, download_and_extract_csv,
                        build_results, load_csv_rows, extract_text_block, to_number)

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).parent.parent
DATA = BASE / "data"
OUT = Path(__file__).parent / "output" / "deepdive_8companies.json"

CODES = ["6855", "6627", "4970", "6227", "255A", "6521", "6677", "4972"]

RND_TAGS = [
    ("jpcrp_cor:ResearchAndDevelopmentExpensesResearchAndDevelopmentActivities", "CurrentYearDuration"),
    ("jppfs_cor:ResearchAndDevelopmentExpensesSGA", "CurrentYearDuration"),
]


def extract_rnd(rows):
    for tag, ctx in RND_TAGS:
        for r in rows:
            if r[0] == tag and r[2] == ctx:
                v = to_number(r[-1])
                if v is not None:
                    return v
    return None


def main():
    env = load_env(BASE / ".env")
    api_key = env["EDINET_API_KEY"]
    all_out = {}

    for code in CODES:
        print(f"\n===== {code} 検索中 =====")
        found = find_annual_report_docs(code, api_key, num_periods=5, sleep_sec=0.5)
        if not found:
            all_out[code] = {"error": "有報未発見"}
            continue
        filings = []
        for target_date, doc in found:
            doc_id = doc["docID"]
            download_and_extract_csv(doc_id, api_key, DATA)
            time.sleep(0.4)
            ps = doc.get("periodStart") or ""
            pe = doc.get("periodEnd") or str(target_date)
            filings.append((doc.get("docDescription", ""), f"{ps} - {pe}", doc_id))
        results = build_results(DATA, filings)
        doc_ids = [d for _, _, d in filings]

        periods = []
        for did in doc_ids:
            r = results[did]
            periods.append({
                "period_end": r.get("period_end_date"),
                "standard": r.get("standard"),
                "revenue": r.get("revenue"),
                "operating_income": r.get("operating_income"),
                "net_income": r.get("net_income"),
                "self_capital": r.get("self_capital"),
                "operating_margin": r.get("operating_margin"),
                "roe": r.get("roe"),
                "equity_ratio": r.get("equity_ratio"),
                "roe_flag": r.get("roe_flag"),
            })

        latest_rows = load_csv_rows(DATA, doc_ids[-1])
        rnd = extract_rnd(latest_rows)
        latest_rev = results[doc_ids[-1]].get("revenue")
        rnd_ratio = (rnd / latest_rev) if (rnd and latest_rev) else None
        customer = extract_text_block(latest_rows, "jpcrp_cor:InformationForEachOfMainCustomersTextBlock")

        all_out[code] = {
            "periods": periods,
            "latest_standard": periods[-1]["standard"] if periods else None,
            "fiscal_month": (periods[-1]["period_end"] or "")[5:7] if periods and periods[-1]["period_end"] else None,
            "rnd": rnd,
            "rnd_ratio": rnd_ratio,
            "major_customer_text": (customer or "")[:300] if customer else None,
        }
        print(f"  {code}: {len(periods)}期取得, 基準={all_out[code]['latest_standard']}, "
              f"決算月={all_out[code]['fiscal_month']}, R&D比={rnd_ratio}")

    OUT.write_text(json.dumps(all_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {OUT}")


if __name__ == "__main__":
    main()
