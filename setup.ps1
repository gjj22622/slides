# 新機器安裝（Windows PowerShell）：把這台機器接上 HTML 簡報發佈管線。
# 用法：
#   git clone https://github.com/gjj22622/slides.git $HOME\slides
#   powershell -ExecutionPolicy Bypass -File $HOME\slides\setup.ps1

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ok = 0; $warn = 0; $fail = 0

function Pass($m) { Write-Host "  [OK]   $m" -ForegroundColor Green;  $script:ok++ }
function Note($m) { Write-Host "  [注意] $m" -ForegroundColor Yellow; $script:warn++ }
function Bad($m)  { Write-Host "  [缺]   $m" -ForegroundColor Red;    $script:fail++ }

Write-Host "== HTML 簡報發佈管線 安裝檢查 =="
Write-Host "工作目錄：$Root`n"

# 1. Python
Write-Host "1. Python 3"
$py = $null
foreach ($c in @('python', 'python3', 'py')) {
  $exe = Get-Command $c -ErrorAction SilentlyContinue
  if ($exe) {
    $v = & $c --version 2>&1
    if ("$v" -match 'Python 3') { $py = $c; Pass "$v（指令：$c）"; break }
  }
}
if (-not $py) { Bad "找不到 Python 3。裝這個：https://www.python.org/downloads/ （安裝時勾選 Add Python to PATH）"; $py = 'python' }

# 2. cryptography
Write-Host "2. cryptography（私密區加密用）"
& $py -c "import cryptography" 2>$null
if ($LASTEXITCODE -eq 0) {
  $cv = & $py -c "import cryptography;print(cryptography.__version__)" 2>$null
  Pass "已安裝 $cv"
} else {
  Note "未安裝。公開發佈不受影響，要用私密區才需要。安裝指令："
  Write-Host "     $py -m pip install --user cryptography"
}

# 3. git 與 gh
Write-Host "3. git 與 GitHub CLI"
if (Get-Command git -ErrorAction SilentlyContinue) { Pass (git --version) }
else { Bad "找不到 git：https://git-scm.com/download/win" }

if (Get-Command gh -ErrorAction SilentlyContinue) {
  Pass ((gh --version) -split "`n")[0]
  gh auth status 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $who = gh api user -q .login 2>$null
    Pass "已登入 GitHub（$who）"
    gh auth setup-git 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Pass "git 憑證已設定（push 不會再問密碼）" }
    else { Note "gh auth setup-git 沒跑成功，push 可能會要求帳密" }
  } else {
    Bad "尚未登入。跑：gh auth login   （選 GitHub.com -> HTTPS -> 用瀏覽器登入，帳號 gjj22622）"
  }
} else {
  Bad "找不到 gh：winget install GitHub.cli"
}

# 4. pubslide 指令
Write-Host "4. pubslide 指令"
$bin = Join-Path $HOME 'bin'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
$cmd = Join-Path $bin 'pubslide.cmd'
"@echo off`r`n`"$py`" `"$Root\publish.py`" %*" | Set-Content -Encoding ASCII $cmd
Pass "已建立 $cmd"
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($userPath -split ';' -contains $bin) {
  Pass "$bin 已在 PATH 上"
} else {
  [Environment]::SetEnvironmentVariable('Path', "$bin;$userPath", 'User')
  Note "$bin 已加進 PATH，請關掉這個視窗重開一個新的 PowerShell 才會生效"
}

# 5. 私密區密碼
Write-Host "5. 私密區密碼"
$pwFile = Join-Path $HOME '.config\slides\password'
if (Test-Path $pwFile) {
  Pass "密碼檔已存在"
} else {
  Note "還沒有密碼檔。只發公開簡報可以略過。要用私密區就二選一："
  Write-Host "     (a) 從舊機器複製 ~/.config/slides/password 到 $pwFile"
  Write-Host "     (b) 設一組新的：pubslide --set-password '你的密碼'"
  Write-Host "         注意：換密碼後，已發佈的私密簡報要重發一次才會用新密碼。"
}

# 6. 連線測試
Write-Host "6. 連線測試"
git -C $Root ls-remote origin 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "能連到 GitHub repo" }
else { Bad "連不到 repo。確認 gh auth login 做完了。" }

Write-Host "`n== 結果：$ok 項通過、$warn 項提醒、$fail 項要處理 =="
if ($fail -eq 0) {
  Write-Host "`n接著驗證（應該列出已發佈的簡報）："
  Write-Host "  pubslide --list"
  Write-Host "`n發佈一份："
  Write-Host "  pubslide 你的簡報.html --title `"標題`""
  Write-Host "`n範本在 $Root\decks\_template.html，複製改標題就開工。"
} else {
  Write-Host "`n先把上面 [缺] 的項目處理完，再跑一次這個腳本。"
}
