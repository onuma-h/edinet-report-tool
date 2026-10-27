import math
import sys
import time
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 画面表示なしでファイル保存するための設定
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether,
)

from edinet_lib import (
    load_env, find_annual_report_docs, download_and_extract_csv, build_results,
    load_csv_rows, extract_english_name,
)

sys.stdout.reconfigure(encoding="utf-8")

if len(sys.argv) < 2:
    print("使い方: python generate_report.py <証券コード>")
    print("例:     python generate_report.py 7203")
    sys.exit(1)

sec_code = sys.argv[1]
base_dir = Path(__file__).parent

env = load_env(base_dir / ".env")
api_key = env["EDINET_API_KEY"]

print(f"証券コード{sec_code}の直近5期分の有価証券報告書を検索しています(数分かかります)...")
found = find_annual_report_docs(sec_code, api_key, num_periods=5)

if not found:
    print("有価証券報告書が見つかりませんでした。証券コードを確認してください。")
    sys.exit(1)
if len(found) < 5:
    print(f"注意: {len(found)}件しか見つかりませんでした(直近{len(found)}期分でレポートを作成します)。")

japanese_name = found[-1][1].get("filerName", sec_code)
data_dir = base_dir / "data"

filings = []
for target_date, doc in found:
    doc_id = doc["docID"]
    print(f"ダウンロード中: {doc.get('docDescription')} ({doc_id})")
    download_and_extract_csv(doc_id, api_key, data_dir)
    time.sleep(1)
    period_start = doc.get("periodStart") or ""
    period_end = doc.get("periodEnd") or str(target_date)
    filings.append((doc.get("docDescription", ""), f"{period_start} - {period_end}", doc_id))

print("財務データを抽出しています...")
results = build_results(data_dir, filings)

latest_doc_id = filings[-1][2]
company_name = extract_english_name(load_csv_rows(data_dir, latest_doc_id), fallback=japanese_name)

doc_ids = [doc_id for _, _, doc_id in filings]


# ============================================================
# 【4】会計年度表記: XBRLの決算期日から "FY20XX (year ended MMM DD, YYYY)" を作る
# ============================================================
def fy_label_long(doc_id):
    date_str = results[doc_id].get("period_end_date")
    if not date_str:
        return f"FY? ({filings_period_fallback(doc_id)})"
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"FY{d.year} (year ended {d.strftime('%b %d, %Y')})"


def filings_period_fallback(doc_id):
    for _, period, d_id in filings:
        if d_id == doc_id:
            return period
    return "unknown period"


fy_labels = [fy_label_long(doc_id) for doc_id in doc_ids]
# 表の見出し用(2行に折り返す)とグラフの目盛り用(改行区切り)を分けて作る
fy_labels_header_html = [lbl.replace(" (", "<br/>(") for lbl in fy_labels]
fy_labels_chart = [lbl.replace(" (", "\n(") for lbl in fy_labels]


# ============================================================
# 【1】表示単位の自動調整(売上高の最大値を基準に、有効数字3桁を確保)
# ============================================================
def choose_display_unit(results, doc_ids):
    revenue_values = [results[d]["revenue"] for d in doc_ids if results[d]["revenue"] is not None]
    max_revenue = max((abs(v) for v in revenue_values), default=0)
    if max_revenue < 1e11:  # 1000億円未満
        return 1e6, "JPY millions"
    else:  # 1000億円以上(1兆円以上を含む)
        return 1e9, "JPY billions"


unit, unit_label = choose_display_unit(results, doc_ids)


def fmt_jpy(value, min_sigfigs=3):
    """有効数字を最低min_sigfigs桁確保しつつ、選択した単位で金額を整形する"""
    if value is None:
        return "N/A"
    scaled = value / unit
    if scaled == 0:
        return "0"
    abs_val = abs(scaled)
    magnitude = math.floor(math.log10(abs_val))
    decimals = max(0, min_sigfigs - 1 - magnitude)
    return f"{scaled:,.{decimals}f}"


def fmt_pct(value):
    return "N/A" if value is None else f"{value * 100:.1f}%"


