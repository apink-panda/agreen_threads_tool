# 🎁 Threads 應援抽獎留言整理與現場掃碼工具

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)

這是一款專為 Threads 創作者設計的「活動應援物發放神器」。從前期的**活動留言抓取、留言符號分析**，到線下活動現場的**手機 QR Code 掃碼驗證與庫存發放**，達成真正的一站式無紙化雲端雙向同步系統！

## ✨ 核心亮點功能

1. **Meta 官方 API 極速抓取** ⚡  
   支援直接串接 Threads (Meta) 的 User Access Token，一鍵讀取目標貼文的所有留言資訊，還能自訂要篩選的特定留言關鍵字（抽、包場、推...等等）。

2. **智慧符號解析與自動配給庫存** 🍬❤️🐨  
   讀取粉絲留言內的各種特定表符（如愛心、棒棒糖、無尾熊），自動換算成「對應要發放的應援物組別」（例如：鑰匙圈、手幅、大禮包組合）。

3. **雙向 Google Sheets 雲端即時同步** ☁️  
   完全捨棄傳統用大腦核對 Excel 的痛苦流程，直接透過 GCP Service Account 把最新得獎清單推送上 Google 試算表。活動現場更是 100% 同步串聯該份表單。

4. **主辦方專屬 QR Code 核銷系統 (PyZbar)** 📸📱  
   直接用手機瀏覽器連線，對準粉絲出示的 Threads 帳號分享 QR Code 掃描，即刻讀取粉絲名稱。系統將自動過濾資格（是否已領取過？作者是否有回覆代表獲得資格的 💚 綠心？），並在按鈕點擊瞬間，即刻將雲端的 Google Sheets 註記為已發放 `TRUE`！
   
5. **精準動態庫存儀表板** 📦  
   畫面上即時顯示已發放數量與對應特定實體獎品（手幅／鑰匙圈等）的剩餘庫存，並會正確扣除「組合包（大禮包）」佔用的各別庫存量。

---

## 🛠️ 開發與建置要求

本專案使用 [Streamlit](https://streamlit.io/) 作為全端框架，適合部署於 **Streamlit Community Cloud**。

### 檔案結構

- `app.py`: 核心主程式（包含 Tab1: 留言抓取區、Tab2: 現場掃碼區）
- `requirements.txt`: 紀錄需安裝的 Python 套件 (`gspread`, `pyzbar` 等)
- `packages.txt`: 紀錄需安裝的 Linux 底層 C 語言編譯庫 (特別為了 PyZbar 能夠順利呼叫相機與讀取條碼的 `libzbar0` 依賴)
- `.gitignore`: 預防上傳重要資料與機密 JSON 檔案的安全鎖

---

## 🚀 如何部署至 Streamlit Cloud？

在您開心地把這份程式碼打包發布前，請確保您的 **資料庫金鑰** 有獲得妥善的保護！

### 1. 建立您的個人 Github 私有專案 (Private Repo)
為了絕對的安全，請建立一個 **Private** 的 GitHub Repository，並只上傳以下 **三個** 檔案：
✅ `app.py`
✅ `requirements.txt`
✅ `packages.txt`

❌ **絕對不要上傳** `apink-panda-xxxxxxxx.json`，這可能會讓您的 Google Cloud 權限遭到洩漏。

### 2. 對接下來的 Streamlit 部署進行 Secrets (機密環境變數) 設定
1. 前往 [Streamlit Community Cloud](https://share.streamlit.io/) 並登入。
2. 點擊 `New App`，連結到您剛才建立的 Private Repository，但在點擊 Deploy 之前，請拉到最下方的 **`Advanced settings...`**。
3. 尋找 **`Secrets`** 設定框，將您擁有的 `apink-panda-xxxxxxxx.json` 金鑰檔案的**原始內容 (全選覆制)** 作為字串貼進去：

```toml
gcp_service_account_json = '''
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE ...",
  "client_email": "..."
}
'''
```
4. 點選儲存後，按下 **Deploy** 即大功告成！

### 3. 一勞永逸的測試與發放
- 手機瀏覽器只要開啟那串 `https://...streamlit.app` 開頭的網誌，因為有 SSL 加密保護，就能100%正常授權使用鏡頭了！
- 您可以使用自己身為主辦方的 `@帳號名稱` (例如：`yung_hsin_c`) 來生產獨立的 QR Code，系統內建「天字第一號測試無敵特權」，能直接跳過 💚 留言資格審核，進入大禮包發放階段來做事前演練。

---

*Powered meticulously by pure Python, Streamlit, and Meta Graph API.*
