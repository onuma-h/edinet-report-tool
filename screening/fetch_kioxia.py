"""キオクシアホールディングス(285A)の有報をEDINETから取得し、
dashboard_data.jsonと同じ形状の1社分データを screening/output/kioxia_data.json に保存する。

小型株スクリーニングの対象外(大型株・話題株のスポット企業)なので、
既存の dashboard_data.json / candidates_final.csv には混ぜない。
市場が算出する時価総額・外国人保有比率はJ-Quants/EDINETどちらにも
無い項目もあるため、XBRLから機械的に取れる範囲のみ埋める。
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import (
    load_env, find_annual_report_docs, download_and_extract_csv,
    load_csv_rows, build_results, extract_text_block, extract_period_end_date,
    to_number,
)

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).parent.parent
DATA = BASE / "data"
OUT = Path(__file__).parent / "output"

SEC_CODE = "285A"

TB_BUSINESS = "jpcrp_cor:DescriptionOfBusinessTextBlock"
TB_RISKS = "jpcrp_cor:BusinessRisksTextBlock"
TB_CUSTOMERS = "jpcrp_cor:InformationForEachOfMainCustomersTextBlock"
CAPEX_TAG = "jpcrp_cor:CapitalExpendituresOverviewOfCapitalExpendituresEtc"
RND_TAG = "jpcrp_cor:ResearchAndDevelopmentExpensesResearchAndDevelopmentActivities"
SEG_CTX_PAT = re.compile(r"^CurrentYearDuration_.*?E\d+-\d+([A-Za-z0-9]+?)ReportableSegments?Member$")
FOREIGN_TAGS = [
    "jpcrp_cor:PercentageOfShareholdingsForeignersOtherThanIndividuals",
    "jpcrp_cor:PercentageOfShareholdingsForeignIndividuals",
]

DUR_CTXS = ("CurrentYearDuration", "CurrentYearDuration_NonConsolidatedMember",
            "CurrentYearDuration_CorporateSharedMember")


def camel_split(s):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s).strip()


def _first_val(rows, tag, contexts):
    for ctx in contexts:
        for r in rows:
            if r[0] == tag and r[2] == ctx:
                v = to_number(r[-1])
                if v is not None:
                    return v
    return None


def extract_capex(rows):
    return _first_val(rows, CAPEX_TAG, DUR_CTXS)


def extract_rnd(rows):
    v = _first_val(rows, RND_TAG, DUR_CTXS)
    if v is not None:
        return v
    return _first_val(rows, "jppfs_cor:ResearchAndDevelopmentExpensesSGA",
                      ("CurrentYearDuration", "CurrentYearDuration_NonConsolidatedMember"))


def extract_segment_pl(rows):
    segs = {}
    for r in rows:
        tag, ctx, val = r[0], r[2], r[-1]
        mo = SEG_CTX_PAT.match(ctx)
        if not mo:
            continue
        name = camel_split(mo.group(1))
        if not name:
            continue
        d = segs.setdefault(name, {"name": name, "net_sales": None, "operating_income": None})
        if tag == "jppfs_cor:NetSales" and d["net_sales"] is None:
            d["net_sales"] = to_number(val)
        elif tag == "jppfs_cor:OperatingIncome" and d["operating_income"] is None:
            d["operating_income"] = to_number(val)
    out = [d for d in segs.values() if d["net_sales"] is not None or d["operating_income"] is not None]
    for d in out:
        ns, oi = d["net_sales"], d["operating_income"]
        d["margin"] = (oi / ns) if (ns and oi is not None and ns != 0) else None
    return out


def extract_foreign_ratio(rows):
    total, found = 0.0, False
    for r in rows:
        if r[0] in FOREIGN_TAGS and "CurrentYear" in r[2]:
            v = to_number(r[-1])
            if v is not None:
                total += v
                found = True
    return round(total * 100, 2) if found else None


def extract_employees(rows):
    for r in rows:
        if r[0] == "jpcrp_cor:NumberOfEmployees" and r[2] == "CurrentYearInstant":
            v = to_number(r[-1])
            if v is not None:
                return v
    for r in rows:
        if r[0] == "jpcrp_cor:NumberOfEmployees" and r[2] == "CurrentYearInstant_NonConsolidatedMember":
            v = to_number(r[-1])
            if v is not None:
                return v
    return None


FIN_KEYS = ("period_end", "revenue", "operating_income", "net_income", "self_capital",
            "operating_margin", "roe", "equity_ratio", "roe_flag", "is_non_consolidated", "standard")


def main():
    env = load_env(BASE / ".env")
    api_key = env["EDINET_API_KEY"]

    print(f"[1/3] EDINETで{SEC_CODE}の有報を検索中(直近から日次スキャン)...")
    docs = find_annual_report_docs(SEC_CODE, api_key, num_periods=5, progress=True)
    if not docs:
        print("有報が見つかりませんでした。証券コードを確認してください。")
        return
    print(f"  発見: {len(docs)}期分")
    for fdate, doc in docs:
        print(f"    {fdate.isoformat()}  {doc['docID']}  {doc.get('filerName')}")

    print("\n[2/3] CSVダウンロード・展開...")
    filings = []
    for fdate, doc in docs:
        doc_id = doc["docID"]
        download_and_extract_csv(doc_id, api_key, DATA)
        time.sleep(0.5)
        rows = load_csv_rows(DATA, doc_id)
        ped = extract_period_end_date(rows) or fdate.isoformat()
        filings.append(("有報", ped, doc_id))
    filings.sort(key=lambda x: x[1])

    print("\n[3/3] 財務データ抽出中...")
    fin = build_results(DATA, filings)

    periods = []
    for _, ped, doc_id in filings:
        r = fin[doc_id]
        rows = load_csv_rows(DATA, doc_id)
        p = {k: r.get(k) for k in FIN_KEYS}
        p["period_end"] = r.get("period_end_date") or ped
        p["doc_id"] = doc_id
        p["capex"] = extract_capex(rows)
        p["segments"] = extract_segment_pl(rows)
        periods.append(p)

    latest_doc_id = filings[-1][2]
    latest_rows = load_csv_rows(DATA, latest_doc_id)
    latest_ped = periods[-1]["period_end"]

    rnd = extract_rnd(latest_rows)
    latest_rev = periods[-1].get("revenue")
    rnd_ratio = (rnd / latest_rev) if (rnd is not None and latest_rev) else None
    foreign_ratio_pct = extract_foreign_ratio(latest_rows)
    employees = extract_employees(latest_rows)

    name_en = None
    for r in latest_rows:
        if r[0] == "jpdei_cor:FilerNameInEnglishDEI" and r[-1] and r[-1] != "－":
            name_en = r[-1]
            break

    src = f"有価証券報告書 {latest_ped}(doc:{latest_doc_id})"
    company = {
        "code": SEC_CODE,
        "sector": "Semiconductor (NAND flash memory)",
        "name_jp": "キオクシアホールディングス",
        "name_en": name_en or "Kioxia Holdings Corporation",
        "fiscal_month": latest_ped[5:7],
        "standard": periods[-1].get("standard", ""),
        "rnd": rnd,
        "rnd_ratio": rnd_ratio,
        "foreign_ratio_pct": foreign_ratio_pct,
        "employees": employees,
        "market_cap_oku": None,
        "is_non_consolidated": bool(periods[-1].get("is_non_consolidated")),
        "latest_doc_id": latest_doc_id,
        "latest_period_end": latest_ped,
        "periods": periods,
        "text_business": {"text": extract_text_block(latest_rows, TB_BUSINESS), "source": f"事業の内容 / {src}"},
        "text_customers": {"text": extract_text_block(latest_rows, TB_CUSTOMERS),
                           "source": f"主要な顧客ごとの情報 / {src}"},
        "text_risks": {"text": extract_text_block(latest_rows, TB_RISKS), "source": f"事業等のリスク / {src}"},
    }

    OUT.mkdir(exist_ok=True)
    with open(OUT / "kioxia_data.json", "w", encoding="utf-8") as f:
        json.dump({"company": company}, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {OUT / 'kioxia_data.json'}")
    print(f"期数: {len(periods)}  最新決算期: {latest_ped}  最新doc: {latest_doc_id}")
    print(f"外国人保有比率: {foreign_ratio_pct}  従業員数: {employees}  R&D比率: "
          f"{('%.1f%%' % (rnd_ratio*100)) if rnd_ratio else 'N/A'}")


if __name__ == "__main__":
    main()
