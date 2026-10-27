"""検証シートHTML用のデータ層を構築する。API呼び出しは一切しない(キャッシュ済みCSVのみ使用)。

出力: screening/output/dashboard_data.json

【設計方針】結論・評価は書かない。事実・数値・原文・出典・「要確認の論点(質問形式)」のみ。
"""
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import (load_csv_rows, extract_text_block, extract_period_end_date,
                        to_number, build_results)

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).parent.parent
DATA = BASE / "data"
OUT = Path(__file__).parent / "output"

# 最終対象5社(この順で横断比較表に並ぶ)。最大・最小ハイライトはこの5社内で再計算される。
FOCUS_CODES = ["6855", "6677", "4972", "6627", "4970"]
# 今回は対象外。データは削除せず別ファイル(dashboard_data_reserved.json)に保持。
# 次回「先行投資フェーズ企業」特集で使用予定。
RESERVED_CODES = ["6521", "255A", "6227"]
CODES = FOCUS_CODES + RESERVED_CODES

# セクター区分(比較表・検証シートで会社名の横にタグ表示)
SECTORS = {
    "6855": "Semiconductor (wafer test)",
    "6627": "Semiconductor (wafer test, foundry service)",
    "4970": "Semiconductor Materials (photoresist)",
    "6677": "Display (photomask)",
    "4972": "Display / Electronic Materials",
}

# 原文抜粋タグ
TB_BUSINESS = "jpcrp_cor:DescriptionOfBusinessTextBlock"
TB_RISKS = "jpcrp_cor:BusinessRisksTextBlock"
TB_CUSTOMERS = "jpcrp_cor:InformationForEachOfMainCustomersTextBlock"
# 設備投資(当期の設備投資額)
CAPEX_TAG = "jpcrp_cor:CapitalExpendituresOverviewOfCapitalExpendituresEtc"
# 研究開発費
RND_TAG = "jpcrp_cor:ResearchAndDevelopmentExpensesResearchAndDevelopmentActivities"
# セグメント個別メンバーを捕捉。企業コード(E\d+-\d+)+名称トークンが有るものだけを個別
# セグメントとみなし、名称の無い集計行(CurrentYearDuration_ReportableSegmentsMember)は除外する。
# サフィックスは単数形・複数形の両方があるため Segments? で吸収する。
SEG_CTX_PAT = re.compile(r"^CurrentYearDuration_.*?E\d+-\d+([A-Za-z0-9]+?)ReportableSegments?Member$")


def camel_split(s):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s).strip()


def sec_code_of(rows):
    for r in rows:
        if r[0] == "jpdei_cor:SecurityCodeDEI" and r[-1]:
            return r[-1][:4]
    return None


def build_docid_map():
    """キャッシュ済み全フォルダを走査し、{code4: [(period_end, doc_id), ...]} を返す。"""
    m = {c: [] for c in CODES}
    for folder in DATA.iterdir():
        if not folder.is_dir():
            continue
        try:
            rows = load_csv_rows(DATA, folder.name)
        except Exception:
            continue
        code = sec_code_of(rows)
        if code not in m:
            continue
        ped = extract_period_end_date(rows)
        m[code].append((ped, folder.name))
    for c in m:
        m[c].sort(key=lambda x: (x[0] or ""))
    return m


def _first_val(rows, tag, contexts):
    for ctx in contexts:
        for r in rows:
            if r[0] == tag and r[2] == ctx:
                v = to_number(r[-1])
                if v is not None:
                    return v
    return None


DUR_CTXS = ("CurrentYearDuration", "CurrentYearDuration_NonConsolidatedMember",
            "CurrentYearDuration_CorporateSharedMember")


def extract_capex(rows):
    return _first_val(rows, CAPEX_TAG, DUR_CTXS)


