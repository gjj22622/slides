#!/usr/bin/env python3
"""機器可讀的簡報目錄 — 給 AI 助理直接讀 GitHub 用。

publish.py 每次發佈／重建索引都會叫這支，所以永遠跟 decks/ 同步。

產出三個檔（都在 repo 根目錄，GitHub Pages 也直接服務）：
  index.json    結構化目錄，程式與 AI 都好解析
  CATALOG.md    全文目錄，AI 讀這一個檔就能回答「我要的那份在哪」
  llms.txt      AI 工具查一個站台時的慣例入口，指向上面兩個

另外寫 private-src/CATALOG.md（gitignore，只留本機），給本機的 AI 查私密簡報。

分類（domain／cluster／desc）讀 decks-meta.json，跟公開首頁同一份真相源。
標籤與摘要優先讀簡報自己 <head> 裡的 <meta>；沒寫的就從內文推導，
所以雲端 AI 隨手丟進來、什麼都沒標的檔案一樣進得了目錄。

私密簡報在公開產物裡只列 slug 與網址，不列標題或摘要——
slug 本來就是 repo 裡的檔名（寫了不會多洩漏什麼），
標題跟摘要寫進去就等於把 AES 加密自己拆了。
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECKS = ROOT / "decks"
PRIV = ROOT / "p"
PRIV_SRC = ROOT / "private-src"
CLASSIFY = ROOT / "decks-meta.json"
BASE = "https://gjj22622.github.io/slides"
REPO = "https://github.com/gjj22622/slides"
RAW = "https://raw.githubusercontent.com/gjj22622/slides/main"

SCHEMA = 1
HEAD_WINDOW = 8000          # 跟 publish.py 的 extract_title 同一個窗口
MAX_OUTLINE = 24
MAX_HEADING = 80
MAX_SUMMARY = 160
MIN_SUMMARY = 40

_SKIP = {"script", "style", "template", "svg", "noscript", "head"}
_BLOCK = {"p", "div", "section", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6"}
_HEADS = {"h1", "h2", "h3", "h4"}


class DeckText(HTMLParser):
    """抽標題大綱與純文字。

    標題文字一定要累積到 endtag 才吐出——簡報裡的標題常常長這樣：
        <h2 class="t r">行銷部，<br><span>正在被 AI 重寫</span></h2>
    用 regex 只會抓到「行銷部，」半句。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self._parts: list[str] = []
        self._skip = 0
        self._head: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag in _HEADS and self._skip == 0:
            self._head = []
        elif tag in _BLOCK and self._skip == 0:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _HEADS and self._head is not None:
            text = _squash("".join(self._head))
            if text:
                self.headings.append(text[:MAX_HEADING])
            self._head = None
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._head is not None:
            self._head.append(data)
        self._parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self._parts)


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_head_meta(text: str) -> dict:
    """讀簡報 <head> 前 8000 bytes 裡的 <meta name=... content=...>。"""
    head = text[:HEAD_WINDOW]
    out: dict[str, str] = {}
    for m in re.finditer(r"<meta\b([^>]*)>", head, re.I):
        attrs = m.group(1)
        name = re.search(r'\bname\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
        content = re.search(r'\bcontent\s*=\s*["\']([^"\']*)["\']', attrs, re.I)
        if name and content:
            out[name.group(1).strip().lower()] = _squash(content.group(1))
    return out


def _tags(raw: str) -> list[str]:
    seen, out = set(), []
    for t in re.split(r"[,，、;；]", raw or ""):
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:12]


