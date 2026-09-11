#!/usr/bin/env python3
"""私密簡報加密盒 — 把一份 HTML 用密碼加密成一個自帶解鎖畫面的單檔。

為什麼要真加密：
  GitHub Pages 是靜態託管，檔案本身一定是公開的。「用 JavaScript 檢查密碼再顯示內容」
  是假的——看原始碼就破。這裡的做法是**內容本身被加密**，沒有密碼拿到的只是亂碼。

規格（Python 加密 ↔ 瀏覽器 Web Crypto 解密，兩邊參數必須一致）：
  金鑰推導  PBKDF2-HMAC-SHA256, 310,000 次, 隨機 16 bytes salt, 產出 256-bit key
  加密      AES-256-GCM, 隨機 12 bytes IV, 認證標籤附在密文尾端
  兩端都用內建工具：Python 用 cryptography，瀏覽器用 crypto.subtle，沒有新依賴。

誠實的限制（一定要讓 Jacky 知道）：
  1. 密文是公開的 → 密碼弱就能離線暴力破解。密碼要長。
  2. 拿到密碼的人可以把解密後的內容轉發出去。
  3. 合約、報價、財務這種真敏感的，還是走 Google Drive 權限管控。
     這套適合「不想被公開搜到、但給對方連結加密碼就能看」的東西。
"""
from __future__ import annotations

import base64
import html as html_mod
import json
import os
import secrets
import stat
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITERATIONS = 310_000
PW_FILE = Path.home() / ".config" / "slides" / "password"


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def derive(password: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=ITERATIONS).derive(password.encode("utf-8"))


def encrypt(plaintext: str, password: str) -> dict:
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)
    key = derive(password, salt)
    ct = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    return {"s": b64(salt), "i": b64(iv), "c": b64(ct), "n": ITERATIONS}


def decrypt_payload(payload: dict, password: str) -> str:
    """encrypt() 的反向操作（本機用；瀏覽器那邊由 Web Crypto 做同樣的事）。"""
    salt = base64.b64decode(payload["s"])
    iv = base64.b64decode(payload["i"])
    ct = base64.b64decode(payload["c"])
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=int(payload.get("n", ITERATIONS))).derive(password.encode("utf-8"))
    return AESGCM(key).decrypt(iv, ct, None).decode("utf-8")


# ─────────────────────────── 密碼管理 ───────────────────────────
def load_password() -> str:
    """讀本機密碼檔。這個檔永遠不進 repo。"""
    if not PW_FILE.exists():
        raise SystemExit(
            f"還沒設密碼。跑一次：\n"
            f"  mkdir -p {PW_FILE.parent} && printf '你的密碼' > {PW_FILE} && chmod 600 {PW_FILE}\n"
            f"或用 pubslide --set-password '你的密碼'")
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    if not pw:
        raise SystemExit("密碼檔是空的")
    return pw


def save_password(pw: str) -> None:
    pw = pw.strip()
    if len(pw) < 8:
        raise SystemExit("密碼至少 8 個字元。密文是公開的，短密碼會被離線破解。")
    PW_FILE.parent.mkdir(parents=True, exist_ok=True)
    PW_FILE.write_text(pw, encoding="utf-8")
    os.chmod(PW_FILE, stat.S_IRUSR | stat.S_IWUSR)   # 600


def strength_note(pw: str) -> str:
    n = len(pw)
    if n >= 16:
        return "夠強"
    if n >= 12:
        return "可以，再長一點更好"
    return "偏短，建議 16 字元以上（密文是公開的）"


