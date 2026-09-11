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

## 換一台機器

```bash
gh auth login                                              # 帳號 gjj22622
git clone https://github.com/gjj22622/slides.git ~/slides
bash ~/slides/setup.sh                                     # Windows: powershell -File setup.ps1
```

設定完再做兩件事：
1. 私密區密碼：從舊機器複製 `~/.config/slides/password`，或 `pubslide --set-password '新密碼'`
2. 讓 AI 知道要自動發佈：把 `claude-rule.md` 裡的規則貼到 `~/.claude/CLAUDE.md`

