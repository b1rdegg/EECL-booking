import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. 連接 Google Sheets 設定 ---
# 設定 Scope
SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 
         'https://www.googleapis.com/auth/drive']

"""112"""
@st.cache_resource
def init_connection():
    """初始化與 Google Sheets 的連線"""
    # 從 Streamlit Secrets 讀取憑證
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], SCOPE)
    return gspread.authorize(creds)

def get_data():
    """讀取 Google Sheet 資料"""
    client = init_connection()
    # 請將下方的 'lab_booking_data' 改成你的 Google Sheet 名稱
    sheet = client.open("lab_booking_data").sheet1 
    data = sheet.get_all_records()
    return data

def add_booking(date, time, user, prof):
    """寫入資料到 Google Sheet"""
    client = init_connection()
    sheet = client.open("lab_booking_data").sheet1
    # 寫入一行新資料: date, time, user, prof, status
    sheet.append_row([date, time, user, prof, "booked"])

# --- 2. 頁面設定 ---
st.set_page_config(page_title="實驗室儀器預約系統", layout="wide")
st.title("🧪 EECL儀器預約系統")

# --- 3. 讀取最新資料 ---
try:
    # 嘗試從 Google Sheets 抓取資料
    existing_bookings = get_data()
    df_bookings = pd.DataFrame(existing_bookings)
except Exception as e:
    st.error("無法連接資料庫，請檢查 Secrets 設定或是 Sheet 名稱是否正確。")
    st.stop()

# --- 4. 定義常數與顏色 ---

TIME_SLOTS = [
    "0", "1", "2", "3", "4", "5", "6",
    "7", "8", "9", "10", "11", "12", 
    "13", "14", "15", "16", "17", "18", 
    "19", "20", "21", "22", "23", "24"]

COLOR_MAP = {
    "呂宗昕": "background-color: #9b59b6; color: white;",
    "陳嘉晉": "background-color: #a04000; color: white;",
    "tan":    "background-color: #f1c40f; color: black;",
    "其他":    "background-color: #2ecc71; color: white;",
    "FREE":   "background-color: #ffffff; color: black;",
    "PAST":   "background-color: #FFFF00; color: yellow;",
}

# --- 5. 核心邏輯函式 ---
def get_week_dates(base_date):
    start_of_week = base_date - timedelta(days=(base_date.weekday() + 1) % 7)
    return [start_of_week + timedelta(days=i) for i in range(7)]

def style_dataframe(val):
    val_str = str(val)
    if "已過" in val_str: return COLOR_MAP["PAST"]
    elif "點此預約" in val_str: return COLOR_MAP["FREE"]
    elif "呂宗昕" in val_str: return COLOR_MAP["呂宗昕"]
    elif "陳嘉晉" in val_str: return COLOR_MAP["陳嘉晉"]
    elif "tan" in val_str: return COLOR_MAP["tan"]
    elif "其他" in val_str: return COLOR_MAP["其他"]
    return ""

# --- 6. 介面與顯示 ---
col1, col2 = st.columns([2, 1])
with col1:
    selected_date = st.date_input("選擇日期", datetime.now())

week_dates = get_week_dates(selected_date)
week_headers = [d.strftime("%m/%d\n(%a)") for d in week_dates]
week_date_strs = [d.strftime("%Y-%m-%d") for d in week_dates]

# 準備矩陣
df_grid = pd.DataFrame(index=TIME_SLOTS, columns=week_headers)
current_time = datetime.now()

for col_idx, date_str in enumerate(week_date_strs):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    header = week_headers[col_idx]
    
    for time_slot in TIME_SLOTS:
        cell_content = "點此預約"
        
        # 1. 檢查過期
        if date_obj.date() < current_time.date():
            cell_content = "已過"
        else:
            # 2. 檢查 Google Sheet 資料
            # 篩選符合日期與時間的資料
            if not df_bookings.empty:
                # 確保 date 欄位是字串比對
                matched = df_bookings[
                    (df_bookings['date'].astype(str) == date_str) & 
                    (df_bookings['time'] == time_slot)
                ]
                if not matched.empty:
                    record = matched.iloc[0]
                    cell_content = f"{record['user']}\n({record['prof']})\n已借閱"

        df_grid.at[time_slot, header] = cell_content

st.subheader("預約狀況表")
st.dataframe(df_grid.style.map(style_dataframe), height=400, use_container_width=True)

# --- 7. 預約表單 ---
st.divider()
st.header("📝 新增預約")

with st.form("booking_form"):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_input = st.date_input("預約日期")
    with c2:
        time_input = st.selectbox("預約時段", TIME_SLOTS)
    with c3:
        user_input = st.text_input("姓名")
    with c4:
        prof_input = st.selectbox("指導教授", ["呂宗昕", "陳嘉晉", "tan", "其他"])
    
    submitted = st.form_submit_button("送出預約")
    
    if submitted:
        # 簡單防呆：檢查是否已預約
        is_booked = False
        if not df_bookings.empty:
            check = df_bookings[
                (df_bookings['date'].astype(str) == date_input.strftime("%Y-%m-%d")) & 
                (df_bookings['time'] == time_input)
            ]
            if not check.empty:
                is_booked = True

        if is_booked:
            st.error("該時段已被預約！請重新整理頁面。")
        elif user_input == "":
            st.warning("請輸入姓名！")
        else:
            # 寫入 Google Sheet
            add_booking(date_input.strftime("%Y-%m-%d"), time_input, user_input, prof_input)
            st.success("預約成功！")
            # 清除快取並重新執行以顯示最新資料
            st.cache_resource.clear()
            st.rerun()