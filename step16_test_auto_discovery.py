import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import load_env, find_annual_report_docs

sys.stdout.reconfigure(encoding="utf-8")

env = load_env(Path(__file__).parent / ".env")
api_key = env["EDINET_API_KEY"]

sec_code = "7203"  # トヨタ自動車(結果が既知なので検証用)

print(f"証券コード{sec_code}の直近5期分を自動検索します...")
found = find_annual_report_docs(sec_code, api_key, num_periods=5, progress=True)

print(f"\n見つかった件数: {len(found)}")
for target_date, doc in found:
    print(f"{target_date}: {doc.get('filerName')} - {doc.get('docDescription')} (docID={doc.get('docID')})")
