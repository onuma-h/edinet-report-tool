import csv
import html
import re
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import requests

DOCS_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
DOC_URL_TEMPLATE = "https://api.edinet-fsa.go.jp/api/v2/documents/{doc_id}"

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

# 自己資本(非支配株主持分・新株予約権を除く) の算出用タグ
IFRS_SELF_CAPITAL_TAG = "jpigp_cor:EquityAttributableToOwnersOfParentIFRS"
JGAAP_SUBSCRIPTION_RIGHTS_TAG = "jppfs_cor:SubscriptionRightsToShares"
JGAAP_NONCONTROLLING_INTERESTS_TAG = "jppfs_cor:NonControllingInterests"

PERIOD_END_DATE_TAG = "jpdei_cor:CurrentPeriodEndDateDEI"

# 単体決算会社の当期純利益。連結専用の「親会社株主に帰属する当期純利益」が無いとき使う。
# (連結会社では親会社株主帰属タグが存在するのでこのフォールバックには入らない)
JGAAP_NET_INCOME_FALLBACK_TAG = "jppfs_cor:ProfitLoss"


def load_env(path):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def load_csv_rows(base_dir, doc_id):
    folder = Path(base_dir) / doc_id / "XBRL_TO_CSV"
    candidates = list(folder.glob("jpcrp*-asr-*.csv"))
    if not candidates:
        raise FileNotFoundError(f"jpcrp CSVが見つかりません: {doc_id}")
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


def extract_text_block(rows, element_id_target):
    """経営方針・事業等のリスクなどのテキストブロックを取り出し、HTMLタグを除いたプレーンテキストにする"""
    for row in rows:
        if row[0] == element_id_target:
            raw = row[-1] or ""
            text = re.sub(r"<[^>]+>", " ", raw)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
    return None


def extract_english_name(rows, fallback):
    for row in rows:
        if row[0] == "jpdei_cor:FilerNameInEnglishDEI" and row[-1] and row[-1] != "－":
            return row[-1]
    return fallback


def extract_revenue(rows, context="CurrentYearDuration"):
    best_value = None
    for row in rows:
        element_id, context_id = row[0], row[2]
        if context_id != context or "Cost" in element_id:
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


def extract_standard_nc(rows, element_id_target, context):
    """連結コンテキストを優先し、値が無ければ単体(_NonConsolidatedMember)を探す。
    戻り値: (値 or None, 単体を採用したか bool)"""
    val = extract_standard(rows, element_id_target, context)
    if val is not None:
        return val, False
    val = extract_standard(rows, element_id_target, context + "_NonConsolidatedMember")
    if val is not None:
        return val, True
    return None, False


def extract_period_end_date(rows):
    """当会計期間終了日(決算期)をXBRLのDEIから取得する。"YYYY-MM-DD"形式の文字列、なければNone"""
    for row in rows:
        if row[0] == PERIOD_END_DATE_TAG and row[-1] and row[-1] != "－":
            return row[-1]
    return None


def safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def fetch_documents(target_date, api_key):
    params = {"date": target_date.isoformat(), "type": "2", "Subscription-Key": api_key}
    response = requests.get(DOCS_URL, params=params)
    data = response.json()
    return data.get("results", []) or []


def is_annual_report(doc, sec_code):
    if not (doc.get("secCode") or "").startswith(sec_code):
        return False
    return (doc.get("docDescription") or "").startswith("有価証券報告書")


def find_annual_report_docs(sec_code, api_key, num_periods=5, initial_scan_days=400,
                             window_days=45, sleep_sec=1, progress=False):
    """証券コードから直近num_periods期分の有価証券報告書を自動で探す。
    戻り値: [(提出日, docの辞書), ...] を古い順に並べたリスト
    """
    today = date.today()
    found = []
    anchor_date = None

    for i in range(initial_scan_days):
        target_date = today - timedelta(days=i)
        docs = fetch_documents(target_date, api_key)
        for doc in docs:
            if is_annual_report(doc, sec_code):
                found.append((target_date, doc))
                anchor_date = target_date
                break
        if progress and i % 20 == 0:
            print(f"  ...直近{i}日分を検索済み")
        time.sleep(sleep_sec)
        if anchor_date:
            break

    if anchor_date is None:
        return found

    for period in range(1, num_periods):
        try:
            center = anchor_date.replace(year=anchor_date.year - period)
        except ValueError:
            center = anchor_date.replace(year=anchor_date.year - period, day=28)
        start = center - timedelta(days=window_days)
        end = center + timedelta(days=window_days)
        days = (end - start).days + 1

        for i in range(days):
            target_date = start + timedelta(days=i)
            if target_date > today:
                continue
            docs = fetch_documents(target_date, api_key)
            matched = False
            for doc in docs:
                if is_annual_report(doc, sec_code):
                    found.append((target_date, doc))
                    matched = True
                    break
            time.sleep(sleep_sec)
            if matched:
                break

    found.sort(key=lambda x: x[0])
    return found[-num_periods:]


