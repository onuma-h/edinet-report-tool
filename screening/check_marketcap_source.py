"""時価総額を計算するための材料(株価・発行済株式数)がJ-Quants無料プランで取れるか調査する。
トヨタ(7203)を例に、財務情報と株価に何の列があるか確認する。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

# get_eq_master 以外に、財務・株価系のメソッドを探す
print("=== ClientV2 の主なメソッド一覧 ===")
methods = [m for m in dir(cli) if m.startswith("get_") and not m.startswith("get_eq_bars")]
for m in methods:
    print(" ", m)

# 財務情報を試す (トヨタ 7203 -> 5桁コード 72030)
print("\n=== 財務情報 (statements) の列 ===")
for meth in ["get_fin_statements", "get_fins_statements", "get_statements"]:
    fn = getattr(cli, meth, None)
    if fn is None:
        continue
    try:
        df = fn(code="72030")
        print(f"[{meth}] 件数={len(df)}")
        print("列:", list(df.columns))
        # 発行済株式数っぽい列を探す
        share_cols = [c for c in df.columns if "Share" in c or "share" in c or "株式" in c]
        print("株式数っぽい列:", share_cols)
        if len(df):
            last = df.iloc[-1]
            for c in share_cols:
                print(f"  {c} = {last[c]}")
        break
    except Exception as e:
        print(f"[{meth}] 失敗: {type(e).__name__}: {e}")
