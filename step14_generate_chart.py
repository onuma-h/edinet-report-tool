import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 画面表示なしでファイル保存するための設定
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import build_results

sys.stdout.reconfigure(encoding="utf-8")

base_dir = Path(__file__).parent / "data"

filings = [
    ("第118期", "2021/04-2022/03", "S100OC13"),
    ("第119期", "2022/04-2023/03", "S100QZHY"),
    ("第120期", "2023/04-2024/03", "S100TR7I"),
    ("第121期", "2024/04-2025/03", "S100VWVY"),
    ("第122期", "2025/04-2026/03", "S100Y8NY"),
]

results = build_results(base_dir, filings)

fy_labels = []
revenue = []
operating_income = []
net_income = []

for label, period, doc_id in filings:
    r = results[doc_id]
    end_year = period.split("-")[1].split("/")[0]  # "2021/04-2022/03" -> "2022"
    fy_labels.append(f"FY{end_year}")
    revenue.append(r["revenue"] / 1e12)
    operating_income.append(r["operating_income"] / 1e12)
    net_income.append(r["net_income"] / 1e12)

fig, ax = plt.subplots(figsize=(8, 5))

x = range(len(fy_labels))
ax.bar(x, revenue, color="#4C72B0", label="Revenue", width=0.5)
ax.plot(x, operating_income, color="#DD8452", marker="o", linewidth=2, label="Operating Income")
ax.plot(x, net_income, color="#55A868", marker="o", linewidth=2, label="Net Income")

ax.set_xticks(list(x))
ax.set_xticklabels(fy_labels)
ax.set_ylabel("JPY (trillion)")
ax.set_title("Toyota Motor Corporation: Revenue & Profit Trend")
ax.legend()
ax.grid(axis="y", linestyle="--", alpha=0.4)

fig.tight_layout()

output_dir = Path(__file__).parent / "output"
output_dir.mkdir(exist_ok=True)
output_path = output_dir / "chart_revenue_profit.png"
fig.savefig(output_path, dpi=150)

print(f"グラフを保存しました: {output_path}")
