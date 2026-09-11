#!/usr/bin/env bash
# 新機器安裝：把這台機器接上 HTML 簡報發佈管線。
# 用法：git clone https://github.com/gjj22622/slides.git ~/slides && bash ~/slides/setup.sh
# 適用 macOS / Linux / WSL2。Windows 原生 PowerShell 請改跑 setup.ps1。
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ok=0; warn=0; fail=0
say(){ printf '%s\n' "$*"; }
pass(){ say "  ✅ $*"; ok=$((ok+1)); }
note(){ say "  ⚠️  $*"; warn=$((warn+1)); }
bad(){  say "  ❌ $*"; fail=$((fail+1)); }

say "══ HTML 簡報發佈管線 安裝檢查 ══"
say "工作目錄：$ROOT"
say ""

# 1. Python
say "1. Python 3"
if command -v python3 >/dev/null 2>&1; then
  pass "$(python3 --version)"
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c 'import sys;exit(0 if sys.version_info[0]==3 else 1)' 2>/dev/null; then
  pass "$(python --version)"
  PY=python
else
  bad "找不到 Python 3。先裝：https://www.python.org/downloads/"
  PY=python3
fi

# 2. 加密套件（只有私密區需要；公開發佈不需要）
say "2. cryptography（私密區加密用）"
if $PY -c 'import cryptography' 2>/dev/null; then
  pass "已安裝 $($PY -c 'import cryptography;print(cryptography.__version__)')"
else
  note "未安裝。公開發佈不受影響，要用私密區才需要。安裝指令："
  say "     $PY -m pip install --user cryptography"
fi

# 3. git 與 gh
say "3. git 與 GitHub CLI"
command -v git >/dev/null 2>&1 && pass "$(git --version)" || bad "找不到 git：https://git-scm.com/downloads"
if command -v gh >/dev/null 2>&1; then
  pass "$(gh --version | head -1)"
  if gh auth status >/dev/null 2>&1; then
    pass "已登入 GitHub（$(gh api user -q .login 2>/dev/null || echo '帳號讀取失敗')）"
    gh auth setup-git >/dev/null 2>&1 && pass "git 憑證已設定（push 不會再問密碼）" \
      || note "gh auth setup-git 沒跑成功，push 可能會要求帳密"
  else
    bad "尚未登入。跑：gh auth login   （選 GitHub.com → HTTPS → 用瀏覽器登入，帳號 gjj22622）"
  fi
else
  bad "找不到 gh：https://cli.github.com/"
fi

# 4. pubslide 指令
say "4. pubslide 指令"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
printf '#!/usr/bin/env bash\nexec %s "%s/publish.py" "$@"\n' "$PY" "$ROOT" > "$BIN/pubslide"
chmod +x "$BIN/pubslide"
pass "已建立 $BIN/pubslide"
case ":$PATH:" in
  *":$BIN:"*) pass "$BIN 已在 PATH 上" ;;
  *) note "$BIN 不在 PATH。把這行加進 ~/.bashrc 或 ~/.zshrc："
     say "     export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# 5. 私密區密碼
say "5. 私密區密碼"
PW="$HOME/.config/slides/password"
if [ -f "$PW" ]; then
  pass "密碼檔已存在（$(wc -c <"$PW" | tr -d ' ') bytes）"
else
  note "還沒有密碼檔。只發公開簡報可以略過。要用私密區就二選一："
  say "     (a) 從舊機器複製過來：scp 舊機器:~/.config/slides/password ~/.config/slides/password"
  say "     (b) 設一組新的：pubslide --set-password '你的密碼'"
  say "         注意：換密碼後，已發佈的私密簡報要重發一次才會用新密碼。"
fi

# 6. 連線測試
say "6. 連線測試"
if command -v git >/dev/null 2>&1; then
  if git -C "$ROOT" ls-remote origin >/dev/null 2>&1; then
    pass "能連到 GitHub repo"
  else
    bad "連不到 repo。確認 gh auth login 做完了。"
  fi
fi

say ""
say "══ 結果：$ok 項通過、$warn 項提醒、$fail 項要處理 ══"
if [ "$fail" -eq 0 ]; then
  say ""
  say "接著驗證（應該列出已發佈的簡報）："
  say "  pubslide --list"
  say ""
  say "發佈一份："
  say "  pubslide 你的簡報.html --title \"標題\""
  say ""
  say "範本在 $ROOT/decks/_template.html，複製改標題就開工。"
else
  say ""
  say "先把上面 ❌ 的項目處理完，再跑一次這個腳本。"
fi
exit 0
