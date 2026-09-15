#!/usr/bin/env python3
"""產生簡報總索引 — 依 jacky-wiki 域分類，資料來自實際發佈狀態，不會過期。

用法：
  python3 index-decks.py            產生並發佈到私密區（slug: deck-index）
  python3 index-decks.py --dry      只產生檔案不發佈

資料來源：
  publish.py 的 list_decks() / list_private()  ← 實際發佈狀態，唯一真相
  decks-meta.json                              ← 域分類與一句話說明（手動維護）
沒寫進 decks-meta.json 的簡報會列在「未分類」，提醒補。
"""
from __future__ import annotations

import html as H
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import publish as P  # noqa: E402
import lockbox  # noqa: E402

TPE = ZoneInfo("Asia/Taipei")
META = ROOT / "decks-meta.json"
OUT = ROOT / "private-src" / "deck-index.html"

CSS = """
 :root{ --bg:#f6f8fa; --paper:#fff; --ink:#14181e; --mut:#5c6673; --line:#e2e7ed;
   --acc:#2f6bff; --grn:#0f9d58; --amb:#d97706; --soft:#f1f5fa;
   --font:"PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
   --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
 @media (prefers-color-scheme:dark){ :root{ --bg:#0e1116; --paper:#151a21; --ink:#e6eaee;
   --mut:#98a2ae; --line:#242b34; --soft:#1a212a; } }
 *{ box-sizing:border-box; margin:0; padding:0; }
 body{ background:var(--bg); color:var(--ink); font-family:var(--font);
   font-size:16px; line-height:1.7; -webkit-font-smoothing:antialiased; }
 .wrap{ max-width:900px; margin:0 auto; padding:44px 20px 90px; }
 header{ border-bottom:1px solid var(--line); padding-bottom:20px; }
 .kick{ font-size:12px; letter-spacing:.2em; color:var(--acc); font-weight:700; }
 h1{ font-size:clamp(23px,3.6vw,31px); margin:10px 0 8px; letter-spacing:-.02em; }
 .sub{ color:var(--mut); font-size:14.5px; }
 .stats{ display:flex; gap:20px; flex-wrap:wrap; margin-top:14px; font-size:14px; color:var(--mut); }
 .stats b{ color:var(--ink); font-size:19px; font-family:var(--mono); }
 #q{ width:100%; margin:22px 0 6px; padding:12px 15px; font-size:16px; border-radius:10px;
   border:1px solid var(--line); background:var(--paper); color:var(--ink); outline:none; }
 #q:focus{ border-color:var(--acc); }
 .hint{ font-size:12.5px; color:var(--mut); margin-bottom:18px; }
 h2{ font-size:18px; margin:32px 0 2px; padding-top:18px; border-top:1px solid var(--line);
   display:flex; align-items:baseline; gap:9px; }
 h2 .code{ font:700 11px/1 var(--mono); letter-spacing:.06em; color:#fff; background:var(--acc);
   padding:5px 8px; border-radius:6px; }
 h2 .cnt{ margin-left:auto; font:600 13px/1 var(--mono); color:var(--mut); }
 h3{ font-size:14px; color:var(--mut); margin:18px 0 6px; font-weight:700; letter-spacing:.02em; }
 .card{ display:block; background:var(--paper); border:1px solid var(--line); border-left:3px solid var(--line);
   border-radius:10px; padding:14px 16px; margin:9px 0; text-decoration:none; color:inherit; }
 .card:hover{ border-color:var(--acc); border-left-color:var(--acc); }
 .card.pub{ border-left-color:var(--grn); }
 .card.pri{ border-left-color:var(--amb); }
 .card .t{ font-weight:700; font-size:16px; }
 .card .d{ color:var(--mut); font-size:14px; margin-top:4px; }
 .card .m{ color:var(--mut); font-size:11.5px; font-family:var(--mono); margin-top:7px;
   display:flex; gap:9px; flex-wrap:wrap; align-items:center; }
 .pill{ padding:3px 7px; border-radius:99px; background:var(--soft); }
 .pill.g{ background:#e6f6ed; color:var(--grn); }
 .pill.a{ background:#fdf1e0; color:var(--amb); }
 .none{ color:var(--mut); font-size:14px; padding:10px 0; }
 footer{ margin-top:44px; padding-top:16px; border-top:1px solid var(--line);
   color:var(--mut); font-size:12.5px; }
 code{ font-family:var(--mono); font-size:.88em; background:var(--soft); padding:2px 5px; border-radius:4px; }
 @media(max-width:640px){ .wrap{ padding:26px 14px 60px; } h1{ font-size:21px; } }
"""


