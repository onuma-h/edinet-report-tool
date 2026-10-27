import sys
import csv
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

base_dir = Path(__file__).parent / "data"

filings = [
    ("第118期", "2021/04-2022/03", "S100OC13"),
    ("第119期", "2022/04-2023/03", "S100QZHY"),
    ("第120期", "2023/04-2024/03", "S100TR7I"),
    ("第121期", "2024/04-2025/03", "S100VWVY"),
    ("第122期", "2025/04-2026/03", "S100Y8NY"),
]

IFRS_TAGS = {
    "total_assets": "jpigp_cor:AssetsIFRS",
    "net_assets": "jpigp_cor:EquityIFRS",
    "operating_income": "jpigp_cor:OperatingProfitLossIFRS",
    "net_income": "jpigp_cor:ProfitLossAttributableToOwnersOfParentIFRS",
    "operating_cf": "jpigp_cor:NetCashProvidedByUsedInOperatingActivitiesIFRS",
    "cash_equivalents": "jpigp_cor:CashAndCashEquivalentsIFRS",
}

JGAAP_TAGS = {
    "total_assets": "jppfs_cor:Assets",
    "net_assets": "jppfs_cor:NetAssets",
    "operating_income": "jppfs_cor:OperatingIncome",
    "net_income": "jppfs_cor:ProfitLossAttributableToOwnersOfParent",
    "operating_cf": "jppfs_cor:NetCashProvidedByUsedInOperatingActivities",
    "cash_equivalents": "jppfs_cor:CashAndCashEquivalents",
}

INSTANT_ITEMS = {"total_assets", "net_assets", "cash_equivalents"}


def load_csv_rows(doc_id):
    folder = base_dir / doc_id / "XBRL_TO_CSV"
    candidates = list(folder.glob("jpcrp*-asr-*.csv"))
    with open(candidates[0], encoding="utf-16", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        return list(reader)[1:]


def to_number(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return None


def extract_revenue(rows):
    best_value = None
    for row in rows:
        element_id, context_id = row[0], row[2]
        if context_id != "CurrentYearDuration" or "Cost" in element_id:
            continue
        if "Revenue" in element_id or "NetSales" in element_id or "Sales" in element_id:
            value = to_number(row[-1])
            if value is not None and (best_value is None or value > best_value):
                best_value = value
    return best_value


def extract_standard(rows, element_id_target, context):
    for row in rows:
        if row[0] == element_id_target and row[2] == context:
            return to_number(row[-1])
    return None


results = {}
for label, period, doc_id in filings:
    rows = load_csv_rows(doc_id)
    is_ifrs = any(r[0] == "jpigp_cor:AssetsIFRS" and r[2] == "CurrentYearInstant" for r in rows)
    tags = IFRS_TAGS if is_ifrs else JGAAP_TAGS

    values = {}
    for key, tag in tags.items():
        context = "CurrentYearInstant" if key in INSTANT_ITEMS else "CurrentYearDuration"
        values[key] = extract_standard(rows, tag, context)
    values["revenue"] = extract_revenue(rows)

    results[doc_id] = {"label": label, "period": period, "standard": "IFRS" if is_ifrs else "JGAAP", **values}


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


doc_ids = [doc_id for _, _, doc_id in filings]
for i, doc_id in enumerate(doc_ids):
    r = results[doc_id]
    r["operating_margin"] = safe_div(r["operating_income"], r["revenue"])
    r["roe"] = safe_div(r["net_income"], r["net_assets"])
    r["equity_ratio"] = safe_div(r["net_assets"], r["total_assets"])
    r["operating_cf_margin"] = safe_div(r["operating_cf"], r["revenue"])

    if i == 0:
        r["revenue_growth"] = None
    else:
        prev_revenue = results[doc_ids[i - 1]]["revenue"]
        r["revenue_growth"] = safe_div(
            (r["revenue"] - prev_revenue) if (r["revenue"] is not None and prev_revenue is not None) else None,
            prev_revenue,
        )


def pct(v):
    return "N/A" if v is None else f"{v * 100:.1f}%"


ratio_labels = [
    ("operating_margin", "営業利益率"),
    ("roe", "ROE"),
    ("equity_ratio", "自己資本比率"),
    ("revenue_growth", "売上成長率"),
    ("operating_cf_margin", "営業CFマージン"),
]

header = f"{'期':<8}" + "".join(f"{jp:>14}" for _, jp in ratio_labels)
print(header)
for label, period, doc_id in filings:
    r = results[doc_id]
    line = f"{label:<8}"
    for key, _ in ratio_labels:
        line += f"{pct(r[key]):>14}"
    print(line)
