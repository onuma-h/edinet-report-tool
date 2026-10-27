"""dashboard_data.json から検証シートHTMLを生成する。

【設計方針】結論・評価語を書かない。事実・数値・原文・出典・要確認論点のみ。
自由記述欄はブラウザ内(localStorage)に保持し、JSONエクスポート可能。

出力: screening/output/verification_sheet.html
"""
import html
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).parent / "output"
DATA_JSON = OUT / "dashboard_data.json"
HTML_OUT = OUT / "verification_sheet.html"

# レポートのテーマ・タイトル(2026-07-21 テーマ再定義: 半導体関連小型株 → 日本の精密材料産業)
REPORT_TITLE = "Japan's Precision Materials: Where Selection Beats Scale"
REPORT_SUBTITLE = (
    "As semiconductor and display manufacturing shift from scaling "
    "to selection — testing, yield, and material precision — five "
    "under-covered Japanese suppliers sit at the center of that shift."
)

# Executive Summary 下書き。ユーザーが用意した文章をそのまま(改変せず)埋め込む。
# AIによる自動生成の本文ではない。ユーザーが編集する前提の初期値(textarea)。
EXEC_SUMMARY_DRAFT = """Semiconductor and display manufacturing are entering a selection \
phase. As process miniaturization approaches its physical and \
economic limits, competitiveness is shifting from "how small can \
you make it" to "how precisely can you integrate and verify it" — \
particularly in advanced packaging, where known-good-die testing \
becomes critical once multiple chiplets are combined into a single \
package. A similar dynamic applies in display manufacturing, where \
higher pixel density and panel complexity raise the bar for \
photomask and material precision.

Japan's materials and component suppliers have historically \
competed on precision and quality control rather than scale — an \
advantage that is difficult to replicate through capital investment \
alone. The five companies profiled here sit at different points of \
this selection process: two in semiconductor wafer testing, one in \
advanced photoresist materials, and two in display-related precision \
components. None currently carries meaningful English-language \
coverage.

A sixth dynamic worth noting separately: materials that enable \
miniaturization itself — such as advanced photoresists — sit \
upstream of the selection process described above, supporting \
the physical limits that make selection increasingly necessary \
in the first place."""


def esc(s):
    return html.escape(str(s)) if s is not None else ""


def oku(v, nd=1):
    if v is None:
        return "N/A"
    return f"{v/1e8:.{nd}f}"


def pct(v, nd=1):
    if v is None:
        return "N/A"
    return f"{v*100:.{nd}f}%"


def sparkline(values, width=88, height=22, pad=3):
    """None混在の系列を折れ線SVGにする。評価色は使わずcurrentColor。"""
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return '<span class="na">—</span>'
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1
    n = len(values)
    step = (width - 2 * pad) / (n - 1)
    coords = []
    dots = []
    for i, v in enumerate(values):
        if v is None:
            continue
        x = pad + i * step
        y = height - pad - (v - lo) / rng * (height - 2 * pad)
        coords.append(f"{x:.1f},{y:.1f}")
        dots.append((x, y, i == n - 1))
    line = " ".join(coords)
    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{2.2 if last else 1.4}" '
        f'{"" if last else "opacity=\'0.5\'"}/>' for x, y, last in dots)
    return (f'<svg class="spark" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            f'<polyline points="{line}" fill="none" stroke="currentColor" '
            f'stroke-width="1.3"/>{circles}</svg>')