# ─────────────────────────── 解鎖殼 ───────────────────────────
SHELL = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>__TITLE__</title>
<style>
  :root{ --bg:#0d1017; --card:#161a22; --line:#272d3a; --fg:#e8eaed; --mut:#8b93a3; --acc:#2f6bff; }
  *{ box-sizing:border-box; margin:0; padding:0; }
  html,body{ height:100%; }
  body{ background:var(--bg); color:var(--fg); display:grid; place-items:center;
    font:16px/1.6 "PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif; }
  .box{ width:min(400px,92vw); background:var(--card); border:1px solid var(--line);
    border-radius:16px; padding:34px 30px; box-shadow:0 24px 70px rgba(0,0,0,.5); }
  .lock{ font-size:26px; }
  h1{ font-size:19px; margin:14px 0 6px; letter-spacing:-.01em; }
  p.s{ color:var(--mut); font-size:13.5px; margin-bottom:22px; line-height:1.55; }
  input{ width:100%; padding:13px 15px; border-radius:10px; border:1px solid var(--line);
    background:#0f131b; color:var(--fg); font-size:16px; outline:none; }
  input:focus{ border-color:var(--acc); }
  button{ width:100%; margin-top:11px; padding:13px; border:0; border-radius:10px;
    background:var(--acc); color:#fff; font-size:15.5px; font-weight:600; cursor:pointer; }
  button:disabled{ opacity:.55; cursor:default; }
  .err{ color:#ff8080; font-size:13.5px; margin-top:12px; min-height:19px; }
  .foot{ color:#5f6675; font-size:11.5px; margin-top:20px; line-height:1.5; }
  #frame{ position:fixed; inset:0; width:100%; height:100%; border:0; display:none;
    background:#fff; z-index:10; }
</style>
</head>
<body>
  <div class="box" id="gate">
    <div class="lock">🔒</div>
    <h1>__TITLE__</h1>
    <p class="s">這份內容是加密的，輸入密碼才看得到。</p>
    <input id="pw" type="password" placeholder="密碼" autocomplete="current-password" autofocus>
    <button id="go">解鎖</button>
    <div class="err" id="err"></div>
    <div class="foot">內容以 AES-256-GCM 加密，解密在你的瀏覽器裡完成，密碼不會送到任何伺服器。</div>
  </div>
  <iframe id="frame" allow="fullscreen" allowfullscreen></iframe>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
(function(){
  var WAS_BUSTED = /[?&]v=/.test(location.search);   // 進站當下就記住，之後網址會被清掉
  function busted(){ return WAS_BUSTED; }
  var D = JSON.parse(document.getElementById('payload').textContent);
  var gate = document.getElementById('gate'), pw = document.getElementById('pw'),
      go = document.getElementById('go'), err = document.getElementById('err'),
      frame = document.getElementById('frame');

  function b2a(b64){ var s=atob(b64), u=new Uint8Array(s.length);
    for(var i=0;i<s.length;i++) u[i]=s.charCodeAt(i); return u; }

  async function unlock(){
    var p = pw.value;
    if(!p) return;
    go.disabled = true; err.textContent = ''; go.textContent = '解密中…';
    try{
      var base = await crypto.subtle.importKey('raw', new TextEncoder().encode(p),
                    'PBKDF2', false, ['deriveKey']);
      var key = await crypto.subtle.deriveKey(
        { name:'PBKDF2', salt:b2a(D.s), iterations:D.n, hash:'SHA-256' },
        base, { name:'AES-GCM', length:256 }, false, ['decrypt']);
      var plain = await crypto.subtle.decrypt({ name:'AES-GCM', iv:b2a(D.i) }, key, b2a(D.c));
      var html = new TextDecoder().decode(plain);
      gate.style.display = 'none';
      frame.style.display = 'block';
      frame.srcdoc = html;
      frame.onload = function(){ try{ frame.contentWindow.focus(); }catch(e){} };
      try{ sessionStorage.setItem('sk', p); }catch(e){}
    }catch(e){
      // 清掉可能是舊密碼的暫存，否則下次進來又自動試一次錯的
      try{ sessionStorage.removeItem('sk'); }catch(_){}
      go.disabled = false; go.textContent = '解鎖';
      if (!busted()) {
        err.innerHTML = '密碼不對。若剛換過密碼，你手上可能是瀏覽器的舊版快取 &mdash; ' +
                        '<a href="#" id="rl" style="color:#7aa2ff">載入最新版再試</a>';
        var rl = document.getElementById('rl');
        if (rl) rl.onclick = function(ev){
          ev.preventDefault();
          location.replace(location.pathname + '?v=' + Date.now());
        };
      } else {
        err.textContent = '密碼不對。這已經是最新版了。';
      }
      pw.select();
    }
  }


  go.onclick = unlock;
  pw.addEventListener('keydown', function(e){ if(e.key === 'Enter') unlock(); });
  // 同一分頁內解過一次就不用再輸入（關掉分頁就失效）
  try{
    var saved = sessionStorage.getItem('sk');
    if(saved){ pw.value = saved; unlock(); }
  }catch(e){}
  // 網址帶了避開快取的參數就把它藏起來，分享連結時不會帶著走
  if (busted() && history.replaceState) {
    try{ history.replaceState(null, '', location.pathname); }catch(e){}
  }
})();
</script>
</body>
</html>
"""


def wrap(plaintext: str, password: str, title: str) -> str:
    payload = encrypt(plaintext, password)
    return (SHELL
            .replace("__TITLE__", html_mod.escape(title or "私密內容"))
            .replace("__PAYLOAD__", json.dumps(payload)))


# ─────────────────────────── 私密區管理介面 ───────────────────────────
INDEX_CSS = """
 :root{ --bg:#0f1115; --fg:#e8eaed; --mut:#9aa0a6; --card:#171a20; --line:#272b33; --acc:#7aa2ff; }
 *{ box-sizing:border-box; }
 body{ margin:0; background:var(--bg); color:var(--fg);
   font:16px/1.6 "PingFang TC","Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif; }
 .wrap{ max-width:860px; margin:0 auto; padding:44px 20px 70px; }
 h1{ font-size:24px; margin:0 0 5px; }
 .sub{ color:var(--mut); font-size:13.5px; margin:0 0 28px; }
 .grid{ display:grid; gap:11px; }
 .card{ display:flex; flex-direction:column; gap:5px; padding:17px 19px; background:var(--card);
   border:1px solid var(--line); border-radius:12px; text-decoration:none; color:inherit; }
 .card:hover{ border-color:var(--acc); }
 .t{ font-weight:600; font-size:16.5px; }
 .m{ color:var(--mut); font-size:12.5px; }
 .empty{ color:var(--mut); }
 code{ background:var(--line); padding:2px 6px; border-radius:5px; font-size:13px; }
 footer{ margin-top:34px; color:var(--mut); font-size:12.5px;
   border-top:1px solid var(--line); padding-top:14px; }
"""


def private_index_html(rows: list[tuple[str, dict]], stamp: str) -> str:
    """rows: [(slug, {title,date,size}), ...] 已排序。回傳未加密的管理介面 HTML。"""
    if rows:
        cards = "\n".join(
            '<a class="card" href="{s}.html"><span class="t">{t}</span>'
            '<span class="m">{d} &middot; {k} KB</span></a>'.format(
                s=html_mod.escape(slug),
                t=html_mod.escape(info.get("title") or slug),
                d=html_mod.escape(info.get("date", "")),
                k=info.get("size", 0) // 1024)
            for slug, info in rows)
    else:
        cards = ('<p class="empty">私密區還是空的。'
                 '用 <code>pubslide 檔案.html --private</code> 放東西進來。</p>')

    return (
        '<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>私密簡報</title><style>' + INDEX_CSS + '</style></head><body><div class="wrap">'
        '<h1>&#128274; 私密簡報</h1>'
        '<p class="sub">共 ' + str(len(rows)) + ' 份 &middot; 更新於 ' + html_mod.escape(stamp) + '</p>'
        '<div class="grid">' + cards + '</div>'
        '<footer>每一份都獨立加密，用同一組密碼。真正機密的東西（合約、報價、財務）請走 Google Drive。</footer>'
        '</div></body></html>')


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--set-password":
        save_password(sys.argv[2])
        print(f"密碼已存到 {PW_FILE}（權限 600，不會進 repo）。強度：{strength_note(sys.argv[2])}")
    else:
        print(__doc__)
