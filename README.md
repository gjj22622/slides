# slides — Jacky 的 HTML 簡報公開空間

任何 .html 簡報丟進 `decks/`，push 後即得公開網址。

- 首頁：https://gjj22622.github.io/slides/
- 單頁：https://gjj22622.github.io/slides/decks/<slug>.html

發佈方式（三選一）：
1. Telegram 傳 .html 檔給薇姐（@candoanyjobbot），她回你公開網址
2. 終端機 `pubslide 檔案.html "標題"`
3. 手動放進 `decks/` 後 `python3 publish.py --reindex && git push`

⚠️ 這個 repo 是公開的。客戶機密簡報請放 Google Drive，不要放這裡。
私密簡報用 `pubslide 檔案.html --private`，內容會真加密，要密碼才看得到。

## 要找某一份簡報

| 你是 | 用這個 |
|---|---|
| 人 | [首頁](https://gjj22622.github.io/slides/) — 依域分類的卡片＋即時搜尋 |
| AI 助理 | [`CATALOG.md`](https://raw.githubusercontent.com/gjj22622/slides/main/CATALOG.md) — 每份的標題、摘要、大綱、網址，讀這一個檔就夠 |
| 程式 | [`index.json`](https://gjj22622.github.io/slides/index.json) — 同樣資料的結構化版本 |

三個都由 `publish.py` 自動產生，發佈時同步更新，不要手動編輯。
`llms.txt` 是給 AI 工具的入口，指向上面兩個。

**簡報可以自己描述自己**——在 `<head>` 裡寫這幾行，目錄就會照你寫的收：

```html
<meta name="description" content="一句話說這份在講什麼。">
<meta name="keywords"    content="TBSA, 認證, 企業合作">
<meta name="deck-category" content="對外簡介">
<meta name="deck-audience" content="企業／業界">
<meta name="deck-kind"     content="slides">
```

沒寫也沒關係：摘要會從內文第一段抓，大綱從各級標題抓，類型自己判斷。
分類（域／群組／說明）另外寫在 `decks-meta.json`，沒寫的會列進「未分類」提醒補。

私密簡報在公開目錄裡只出現 slug 與網址，不列標題與摘要。
要查私密簡報：本機跑 `pubslide --list`，或看 `private-src/CATALOG.md`（不進 repo，需密碼才建得出來）。

## 換一台機器

```bash
gh auth login                                              # 帳號 gjj22622
git clone https://github.com/gjj22622/slides.git ~/slides
bash ~/slides/setup.sh                                     # Windows: powershell -File setup.ps1
```

設定完再做兩件事：
1. 私密區密碼：從舊機器複製 `~/.config/slides/password`，或 `pubslide --set-password '新密碼'`
2. 讓 AI 知道要自動發佈：把 `claude-rule.md` 裡的規則貼到 `~/.claude/CLAUDE.md`