def num_or_na(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def comparison_table(companies):
    # 各列の最大/最小を求める(単一値列)
    def col(key_fn):
        vals = [(c["code"], key_fn(c)) for c in companies]
        nums = [v for _, v in vals if v is not None]
        return (max(nums) if nums else None, min(nums) if nums else None)

    mc_max, mc_min = col(lambda c: num_or_na(c.get("market_cap_oku")))
    fr_max, fr_min = col(lambda c: num_or_na(c.get("foreign_ratio_pct")))
    rd_max, rd_min = col(lambda c: c.get("rnd_ratio"))

    def latest(c, key):
        for p in reversed(c["periods"]):
            if p.get(key) is not None:
                return p[key]
        return None

    om_max, om_min = col(lambda c: latest(c, "operating_margin"))
    roe_max, roe_min = col(lambda c: latest(c, "roe"))

    def mark(v, mx, mn):
        if v is None:
            return ""
        if mx is not None and abs(v - mx) < 1e-12:
            return ' <span class="tag mx">最大</span>'
        if mn is not None and abs(v - mn) < 1e-12:
            return ' <span class="tag mn">最小</span>'
        return ""

    rows = []
    for c in companies:
        oms = [p.get("operating_margin") for p in c["periods"]]
        roes = [p.get("roe") for p in c["periods"]]
        mc = num_or_na(c.get("market_cap_oku"))
        fr = num_or_na(c.get("foreign_ratio_pct"))
        rd = c.get("rnd_ratio")
        om_l = num_or_na(oms[-1]) if oms else None
        roe_l = roes[-1] if roes else None
        sector_tag = f"<br><span class='sector-tag'>{esc(c.get('sector', ''))}</span>" if c.get("sector") else ""
        rows.append(f"""      <tr>
        <td class="name"><a href="#c{c['code']}">{esc(c['name_jp'])}</a>{sector_tag}<br><span class="code">{esc(c['code'])} · {esc(c['name_en'])}</span></td>
        <td class="s">{esc(c['sector33'])}</td>
        <td class="c">{esc(c['fiscal_month'])}月期</td>
        <td class="c">{esc(c['standard'])}{'<br><span class="nc">単体</span>' if c.get('is_non_consolidated') else ''}</td>
        <td class="num">{esc(c.get('market_cap_oku') or 'N/A')}{mark(mc, mc_max, mc_min)}</td>
        <td class="num">{esc(c.get('foreign_ratio_pct') or 'N/A')}{mark(fr, fr_max, fr_min)}</td>
        <td class="num spk"><span class="ico">{sparkline(oms)}</span> {pct(om_l)}{mark(om_l, om_max, om_min)}</td>
        <td class="num spk"><span class="ico">{sparkline(roes)}</span> {pct(roe_l)}{mark(roe_l, roe_max, roe_min)}</td>
        <td class="num">{pct(rd)}{mark(rd, rd_max, rd_min)}</td>
      </tr>""")
    return f"""  <table class="cmp">
    <thead><tr>
      <th>会社(コード/英名)</th><th>業種(33)</th><th>決算期</th><th>基準</th>
      <th>時価総額<br>(億円)</th><th>外国人<br>保有%</th>
      <th>営業利益率<br>(5期推移/最新)</th><th>ROE<br>(5期推移/最新)</th><th>R&amp;D比率<br>(最新期)</th>
    </tr></thead>
    <tbody>
{''.join(rows)}
    </tbody>
  </table>"""


def financial_table(c):
    heads = "".join(f"<th>{esc(p['period_end'][:7])}</th>" for p in c["periods"])
    def line(label, fn):
        cells = "".join(f"<td>{fn(p)}</td>" for p in c["periods"])
        return f"<tr><th class='rh'>{label}</th>{cells}</tr>"
    body = "".join([
        line("売上高(億)", lambda p: oku(p.get("revenue"))),
        line("営業利益(億)", lambda p: oku(p.get("operating_income"))),
        line("営業利益率", lambda p: pct(p.get("operating_margin"))),
        line("純利益(億)", lambda p: oku(p.get("net_income"))),
        line("自己資本(億)", lambda p: oku(p.get("self_capital"))),
        line("自己資本比率", lambda p: pct(p.get("equity_ratio"))),
        line("ROE", lambda p: pct(p.get("roe")) + (
            f" <span class='flag'>{esc(p.get('roe_flag'))}</span>" if p.get("roe_flag") else "")),
        line("設備投資(億)", lambda p: oku(p.get("capex"))),
    ])
    return f"<table class='fin'><thead><tr><th></th>{heads}</tr></thead><tbody>{body}</tbody></table>"


def segment_table(c):
    # 全期のセグメント名を統合
    names = []
    for p in c["periods"]:
        for s in p.get("segments", []):
            if s["name"] not in names:
                names.append(s["name"])
    if not names:
        return "<p class='muted'>報告セグメントは単一、またはセグメント別損益の記載が取得できませんでした。</p>"
    heads = "".join(f"<th>{esc(p['period_end'][:7])}</th>" for p in c["periods"])
    rows = []
    for nm in names:
        cells = []
        for p in c["periods"]:
            seg = next((s for s in p.get("segments", []) if s["name"] == nm), None)
            if seg is None:
                cells.append("<td class='na'>—</td>")
            else:
                cells.append(f"<td>{oku(seg.get('net_sales'))}<br>"
                             f"<span class='mg'>{pct(seg.get('margin'))}</span></td>")
        rows.append(f"<tr><th class='rh'>{esc(nm)}</th>{''.join(cells)}</tr>")
    return (f"<table class='seg'><thead><tr><th>セグメント<br>(上=売上億 / 下=利益率)</th>{heads}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def excerpt_block(title, obj):
    text = (obj or {}).get("text")
    src = (obj or {}).get("source", "")
    badge = "<span class='quote-badge'>&#10077; 原文引用(有報より)</span>"
    if not text:
        return (f"<div class='exc quote'><div class='exc-h'>{esc(title)} {badge} "
                f"<span class='src'>出典: {esc(src)}(記載なし/未取得)</span></div></div>")
    return (f"<div class='exc quote'><div class='exc-h'>{esc(title)} {badge} "
            f"<span class='src'>出典: {esc(src)}</span></div>"
            f"<div class='exc-body'>{esc(text)}</div></div>")


def questions_block(c):
    qs = c.get("questions", [])
    if not qs:
        return ""
    items = "".join(f"<li>{esc(q)}</li>" for q in qs)
    return f"<div class='q'><div class='q-h'>検証すべき論点(要確認・質問形式)</div><ol>{items}</ol></div>"


_DRAFTS = None


def load_drafts():
    """記入欄の初期下書き(notes_drafts.json)を一度だけ読み込む。無ければ空。"""
    global _DRAFTS
    if _DRAFTS is None:
        p = OUT / "notes_drafts.json"
        _DRAFTS = json.load(open(p, encoding="utf-8")) if p.exists() else {}
    return _DRAFTS


def notes_block(c):
    code = c["code"]
    drafts = load_drafts().get(code, {})
    fields = [
        ("technology_position", "Technology position(記入欄)"),
        ("where_margins", "Where the margins come from(記入欄)"),
        ("dependencies_risks", "Key dependencies & risks の補足(記入欄)"),
        ("sector_position", "Sector position — 『選別』の流れの中でどこに位置するか(記入欄)"),
    ]
    boxes = []
    for fid, lbl in fields:
        draft = drafts.get(fid, "")
        tag = " <span class='draft-tag'>下書き入り・編集してください</span>" if draft else ""
        boxes.append(
            f"<label class='nlabel'>{esc(lbl)}{tag}"
            f"<textarea data-code='{code}' data-field='{fid}' "
            f"placeholder='(あなたが記入)'>{esc(draft)}</textarea></label>")
    return f"<div class='notes'>{''.join(boxes)}</div>"


def research_note_link(c):
    """同ディレクトリに調査ノート(<code>_research_notes.md)が有ればリンクを返す。"""
    fn = f"{c['code']}_research_notes.md"
    if not (OUT / fn).exists():
        return ""
    return (f"<div class='note-ref'>&#128196; 調査ノート(有報原文・外部出典・要確認論点): "
            f"<a href='{esc(fn)}' target='_blank'>{esc(fn)}</a></div>")


def company_section(c):
    flag = "<span class='nc-badge'>連結財務諸表非作成(単体)</span>" if c.get("is_non_consolidated") else ""
    sector_tag = f"<span class='sector-tag'>{esc(c.get('sector', ''))}</span>" if c.get("sector") else ""
    meta = (f"英名 {esc(c['name_en'])} ・ {esc(c['market'])} ・ 業種 {esc(c['sector33'])} ・ "
            f"時価総額 {esc(c['market_cap_oku'])}億 ・ 外国人保有 {esc(c['foreign_ratio_pct'])}% ・ "
            f"従業員 {esc(c['employees'])} ・ {esc(c['fiscal_month'])}月期 ・ {esc(c['standard'])}")
    return f"""  <details class="company" id="c{c['code']}">
    <summary><span class="sum-name">{esc(c['name_jp'])}</span>
      <span class="sum-code">{esc(c['code'])}</span>{sector_tag}{flag}</summary>
    <div class="cbody">
      <div class="meta">{meta}</div>
      {research_note_link(c)}

      <h4>5期 財務・設備投資</h4>
      {financial_table(c)}

      <h4>セグメント別損益(5期)</h4>
      {segment_table(c)}

      <h4>原文抜粋(要約なし・出典併記)</h4>
      {excerpt_block("事業の内容", c.get("text_business"))}
      {excerpt_block("主要な顧客ごとの情報", c.get("text_customers"))}
      {excerpt_block("事業等のリスク", c.get("text_risks"))}

      {questions_block(c)}

      <h4>自由記述(ブラウザ内に自動保存 / エクスポート対象)</h4>
      {notes_block(c)}
    </div>
  </details>"""


CSS = """
:root{--fg:#1b1f24;--muted:#6b7480;--line:#dfe3e8;--bg:#fff;--panel:#f7f8fa;--accent:#2f4b6e;--mx:#eef4ff;--mn:#fff4ee;--quote-bg:#fbf6ea;--quote-line:#c39a3f;--quote-fg:#574620;}
@media (prefers-color-scheme:dark){:root{--fg:#e6e9ee;--muted:#98a2b0;--line:#333a44;--bg:#14171c;--panel:#1c2027;--accent:#9db8dd;--mx:#1c2836;--mn:#332420;--quote-bg:#241f13;--quote-line:#9a7a34;--quote-fg:#d8c99a;}}
*{box-sizing:border-box}
body{font-family:"Segoe UI",Meiryo,system-ui,sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:24px;line-height:1.5;font-size:14px}
h1{font-size:20px;margin:0 0 4px}
h4{margin:18px 0 6px;font-size:14px;color:var(--accent)}
.lead{color:var(--muted);max-width:900px;margin:0 0 6px}
.policy{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:12px 0 20px;color:var(--muted);font-size:13px}
.toolbar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);margin-bottom:16px;z-index:5;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
button{font:inherit;padding:7px 14px;border:1px solid var(--accent);background:var(--accent);color:#fff;border-radius:6px;cursor:pointer}
button.ghost{background:transparent;color:var(--accent)}
.hint{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%;margin:4px 0;font-size:13px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}
th{background:var(--panel);font-weight:600}
.cmp td.num,.cmp th{white-space:nowrap}
.cmp .num{text-align:right;font-variant-numeric:tabular-nums}
.cmp .c{text-align:center}
.cmp .name a{color:var(--accent);text-decoration:none;font-weight:600}
.cmp .code{color:var(--muted);font-size:11px}
.cmp .s{font-size:12px;color:var(--muted)}
.spk{white-space:nowrap}.spk .ico{color:var(--accent);vertical-align:middle;margin-right:4px}
.spark circle{fill:currentColor}
.tag{font-size:10px;padding:1px 4px;border-radius:3px;vertical-align:middle}
.tag.mx{background:var(--mx);color:var(--accent)}
.tag.mn{background:var(--mn);color:#a2542c}
.nc,.nc-badge,.flag{color:#a2542c}
.nc-badge{font-size:11px;border:1px solid #a2542c;border-radius:4px;padding:1px 6px;margin-left:8px}
.fin .rh,.seg .rh{background:var(--panel);white-space:nowrap}
.fin td,.seg td{text-align:right;font-variant-numeric:tabular-nums}
.seg .mg{color:var(--muted);font-size:11px}
.flag{font-size:11px}
.na,.muted{color:var(--muted)}
.company{border:1px solid var(--line);border-radius:8px;margin:10px 0;background:var(--bg)}
.company>summary{cursor:pointer;padding:12px 16px;font-size:15px;list-style:none;display:flex;align-items:center;gap:10px}
.company>summary::-webkit-details-marker{display:none}
.company>summary:before{content:"▸";color:var(--muted)}
.company[open]>summary:before{content:"▾"}
.sum-name{font-weight:700}.sum-code{color:var(--muted);font-size:12px}
.cbody{padding:0 16px 16px}
.meta{color:var(--muted);font-size:12px;margin:2px 0 6px}
.note-ref{font-size:12.5px;margin:2px 0 8px;padding:6px 10px;background:var(--panel);border:1px dashed var(--accent);border-radius:6px}
.note-ref a{color:var(--accent);font-weight:600}
.exc{margin:6px 0;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.exc-h{background:var(--panel);padding:6px 10px;font-weight:600;font-size:13px}
.src{font-weight:400;color:var(--muted);font-size:11px;margin-left:6px}
.exc-body{padding:8px 10px;white-space:pre-wrap;max-height:240px;overflow:auto;font-size:12.5px;color:var(--fg)}
/* 原文引用(有報より): 企業自身の言葉。ツール生成部分と暖色背景・金罫線で区別する */
.exc.quote{border-color:var(--quote-line)}
.quote .exc-h{background:var(--quote-bg);color:var(--quote-fg)}
.quote-badge{display:inline-block;font-size:10.5px;font-weight:700;background:var(--quote-line);color:#fff;padding:1px 8px;border-radius:10px;margin:0 6px;vertical-align:middle}
.quote .exc-body{background:var(--quote-bg);border-left:4px solid var(--quote-line)}
.q{margin:12px 0;border-left:3px solid var(--accent);background:var(--panel);padding:8px 14px;border-radius:0 6px 6px 0}
.q-h{font-weight:600;margin-bottom:4px}
.q ol{margin:4px 0 4px 18px;padding:0}.q li{margin:3px 0}
.notes{display:grid;gap:10px;margin-top:6px}
.nlabel{display:flex;flex-direction:column;font-size:12px;color:var(--muted);gap:4px}
.draft-tag{display:inline-block;font-size:10px;font-weight:700;background:var(--accent);color:#fff;padding:1px 6px;border-radius:8px}
textarea{font:inherit;min-height:64px;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);resize:vertical}
.saved{color:#2f7a4d;font-size:12px}
footer{margin-top:28px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:10px}
.report-title{font-size:26px;line-height:1.25;margin:0 0 6px;letter-spacing:-.2px}
.subtitle{font-size:15px;color:var(--muted);max-width:900px;margin:0 0 16px;line-height:1.5}
.sector-tag{display:inline-block;font-size:10.5px;font-weight:600;color:var(--accent);background:var(--mx);border:1px solid var(--accent);border-radius:10px;padding:1px 8px;vertical-align:middle;white-space:nowrap}
.cmp .sector-tag{font-size:10px;margin-left:4px}
.exec{border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:8px;padding:12px 14px;margin:0 0 20px;background:var(--panel)}
.exec-label{font-weight:700;font-size:14px;margin-bottom:6px;color:var(--accent)}
.exec-ta{width:100%;min-height:210px;line-height:1.55;background:var(--bg)}
"""

JS = """
const KEY='verif_sheet_notes_v1';
function load(){let d={};try{d=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
  document.querySelectorAll('textarea').forEach(t=>{const k=t.dataset.code+'|'+t.dataset.field;if(d[k]!=null)t.value=d[k];});}
function save(){const d={};document.querySelectorAll('textarea').forEach(t=>{d[t.dataset.code+'|'+t.dataset.field]=t.value;});
  localStorage.setItem(KEY,JSON.stringify(d));const s=document.getElementById('saved');s.textContent='保存済 '+new Date().toLocaleTimeString();}
function exportJSON(){const out={exported_at:new Date().toISOString(),notes:{}};
  document.querySelectorAll('textarea').forEach(t=>{const c=t.dataset.code;out.notes[c]=out.notes[c]||{};out.notes[c][t.dataset.field]=t.value;});
  if(window.SECTORS){for(const c in window.SECTORS){out.notes[c]=out.notes[c]||{};out.notes[c].sector=window.SECTORS[c];}}
  const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='verification_notes.json';a.click();}
function expandAll(v){document.querySelectorAll('details.company').forEach(d=>d.open=v);}
document.addEventListener('input',e=>{if(e.target.tagName==='TEXTAREA')save();});
window.addEventListener('DOMContentLoaded',load);
"""


def main():
    data = json.load(open(DATA_JSON, encoding="utf-8"))
    companies = data["companies"]
    n = len(companies)
    sections = "\n".join(company_section(c) for c in companies)
    sectors_js = json.dumps({c["code"]: c.get("sector", "") for c in companies}, ensure_ascii=False)
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(REPORT_TITLE)}</title>
<style>{CSS}</style></head><body>
<h1 class="report-title">{esc(REPORT_TITLE)}</h1>
<p class="subtitle">{esc(REPORT_SUBTITLE)}</p>
<p class="lead">検証シート — 対象{n}社。本シートは判断のための材料(事実・数値・原文抜粋・要確認の論点)を並べたものです。</p>
<div class="policy">このツールは結論・評価を書きません。「強み」「優位」等の評価的記述は含みません。
数値の出典はすべて有価証券報告書(XBRL)。特許データは方針により省略し、研究開発は有報の原文・研究開発費比率で代替しています。
外国人保有比率・時価総額の算出時点、会計基準の連結/単体の別に注意してご確認ください。生成日: {esc(data.get('generated_at'))}
<div style="margin-top:8px"><span class="quote-badge">&#10077; 原文引用(有報より)</span>
のバッジ・暖色背景・金色の左罫線が付いた箇所は、<b>企業自身が有価証券報告書に記載した文言をそのまま引用</b>したものです(当ツールが生成・評価した文章ではありません)。</div></div>

<div class="exec">
  <div class="exec-label">Executive Summary <span class="draft-tag">下書き入り・編集してください</span></div>
  <textarea class="exec-ta" data-code="_meta" data-field="exec_summary">{esc(EXEC_SUMMARY_DRAFT)}</textarea>
</div>

<div class="toolbar">
  <button onclick="exportJSON()">ノートをJSONエクスポート</button>
  <button class="ghost" onclick="expandAll(true)">全て展開</button>
  <button class="ghost" onclick="expandAll(false)">全て折りたたむ</button>
  <span id="saved" class="saved"></span>
  <span class="hint">記入欄はブラウザ内(localStorage)に自動保存されます。</span>
</div>

<h4>1. 横断比較(数値のみ・各列の最大/最小をマーク)</h4>
{comparison_table(companies)}

<h4>2. 各社詳細</h4>
{sections}
<script>window.SECTORS={sectors_js};</script>

<footer>出典: EDINET 有価証券報告書 XBRL。数値は円を億円換算(小数1桁)。N/A=当該期のデータが取得できない、または算出不能。
セグメント別営業利益の合計は全社調整(全社費用・消去)前のため全社営業利益と一致しない場合があります。</footer>
<script>{JS}</script>
</body></html>"""
    HTML_OUT.write_text(doc, encoding="utf-8")
    print(f"生成: {HTML_OUT}  ({len(companies)}社)")


if __name__ == "__main__":
    main()
