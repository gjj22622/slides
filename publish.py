#!/usr/bin/env python3
"""把一份 HTML 簡報發佈到 GitHub Pages，回傳公開網址。

用法：
  publish.py <檔案.html> [--title "標題"] [--slug my-deck]   發佈（或覆蓋同名）
  publish.py --list                                          列出已發佈
  publish.py --unpublish <slug>                              撤下
  publish.py --reindex                                       只重建首頁

設計原則（deterministic，不經 AI）：
  - slug 一律 ASCII：中文檔名在網址會被百分比編碼，難傳。中文標題放 <title> 與首頁。
  - 檔案原封不動複製進 decks/，不改內容——單檔 HTML 自帶樣式，動了就壞。
  - push 後輪詢網址直到 200（GitHub Pages 首次部署可能要幾分鐘）才回報成功。
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")


def today() -> date:
    return datetime.now(TPE).date()


def now() -> datetime:
    return datetime.now(TPE)

ROOT = Path(__file__).resolve().parent
DECKS = ROOT / "decks"
BASE = "https://gjj22622.github.io/slides"
META = ROOT / "decks" / "_meta.json"
PRIV = ROOT / "p"                    # 加密後的私密簡報（進 repo，但是密文）
PRIV_SRC = ROOT / "private-src"      # 私密原始檔＋索引資料（gitignore，只留本機）
PRIV_META = PRIV_SRC / "_meta.json"
GIT_ENV = ["-c", "user.email=gjj22622@gmail.com", "-c", "user.name=Jacky"]


def sh(args: list[str], check: bool = True, timeout: int = 180) -> str:
    r = subprocess.run(args, cwd=str(ROOT), text=True, capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"指令失敗 {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return (r.stdout or "").strip()


def slugify(s: str) -> str:
    """轉成 ASCII slug；中文等非 ASCII 會被移除，全空則回空字串由呼叫端補亂數。"""
    s = unicodedata.normalize("NFKD", s or "")
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)[:48]


def extract_title(path: Path) -> str:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:8000]
    except Exception:
        return ""
    m = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", head, re.S | re.I)
    return re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip() if m else ""


def load_meta() -> dict:
    try:
        return json.loads(META.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_meta(m: dict) -> None:
    META.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def load_priv_meta() -> dict:
    try:
        return json.loads(PRIV_META.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_priv_meta(m: dict) -> None:
    PRIV_SRC.mkdir(parents=True, exist_ok=True)
    PRIV_META.write_text(json.dumps(m, ensure_ascii=False, indent=1, sort_keys=True),
                         encoding="utf-8")


def build_private_index(password: str) -> None:
    """私密區管理介面：本身也加密，解鎖後才看得到有哪些簡報。"""
    import lockbox
    meta = load_priv_meta()
    rows = sorted(meta.items(), key=lambda kv: kv[1].get("date", ""), reverse=True)
    inner = lockbox.private_index_html(rows, now().strftime("%Y-%m-%d %H:%M"))
    PRIV.mkdir(parents=True, exist_ok=True)
    (PRIV / "index.html").write_text(lockbox.wrap(inner, password, "私密簡報"), encoding="utf-8")


def publish_private(src: Path, password: str, title: str = "", slug: str = "",
                    wait: bool = True) -> dict:
    """加密後發佈。原始檔留本機 private-src/（gitignore），repo 裡只有密文。"""
    import lockbox
    if not src.exists():
        raise SystemExit(f"找不到檔案：{src}")
    if src.suffix.lower() not in (".html", ".htm"):
        raise SystemExit("只收 .html / .htm 單檔簡報")

    title = title or extract_title(src) or src.stem
    slug = slugify(slug) or slugify(src.stem) or slugify(title) or "deck-" + now().strftime("%H%M%S")
    if not re.match(r"^\d{4}-\d{2}-\d{2}-", slug):
        slug = f"{today():%Y-%m-%d}-{slug}"

    plaintext = src.read_text(encoding="utf-8")
    PRIV.mkdir(parents=True, exist_ok=True)
    PRIV_SRC.mkdir(parents=True, exist_ok=True)
    dest = PRIV / f"{slug}.html"
    replaced = dest.exists()
    dest.write_text(lockbox.wrap(plaintext, password, title), encoding="utf-8")
    shutil.copyfile(src, PRIV_SRC / f"{slug}.html")      # 本機留明文原稿，方便改

    meta = load_priv_meta()
    meta[slug] = {"title": title, "date": today().isoformat(),
                  "size": len(plaintext.encode()),
                  "updated": now().isoformat(timespec="seconds")}
    save_priv_meta(meta)
    build_private_index(password)
    build_index()
    git_sync(("update" if replaced else "publish") + f": [private] {slug}")

    url = f"{BASE}/p/{slug}.html"
    live = wait_live(url) if wait else True
    return {"slug": slug, "title": title, "url": url, "index": f"{BASE}/p/",
            "live": live, "replaced": replaced, "size": len(plaintext.encode()),
            "private": True}


def unpublish_private(slug: str, password: str) -> dict:
    slug = slug.strip().removesuffix(".html")
    all_p = [q for q in sorted(PRIV.glob("*.html")) if q.name != "index.html"]
    exact = [q for q in all_p if q.stem == slug]
    if exact:
        target = exact[0]
    else:
        part = [q for q in all_p if slug and slug in q.stem]
        if not part:
            raise SystemExit(f"私密區找不到：{slug}")
        if len(part) > 1:
            raise SystemExit("「" + slug + "」對到多份：" + "、".join(q.stem for q in part[:6]))
        target = part[0]
    target.unlink()
    (PRIV_SRC / target.name).unlink(missing_ok=True)
    meta = load_priv_meta()
    meta.pop(target.stem, None)
    save_priv_meta(meta)
    build_private_index(password)
    git_sync(f"unpublish: [private] {target.stem}")
    return {"slug": target.stem, "removed": True, "private": True}


def list_private() -> list[dict]:
    meta = load_priv_meta()
    return [{"slug": k, "title": v.get("title", k), "date": v.get("date", ""),
             "url": f"{BASE}/p/{k}.html"}
            for k, v in sorted(meta.items(), key=lambda kv: kv[1].get("date", ""), reverse=True)]


def build_index() -> None:
    meta = load_meta()
    items = []
    for f in sorted(DECKS.glob("*.html")):
        if f.name.startswith("_"):
            continue
        info = meta.get(f.stem, {})
        items.append({
            "slug": f.stem,
            "title": info.get("title") or extract_title(f) or f.stem,
            "date": info.get("date", ""),
            "size": f.stat().st_size,
        })
    items.sort(key=lambda x: (x["date"], x["slug"]), reverse=True)

    cards = "\n".join(
        f'''      <a class="card" href="decks/{html_mod.escape(i["slug"])}.html">
        <span class="t">{html_mod.escape(i["title"])}</span>
        <span class="m">{html_mod.escape(i["date"])} · {i["size"] // 1024} KB</span>
      </a>''' for i in items) or '      <p class="empty">還沒有簡報。傳一份 .html 給薇姐，或跑 <code>pubslide 檔案.html</code>。</p>'

    (ROOT / "index.html").write_text(f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Jacky 的簡報</title>
<style>
  :root {{ color-scheme: light dark;
    --bg:#f6f7f9; --fg:#16181d; --mut:#6b7280; --card:#fff; --line:#e5e7eb; --acc:#2563eb; }}
  @media (prefers-color-scheme:dark) {{ :root {{
    --bg:#0f1115; --fg:#e8eaed; --mut:#9aa0a6; --card:#171a20; --line:#272b33; --acc:#7aa2ff; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.6
    "PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif; }}
  .wrap {{ max-width:860px; margin:0 auto; padding:48px 20px 80px; }}
  h1 {{ font-size:26px; margin:0 0 6px; letter-spacing:-.01em; }}
  .sub {{ color:var(--mut); font-size:14px; margin:0 0 32px; }}
  .grid {{ display:grid; gap:12px; }}
  .card {{ display:flex; flex-direction:column; gap:6px; padding:18px 20px; background:var(--card);
    border:1px solid var(--line); border-radius:12px; text-decoration:none; color:inherit;
    transition:border-color .15s, transform .15s; }}
  .card:hover {{ border-color:var(--acc); transform:translateY(-1px); }}
  .t {{ font-weight:600; font-size:17px; }}
  .m {{ color:var(--mut); font-size:13px; }}
  .empty {{ color:var(--mut); }}
  code {{ background:var(--line); padding:2px 6px; border-radius:5px; font-size:13px; }}
  footer {{ margin-top:40px; color:var(--mut); font-size:13px; border-top:1px solid var(--line); padding-top:16px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Jacky 的簡報</h1>
    <p class="sub">共 {len(items)} 份 · 更新於 {now().strftime("%Y-%m-%d %H:%M")}</p>
    <div class="grid">
{cards}
    </div>
    <footer>公開網址，任何拿到連結的人都能看。真正機密的請放 Google Drive。
      <a href="p/" style="color:var(--mut);text-decoration:none;float:right">&#128274; 私密區</a></footer>
  </div>
</body>
</html>
''', encoding="utf-8")


def wait_live(url: str, timeout: int = 150) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "pubslide"})
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status == 200:
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 200:
                return True
        except Exception:
            pass
        time.sleep(6)
    return False


def git_sync(msg: str) -> None:
    """commit + push；多個對話／裝置同時發佈時先 rebase 再推，不互相打架。"""
    sh(["git", "add", "-A"])
    if sh(["git", "status", "--porcelain"]):
        sh(["git", *GIT_ENV, "commit", "-qm", msg])
    for attempt in range(3):
        r = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=str(ROOT),
                           text=True, capture_output=True, timeout=180)
        if r.returncode == 0:
            return
        # 遠端有別人剛推的東西 → 拉下來重放自己的 commit 再推
        subprocess.run(["git", *GIT_ENV, "pull", "--rebase", "-q", "origin", "main"],
                       cwd=str(ROOT), text=True, capture_output=True, timeout=180)
        time.sleep(1 + attempt)
    raise SystemExit(f"推不上去：{r.stderr.strip()[:200]}")


def publish(src: Path, title: str = "", slug: str = "", wait: bool = True) -> dict:
    if not src.exists():
        raise SystemExit(f"找不到檔案：{src}")
    if src.suffix.lower() not in (".html", ".htm"):
        raise SystemExit("只收 .html / .htm 單檔簡報")
    DECKS.mkdir(parents=True, exist_ok=True)
    title = title or extract_title(src) or src.stem
    slug = slugify(slug) or slugify(src.stem) or slugify(title)
    if not slug:
        slug = "deck-" + now().strftime("%H%M%S")
    slug = f"{today():%Y-%m-%d}-{slug}" if not re.match(r"^\d{4}-\d{2}-\d{2}-", slug) else slug

    dest = DECKS / f"{slug}.html"
    replaced = dest.exists()
    shutil.copyfile(src, dest)

    meta = load_meta()
    meta[slug] = {"title": title, "date": today().isoformat(),
                  "updated": now().isoformat(timespec="seconds")}
    save_meta(meta)
    build_index()
    git_sync(("update" if replaced else "publish") + f": {slug}")

    url = f"{BASE}/decks/{slug}.html"
    live = wait_live(url) if wait else True
    return {"slug": slug, "title": title, "url": url, "index": BASE + "/",
            "live": live, "replaced": replaced, "size": dest.stat().st_size}


def unpublish(slug: str) -> dict:
    slug = slug.strip().removesuffix(".html")
    all_decks = [p for p in sorted(DECKS.glob("*.html")) if not p.name.startswith("_")]
    exact = [p for p in all_decks if p.stem == slug]
    if exact:
        target = exact[0]
    else:
        part = [p for p in all_decks if slug and slug in p.stem]
        if not part:
            raise SystemExit(f"找不到已發佈的：{slug}")
        if len(part) > 1:
            raise SystemExit("「" + slug + "」對到多份，講清楚是哪一份：" +
                             "、".join(p.stem for p in part[:6]))
        target = part[0]
    target.unlink()
    meta = load_meta()
    meta.pop(target.stem, None)
    save_meta(meta)
    build_index()
    git_sync(f"unpublish: {target.stem}")
    return {"slug": target.stem, "removed": True}


def list_decks() -> list[dict]:
    meta = load_meta()
    out = []
    for f in sorted(DECKS.glob("*.html"), reverse=True):
        if f.name.startswith("_"):
            continue
        out.append({"slug": f.stem, "title": meta.get(f.stem, {}).get("title") or extract_title(f),
                    "url": f"{BASE}/decks/{f.stem}.html"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="發佈 HTML 簡報到 GitHub Pages")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--title", default="")
    ap.add_argument("--slug", default="")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--unpublish", default="")
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--private", action="store_true", help="加密後發佈到私密區")
    ap.add_argument("--password", default="", help="這一份用別的密碼（預設用本機密碼檔）")
    ap.add_argument("--set-password", default="", help="設定／更換私密區主密碼")
    a = ap.parse_args()

    import lockbox
    if a.set_password:
        lockbox.save_password(a.set_password)
        try:
            build_private_index(a.set_password)
            if load_priv_meta():
                print("提醒：既有私密簡報仍是舊密碼加密的，要換密碼請重跑一次 --private 發佈。")
            git_sync("rekey: private index")
        except Exception as exc:
            print(f"（索引更新略過：{exc}）")
        print(f"密碼已設定。強度：{lockbox.strength_note(a.set_password)}")
        return 0

    if a.list:
        for d in list_decks():
            print(f"公開\t{d['slug']}\t{d['title']}\t{d['url']}")
        for d in list_private():
            print(f"私密\t{d['slug']}\t{d['title']}\t{d['url']}")
        return 0
    if a.unpublish:
        if a.private:
            print(json.dumps(unpublish_private(a.unpublish, a.password or lockbox.load_password()),
                             ensure_ascii=False))
        else:
            try:
                print(json.dumps(unpublish(a.unpublish), ensure_ascii=False))
            except SystemExit:
                print(json.dumps(unpublish_private(a.unpublish,
                      a.password or lockbox.load_password()), ensure_ascii=False))
        return 0
    if a.reindex:
        build_index()
        if load_priv_meta():
            build_private_index(a.password or lockbox.load_password())
        git_sync("reindex"); print("首頁已重建"); return 0
    if not a.file:
        ap.print_help(); return 1
    if a.private:
        r = publish_private(Path(a.file).expanduser(), a.password or lockbox.load_password(),
                            a.title, a.slug, wait=not a.no_wait)
    else:
        r = publish(Path(a.file).expanduser(), a.title, a.slug, wait=not a.no_wait)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