def build() -> str:
    meta = json.loads(META.read_text(encoding="utf-8"))
    domains, dmeta = meta["_域"], meta["decks"]
    try:
        pw = lockbox.load_password()
    except SystemExit:
        pw = ""
    pub = {d["slug"]: dict(d, vis="pub") for d in P.list_decks()}
    pri = {d["slug"]: dict(d, vis="pri") for d in P.list_private(pw)}
    allx = {**pub, **pri}

    # 分群：域 → cluster → decks
    tree: dict[str, dict[str, list]] = {}
    unclassified = []
    for slug, d in allx.items():
        m = dmeta.get(slug)
        if not m:
            unclassified.append(d); continue
        tree.setdefault(m["domain"], {}).setdefault(m.get("cluster", "—"), []).append(dict(d, **m))

    def card(d: dict) -> str:
        vis = "公開" if d["vis"] == "pub" else "🔒 需密碼"
        cls = "pub" if d["vis"] == "pub" else "pri"
        pill = "g" if d["vis"] == "pub" else "a"
        date = d["slug"][:10] if d["slug"][:4].isdigit() else ""
        return (f'<a class="card {cls}" href="{H.escape(d["url"])}" '
                f'data-s="{H.escape((d["title"] + " " + d.get("desc","") + " " + d["slug"]).lower())}">'
                f'<div class="t">{H.escape(d["title"])}</div>'
                + (f'<div class="d">{H.escape(d["desc"])}</div>' if d.get("desc") else "")
                + f'<div class="m"><span class="pill {pill}">{vis}</span>'
                  f'<span>{H.escape(date)}</span><span>{H.escape(d["slug"])}</span></div></a>')

    order = [k for k in domains if k in tree] + [k for k in tree if k not in domains]
    body = []
    for dom in order:
        clusters = tree[dom]
        n = sum(len(v) for v in clusters.values())
        body.append(f'<section data-dom><h2><span class="code">{H.escape(dom)}</span>'
                    f'{H.escape(domains.get(dom, dom))}<span class="cnt">{n} 份</span></h2>')
        for cl in sorted(clusters, key=lambda c: -len(clusters[c])):
            items = sorted(clusters[cl], key=lambda d: d["slug"], reverse=True)
            if cl != "—":
                body.append(f'<h3>{H.escape(cl)}　<span style="font-weight:400">{len(items)}</span></h3>')
            body += [card(d) for d in items]
        body.append("</section>")
    if unclassified:
        body.append('<section data-dom><h2><span class="code" style="background:var(--amb)">未分類</span>'
                    f'還沒歸類<span class="cnt">{len(unclassified)} 份</span></h2>'
                    '<p class="none">這些是新發佈但還沒寫進 <code>decks-meta.json</code> 的，'
                    '補完分類後重跑 <code>index-decks.py</code>。</p>')
        body += [card(d) for d in sorted(unclassified, key=lambda d: d["slug"], reverse=True)]
        body.append("</section>")

    stamp = datetime.now(TPE).strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>簡報總索引</title><style>{CSS}</style></head><body><div class="wrap">
<header>
  <div class="kick">SLIDE INDEX · 依 jacky-wiki 域分類</div>
  <h1>簡報總索引</h1>
  <p class="sub">資料來自實際發佈狀態，跑 <code>python3 index-decks.py</code> 就會更新。</p>
  <div class="stats">
    <span><b>{len(allx)}</b> 總份數</span>
    <span><b>{len(pub)}</b> 公開</span>
    <span><b>{len(pri)}</b> 私密</span>
    <span><b>{len(tree)}</b> 個域</span>
  </div>
</header>
<input id="q" type="search" placeholder="搜尋標題、說明、slug…（例如：双云、獎項、10/2、Starlink）" autocomplete="off">
<p class="hint">打字即時篩選。公開＝綠邊，私密＝橘邊需密碼。</p>
{''.join(body)}
<footer>產生於 {stamp} ｜ 公開區 <a href="https://gjj22622.github.io/slides/">gjj22622.github.io/slides</a>
 ｜ 私密區 <a href="https://gjj22622.github.io/slides/p/">/p/</a> ｜ 分類檔 <code>decks-meta.json</code></footer>
</div>
<script>
var q=document.getElementById('q');
q.addEventListener('input',function(){{
  var v=q.value.trim().toLowerCase();
  document.querySelectorAll('[data-dom]').forEach(function(sec){{
    var any=false;
    sec.querySelectorAll('.card').forEach(function(c){{
      var hit=!v||c.dataset.s.indexOf(v)>=0;
      c.style.display=hit?'block':'none'; if(hit) any=true;
    }});
    sec.style.display=any?'block':'none';
  }});
}});
q.addEventListener('keydown',function(e){{ if(e.key==='Escape'){{ q.value=''; q.dispatchEvent(new Event('input')); }} }});
</script>
</body></html>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"已產生 {OUT}（{OUT.stat().st_size // 1024} KB）")
    if "--dry" in sys.argv:
        return 0
    r = subprocess.run([sys.executable, str(ROOT / "publish.py"), str(OUT),
                        "--private", "--slug", "deck-index"],
                       cwd=str(ROOT), text=True, capture_output=True, timeout=600)
    print(r.stdout.strip() or r.stderr.strip()[:400])
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