def scan_text(text: str) -> dict:
    """從一份簡報的 HTML 原始碼推出目錄需要的欄位。

    吃字串而不是路徑，私密簡報解密後的明文才不用落地。
    """
    meta = parse_head_meta(text)
    parser = DeckText()
    try:
        parser.feed(text)
    except Exception:
        pass

    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", text[:HEAD_WINDOW], re.S | re.I)
    if m:
        title = _squash(m.group(1))
    if not title and parser.headings:
        title = parser.headings[0]

    outline, seen = [], set()
    for h in parser.headings:
        if h not in seen:
            seen.add(h)
            outline.append(h)
        if len(outline) >= MAX_OUTLINE:
            break

    summary = meta.get("description", "")
    if not summary:
        for para in parser.text.split("\n"):
            para = _squash(para)
            if len(para) >= MIN_SUMMARY and para != title:
                summary = para
                break
    if len(summary) > MAX_SUMMARY:
        summary = summary[:MAX_SUMMARY].rstrip() + "…"

    # 沒標 deck-kind 就自己看：有一堆 slide / section 的當簡報，其餘當報告
    kind = meta.get("deck-kind", "")
    if not kind:
        n = len(re.findall(r'class="[^"]*\bslide\b', text)) or len(re.findall(r"<section\b", text, re.I))
        kind = "slides" if n >= 3 else "report"

    lang = ""
    m = re.search(r'<html[^>]*\blang\s*=\s*["\']([^"\']+)["\']', text[:HEAD_WINDOW], re.I)
    if m:
        lang = m.group(1)

    return {"title": title, "summary": summary, "outline": outline,
            "tags": _tags(meta.get("keywords", "")),
            "category": meta.get("deck-category", ""),
            "audience": meta.get("deck-audience", ""),
            "kind": kind, "lang": lang,
            "text_chars": len(_squash(parser.text))}


def _classification() -> tuple[dict, dict]:
    """decks-meta.json：域名對照表 + 每份簡報的 domain／cluster／desc。"""
    try:
        m = json.loads(CLASSIFY.read_text(encoding="utf-8"))
        return m.get("_域", {}), m.get("decks", {})
    except Exception:
        return {}, {}


