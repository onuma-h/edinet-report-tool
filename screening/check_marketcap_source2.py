import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

print("=== get_fin_summary (トヨタ 72030) ===")
try:
    df = cli.get_fin_summary(code="72030")
    print("件数:", len(df))
    print("列:", list(df.columns))
    share_cols = [c for c in df.columns if "Share" in c or "Outstanding" in c or "株式" in c or "Cap" in c]
    print("株式数/時価総額っぽい列:", share_cols)
    if len(df):
        last = df.iloc[-1]
        for c in share_cols:
            print(f"  {c} = {last[c]}")
        # 売上・営業利益も確認
        pl_cols = [c for c in df.columns if "Sales" in c or "Revenue" in c or "Operating" in c or "Profit" in c]
        print("損益っぽい列:", pl_cols)
except Exception as e:
    print(f"失敗: {type(e).__name__}: {e}")

print("\n=== get_eq_bars_daily (トヨタ 72030) 株価の列 ===")
try:
    df2 = cli.get_eq_bars_daily(code="72030")
    print("件数:", len(df2))
    print("列:", list(df2.columns))
except Exception as e:
    print(f"失敗: {type(e).__name__}: {e}")
