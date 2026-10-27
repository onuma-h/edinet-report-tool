"""発行済株式数を一括取得できないか調べる。
候補: get_bulk / get_bulk_list / get_td_files / get_td_bulk / get_fin_summary(date指定)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

# 1) get_fin_summary を date 指定で呼べるか(ある1日の全開示を一括取得)
print("=== get_fin_summary(date=...) を試す ===")
for d in ["2026-02-13", "20260213"]:
    try:
        df = cli.get_fin_summary(date=d)
        print(f"  date={d}: 件数={len(df)}  列にShOutFYあり={'ShOutFY' in df.columns}")
        if len(df):
            print("  例:", df.iloc[0]["Code"], df.iloc[0].get("ShOutFY"))
        break
    except Exception as e:
        print(f"  date={d}: {type(e).__name__}: {e}")

# 2) get_bulk_list / get_bulk が何を返すか(引数不明なのでまず list)
print("\n=== get_bulk_list を試す ===")
try:
    bl = cli.get_bulk_list()
    print("  型:", type(bl))
    print("  中身(先頭):", bl[:5] if hasattr(bl, "__getitem__") else bl)
except Exception as e:
    print(f"  失敗: {type(e).__name__}: {e}")

print("\n=== get_td_files を試す ===")
try:
    import inspect
    print("  シグネチャ:", inspect.signature(cli.get_td_files))
except Exception as e:
    print(f"  署名取得失敗: {e}")