def public_entries(meta: dict | None = None) -> list[dict]:
    """掃 decks/ 下每一份公開簡報。檔案系統是真相源，meta 只是補充。"""
    meta = meta or {}
    domains, cls = _classification()
    out = []
    for f in sorted(DECKS.glob("*.html")):
        if f.name.startswith("_"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned = scan_text(text)
        cached = meta.get(f.stem, {})
        c = cls.get(f.stem, {})
        date = cached.get("date", "")
        if not date:
            m = re.match(r"^(\d{4}-\d{2}-\d{2})-", f.stem)
            date = m.group(1) if m else ""
        out.append({
            "slug": f.stem,
            # --title 是人工覆寫過的，優先於檔案裡的 <title>
            "title": cached.get("title") or scanned["title"] or f.stem,
            "date": date,
            "updated": cached.get("updated", ""),
            "url": f"{BASE}/decks/{f.stem}.html",
            "path": f"decks/{f.stem}.html",
            "raw": f"{RAW}/decks/{f.stem}.html",
            "visibility": "public",
            "domain": c.get("domain", ""),
            "domain_name": domains.get(c.get("domain", ""), ""),
            "cluster": c.get("cluster", ""),
            # decks-meta.json 的 desc 是手寫的，比自動抽的摘要準
            "summary": c.get("desc") or scanned["summary"],
            "kind": scanned["kind"],
            "lang": scanned["lang"],
            "category": scanned["category"],
            "audience": scanned["audience"],
            "tags": scanned["tags"],
            "outline": scanned["outline"],
            "bytes": f.stat().st_size,
            "text_chars": scanned["text_chars"],
        })
    out.sort(key=lambda d: (d["date"], d["slug"]), reverse=True)
    return out


def private_slugs() -> list[str]:
    if not PRIV.exists():
        return []
    return sorted((p.stem for p in PRIV.glob("*.html") if p.name != "index.html"), reverse=True)


def write_index_json(pub: list[dict], priv: list[str], stamp: str) -> None:
    doc = {
        "schema": SCHEMA,
        "repo": REPO,
        "base": BASE,
        "generated_date": stamp,
        "counts": {"public": len(pub), "private": len(priv)},
        "note": "公開簡報的內容可直接讀 raw 欄位的網址。私密簡報是 AES-256-GCM 密文，只列 slug 與網址。",
        "decks": pub,
        "private": [{"slug": s, "url": f"{BASE}/p/{s}.html",
                     "visibility": "private", "locked": True} for s in priv],
    }
    (ROOT / "index.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _md_entry(d: dict) -> str:
    bits = [f"## {d['title']}", ""]
    meta_line = [f"- slug: `{d['slug']}`"]
    if d["date"]:
        meta_line.append(f"日期 {d['date']}")
    meta_line.append(f"類型 {d['kind']}")
    if d.get("domain_name"):
        meta_line.append(f"域 {d['domain_name']}（{d['domain']}）")
    if d.get("cluster"):
        meta_line.append(f"群組 {d['cluster']}")
    if d.get("audience"):
        meta_line.append(f"對象 {d['audience']}")
    bits.append(" ｜ ".join(meta_line))
    if d["tags"]:
        bits.append(f"- 標籤：{'、'.join(d['tags'])}")
    bits.append(f"- 網址：{d['url']}")
    bits.append(f"- 原始碼：`{d['path']}`")
    if d["summary"]:
        bits += ["", f"摘要：{d['summary']}"]
    if d["outline"]:
        bits += ["", "大綱："]
        bits += [f"{i}. {h}" for i, h in enumerate(d["outline"], 1)]
    bits.append("")
    return "\n".join(bits)


def write_catalog(pub: list[dict], priv: list[str], stamp: str) -> None:
    head = [
        "# Jacky 的簡報目錄",
        "",
        f"共 {len(pub)} 份公開簡報、{len(priv)} 份私密（加密）。更新於 {stamp}。",
        "",
        "> 本檔由 `publish.py` 自動產生，不要手動編輯——下次發佈就被蓋掉。",
        "> 要程式解析用 `index.json`；要語意檢索讀這一份就夠。",
        "> 每份底下的「大綱」是簡報裡真實出現的標題，可以直接拿來判斷內容涵蓋什麼。",
        "",
        "---",
        "",
    ]
    body = [_md_entry(d) for d in pub] or ["（還沒有公開簡報。）", ""]
    tail = [
        "---",
        "",
        "## 私密簡報",
        "",
        f"另有 {len(priv)} 份私密簡報放在 `p/`，內容以 AES-256-GCM 加密，"
        "標題與摘要都不在這份目錄裡。要查私密簡報請在 Jacky 本機跑 `pubslide --list`，"
        "或讀 `private-src/CATALOG.md`（不進 repo）。",
        "",
    ]
    (ROOT / "CATALOG.md").write_text("\n".join(head + body + tail), encoding="utf-8")


def write_llms_txt(pub: list[dict], priv: list[str], stamp: str) -> None:
    (ROOT / "llms.txt").write_text("\n".join([
        "# Jacky 的簡報空間",
        "",
        "> 鐘基啟（Jacky）的單檔 HTML 簡報庫。每份簡報都是一個獨立的 .html，"
        "打開網址就能看，不需要任何播放器。",
        "",
        f"公開 {len(pub)} 份、私密 {len(priv)} 份。更新於 {stamp}。",
        "",
        "## 要找簡報看這裡",
        "",
        f"- [全文目錄 CATALOG.md]({RAW}/CATALOG.md)：每份簡報的標題、摘要、大綱與網址。想找東西讀這個。",
        f"- [結構化目錄 index.json]({BASE}/index.json)：同樣的資料，JSON 格式。",
        f"- [人看的首頁]({BASE}/)：分類卡片＋即時搜尋。",
        "",
        "## 網址規則",
        "",
        f"- 公開簡報：`{BASE}/decks/<slug>.html`",
        f"- 原始碼：`{RAW}/decks/<slug>.html`",
        f"- 私密簡報：`{BASE}/p/<slug>.html`（AES-256-GCM 加密，要密碼）",
        "",
    ]), encoding="utf-8")


def write_private_catalog(rows: list[dict], stamp: str) -> None:
    """含標題摘要的私密目錄，只寫本機 private-src/（gitignore）。"""
    PRIV_SRC.mkdir(exist_ok=True)
    head = [
        "# Jacky 的私密簡報目錄（本機專用）",
        "",
        f"共 {len(rows)} 份。更新於 {stamp}。",
        "",
        "> 這份檔案不進 repo。內容對應 `p/` 下的加密簡報，開啟需要密碼。",
        "",
        "---",
        "",
    ]
    (PRIV_SRC / "CATALOG.md").write_text(
        "\n".join(head + ([_md_entry(d) for d in rows] or ["（沒有私密簡報。）", ""])),
        encoding="utf-8")


def build(meta: dict | None = None, stamp: str = "") -> dict:
    """公開產物三件套。回傳份數，給呼叫端印訊息用。"""
    pub = public_entries(meta)
    priv = private_slugs()
    write_index_json(pub, priv, stamp)
    write_catalog(pub, priv, stamp)
    write_llms_txt(pub, priv, stamp)
    return {"public": len(pub), "private": len(priv)}
