#!/usr/bin/env python3
"""公開首頁 = 可直接點的分類索引（不用密碼）。

publish.py 每次發佈都會叫這支重建首頁，所以永遠是最新的。
分類與說明讀 decks-meta.json；沒寫進去的會列在「未分類」。
私密簡報不列標題，只在頁尾放一個入口連結。
"""
from __future__ import annotations

import html as H
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
META = ROOT / "decks-meta.json"

CSS = """
 :root{ --bg:#f6f7f9; --paper:#fff; --ink:#16181d; --mut:#6b7280; --line:#e5e7eb;
   --acc:#2563eb; --grn:#0f9d58; --soft:#f1f5fa;
   --font:"PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
   --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
 @media (prefers-color-scheme:dark){ :root{ --bg:#0f1115; --paper:#171a20; --ink:#e8eaed;
   --mut:#9aa0a6; --line:#272b33; --acc:#7aa2ff; --soft:#1a212a; } }
 *{ box-sizing:border-box; margin:0; padding:0; }
 body{ background:var(--bg); color:var(--ink); font-family:var(--font);
   font-size:16px; line-height:1.7; -webkit-font-smoothing:antialiased; }
 .wrap{ max-width:880px; margin:0 auto; padding:46px 20px 90px; }
 header{ border-bottom:1px solid var(--line); padding-bottom:20px; }
 h1{ font-size:clamp(23px,3.6vw,30px); letter-spacing:-.02em; margin:0 0 7px; }
 .sub{ color:var(--mut); font-size:14.5px; }
 .stats{ display:flex; gap:20px; flex-wrap:wrap; margin-top:13px; font-size:14px; color:var(--mut); }
 .stats b{ color:var(--ink); font-size:19px; font-family:var(--mono); }
 #q{ width:100%; margin:22px 0 6px; padding:12px 15px; font-size:16px; border-radius:10px;
   border:1px solid var(--line); background:var(--paper); color:var(--ink); outline:none; }
 #q:focus{ border-color:var(--acc); }
 .hint{ font-size:12.5px; color:var(--mut); margin-bottom:16px; }
 h2{ font-size:18px; margin:30px 0 2px; padding-top:18px; border-top:1px solid var(--line);
   display:flex; align-items:baseline; gap:9px; }
 h2 .code{ font:700 11px/1 var(--mono); letter-spacing:.06em; color:#fff; background:var(--acc);
   padding:5px 8px; border-radius:6px; }
 h2 .cnt{ margin-left:auto; font:600 13px/1 var(--mono); color:var(--mut); }
 h3{ font-size:13.5px; color:var(--mut); margin:16px 0 5px; font-weight:700; }
 .card{ display:block; background:var(--paper); border:1px solid var(--line);
   border-left:3px solid var(--grn); border-radius:10px; padding:14px 16px; margin:9px 0;
   text-decoration:none; color:inherit; transition:border-color .15s, transform .15s; }
 .card:hover{ border-color:var(--acc); border-left-color:var(--acc); transform:translateY(-1px); }
 .card .t{ font-weight:700; font-size:16.5px; }
 .card .d{ color:var(--mut); font-size:14px; margin-top:4px; }
 .card .m{ color:var(--mut); font-size:11.5px; font-family:var(--mono); margin-top:7px; }
 .empty{ color:var(--mut); }
 footer{ margin-top:40px; padding-top:16px; border-top:1px solid var(--line);
   color:var(--mut); font-size:13px; display:flex; gap:14px; flex-wrap:wrap; align-items:center; }
 footer a{ color:var(--acc); text-decoration:none; }
 .lock{ margin-left:auto; }
 code{ font-family:var(--mono); font-size:.88em; background:var(--soft); padding:2px 5px; border-radius:4px; }
 @media(max-width:640px){ .wrap{ padding:26px 14px 60px; } h1{ font-size:21px; } }
"""


