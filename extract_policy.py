import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from edinet_lib import load_csv_rows, extract_text_block

sys.stdout.reconfigure(encoding="utf-8")

rows = load_csv_rows(Path(__file__).parent / "data", "S100Y8NY")

policy = extract_text_block(rows, "jpcrp_cor:BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock")
risks = extract_text_block(rows, "jpcrp_cor:BusinessRisksTextBlock")

print("=== 経営方針、経営環境及び対処すべき課題等 ===")
print(policy)
print("\n\n=== 事業等のリスク ===")
print(risks)
