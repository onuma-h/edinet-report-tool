import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)

sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import build_results

sys.stdout.reconfigure(encoding="utf-8")

base_dir = Path(__file__).parent / "data"
company_name = "Toyota Motor Corporation"
ticker = "7203"

filings = [
    ("第118期", "2021/04-2022/03", "S100OC13"),
    ("第119期", "2022/04-2023/03", "S100QZHY"),
    ("第120期", "2023/04-2024/03", "S100TR7I"),
    ("第121期", "2024/04-2025/03", "S100VWVY"),
    ("第122期", "2025/04-2026/03", "S100Y8NY"),
]

results = build_results(base_dir, filings)


def fy_label(period):
    end_year = period.split("-")[1].split("/")[0]
    return f"FY{end_year}"


def fmt_jpy_bn(value):
    if value is None:
        return "N/A"
    return f"{value / 1e9:,.0f}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=20, spaceAfter=4)
subtitle_style = ParagraphStyle("SubtitleStyle", parent=styles["Normal"], fontSize=11, textColor=colors.grey)
heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8)
note_style = ParagraphStyle("NoteStyle", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceBefore=6)
body_style = styles["Normal"]

elements = []

elements.append(Paragraph(company_name, title_style))
elements.append(Paragraph(f"Securities Code: {ticker}  |  Report Date: {date.today().isoformat()}", subtitle_style))
elements.append(Paragraph(
    "Source: EDINET (Financial Services Agency of Japan). Figures are derived from XBRL data "
    "in the company's Annual Securities Report (Yukashoken Hokokusho).",
    note_style,
))
elements.append(Spacer(1, 10 * mm))

# 5-Year Financial Summary
elements.append(Paragraph("5-Year Financial Summary (JPY billions)", heading_style))

summary_rows = [
    ("Fiscal Year", "revenue", "Revenue"),
    (None, "operating_income", "Operating Income"),
    (None, "net_income", "Net Income"),
    (None, "total_assets", "Total Assets"),
    (None, "net_assets", "Net Assets"),
    (None, "operating_cf", "Operating Cash Flow"),
    (None, "cash_equivalents", "Cash & Equivalents"),
]

header_row = ["Item"] + [fy_label(period) for _, period, _ in filings]
table_data = [header_row]
for _, key, jp_label in summary_rows:
    row = [jp_label]
    for _, _, doc_id in filings:
        row.append(fmt_jpy_bn(results[doc_id][key]))
    table_data.append(row)

summary_table = Table(table_data, hAlign="LEFT")
summary_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4057")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("ALIGN", (0, 0), (0, -1), "LEFT"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(summary_table)

# Financial Ratios
elements.append(Paragraph("Financial Ratios", heading_style))

ratio_rows = [
    ("operating_margin", "Operating Margin"),
    ("roe", "ROE"),
    ("equity_ratio", "Equity Ratio"),
    ("revenue_growth", "Revenue Growth"),
    ("operating_cf_margin", "Operating CF Margin"),
]

ratio_header = ["Ratio"] + [fy_label(period) for _, period, _ in filings]
ratio_data = [ratio_header]
for key, jp_label in ratio_rows:
    row = [jp_label]
    for _, _, doc_id in filings:
        row.append(fmt_pct(results[doc_id][key]))
    ratio_data.append(row)

ratio_table = Table(ratio_data, hAlign="LEFT")
ratio_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4057")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("ALIGN", (0, 0), (0, -1), "LEFT"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
elements.append(ratio_table)
elements.append(Paragraph(
    "Note: Equity Ratio is calculated as Total Net Assets (including non-controlling interests) "
    "divided by Total Assets, as a simplified approximation.",
    note_style,
))

# Chart
elements.append(Paragraph("Revenue & Profit Trend", heading_style))
chart_path = Path(__file__).parent / "output" / "chart_revenue_profit.png"
elements.append(Image(str(chart_path), width=150 * mm, height=93.75 * mm))

# Analyst Commentary (blank section for the user to fill in)
elements.append(PageBreak())
elements.append(Paragraph("Analyst Commentary", heading_style))

commentary_sections = [
    "Business Overview",
    "Financial Analysis",
    "Risks & Outlook",
]

for section_title in commentary_sections:
    elements.append(Paragraph(section_title, ParagraphStyle(
        "SectionTitle", parent=styles["Heading3"], spaceBefore=10, spaceAfter=4,
    )))
    blank_box = Table([[""]], colWidths=[170 * mm], rowHeights=[35 * mm])
    blank_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#999999")),
    ]))
    elements.append(blank_box)
    elements.append(Spacer(1, 4 * mm))

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)
pdf_path = output_dir / f"{ticker}_report.pdf"

doc = SimpleDocTemplate(str(pdf_path), pagesize=A4,
                         leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
doc.build(elements)

print(f"PDFレポートを生成しました: {pdf_path}")
