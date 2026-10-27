"""ステップ1-B(後半): 時価総額を計算して300億〜2000億円で絞る。

方針(リクエスト節約):
 1) 株価は「直近の営業日1日分」を全銘柄まとめて1回で取得
 2) 発行済株式数は決算開示を日付ごとに走査して取得(窓=config.MARKETCAP_WINDOW_DAYS)
    各社の最新開示だけ残す。ついでに売上高・営業利益も保持(1-C/1-Dで使う)

入力: screening/output/filtered_market_sector.csv
出力: screening/output/filtered_marketcap.csv
"""
import csv
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from edinet_lib import load_env

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).parent / "output"
IN_PATH = OUT_DIR / "filtered_market_sector.csv"
OUT_PATH = OUT_DIR / "filtered_marketcap.csv"

SLEEP = 13  # 無料プラン 5req/分 対策(1回あたり約12秒)


def to_f(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# 無料プランのデータ提供上限日(約12週間前)。この日以前しか取得できない。
START_OFFSET_DAYS = 84


def _safe_get(fn, **kwargs):
    """範囲外(400)などのHTTPエラーは空扱いにしてスキップする。"""
    from requests.exceptions import HTTPError
    try:
        return fn(**kwargs)
    except HTTPError as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code == 400:
            return None
        raise


def find_latest_price_table(cli):
    """データがある直近の営業日を探し、その日の全銘柄株価を返す。"""
    start = date.today() - timedelta(days=START_OFFSET_DAYS)
    for i in range(15):
        d = start - timedelta(days=i)
        ymd = d.strftime("%Y%m%d")
        df = _safe_get(cli.get_eq_bars_daily, date_yyyymmdd=ymd)
        time.sleep(SLEEP)
        if df is not None and len(df) > 0:
            print(f"  株価取得日: {d} ({len(df)}銘柄)")
            return {str(r["Code"]): r for _, r in df.iterrows()}
    return {}


def collect_shares(cli, window_days):
    """決算開示を日付ごとに走査し、銘柄ごとの最新の発行済株式数・売上・営業利益を集める。"""
    latest = {}  # code -> dict
    start = date.today() - timedelta(days=START_OFFSET_DAYS)
    n_days = window_days
    calls = 0
    for i in range(n_days):
        d = start - timedelta(days=i)
        if d.weekday() >= 5:  # 土日は開示なし
            continue
        ymd = d.strftime("%Y%m%d")
        df = _safe_get(cli.get_fin_summary, date_yyyymmdd=ymd)
        calls += 1
        time.sleep(SLEEP)
        if df is not None and len(df):
            for _, r in df.iterrows():
                code = str(r["Code"])
                disc = str(r.get("DiscDate"))
                prev = latest.get(code)
                if prev is None or disc > prev["_disc"]:
                    latest[code] = {
                        "_disc": disc,
                        "sh_out": to_f(r.get("ShOutFY")),
                        "tr_sh": to_f(r.get("TrShFY")),
                        "sales": to_f(r.get("Sales")),
                        "op": to_f(r.get("OP")),
                        "per_type": r.get("CurPerType"),
                    }
        if calls % 10 == 0:
            print(f"  ...{calls}日分(営業日)走査済み、収集{len(latest)}社")
    print(f"  開示走査 完了: APIリクエスト{calls}回、収集{len(latest)}社")
    return latest


def main():
    env = load_env(Path(__file__).parent.parent / ".env")
    import jquantsapi
    cli = jquantsapi.ClientV2(api_key=env["JQUANTS_API_KEY"])

    with open(IN_PATH, encoding="utf-8-sig", newline="") as f:
        targets = list(csv.DictReader(f))
    print(f"対象(市場・業種通過): {len(targets)}社")

    print("\n[1/2] 直近営業日の全銘柄株価を取得中...")
    prices = find_latest_price_table(cli)

    print(f"\n[2/2] 発行済株式数を開示走査で取得中(窓{config.MARKETCAP_WINDOW_DAYS}日)...")
    shares = collect_shares(cli, config.MARKETCAP_WINDOW_DAYS)

    print("\n時価総額を計算・絞り込み中...")
    out_rows = []
    n_priced = n_inband = n_missing = 0
    for t in targets:
        code = str(t["code"])
        price_row = prices.get(code)
        sh = shares.get(code)
        close = to_f(price_row["C"]) if price_row is not None else None
        mcap = None
        shares_out = None
        if sh and close is not None and sh["sh_out"] is not None:
            shares_out = sh["sh_out"] - (sh["tr_sh"] or 0)
            mcap = close * shares_out
            n_priced += 1
        else:
            n_missing += 1

        in_band = (mcap is not None and
                   config.MARKET_CAP_MIN <= mcap <= config.MARKET_CAP_MAX)
        if in_band:
            n_inband += 1

        out_rows.append({
            **t,
            "close_price": "" if close is None else f"{close:.1f}",
            "shares_out": "" if shares_out is None else f"{shares_out:.0f}",
            "market_cap_oku": "" if mcap is None else f"{mcap/100_000_000:.1f}",
            "sales": "" if not sh or sh["sales"] is None else f"{sh['sales']:.0f}",
            "operating_income": "" if not sh or sh["op"] is None else f"{sh['op']:.0f}",
            "period_type": "" if not sh else (sh["per_type"] or ""),
            "in_cap_band": "Y" if in_band else "N",
        })

    # 時価総額バンド内のみを出力(不明・バンド外は除外)
    kept = [r for r in out_rows if r["in_cap_band"] == "Y"]
    fieldnames = list(out_rows[0].keys())
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\n--- 結果 ---")
    print(f"  時価総額を計算できた: {n_priced}社 / 計算不可: {n_missing}社")
    print(f"  時価総額 {config.MARKET_CAP_MIN//100_000_000}億〜{config.MARKET_CAP_MAX//100_000_000}億 に該当: {n_inband}社")
    print(f"  保存: {OUT_PATH}")


if __name__ == "__main__":
    main()