# ============================================================
# 【2】ROEの例外処理
# ============================================================
def fmt_roe(r):
    flag = r.get("roe_flag")
    if flag == "negative_equity":
        return "N/A (negative equity)"
    if flag == "small_equity_base":
        return "N/A (equity base too small)"
    return fmt_pct(r["roe"])


# ============================================================
# 異常検知フラグ用: 生の金額を読みやすく整形する簡易ヘルパー
# ============================================================
def fmt_jpy_full(value):
    if value is None:
        return "N/A"
    return f"¥{value:,.0f}"


# ============================================================
# 【5】異常検知フラグ
# ============================================================
def detect_anomalies(results, doc_ids, fy_labels):
    warnings_list = []

    for i, doc_id in enumerate(doc_ids):
        r = results[doc_id]
        oi, ni = r["operating_income"], r["net_income"]
        if oi is not None and ni is not None and oi != 0:
            sign_differs = (oi > 0) != (ni > 0)
            diverges_widely = abs(ni - oi) > 3 * abs(oi)
            if sign_differs or diverges_widely:
                warnings_list.append(
                    f"{fy_labels[i]}: operating income ({fmt_jpy_full(oi)}) and net income ({fmt_jpy_full(ni)}) "
                    f"have opposite signs or diverge by more than 3x operating income."
                )

        ta, rev = r["total_assets"], r["revenue"]
        if ta is not None and rev is not None and rev > 0 and ta > 10 * rev:
            warnings_list.append(
                f"{fy_labels[i]}: total assets ({fmt_jpy_full(ta)}) exceed 10x revenue ({fmt_jpy_full(rev)})."
            )

        if i > 0:
            prev_ta = results[doc_ids[i - 1]]["total_assets"]
            if ta is not None and prev_ta is not None and prev_ta > 0:
                if ta > 2 * prev_ta:
                    warnings_list.append(
                        f"{fy_labels[i]}: total assets more than doubled versus {fy_labels[i - 1]} "
                        f"(from {fmt_jpy_full(prev_ta)} to {fmt_jpy_full(ta)})."
                    )
                elif ta < 0.5 * prev_ta:
                    warnings_list.append(
                        f"{fy_labels[i]}: total assets fell by more than half versus {fy_labels[i - 1]} "
                        f"(from {fmt_jpy_full(prev_ta)} to {fmt_jpy_full(ta)})."
                    )

    return warnings_list


anomaly_warnings = detect_anomalies(results, doc_ids, fy_labels)

# --- グラフ生成 ---
print("グラフを生成しています...")
raw_revenue = [results[d]["revenue"] or 0 for d in doc_ids]
raw_operating_income = [results[d]["operating_income"] or 0 for d in doc_ids]
raw_net_income = [results[d]["net_income"] or 0 for d in doc_ids]

scaled_revenue = [v / unit for v in raw_revenue]
scaled_operating_income = [v / unit for v in raw_operating_income]
scaled_net_income = [v / unit for v in raw_net_income]

# ============================================================
# 【6】グラフ: 最大最小比が20倍を超える場合はパネルを分割する
# ============================================================
all_nonzero = [abs(v) for v in raw_revenue + raw_operating_income + raw_net_income if v != 0]
scale_ratio = (max(all_nonzero) / min(all_nonzero)) if all_nonzero else 1

x = range(len(fy_labels))

if scale_ratio > 20:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=False)

    ax1.bar(x, scaled_revenue, color="#4C72B0", label="Revenue", width=0.5)
    ax1.set_ylabel(unit_label)
    ax1.set_title("Revenue")
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(fy_labels_chart, fontsize=7)

    ax2.plot(x, scaled_operating_income, color="#DD8452", marker="o", linewidth=2, label="Operating Income")
    ax2.plot(x, scaled_net_income, color="#55A868", marker="o", linewidth=2, label="Net Income")
    ax2.set_ylabel(unit_label)
    ax2.set_title("Operating Income & Net Income")
    ax2.legend()
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(fy_labels_chart, fontsize=7)

    fig.suptitle(f"{company_name}: Revenue & Profit Trend")
    fig.tight_layout()
else:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, scaled_revenue, color="#4C72B0", label="Revenue", width=0.5)
    ax.plot(x, scaled_operating_income, color="#DD8452", marker="o", linewidth=2, label="Operating Income")
    ax.plot(x, scaled_net_income, color="#55A868", marker="o", linewidth=2, label="Net Income")
    ax.set_xticks(list(x))
    ax.set_xticklabels(fy_labels_chart, fontsize=7)
    ax.set_ylabel(unit_label)
    ax.set_title(f"{company_name}: Revenue & Profit Trend")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

output_dir = base_dir / "output"
output_dir.mkdir(exist_ok=True)
chart_path = output_dir / f"{sec_code}_chart.png"
fig.savefig(chart_path, dpi=150)

# --- PDF生成 ---
print("PDFレポートを生成しています...")

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=20, spaceAfter=4)
subtitle_style = ParagraphStyle("SubtitleStyle", parent=styles["Normal"], fontSize=11, textColor=colors.grey)
heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8)
note_style = ParagraphStyle("NoteStyle", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceBefore=6)
warning_style = ParagraphStyle("WarningStyle", parent=styles["Normal"], fontSize=9,
                                textColor=colors.HexColor("#B00020"), spaceBefore=4, spaceAfter=4)
header_cell_style = ParagraphStyle("HeaderCell", parent=styles["Normal"], fontSize=7,
                                    textColor=colors.white, alignment=2, leading=9)  # alignment=2 -> RIGHT


# ============================================================
# 【3】ディスクレーマーを無条件で挿入する(分岐から独立させる)
# ============================================================
def build_header_block(company_name, sec_code, is_non_consolidated=False):
    block = [
        Paragraph(company_name, title_style),
        Paragraph(f"Securities Code: {sec_code}  |  Report Date: {date.today().isoformat()}", subtitle_style),
        Paragraph(
            "Source: EDINET (Financial Services Agency of Japan). Figures are derived from XBRL data "
            "in the company's Annual Securities Report (Yukashoken Hokokusho).",
            note_style,
        ),
        Paragraph(
            "<b>Disclaimer:</b> This report presents factual, historical financial data only. "
            "It does not constitute investment advice, a recommendation, or a solicitation to buy, sell, "
            "or hold any securities. It offers no opinion on valuation or investment merit.",
            note_style,
        ),
    ]
    if is_non_consolidated:
        block.append(Paragraph(
            "<b>Note:</b> This company does not prepare consolidated financial statements. "
            "The figures below are non-consolidated (parent-company-only) results "
            "(連結財務諸表非作成・単体).",
            note_style,
        ))
    return block


elements = []
_latest_is_nc = results[doc_ids[-1]].get("is_non_consolidated", False)
elements.extend(build_header_block(company_name, sec_code, is_non_consolidated=_latest_is_nc))
elements.append(Spacer(1, 10 * mm))

# ============================================================
# 【7】出力の完全性チェック
# ============================================================
def check_completeness(results, doc_ids, chart_path):
    issues = []
    for key, label in [
        ("revenue", "Revenue"), ("operating_income", "Operating Income"), ("net_income", "Net Income"),
        ("total_assets", "Total Assets"), ("net_assets", "Net Assets"),
        ("operating_cf", "Operating Cash Flow"), ("cash_equivalents", "Cash & Equivalents"),
    ]:
        if all(results[d][key] is None for d in doc_ids):
            issues.append(f"'{label}' could not be extracted for any of the {len(doc_ids)} periods.")

    if not chart_path.exists() or chart_path.stat().st_size == 0:
        issues.append("The trend chart image was not generated correctly.")

    return issues


completeness_issues = check_completeness(results, doc_ids, chart_path)
if completeness_issues:
    print("\n[警告] 出力の完全性チェックで問題が見つかりました:")
    for issue in completeness_issues:
        print(f"  - {issue}")
    elements.append(Paragraph("<b>Data Completeness Warning</b>", warning_style))
    for issue in completeness_issues:
        elements.append(Paragraph(f"• {issue}", warning_style))
    elements.append(Spacer(1, 4 * mm))

