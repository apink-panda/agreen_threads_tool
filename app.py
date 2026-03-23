import streamlit as st
import pandas as pd
import requests
import io
import time
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------- 核心 API 函數 ----------------- #

import json
import os

def load_config():
    # 優先嘗試從 Streamlit Cloud Secrets 讀取設定
    try:
        if "google_sheet_url" in st.secrets and "admin_username" in st.secrets:
            return {
                "google_sheet_url": st.secrets["google_sheet_url"],
                "admin_username": st.secrets["admin_username"]
            }
    except Exception:
        pass
        
    # 本機測試時回退到讀取實體檔案
    config_path = "config.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

APP_CONFIG = load_config()
GOOGLE_SHEET_URL = APP_CONFIG.get("google_sheet_url", "")
ADMIN_USERNAME = APP_CONFIG.get("admin_username", "yung_hsin_c")

def get_gsheet():
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 優先嘗試從 Streamlit Cloud Secrets 讀取 (不需上傳檔案)
    has_secret = False
    try:
        if "gcp_service_account_json" in st.secrets:
            has_secret = True
    except Exception:
        pass

    if has_secret:
        import json
        creds_dict = json.loads(st.secrets["gcp_service_account_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
    else:
        # 若本機端測試，則讀取同資料夾底下的 json 檔案
        creds = ServiceAccountCredentials.from_json_keyfile_name('apink-panda-b681970b9c7c.json', scopes)
        
    client = gspread.authorize(creds)
    sheet = client.open_by_url(GOOGLE_SHEET_URL)
    return sheet.get_worksheet(0)

def fetch_my_threads(access_token):
    """取得自己的最新貼文"""
    url = "https://graph.threads.net/v1.0/me/threads"
    params = {
        "fields": "id,text,timestamp,permalink",
        "access_token": access_token,
        "limit": 50
    }
    response = requests.get(url, params=params)
    res_json = response.json()
    
    if response.status_code == 200:
        return res_json.get("data", [])
    else:
        error_msg = res_json.get("error", {}).get("message", "Unknown error")
        st.error(f"取得貼文失敗: {error_msg}")
        return []

def fetch_thread_replies(media_id, access_token):
    """取得特定貼文的所有留言"""
    url = f"https://graph.threads.net/v1.0/{media_id}/replies"
    all_replies = []
    params = {
        "fields": "id,text,username,timestamp",
        "access_token": access_token,
        "limit": 100
    }
    
    while url:
        response = requests.get(url, params=params)
        res_json = response.json()
        
        if response.status_code == 200:
            data = res_json.get("data", [])
            all_replies.extend(data)
            paging = res_json.get("paging", {})
            next_url = paging.get("next")
            url = next_url
            params = None
        else:
            error_msg = res_json.get("error", {}).get("message", "Unknown error")
            st.error(f"API錯誤: {error_msg}")
            break
            
    return all_replies

def fetch_reply_to_comment(comment_id, access_token):
    """取得針對某則留言的『下一層回覆』(通常是主辦方的序號回覆)"""
    url = f"https://graph.threads.net/v1.0/{comment_id}/replies"
    params = {
        "fields": "text,username",
        "access_token": access_token,
        "limit": 1
    }
    res = requests.get(url, params=params)
    if res.status_code == 200:
        data = res.json().get("data", [])
        if data:
            return data[0].get("username", ""), data[0].get("text", "")
    elif res.status_code == 429:
        pass
    return "", ""

# ----------------- UI 介面設計 ----------------- #
st.set_page_config(page_title="Threads 應援抽獎工具 ☁️ 雲端版", page_icon="🎁", layout="wide")

st.title("🎁 Threads 應援抽獎留言整理工具")
st.markdown("一站式完成 **得獎名單連線拉取** 與 **現場防重複發放系統**！全部資料與 **Google Sheets 雙向同步**！")

tab1, tab2 = st.tabs(["📝 整理與產生得獎名單", "📱 現場掃碼發放區 ☁️"])

with tab1:
    st.info("在這個頁面中，您可以使用 Meta API 自動抓取 Threads 留言，並直接推送到您的 Google Sheets 作為最基礎的名單庫。")
    # --- 1. 設定 Token ---
    st.header("1. API 授權設定")
    with st.expander("如何取得 Meta Threads Access Token?", expanded=False):
        st.markdown('''
        **步驟指南：**
        1. 前往 **[Meta for Developers](https://developers.facebook.com/)** 註冊開發者帳號。
        2. 點擊右上角「我的應用程式」>「建立應用程式」> 選擇以「允許用戶使用其 Threads 帳號登入...」為目標。
        3. 在應用程式設定中添加 **Threads API** 產品。
        4. 運用 User Token Generator 產生一組給自己帳號使用的 **User Access Token** (建議產生 60 天長效型)。
        5. 複製 Token 並直接貼在下方的輸入框。
        ''')

    with st.expander("🔄 實用工具：將短效 Token 轉換為 60 天長效 Token", expanded=False):
        st.info("如果您剛在 Meta 後台產生的 Token 只有 1 小時效期，可以在這裡換成 60 天的長效 Token。之後請把換出來的這串寫進 `st.secrets` 裡 (變數名稱取名為 `threads_access_token`)，或是每次手動貼在下方都可以。")
        app_secret_input = st.text_input("1. 輸入您的 Meta App Secret (應用程式密鑰)", type="password", help="可在 Meta 開發者後台「應用程式設定 > 基本資料」找到")
        short_token_input = st.text_input("2. 輸入剛剛拿到的短效 Token", type="password")
        
        if st.button("🚀 換取 60 天長效 Token"):
            if app_secret_input and short_token_input:
                exchange_url = "https://graph.threads.net/access_token"
                exchange_params = {
                    "grant_type": "th_exchange_token",
                    "client_secret": app_secret_input.strip(),
                    "access_token": short_token_input.strip()
                }
                with st.spinner("正在與 Meta 伺服器交換 Token..."):
                    try:
                        ex_res = requests.get(exchange_url, params=exchange_params)
                        ex_json = ex_res.json()
                        if ex_res.status_code == 200:
                            long_token = ex_json.get("access_token")
                            expires_in = ex_json.get("expires_in", 0)
                            days = expires_in // (24 * 3600)
                            st.success(f"✅ 成功！這是你的全新 Token (效期約 {days} 天)")
                            st.code(long_token, language="text")
                            st.info("☝️ 請點擊上方黑框右上角的「複製圖示」將 Token 複製下來。")
                        else:
                            error_msg = ex_json.get("error", {}).get("message", "Unknown error")
                            st.error(f"❌ 轉換失敗：{error_msg}")
                    except Exception as e:
                        st.error(f"❌ 發生錯誤：{str(e)}")
            else:
                st.warning("⚠️ 請先輸入 App Secret 與短效 Token")

    # 若 secrets 中有存 threads_access_token，則自動帶入
    default_token = ""
    try:
        if "threads_access_token" in st.secrets:
            default_token = st.secrets["threads_access_token"]
    except Exception:
        pass

    access_token = st.text_input("🔑 Threads Access Token", value=default_token, type="password", help="您的 Meta 開發者存取權杖")

    if access_token:
        if default_token and access_token == default_token:
            st.success("✅ 已自動從 st.secrets 載入您的長效 Token！")
        else:
            st.success("✅ Token 已輸入就緒！")
        
        # --- 2. 選擇貼文 ---
        st.header("2. 選擇目標貼文")
        with st.spinner("正在讀取您的貼文列表..."):
            threads_data = fetch_my_threads(access_token)
            
        if threads_data:
            thread_options = {}
            for t in threads_data:
                text_snippet = t.get('text', '無文字內容')[:30].replace('\n', ' ')
                label = f"{t.get('timestamp', '')[:10]} - {text_snippet}..."
                thread_options[label] = t['id']
                
            selected_label = st.selectbox("📝 選擇要統計的貼文", options=list(thread_options.keys()))
            selected_media_id = thread_options[selected_label]
            
            # --- 3. 設定關鍵字與抓取 ---
            st.header("3. 留言篩選與執行")
            keywords_input = st.text_input("🔍 搜尋關鍵字 (多個請用半角逗號 , 隔開，若不填則抓取全部)", placeholder="例如：排, 想要, 推, 抽")
            fetch_sub_replies = st.checkbox("一併抓取『留言底下的回覆』(例如您的發放序號)", value=True)
            
            # 初始化 session_state 來儲存解析結果，這樣操作下拉選單才不會導致畫面重整消失
            if 'parsed_data' not in st.session_state:
                st.session_state.parsed_data = None
                
            if st.button("🚀 開始極速抓取", type="primary"):
                keywords = [kw.strip() for kw in keywords_input.split(',')] if keywords_input.strip() else []
                
                with st.spinner("正在呼叫官方 API 抓取留言... 超快！"):
                    all_raw_replies = fetch_thread_replies(selected_media_id, access_token)
                    
                    valid_comments = {}
                    progress_bar = st.progress(0)
                    
                    for idx, reply in enumerate(all_raw_replies):
                        # Update progress visually
                        progress_bar.progress(min(1.0, (idx + 1) / len(all_raw_replies)))
                        
                        username = reply.get("username", "Unknown")
                        text = reply.get("text", "")
                        comment_id = reply.get("id")
                        timestamp = reply.get("timestamp", "")
                        
                        if not keywords or any(kw in text for kw in keywords):
                            if username and username not in valid_comments:
                                sub_reply_user = ""
                                sub_reply_text = ""
                                
                                # Fetch sub-reply if requested
                                if fetch_sub_replies and comment_id:
                                    # Add a tiny sleep to avoid rate limiting
                                    time.sleep(0.1)
                                    sub_reply_user, sub_reply_text = fetch_reply_to_comment(comment_id, access_token)
                                    
                                valid_comments[username] = {
                                    "帳號 (Username)": username,
                                    "時間標籤": timestamp,
                                    "留言內容 (Text)": text,
                                    "回覆留言帳號": sub_reply_user,
                                    "回覆內容": sub_reply_text
                                }
                            else:
                                # 相同粉絲的第二則留言，直接續加上去
                                valid_comments[username]["留言內容 (Text)"] += f"\n---\n{text}"
                    
                    progress_bar.empty()
                    st.session_state.parsed_data = list(valid_comments.values())
            
            # 將顯示邏輯移出 button 外，並依賴 session_state 渲染
            if st.session_state.parsed_data is not None:
                parsed_data = st.session_state.parsed_data
                
                if not parsed_data:
                    st.info("⚠️ 找不到任何符合條件的留言。")
                else:
                    # 根據 API 提供的 ISO 8601 時間字串進行倒序排序 (最新到最舊)
                    parsed_data.sort(key=lambda x: str(x.get('時間標籤', '')), reverse=True)
                    
                    # 統計數據變數
                    heart_emojis = ['❤️', '♥️', '♥']
                    only_heart_count = 0
                    only_candy_count = 0
                    both_count = 0
                    green_heart_reply_count = 0
                    
                    for item in parsed_data:
                        text = item['留言內容 (Text)']
                        reply_text = item['回覆內容']
                        
                        has_heart = any(h in text for h in heart_emojis)
                        has_candy = '🍭' in text
                        has_koala = '🐨' in text
                        
                        reward_items = []
                        if has_heart and has_candy:
                            both_count += 1
                            reward_items.append("鑰匙圈貼紙手幅")
                        elif has_heart:
                            only_heart_count += 1
                            reward_items.append("鑰匙圈貼紙")
                        elif has_candy:
                            only_candy_count += 1
                            reward_items.append("鑰匙圈貼紙")
                            
                        if has_koala:
                            reward_items.append("手幅")
                            
                        combined_reward = " + ".join(reward_items)
                        if "鑰匙圈貼紙手幅" in combined_reward and " + 手幅" in combined_reward:
                            # 鑰匙圈貼紙手幅 已經包含手幅，去重複
                            combined_reward = "鑰匙圈貼紙手幅"
                            
                        if not combined_reward:
                            combined_reward = "無對應符號"
                            
                        item['應發放物'] = combined_reward
                            
                        if '💚' in reply_text:
                            green_heart_reply_count += 1
                            
                    st.success(f"🎉 成功解析並找到 {len(parsed_data)} 個不重複的帳號！(依留言時間最新到最舊排序)")
                    
                    # 顯示統計數據
                    st.markdown("---")
                    st.subheader("📊 符號統計數據")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric(label="只有 ❤️ 的人數", value=only_heart_count, help="留言中有愛心，且沒有棒棒糖")
                    col2.metric(label="只有 🍭 的人數", value=only_candy_count, help="留言中有棒棒糖，且沒有愛心")
                    col3.metric(label="❤️ + 🍭 都有的人數", value=both_count, help="留言中兩個圖案都有")
                    col4.metric(label="作者已回覆 💚 的人數", value=green_heart_reply_count, help="您的回覆中出現過綠色愛心的人數")
                    st.markdown("---")
                    
                    # 顯示資料表
                    df = pd.DataFrame(parsed_data)
                    st.dataframe(df, width='stretch')
                    
                    # 提供上傳與下載按鈕
                    st.markdown("---")
                    st.subheader("☁️ 上傳名單至 Google 試算表")
                    st.info("按下這顆按鈕後，程式會自動尋找我們設定的 Google Sheets，並把上面這張表格完整的上傳寫入，作為活動現場的『即時發放名冊資料庫』！")
                    
                    if st.button("⬆️ 將名單同步寫入 Google 雲端試算表", type="primary"):
                        with st.spinner("正在連線並寫入 Google 試算表..."):
                            try:
                                ws = get_gsheet()
                                ws.clear()
                                # Prepare data
                                df_upload = df.copy()
                                if '是否已領取 (Claimed)' not in df_upload.columns:
                                    df_upload['是否已領取 (Claimed)'] = 'FALSE'
                                
                                data_list = [df_upload.columns.values.tolist()] + df_upload.values.tolist()
                                ws.update(values=data_list, range_name="A1")
                                st.success("✅ 名單已成功推寫至雲端 Google 表單！")
                            except Exception as e:
                                st.error(f"寫入失敗: {e}")
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sheet1')
                    
                    st.download_button(
                        label="📥 還是想備份 Excel 的話點此下載",
                        data=buffer.getvalue(),
                        file_name="threads_giveaway_api.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

with tab2:
    st.header("1. 從 Google Sheets 遠端載入發放名單")
    st.markdown("活動現場請點擊下方按鈕，直接拉取那份 Google Sheets 中的最新資訊，就算關掉網頁重開也能一秒拉回現場所有最新狀態。")
    
    if st.button("🔄 載入 / 更新雲端名單 (Fetch from Google)", type="primary"):
        with st.spinner("正在連線至 Google Sheets 遠端抓取資料庫..."):
            try:
                ws = get_gsheet()
                records = ws.get_all_records()
                if not records:
                    st.warning("⚠️ Google Sheets 中目前沒有資料，請先回到上一頁進行「上傳」。")
                else:
                    st.session_state.df_rewards = pd.DataFrame(records)
                    st.success(f"✅ 成功載入名單！共有 {len(records)} 筆紀錄。")
            except Exception as e:
                st.error(f"連線讀取失敗: {e}")
                
    if 'df_rewards' in st.session_state and not st.session_state.df_rewards.empty:
        df_rewards = st.session_state.df_rewards
        
        # 初始化發放紀錄 (本地即時呈現用)
        if 'claimed_users' not in st.session_state:
            st.session_state.claimed_users = set()
            
        st.markdown("---")
        st.header("2. 📸 手機拍下粉絲出示的 QR Code (掃描區)")
        st.info("點擊下方開關來開啟相機。如果粉絲出示了 Threads 的 QR Code，請對準拍照。需要省電時可隨時關閉相機！")
        
        # 覆寫相機視窗原本受限的寬度尺寸，強制100%滿版
        st.markdown("""
        <style>
        [data-testid="stCameraInput"] > div > div > video, 
        [data-testid="stCameraInput"] > div > div > img {
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        enable_camera = st.toggle("📷 開啟相機掃描", value=False)
        camera_image = None
        if enable_camera:
            camera_image = st.camera_input("📸 請對準粉絲 QR Code 點擊拍照（可點右上角 🔁 切換鏡頭）")
        
        st.markdown("---")
        st.subheader("✍️ 備用：手動輸入帳號驗證")
        manual_username = st.text_input("如果相機一直無法掃描（例如螢幕碎裂、嚴重反光），請直接在此輸入該粉絲的 Threads 帳號 (按 Enter 送出)", placeholder="例如：panda_lover")
        
        target_username = None
        
        # 1. 判斷來源 (手動優先，相機其次)
        if manual_username.strip():
            target_username = manual_username.strip()
            
        elif camera_image is not None:
            from PIL import Image, ImageOps, ImageEnhance
            from pyzbar.pyzbar import decode
            import re
            
            try:
                # 影像處理
                img = Image.open(camera_image)
                
                # 自動修正 iOS 手機相機常見的 EXIF 旋轉問題
                img = ImageOps.exif_transpose(img)
                
                # 轉成灰階並加強對比度，讓條碼更清晰
                img_gray = img.convert('L')
                enhancer = ImageEnhance.Contrast(img_gray)
                img_enhanced = enhancer.enhance(2.0)
                
                # 第一波掃描 (正常白底黑線)
                decoded_objects = decode(img_enhanced)
                
                # 第二波掃描 (深色模式/黑底白線) 
                if not decoded_objects:
                    img_inverted = ImageOps.invert(img_gray)
                    enhancer_inv = ImageEnhance.Contrast(img_inverted)
                    img_inv_enhanced = enhancer_inv.enhance(2.0)
                    decoded_objects = decode(img_inv_enhanced)
                
                # 第三波掃描 如果都失敗，退回使用純色修正原圖再掃一次
                if not decoded_objects:
                    decoded_objects = decode(img)
                
                if not decoded_objects:
                    st.error("❌ 無法辨識圖片中的 QR Code，請對焦清楚再拍一次（或者是直接在下方手動輸入帳號）！")
                else:
                    # 取得掃描到的內容
                    data = decoded_objects[0].data.decode('utf-8')
                    match = re.search(r'[@]([\w._]+)', data)
                    if match:
                        target_username = match.group(1)
                    else:
                        st.error(f"❌ 掃描到的不是有效的 Threads 帳號網址！({data})")
            except Exception as e:
                st.error(f"處理照片時發生錯誤: {e}")

        # ----------------- 2. 統一驗證核心邏輯 ----------------- #
        if target_username:
            st.subheader(f"👤 準備驗證：@{target_username}")
            
            # 在資料表中尋找該帳號
            if '帳號 (Username)' not in df_rewards.columns:
                st.error("❌ 雲端資料庫的格式錯誤，找不到「帳號 (Username)」欄位！")
            else:
                user_row = df_rewards[df_rewards['帳號 (Username)'] == target_username]
                
                if user_row.empty:
                    st.error("❌ 此帳號不在得獎的雲端名單中！")
                else:
                    # 檢查是否獲得綠心 (💚) 回覆
                    reply_text = str(user_row.iloc[0].get('回覆內容', ''))
                    # 解析雲端同步的已領取狀態
                    is_claimed_gsheet = str(user_row.iloc[0].get('是否已領取 (Claimed)', 'FALSE')).upper() == 'TRUE'
                    
                    if target_username != ADMIN_USERNAME and '💚' not in reply_text:
                        st.warning("⚠️ 此帳號雖然有留言，但作者並未以 💚 回覆，不符合領取資格喔！")
                    else:
                        # 檢查是否已領取過 (本地紀錄 或 遠端 Google 表單為 TRUE)
                        if target_username in st.session_state.claimed_users or is_claimed_gsheet:
                            st.error(f"🛑 @{target_username} 您已經領取過應援物了，給別人機會領囉！")
                        else:
                            reward_str = user_row.iloc[0].get('應發放物', '應援物')
                            if target_username == ADMIN_USERNAME:
                                st.success(f"🎉 測試帳號通關！主辦方 @{target_username} 無需綠心審核！\n\n### 🎁 測試發放物件：【 {reward_str} 】")
                            else:
                                st.success(f"🎉 驗證成功！@{target_username} 有留言且獲得 💚 回覆！\n\n### 🎁 請發放：【 {reward_str} 】")
                            st.markdown("👇 **您發放給他後，記得一定要點下方的發放按鈕！系統會幫您寫入遠端表單。**")
                            
                            if st.button("✅ 確認發放 (打勾狀態並同步寫回 Google Sheets)", type="primary"):
                                # 更新本地
                                st.session_state.claimed_users.add(target_username)
                                st.session_state.df_rewards.loc[st.session_state.df_rewards['帳號 (Username)'] == target_username, '是否已領取 (Claimed)'] = 'TRUE'
                                
                                # 同步寫回 Google Sheets
                                with st.spinner("🔄 同步狀態至雲端 Google Sheets..."):
                                    try:
                                        ws = get_gsheet()
                                        header_row = ws.row_values(1)
                                        
                                        if '帳號 (Username)' in header_row and '是否已領取 (Claimed)' in header_row:
                                            username_col_idx = header_row.index('帳號 (Username)') + 1
                                            col_idx = header_row.index('是否已領取 (Claimed)') + 1
                                            
                                            # 從表單精準在「帳號」那一欄尋找該帳號所在的 row
                                            cell = ws.find(target_username, in_column=username_col_idx)
                                            if cell:
                                                row_num = cell.row
                                                ws.update_cell(row_num, col_idx, "TRUE")
                                                st.success("✅ 真．同步完成！已經將此人狀態更改為「TRUE」，更新到 Google Sheets 裡了！")
                                            else:
                                                st.warning("⚠️ 寫入失敗，在 Google 表單「帳號」欄位裡找不到這個帳號的儲存格。")
                                        else:
                                            st.error("找不到必須的欄位！您的 Google 表單格式不對。")
                                    except Exception as e:
                                        st.error(f"雲端連線更新失敗：{e}")
                                time.sleep(1) # 暫停讓使用者看到成功訊息
                                try:
                                    st.rerun()
                                except AttributeError:
                                    st.experimental_rerun()
                
        st.markdown("---")
        st.header("🏃 3. 現場直接發放 (無登記名單)")
        st.info("如果是現場隨機發送給沒有填表/預先留言的粉絲，可以點擊下方按鈕直接發出 1 份『手幅』。這會在 Google 表單新增一筆紀錄，以此扣抵庫存數量。")
        if st.button("🎁 現場直接發放 1 份『手幅』 (免登記)", type="secondary"):
            with st.spinner("🔄 正在寫入現場發放紀錄至 Google Sheets..."):
                try:
                    import datetime
                    ws = get_gsheet()
                    header_row = ws.row_values(1)
                    
                    timestamp_str = datetime.datetime.now().strftime("%H%M%S")
                    fake_username = f"現場直發無帳號_{timestamp_str}"
                    
                    row_to_append = [""] * len(header_row)
                    if '帳號 (Username)' in header_row:
                        row_to_append[header_row.index('帳號 (Username)')] = fake_username
                    if '應發放物' in header_row:
                        row_to_append[header_row.index('應發放物')] = "手幅"
                    if '是否已領取 (Claimed)' in header_row:
                        row_to_append[header_row.index('是否已領取 (Claimed)')] = "TRUE"
                        
                    ws.append_row(row_to_append)
                    
                    # 更新本地 DataFrame
                    new_row = {"帳號 (Username)": fake_username, "應發放物": "手幅", "是否已領取 (Claimed)": "TRUE"}
                    new_df = pd.DataFrame([new_row])
                    st.session_state.df_rewards = pd.concat([st.session_state.df_rewards, new_df], ignore_index=True)
                    
                    st.success(f"✅ 成功發放 1 份手幅！(系統產生佔位編號: {fake_username})")
                    time.sleep(1)
                    try:
                        st.rerun()
                    except AttributeError:
                        st.experimental_rerun()
                except Exception as e:
                    st.error(f"❌ 直接發放寫入失敗：{e}")

        st.markdown("---")
        st.header("📊 4. 遠端發放進度統計資料 (包含已打勾)")
        
        # 1. 計算總打勾人數
        claimed_df = df_rewards[df_rewards['是否已領取 (Claimed)'].astype(str).str.upper() == 'TRUE']
        true_count = len(claimed_df)
        
        col_a, col_b = st.columns(2)
        col_a.metric("得獎名單總人數", len(df_rewards))
        col_b.metric("雲端顯示已領取成功", true_count)
        
        # 2. 計算各品項庫存 (動態扣抵真實物資)
        count_all = len(claimed_df[claimed_df['應發放物'].astype(str).str.contains('鑰匙圈貼紙手幅', na=False)])
        count_slogan = len(claimed_df[claimed_df['應發放物'].astype(str) == '手幅'])
        count_two = len(claimed_df[claimed_df['應發放物'].astype(str) == '鑰匙圈貼紙'])
        
        # 鑰匙圈貼紙組合 總共 30 份 (只要有包含這個品項不管是大禮包還是單獨發放都會扣除)
        total_keychain = 30
        used_keychain = count_all + count_two
        
        # 手幅 總共 60 份 (不管是不是透過大禮包發出，只要發出手幅就算一份)
        total_slogan = 60
        used_slogan = count_all + count_slogan
        
        st.markdown("### 📦 現場實體物資庫存倒數")
        
        st.warning(f"🔰 **鑰匙圈+貼紙** 總庫存：已發出 **{used_keychain}** 組 / 共 {total_keychain} 組 ➔ (剩下 **{total_keychain - used_keychain}** 組) \n\n*(包含大禮包扣除量)*")
        st.info(f"🧣 **手幅** 總庫存：已發出 **{used_slogan}** 份 / 共 {total_slogan} 份 ➔ (剩下 **{total_slogan - used_slogan}** 份) \n\n*(包含大禮包扣除量)*")