def extract_rnd(rows):
    v = _first_val(rows, RND_TAG, DUR_CTXS)
    if v is not None:
        return v
    # 研究開発費(販管費)タグへフォールバック
    return _first_val(rows, "jppfs_cor:ResearchAndDevelopmentExpensesSGA",
                      ("CurrentYearDuration", "CurrentYearDuration_NonConsolidatedMember"))


def extract_segment_pl(rows):
    """個別セグメントの 売上/営業利益 を返す。[{name, net_sales, operating_income}]"""
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


def load_meta():
    meta = {}
    with open(OUT / "candidates_final.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            meta[r["code"][:4]] = r
    return meta


def gen_questions(c):
    """検証すべき論点を質問形式で生成。評価語は使わない。数値の事実+要確認のみ。"""
    q = []
    periods = c["periods"]
    oms = [(p["period_end"], p["operating_margin"]) for p in periods if p["operating_margin"] is not None]
    if len(oms) >= 2:
        (e0, m0), (e1, m1) = oms[0], oms[-1]
        if abs(m1 - m0) >= 0.03:
            direction = "上昇" if m1 > m0 else "低下"
            q.append(f"営業利益率が {e0[:7]} の {m0*100:.1f}% から {e1[:7]} の {m1*100:.1f}% へ{direction}している。"
                     f"有報のどの記載(数量・価格・構成・費用)が対応するか要確認。")
    # セグメント間の利益率差(事実のみ)
    latest = periods[-1]
    segs = [s for s in latest.get("segments", []) if s.get("margin") is not None]
    if len(segs) >= 2:
        segs_sorted = sorted(segs, key=lambda s: s["margin"])
        lo, hi = segs_sorted[0], segs_sorted[-1]
        if hi["margin"] - lo["margin"] >= 0.05:
            q.append(f"最新期のセグメント別営業利益率に差がある(「{hi['name']}」{hi['margin']*100:.1f}% / "
                     f"「{lo['name']}」{lo['margin']*100:.1f}%)。有報内に差の理由の説明があるか要確認。")
    # ROE 算出不能期
    na = [p["period_end"][:7] for p in periods if p.get("roe") is None]
    if na:
        q.append(f"ROEが算出不能の期がある({', '.join(na)})。純利益・自己資本のどの項目が欠損しているか要確認。")
    # 単体決算
    if c.get("is_non_consolidated"):
        q.append("連結財務諸表を作成しておらず単体決算である。海外投資家向け開示として単体のみである背景を要確認。")
    # 主要顧客への集中
    if c.get("text_customers", {}).get("text"):
        q.append("主要な顧客に関する記載がある(下記原文参照)。特定顧客への売上集中度と、その変動を要確認。")
    # R&D 比率(最新期のみ取得している点の注意)
    if c.get("rnd_ratio") is not None:
        q.append(f"研究開発費比率は最新期 {c['rnd_ratio']*100:.1f}% のみ取得。5期の推移と用途は有報の研究開発活動の状況で要確認。")
    return q[:5]


FIN_KEYS = ("period_end", "revenue", "operating_income", "net_income", "self_capital",
            "operating_margin", "roe", "equity_ratio", "roe_flag", "is_non_consolidated", "standard")


def main():
    meta = load_meta()
    docmap = build_docid_map()

    companies = []
    for code in CODES:
        md = meta.get(code, {})
        docs = docmap.get(code, [])  # [(period_end, doc_id), ...] 古い順
        if not docs:
            print(f"  {code}: キャッシュ無し(スキップ)")
            continue
        latest_ped, latest_doc = docs[-1]
        latest_rows = load_csv_rows(DATA, latest_doc)

        # 修正済み build_results で財務を再計算(単体フォールバック込み)
        filings = [("有報", pe, did) for pe, did in docs]
        fin = build_results(DATA, filings)

        periods = []
        for pe, did in docs:
            r = fin[did]
            rws = load_csv_rows(DATA, did)
            p = {k: r.get(k) for k in FIN_KEYS}
            p["period_end"] = r.get("period_end_date") or pe
            p["doc_id"] = did
            p["capex"] = extract_capex(rws)
            p["segments"] = extract_segment_pl(rws)
            periods.append(p)

        # R&D は最新期から取得し、同期の売上で比率化
        rnd = extract_rnd(latest_rows)
        latest_rev = periods[-1].get("revenue")
        rnd_ratio = (rnd / latest_rev) if (rnd is not None and latest_rev) else None

        src = f"有価証券報告書 {latest_ped}(doc:{latest_doc})"
        company = {
            "code": code,
            "sector": SECTORS.get(code, ""),
            "name_jp": md.get("company_name", ""),
            "name_en": md.get("company_name_en", ""),
            "market": md.get("market_name", ""),
            "sector33": md.get("sector33_name", ""),
            "market_cap_oku": md.get("market_cap_oku", ""),
            "foreign_ratio_pct": md.get("foreign_ratio_pct", ""),
            "employees": md.get("employees", ""),
            "fiscal_month": (latest_ped or "")[5:7],
            "standard": periods[-1].get("standard", ""),
            "segments_names": [s.strip() for s in (md.get("segments", "") or "").split("/") if s.strip()],
            "rnd": rnd,
            "rnd_ratio": rnd_ratio,
            "is_non_consolidated": bool(periods[-1].get("is_non_consolidated")),
            "latest_doc_id": latest_doc,
            "latest_period_end": latest_ped,
            "periods": periods,
            "text_business": {"text": extract_text_block(latest_rows, TB_BUSINESS), "source": f"事業の内容 / {src}"},
            "text_customers": {"text": extract_text_block(latest_rows, TB_CUSTOMERS),
                               "source": f"主要な顧客ごとの情報 / {src}"},
            "text_risks": {"text": extract_text_block(latest_rows, TB_RISKS), "source": f"事業等のリスク / {src}"},
        }
        company["questions"] = gen_questions(company)
        companies.append(company)
        seg_note = f"{len(periods[-1]['segments'])}seg" if periods[-1]["segments"] else "セグ無/単一"
        roe_l = periods[-1].get("roe")
        print(f"  {code} {company['name_jp'][:14]}: 期{len(periods)} "
              f"最新営利率{('%.1f%%'%(periods[-1].get('operating_margin')*100)) if periods[-1].get('operating_margin') is not None else 'N/A'} "
              f"最新ROE{('%.1f%%'%(roe_l*100)) if roe_l is not None else 'N/A'} "
              f"R&D比{('%.1f%%'%(rnd_ratio*100)) if rnd_ratio is not None else 'N/A'} "
              f"capex={periods[-1]['capex']} {seg_note} 論点{len(company['questions'])}")

    by_code = {c["code"]: c for c in companies}
    focus = [by_code[c] for c in FOCUS_CODES if c in by_code]
    reserved = [by_code[c] for c in RESERVED_CODES if c in by_code]
    gen = date.today().isoformat()
    policy = "結論・評価語なし。事実/数値/原文/出典/要確認論点のみ。"
    OUT.mkdir(exist_ok=True)

    with open(OUT / "dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at": gen, "policy": policy, "companies": focus}, f,
                  ensure_ascii=False, indent=2)
    with open(OUT / "dashboard_data_reserved.json", "w", encoding="utf-8") as f:
        json.dump({"generated_at": gen, "policy": policy,
                   "note": "今回の検証シート対象外。次回『先行投資フェーズ企業』特集用に保持。",
                   "companies": reserved}, f, ensure_ascii=False, indent=2)
    print(f"\n保存: dashboard_data.json (対象{len(focus)}社: {[c['code'] for c in focus]})")
    print(f"保存: dashboard_data_reserved.json (保留{len(reserved)}社: {[c['code'] for c in reserved]})")


if __name__ == "__main__":
    main()