table_style_def = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4057")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("ALIGN", (0, 0), (0, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
])
col_widths = [35 * mm] + [27 * mm] * 5


def header_row(first_cell):
    return [Paragraph(first_cell, header_cell_style)] + [
        Paragraph(lbl, header_cell_style) for lbl in fy_labels_header_html
    ]


elements.append(Paragraph(f"5-Year Financial Summary ({unit_label})", heading_style))
summary_rows = [
    ("revenue", "Revenue"), ("operating_income", "Operating Income"), ("net_income", "Net Income"),
    ("total_assets", "Total Assets"), ("net_assets", "Net Assets"),
    ("operating_cf", "Operating Cash Flow"), ("cash_equivalents", "Cash & Equivalents"),
]
table_data = [header_row("Item")]
for key, label in summary_rows:
    table_data.append([label] + [fmt_jpy(results[d][key]) for d in doc_ids])
summary_table = Table(table_data, hAlign="LEFT", colWidths=col_widths)
summary_table.setStyle(table_style_def)
elements.append(summary_table)

elements.append(Paragraph("Financial Ratios", heading_style))
ratio_data = [header_row("Ratio")]
ratio_data.append(["Operating Margin"] + [fmt_pct(results[d]["operating_margin"]) for d in doc_ids])
ratio_data.append(["ROE"] + [fmt_roe(results[d]) for d in doc_ids])
ratio_data.append(["Equity Ratio"] + [fmt_pct(results[d]["equity_ratio"]) for d in doc_ids])
ratio_data.append(["Revenue Growth"] + [fmt_pct(results[d]["revenue_growth"]) for d in doc_ids])
ratio_data.append(["Operating CF Margin"] + [fmt_pct(results[d]["operating_cf_margin"]) for d in doc_ids])
ratio_table = Table(ratio_data, hAlign="LEFT", colWidths=col_widths)
ratio_table.setStyle(table_style_def)
elements.append(ratio_table)
elements.append(Paragraph(
    "Note: Equity Ratio and ROE use Self Capital (Net Assets excluding non-controlling interests and "
    "subscription rights to shares) as the equity base. ROE is shown as N/A when Self Capital is zero or "
    "negative, or when the equity ratio is below 5% (the ratio becomes statistically unstable in that range). "
    "Revenue is identified heuristically and should be cross-checked against the source filing.",
    note_style,
))

elements.append(Paragraph("Revenue & Profit Trend", heading_style))
chart_display_height = 93.75 * mm if scale_ratio <= 20 else 150 * mm
elements.append(Image(str(chart_path), width=150 * mm, height=chart_display_height))


def build_financial_analysis_bullets(results, doc_ids, fy_labels):
    first_id, last_id = doc_ids[0], doc_ids[-1]
    first_fy, last_fy = fy_labels[0], fy_labels[-1]
    bullets = []

    def trend_bullet(key, label):
        first, last = results[first_id][key], results[last_id][key]
        if not first or not last:
            return None
        change_pct = (last - first) / first * 100
        direction = "increased" if change_pct >= 0 else "decreased"
        return (
            f"{label} {direction} from {fmt_jpy(first)} to {fmt_jpy(last)} ({unit_label}) "
            f"between {first_fy} and {last_fy}, a change of {change_pct:+.1f}%."
        )

    for key, label in [("revenue", "Revenue"), ("operating_income", "Operating income"), ("net_income", "Net income")]:
        bullet = trend_bullet(key, label)
        if bullet:
            bullets.append(bullet)

    def range_bullet(key, label, doc_id_subset):
        values = [results[d][key] for d in doc_id_subset if results[d][key] is not None]
        if not values:
            return None
        return (
            f"{label} ranged from {min(values) * 100:.1f}% to {max(values) * 100:.1f}% over the period, "
            f"with {fmt_pct(results[last_id][key])} recorded in {last_fy}."
        )

    for key, label in [
        ("operating_margin", "Operating margin"),
        ("equity_ratio", "The equity ratio (Self Capital / Total Assets)"),
        ("operating_cf_margin", "Operating cash flow margin"),
    ]:
        bullet = range_bullet(key, label, doc_ids)
        if bullet:
            bullets.append(bullet)

    roe_valid_ids = [d for d in doc_ids if results[d]["roe_flag"] is None]
    roe_bullet = range_bullet("roe", "Return on equity (ROE)", roe_valid_ids)
    if roe_bullet:
        if len(roe_valid_ids) < len(doc_ids):
            roe_bullet += (
                f" ({len(doc_ids) - len(roe_valid_ids)} of {len(doc_ids)} periods excluded due to "
                f"negative or minimal equity; see Financial Ratios table.)"
            )
        bullets.append(roe_bullet)

    return bullets


