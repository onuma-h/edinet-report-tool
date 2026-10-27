import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

for name in ["get_fin_summary", "get_fin_summary_range", "get_fin_summary_cursor",
             "get_eq_bars_daily", "get_eq_bars_daily_range"]:
    fn = getattr(cli, name, None)
    if fn:
        try:
            print(f"{name}{inspect.signature(fn)}")
        except (ValueError, TypeError):
            print(f"{name}: シグネチャ取得不可")

# get_fin_summary_range を1日だけの範囲で試す(全銘柄まとめて返るか)
print("\n=== get_fin_summary_range(2026-02-13 の1日) ===")
from datetime import datetime
from dateutil import tz
try:
    d = datetime(2026, 2, 13, tzinfo=tz.gettz("Asia/Tokyo"))
    df = cli.get_fin_summary_range(start_dt=d, end_dt=d)
    print("件数:", len(df), " 銘柄数:", df["Code"].nunique() if len(df) else 0)
    print("ShOutFYあり:", "ShOutFY" in df.columns)
except Exception as e:
    print(f"失敗: {type(e).__name__}: {e}")
