import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent.parent / ".env")

import jquantsapi

cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])
df = cli.get_eq_master()

print("件数:", len(df))
print("列名:", list(df.columns))
print(df.head(3).to_string())