elements.append(PageBreak())
elements.append(Paragraph("Analyst Commentary", heading_style))
elements.append(Paragraph(
    "<i>The Financial Analysis section below is generated automatically from the data tables above "
    "and states historical facts only — it is not investment advice or a recommendation. "
    "Business Overview and Risks & Outlook are left blank because they require qualitative information "
    "not present in the numeric XBRL data used by this tool; please complete them yourself.</i>",
    note_style,
))
elements.append(Spacer(1, 3 * mm))

bullet_style = ParagraphStyle("BulletStyle", parent=styles["Normal"], fontSize=9, leading=13,
                               leftIndent=10, bulletIndent=0, spaceAfter=4)

commentary_dir = base_dir / "commentary"
attribution_note = ParagraphStyle("Attribution", parent=note_style, spaceBefore=2)

section_files = {
    "Business Overview": commentary_dir / f"{sec_code}_overview.txt",
    "Risks & Outlook": commentary_dir / f"{sec_code}_risks.txt",
}

for section_title in ["Business Overview", "Financial Analysis", "Risks & Outlook"]:
    section_flowables = [Paragraph(section_title, ParagraphStyle(
        "SectionTitle", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4,
    ))]

    if section_title == "Financial Analysis":
        if anomaly_warnings:
            section_flowables.append(Paragraph(
                "<b>Warning:</b> Standard profitability ratios may not adequately describe this "
                "company's actual condition, based on the following:",
                warning_style,
            ))
            for w in anomaly_warnings:
                section_flowables.append(Paragraph(f"• {w}", warning_style))
            section_flowables.append(Spacer(1, 2 * mm))

        bullets = build_financial_analysis_bullets(results, doc_ids, fy_labels)
        if not bullets:
            section_flowables.append(Paragraph(
                "No financial-analysis statements could be generated because the required data points "
                "were not available for this company.",
                warning_style,
            ))
            print("[警告] Financial Analysisセクションに表示できる内容がありませんでした。")
        for bullet in bullets:
            section_flowables.append(Paragraph(f"• {bullet}", bullet_style))
        section_flowables.append(Spacer(1, 4 * mm))
        elements.extend(section_flowables)
    elif section_files[section_title].exists():
        summary_text = section_files[section_title].read_text(encoding="utf-8").strip()
        section_flowables.append(Paragraph(summary_text, bullet_style))
        section_flowables.append(Paragraph(
            "Source: summarized from the company's own disclosure in its Annual Securities Report "
            "filed with EDINET. This is a summary of the company's statements, not an independent assessment.",
            attribution_note,
        ))
        section_flowables.append(Spacer(1, 4 * mm))
        elements.append(KeepTogether(section_flowables))
    else:
        blank_box = Table([[""]], colWidths=[170 * mm], rowHeights=[35 * mm])
        blank_box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#999999"))]))
        section_flowables.append(blank_box)
        section_flowables.append(Spacer(1, 4 * mm))
        elements.extend(section_flowables)

pdf_path = output_dir / f"{sec_code}_report.pdf"
doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                         leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
doc.build(elements)

print(f"\n完了しました: {pdf_path}")