def download_and_extract_csv(doc_id, api_key, base_dir):
    """書類取得API(CSV形式)でZIPをダウンロードし、展開する。既にあればスキップ"""
    data_dir = Path(base_dir) / doc_id
    zip_path = data_dir / "csv.zip"
    if zip_path.exists():
        return
    data_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(
        DOC_URL_TEMPLATE.format(doc_id=doc_id),
        params={"type": "5", "Subscription-Key": api_key},
    )
    zip_path.write_bytes(response.content)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(data_dir)


def build_results(base_dir, filings):
    """filings: list of (label, period, doc_id) -> dict[doc_id] = 財務データ辞書"""
    results = {}
    for label, period, doc_id in filings:
        rows = load_csv_rows(base_dir, doc_id)
        is_ifrs = any(r[0] == "jpigp_cor:AssetsIFRS" and r[2] == "CurrentYearInstant" for r in rows)
        tags = IFRS_TAGS if is_ifrs else JGAAP_TAGS

        values = {}
        nc_used = False  # 連結が無く単体(NonConsolidated)にフォールバックしたか
        for key, tag in tags.items():
            context = "CurrentYearInstant" if key in INSTANT_ITEMS else "CurrentYearDuration"
            val, is_nc = extract_standard_nc(rows, tag, context)
            values[key] = val
            if is_nc:
                nc_used = True

        revenue = extract_revenue(rows)
        if revenue is None:
            revenue_nc = extract_revenue(rows, "CurrentYearDuration_NonConsolidatedMember")
            if revenue_nc is not None:
                revenue = revenue_nc
                nc_used = True
        values["revenue"] = revenue

        # 単体決算会社は「親会社株主に帰属する当期純利益」が無いので当期純利益で補う
        if not is_ifrs and values.get("net_income") is None:
            ni_val, ni_nc = extract_standard_nc(rows, JGAAP_NET_INCOME_FALLBACK_TAG, "CurrentYearDuration")
            if ni_val is not None:
                values["net_income"] = ni_val
                if ni_nc:
                    nc_used = True

        # 自己資本(非支配株主持分・新株予約権を除く)を算出する
        if is_ifrs:
            self_capital, sc_nc = extract_standard_nc(rows, IFRS_SELF_CAPITAL_TAG, "CurrentYearInstant")
            self_capital_is_approximate = self_capital is None
            if sc_nc:
                nc_used = True
            if self_capital is None:
                self_capital = values.get("net_assets")
        else:
            net_assets_raw = values.get("net_assets")
            if net_assets_raw is None:
                self_capital = None
                self_capital_is_approximate = True
            else:
                # 純資産と同じ基準(連結 or 単体)で控除項目も取得する
                subscription_rights, _ = extract_standard_nc(
                    rows, JGAAP_SUBSCRIPTION_RIGHTS_TAG, "CurrentYearInstant")
                noncontrolling, _ = extract_standard_nc(
                    rows, JGAAP_NONCONTROLLING_INTERESTS_TAG, "CurrentYearInstant")
                self_capital = net_assets_raw - (subscription_rights or 0) - (noncontrolling or 0)
                self_capital_is_approximate = False
        values["self_capital"] = self_capital
        values["self_capital_is_approximate"] = self_capital_is_approximate
        values["is_non_consolidated"] = nc_used
        values["period_end_date"] = extract_period_end_date(rows)

        results[doc_id] = {"label": label, "period": period, "standard": "IFRS" if is_ifrs else "JGAAP", **values}

    doc_ids = [doc_id for _, _, doc_id in filings]
    for i, doc_id in enumerate(doc_ids):
        r = results[doc_id]
        r["operating_margin"] = safe_div(r["operating_income"], r["revenue"])
        r["roe"] = safe_div(r["net_income"], r["self_capital"])
        r["equity_ratio"] = safe_div(r["self_capital"], r["total_assets"])
        r["operating_cf_margin"] = safe_div(r["operating_cf"], r["revenue"])

        if r["self_capital"] is None or r["self_capital"] <= 0:
            r["roe_flag"] = "negative_equity"
        elif r["equity_ratio"] is not None and r["equity_ratio"] < 0.05:
            r["roe_flag"] = "small_equity_base"
        else:
            r["roe_flag"] = None

        if i == 0:
            r["revenue_growth"] = None
        else:
            prev_revenue = results[doc_ids[i - 1]]["revenue"]
            r["revenue_growth"] = safe_div(
                (r["revenue"] - prev_revenue) if (r["revenue"] is not None and prev_revenue is not None) else None,
                prev_revenue,
            )

    return results
