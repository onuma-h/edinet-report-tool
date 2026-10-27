"""3社で時価総額計算を試す。
時価総額 = 直近終値 × (期末発行済株式数 ShOutFY - 期末自己株式数 TrShFY)
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")
OUT_DIR = Path(__file__).parent / "output"

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

# 絞り込み済みリストの先頭3社
with open(OUT_DIR / "filtered_market_sector.csv", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))[:3]

for row in rows:
    code4 = row["code"]              # 4桁(master.csvは4桁表記)
    code5 = code4 + "0" if len(code4) == 4 else code4  # J-Quantsは5桁コード
    name = row["company_name"]
    print(f"\n=== {code4} {name} ({row['sector33_name']}) ===")

    # 財務情報から発行済株式数
    fin = cli.get_fin_summary(code=code5)
    if len(fin) == 0:
        print("  財務情報なし")
        continue
    last = fin.iloc[-1]
    sh_out = last.get("ShOutFY")
    tr_sh = last.get("TrShFY")
    print(f"  期末発行済株式数 ShOutFY = {sh_out}")
    print(f"  期末自己株式数   TrShFY  = {tr_sh}")
    print(f"  直近開示 DiscDate={last.get('DiscDate')} 期={last.get('CurPerType')} 売上Sales={last.get('Sales')} 営業利益OP={last.get('OP')}")

    # 株価(直近終値)
    px = cli.get_eq_bars_daily(code=code5)
    if len(px) == 0:
        print("  株価なし")
        continue
    last_px = px.iloc[-1]
    close = last_px.get("C")
    print(f"  直近終値 Date={last_px.get('Date')} C={close}")

    # 時価総額
    try:
        shares = float(sh_out) - float(tr_sh or 0)
        mcap = close * shares
        print(f"  → 発行済(自己株控除後)= {shares:,.0f}株")
        print(f"  → 時価総額 = {mcap/100_000_000:,.1f} 億円")
    except (TypeError, ValueError) as e:
        print(f"  時価総額計算不可: {e}")
