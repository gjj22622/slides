# 給 AI 的全域規則（複製到 `~/.claude/CLAUDE.md` 最後面）

> `~/.claude/CLAUDE.md` 沒有版本控制，換機器不會自動跟著走。
> 這份檔案就是那段規則的正本，新機器裝好後把下面整段貼進去，AI 才知道要自動發佈。
>
> 貼上指令（macOS / Linux / WSL2）：
> ```bash
> sed -n '/^## HTML 簡報自動發佈規則/,$p' ~/slides/claude-rule.md >> ~/.claude/CLAUDE.md
> ```
> Windows PowerShell：
> ```powershell
> $r = Get-Content "$HOME\slides\claude-rule.md" -Raw
> $r.Substring($r.IndexOf("## HTML 簡報自動發佈規則")) | Add-Content "$HOME\.claude\CLAUDE.md"
> ```

---

## HTML 簡報自動發佈規則

**簡報一律做成單檔 HTML（不用 pptx）。做完立刻發佈，回覆時附上公開網址。不等 Jacky 要求。**

- 指令：`pubslide <檔案.html> --title "標題"`（約 30–90 秒，會等到網址真的可開才回報）
- 公開空間：https://gjj22622.github.io/slides/ ｜ 本機 `~/slides/`
- 房型範本：`~/slides/decks/_template.html`（複製改標題就開工；舞台鎖定跨螢幕、O 總覽、N 講者備忘、P 出 PDF）
- 方法論：`~/jacky-wiki/wiki/ailab/patterns/HTML簡報製作法.md`
- 設計深水區（動畫、互動原型、20 種設計哲學、匯出 pptx）：`huashu-design` skill
- 其他指令：`pubslide --list` 清單、`pubslide --unpublish <slug>` 撤下

**公開區 vs 私密區**

| | 指令 | 網址 | 誰看得到 |
|---|---|---|---|
| 公開 | `pubslide 檔案.html` | `/slides/decks/<slug>.html` | 任何拿到連結的人 |
| 私密 | `pubslide 檔案.html --private` | `/slides/p/<slug>.html` | 要輸入密碼；內容以 AES-256-GCM 真加密 |

- 私密區密碼在 `~/.config/slides/password`（600，不進 repo）。換密碼：`pubslide --set-password '新密碼'`（換完既有簡報要重發一次才會用新密碼）。
- **不要把密碼寫進任何回覆、檔案或訊息**。要給對方時叫 Jacky 自己傳。
- 私密區管理介面 `/slides/p/` 本身也加密，解鎖後才看得到有哪些簡報。

**判斷該放哪一區**
- 公開：教材、方法論、對外分享、社群素材。
- 私密：提案草稿、內部討論、還沒定案的東西——**不想被搜到、但給連結加密碼就能看**。
- **都不要放**：合約、報價單、財務、客戶機密（Muzopet、旺德等）。這些走 Google Drive 權限管控，並跟 Jacky 說一句為什麼。不確定就先問他。

理由：密文本身是公開檔案，密碼夠強才安全；拿到密碼的人也可以轉發解密後的內容。私密區擋的是「被搜到、被路過的人看到」，不是「對方存心外流」。

**其他相關**
- 不只簡報：任何要跨裝置給人看的 HTML 產出（報告、儀表板、原型）都適用同一條管線。
- Jacky 人在外面時，也可以直接把 .html 檔傳給薇姐（@candoanyjobbot），她會發佈並回網址。
- 做完視覺類的東西，**先用瀏覽器實際渲染截圖檢查再交件**，不要憑推測說「做好了」。這台若裝了 Playwright 就用它截圖自檢（`pip install playwright && playwright install chromium`）。
