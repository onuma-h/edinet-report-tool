"""確認A 確定: 修正後の build_results をキャッシュ済み5期CSVで直接実行し、
純利益・ROEが全期取得できるか確認する(API呼び出し無し)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import build_results

sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(__file__).parent.parent / "data"

# diag_4970_netincome.py で特定した5期の doc_id(古い順)
FILINGS = [
    ("有報", "FY2022", "S100OFTB"),
    ("有報", "FY2023", "S100R3H5"),
    ("有報", "FY2024", "S100TSTA"),
    ("有報", "FY2025", "S100W2KH"),
    ("有報", "FY2026", "S100YGHH"),
]


def oku(x):
    return "N/A" if x is None else f"{x/1e8:.1f}"


def pct(x):
    return "N/A" if x is None else f"{x*100:.1f}%"


def main():
    results = build_results(DATA, FILINGS)
    print(f"  {'期末':<12}{'単体?':<6}{'営利率':>8}{'純利益億':>9}{'自己資本億':>10}{'自己資本比率':>11}{'ROE':>8}  flag")
    for _, _, did in FILINGS:
        r = results[did]
        print(f"  {str(r.get('period_end_date')):<12}"
              f"{('単体' if r.get('is_non_consolidated') else '連結'):<6}"
              f"{pct(r.get('operating_margin')):>8}{oku(r.get('net_income')):>9}"
              f"{oku(r.get('self_capital')):>10}{pct(r.get('equity_ratio')):>11}"
              f"{pct(r.get('roe')):>8}  {r.get('roe_flag') or ''}")


if __name__ == "__main__":
    main()