def render(items: list[dict], private_count: int, stamp: str) -> str:
    """items: [{slug,title,date,size}]，公開簡報。"""
    try:
        meta = json.loads(META.read_text(encoding="utf-8"))
        domains, dmeta = meta["_域"], meta["decks"]
    except Exception:
        domains, dmeta = {}, {}

    tree: dict[str, dict[str, list]] = {}
    unclassified: list[dict] = []
    for it in items:
        m = dmeta.get(it["slug"])
        if not m:
            unclassified.append(it); continue
        tree.setdefault(m["domain"], {}).setdefault(m.get("cluster", "—"), []).append(dict(it, **m))

    def card(d: dict) -> str:
        blob = (d["title"] + " " + d.get("desc", "") + " " + d["slug"]).lower()
        return (f'<a class="card" href="decks/{H.escape(d["slug"])}.html" '
                f'data-s="{H.escape(blob)}"><div class="t">{H.escape(d["title"])}</div>'
                + (f'<div class="d">{H.escape(d["desc"])}</div>' if d.get("desc") else "")
                + f'<div class="m">{H.escape(d.get("date",""))} · {d.get("size",0)//1024} KB</div></a>')

    body: list[str] = []
    order = [k for k in domains if k in tree] + [k for k in tree if k not in domains]
    for dom in order:
        clusters = tree[dom]
        n = sum(len(v) for v in clusters.values())
        body.append(f'<section data-dom><h2><span class="code">{H.escape(dom)}</span>'
                    f'{H.escape(domains.get(dom, dom))}<span class="cnt">{n}</span></h2>')
        for cl in sorted(clusters, key=lambda c: -len(clusters[c])):
            rows = sorted(clusters[cl], key=lambda d: d["slug"], reverse=True)
            if cl != "—":
                body.append(f'<h3>{H.escape(cl)}</h3>')
            body += [card(d) for d in rows]
        body.append("</section>")
    if unclassified:
        body.append('<section data-dom><h2><span class="code">其他</span>未分類'
                    f'<span class="cnt">{len(unclassified)}</span></h2>')
        body += [card(d) for d in sorted(unclassified, key=lambda d: d["slug"], reverse=True)]
        body.append("</section>")
    if not items:
        body.append('<p class="empty">還沒有公開簡報。傳一份 .html 給薇姐，或跑 '
                    '<code>pubslide 檔案.html</code>。</p>')

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Jacky 的簡報</title>
<style>{CSS}</style>
</head>
<body><div class="wrap">
<header>
  <h1>Jacky 的簡報</h1>
  <p class="sub">依 jacky-wiki 域分類。點卡片直接開，不用密碼。</p>
  <div class="stats"><span><b>{len(items)}</b> 公開</span>
    <span><b>{private_count}</b> 私密</span>
    <span><b>{len(tree)}</b> 個域</span>
    <span>更新 {H.escape(stamp)}</span></div>
</header>
<input id="q" type="search" placeholder="搜尋標題、說明…（例如：陪跑、双云、獎項）" autocomplete="off">
<p class="hint">打字即時篩選，Esc 清除。</p>
{''.join(body)}
<footer>
  <span>公開網址，任何拿到連結的人都能看。機密的請放 Google Drive。</span>
  <a class="lock" href="p/">&#128274; 私密區（{private_count} 份，需密碼）</a>
</footer>
</div>
<script>
var q=document.getElementById('q');
function f(){{
  var v=q.value.trim().toLowerCase();
  document.querySelectorAll('[data-dom]').forEach(function(s){{
    var any=false;
    s.querySelectorAll('.card').forEach(function(c){{
      var hit=!v||c.dataset.s.indexOf(v)>=0;
      c.style.display=hit?'block':'none'; if(hit) any=true;
    }});
    s.style.display=any?'block':'none';
  }});
}}
q.addEventListener('input',f);
q.addEventListener('keydown',function(e){{ if(e.key==='Escape'){{ q.value=''; f(); }} }});
</script>
</body></html>
"""
