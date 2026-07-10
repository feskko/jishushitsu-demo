import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random
import os
import base64
import unicodedata
import streamlit.components.v1 as components

# 日本時間の「今」を取得
jst_now = datetime.utcnow() + timedelta(hours=9)

# 講習期間の判定
def is_special_period(dt_date):
    if dt_date is None: return False
    m = dt_date.month
    d = dt_date.day
    if (m == 3 and d >= 15) or (m == 4 and d <= 7): return True
    if (m == 7 and d >= 15) or m == 8: return True
    if m == 12 or (m == 1 and d <= 7): return True
    return False

# 年間のテスト期間の定義
TEST_PERIODS = [
    (5, 11, 5, 20), (6, 21, 6, 30), (7, 1, 7, 10), (9, 1, 9, 10),
    (10, 11, 10, 20), (11, 1, 11, 10), (12, 1, 12, 10), (2, 20, 2, 29)
]

def get_period_status(dt_date):
    if dt_date is None: return "normal"
    y = dt_date.year
    curr_date = dt_date.date() if isinstance(dt_date, datetime) else dt_date
    for tm1, td1, tm2, td2 in TEST_PERIODS:
        try:
            start_date = datetime(y, tm1, td1).date()
            if tm2 == 2 and td2 == 29:
                is_leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
                end_date = datetime(y, 2, 29 if is_leap else 28).date()
            else:
                end_date = datetime(y, tm2, td2).date()
        except: continue
        before_start = start_date - timedelta(days=7)
        before_end = start_date - timedelta(days=1)
        if start_date <= curr_date <= end_date: return "test"
        elif before_start <= curr_date <= before_end: return "before_test"
    return "normal"

def learn_multipliers(df):
    default_test, default_before = 1.5, 1.2
    if df.empty: return default_test, default_before
    try:
        temp_df = df.copy()
        temp_df['date_only'] = temp_df['日付'].dt.date
        daily_users = temp_df.groupby('date_only')['名前'].nunique().reset_index()
        daily_users['status'] = daily_users['date_only'].apply(get_period_status)
        counts = daily_users.groupby('status')['名前'].agg(['mean', 'count'])
        normal_mean = counts.loc['normal', 'mean'] if 'normal' in counts.index and counts.loc['normal', 'count'] >= 5 else None
        
        test_mult = default_test
        if 'test' in counts.index and counts.loc['test', 'count'] >= 3 and normal_mean and normal_mean > 0:
            actual_mult = max(1.0, min(counts.loc['test', 'mean'] / normal_mean, 3.0))
            weight = min(counts.loc['test', 'count'] / 10.0, 1.0)
            test_mult = default_test * (1 - weight) + actual_mult * weight

        before_mult = default_before
        if 'before_test' in counts.index and counts.loc['before_test', 'count'] >= 3 and normal_mean and normal_mean > 0:
            actual_mult = max(1.0, min(counts.loc['before_test', 'mean'] / normal_mean, 2.5))
            weight = min(counts.loc['before_test', 'count'] / 10.0, 1.0)
            before_mult = default_before * (1 - weight) + actual_mult * weight
        return test_mult, before_mult
    except: return default_test, default_before

def get_time_slots_for_period(period_str):
    if period_str == "累計": return [f"{h:02d}:00" for h in range(9, 23)]
    try:
        m = int(period_str.split("年")[1].replace("月", ""))
        if m in [1, 3, 4, 7, 8, 12]: return [f"{h:02d}:00" for h in range(9, 23)]
        else: return [f"{h:02d}:00" for h in range(12, 23)]
    except: return [f"{h:02d}:00" for h in range(9, 23)]

def parse_custom_time(t_str):
    if not t_str: return None
    t_str = unicodedata.normalize('NFKC', str(t_str)).strip()
    if t_str == "" or "コマ" in t_str: return None
    if ":" in t_str:
        try: return datetime.strptime(t_str[:5], "%H:%M").time()
        except: return None
    elif t_str.isdigit() and (len(t_str) == 3 or len(t_str) == 4):
        try:
            h, m = int(t_str[:-2]), int(t_str[-2:])
            if 0 <= h <= 23 and 0 <= m <= 59: return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()
        except: return None
    return None

def calc_duration(in_time, out_time):
    def to_dt(t):
        if isinstance(t, str):
            parsed = parse_custom_time(t)
            return datetime.combine(datetime.today(), parsed) if parsed else None
        elif t is not None: return datetime.combine(datetime.today(), t)
        return None
    dt_in, dt_out = to_dt(in_time), to_dt(out_time)
    if dt_in and dt_out:
        if dt_out >= dt_in: return (dt_out - dt_in).total_seconds() / 3600.0
        else: return ((dt_out + timedelta(days=1)) - dt_in).total_seconds() / 3600.0
    return 0.0

def format_time_input(key):
    val = st.session_state.get(key, "")
    parsed = parse_custom_time(val)
    if parsed: st.session_state[key] = parsed.strftime("%H:%M")

st.set_page_config(page_title="Study Room Analytics", layout="wide")
img_b64 = ""
if os.path.exists("icon.png"):
    with open("icon.png", "rb") as f: img_b64 = base64.b64encode(f.read()).decode()

js_code = f"""
<script>
    const doc = window.parent.document;
    if ("{img_b64}" !== "") {{
        let links = doc.querySelectorAll("link[rel~='apple-touch-icon']");
        links.forEach(link => link.remove());
        let newLink = doc.createElement('link'); newLink.rel = 'apple-touch-icon'; newLink.href = 'data:image/png;base64,{img_b64}'; doc.head.appendChild(newLink);
    }}
    function formatTimeInput(target) {{
        let val = target.value; if (!val) return;
        let halfVal = val.replace(/[０-９]/g, function(s) {{ return String.fromCharCode(s.charCodeAt(0) - 0xFEE0); }});
        if (/^\d{{3,4}}$/.test(halfVal)) {{
            let h = halfVal.length === 3 ? '0' + halfVal.slice(0,1) : halfVal.slice(0,2);
            let m = halfVal.slice(-2);
            let hNum = parseInt(h, 10); let mNum = parseInt(m, 10);
            if (hNum >= 0 && hNum <= 23 && mNum >= 0 && mNum <= 59) {{
                let formatted = h + ':' + m;
                let prototype = target.tagName === 'INPUT' ? window.HTMLInputElement.prototype : window.HTMLTextAreaElement.prototype;
                let nativeInputValueSetter = Object.getOwnPropertyDescriptor(prototype, "value").set;
                if(nativeInputValueSetter) {{ nativeInputValueSetter.call(target, formatted); target.dispatchEvent(new Event('input', {{ bubbles: true }})); }}
            }}
        }}
    }}
    doc.addEventListener('keydown', function(e) {{ if (e.key === 'Enter' || e.key === 'Tab') {{ if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {{ formatTimeInput(e.target); }} }} }}, true);
    doc.addEventListener('focusout', function(e) {{ if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {{ formatTimeInput(e.target); }} }} }}, true);
</script>
"""
components.html(js_code, height=0, width=0)

st.markdown("""
<style>
    #MainMenu, header, footer, [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    .stApp { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
    
    /* Typography & Core Adjustments */
    .main-title { font-weight: 800; color: var(--text-color); letter-spacing: 0.5px; margin-bottom: 2rem; font-size: 2.2rem; }
    .section-title { font-weight: 700; color: var(--text-color); margin-top: 2.5rem; margin-bottom: 1.5rem; font-size: 1.5rem; }
    
    /* Custom UI Component overrides to adapt to Dark/Light dynamically */
    div[role="radiogroup"] { background-color: transparent; border-bottom: 2px solid rgba(128,128,128,0.2); margin-bottom: 30px; }
    div[role="radiogroup"] label { border-radius: 0; padding-bottom: 10px !important; margin-right: 20px !important; transition: 0.2s; border-bottom: 3px solid transparent; }
    div[role="radiogroup"] label[data-checked="true"] { border-bottom: 3px solid var(--primary-color); background-color: transparent; }
    div[role="radiogroup"] label[data-checked="true"] p { color: var(--text-color) !important; font-weight: 800; }
    div[role="radiogroup"] label p { color: var(--text-color); opacity: 0.6; font-weight: 600; font-size: 0.95rem; }
    
    /* Modern Table Styling for Heatmap */
    .heatmap-container { overflow-x: auto; padding-bottom: 15px; }
    .modern-table { width: 100%; border-collapse: separate; border-spacing: 3px; font-size: 0.85rem; min-width: 700px; }
    .modern-table th { background-color: var(--secondary-background-color); color: var(--text-color); padding: 12px 8px; font-weight: 600; border-radius: 6px; text-align: center; }
    .modern-table th.sticky-col { position: sticky; left: 0; z-index: 2; }
    .modern-table td { padding: 12px 8px; border-radius: 6px; text-align: center; font-weight: 700; transition: transform 0.1s; }
    .modern-table td:hover { transform: scale(1.1); z-index: 10; position: relative; }
    
    /* Ranking Card (SaaS Dashboard Style) */
    .flex-container { display: flex; gap: 24px; margin-bottom: 30px; flex-wrap: wrap; }
    .rank-card {
        background-color: var(--secondary-background-color);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        flex: 1;
        min-width: 250px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03);
        display: flex;
        flex-direction: column;
        align-items: center;
    }
    
    .rank-badge {
        display: inline-block;
        padding: 4px 16px;
        border-radius: 20px;
        font-size: 0.9rem;
        font-weight: 800;
        margin-bottom: 1rem;
        letter-spacing: 1px;
    }
    .badge-gold { background: linear-gradient(135deg, #FDE047 0%, #D97706 100%); color: #422006; box-shadow: 0 2px 10px rgba(217,119,6,0.2); }
    .badge-silver { background: linear-gradient(135deg, #F1F5F9 0%, #94A3B8 100%); color: #0F172A; box-shadow: 0 2px 10px rgba(148,163,184,0.2); }
    .badge-bronze { background: linear-gradient(135deg, #FDBA74 0%, #C2410C 100%); color: #431407; box-shadow: 0 2px 10px rgba(194,65,12,0.2); }
    .badge-normal { background: var(--primary-color); color: #FFFFFF; opacity: 0.9; }
    
    .rank-grade { font-size: 0.85rem; color: var(--text-color); opacity: 0.6; margin-bottom: 5px; font-weight: 600; }
    .rank-name { font-size: 1.8rem; font-weight: 900; color: var(--text-color); margin-bottom: auto; letter-spacing: 1px; }
    
    /* Highly Visible Time Display (Fixed Contrast) */
    .time-display {
        margin-top: auto;
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 10px 24px;
        border-radius: 8px;
        display: inline-flex;
        align-items: baseline;
        gap: 6px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .time-val { font-size: 1.8rem; font-weight: 900; color: #FFFFFF !important; }
    .time-unit { font-size: 0.9rem; font-weight: 700; color: #94A3B8 !important; }
    
    /* Metrics Override */
    div[data-testid="stMetric"] { background-color: transparent; border: none; padding: 0; box-shadow: none; }
    [data-testid="stMetricValue"] > div { font-size: 2.2rem !important; font-weight: 900 !important; }
    [data-testid="stMetricLabel"] p { font-size: 0.95rem !important; opacity: 0.7; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

if "sys_msg" not in st.session_state: st.session_state.sys_msg = None
if "sys_err" not in st.session_state: st.session_state.sys_err = None

APP_PASSWORD = "demo" 
if "authenticated" not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<div style='text-align: center; margin-top: 15vh;'><h3 style='color: var(--text-color); font-weight: 900; font-size: 2.5rem; letter-spacing: 1px;'>STUDY ROOM SYSTEM</h3><p style='color: var(--text-color); opacity: 0.5; font-weight: 600;'>DATA ANALYTICS DASHBOARD</p></div>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.8; margin-bottom: 20px;'>認証パスワードに <b>demo</b> と入力してください。</p>", unsafe_allow_html=True)
        pwd = st.text_input("パスワード", type="password", placeholder="demo", label_visibility="collapsed")
        submitted = st.form_submit_button("ログイン", type="primary", use_container_width=True)
        if submitted:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("パスワードが違います")
    st.stop()

def generate_mock_data():
    records = []
    base_date = jst_now.date() - timedelta(days=365)
    mock_students = [
        ("佐藤 健太", "高3"), ("鈴木 花子", "高3"), ("高橋 翔太", "高3"), ("田中 美咲", "高3"),
        ("伊藤 蓮", "高2"), ("渡辺 結衣", "高2"), ("山本 陽翔", "高2"), ("中村 凛", "高2"),
        ("小林 樹", "高1"), ("加藤 さくら", "高1"), ("吉田 葵", "高1"), ("山田 大樹", "高1"),
        ("佐々木 結菜", "中3"), ("山口 拓海", "中3"), ("松本 陽葵", "中3"), ("井上 陸", "中3"),
        ("木村 紬", "中2"), ("林 湊", "中2"), ("斎藤 莉子", "中2"), ("清水 蒼", "中2"),
        ("山崎 陽菜", "中1"), ("森 悠真", "中1"), ("池田 伊織", "中1"), ("橋本 結", "中1"),
        ("阿部 陽", "小6"), ("石川 澪", "小6"), ("山下 颯太", "小6"), ("中島 凪", "小6"),
        ("小川 結翔", "小5"), ("前田 陽菜乃", "小5"), ("岡田 奏太", "小5"), ("長谷川 琴音", "小5"),
        ("藤田 悠", "小4"), ("後藤 結心", "小4"), ("近藤 律", "小4"), ("村上 杏", "小4")
    ]
    for i in range(366):
        curr_date = base_date + timedelta(days=i)
        if curr_date.weekday() == 6 and random.random() < 0.8: continue
        
        status = get_period_status(curr_date)
        growth = 1.0 + (i / 365.0) * 1.5
        
        if status == "test": base_u = random.randint(10, 16)
        elif status == "before_test": base_u = random.randint(7, 12)
        else: base_u = random.randint(3, 8)
        
        num_users = min(int(base_u * growth), len(mock_students))
        daily_users = random.sample(mock_students, num_users)
        
        for name, grade in daily_users:
            in_h = random.randint(14, 19)
            if curr_date.weekday() >= 5: in_h = random.randint(10, 16)
            out_h = min(in_h + random.randint(1, 4), 22)
            in_m, out_m = random.choice(["00", "15", "30"]), random.choice(["00", "30", "45"])
            in_time_str = f"{in_h:02d}:{in_m}"
            out_time_str = f"{out_h:02d}:{out_m}"
            in_t = datetime.strptime(in_time_str, "%H:%M").time()
            out_t = datetime.strptime(out_time_str, "%H:%M").time()
            duration = calc_duration(in_t, out_t)
            records.append({
                '日付': curr_date.strftime('%Y-%m-%d'),
                '名前': name,
                '学年': grade,
                '入室時間': in_time_str,
                '退室時間': out_time_str,
                '利用時間（時間）': duration
            })
    return pd.DataFrame(records)

if "demo_df" not in st.session_state:
    st.session_state.demo_df = generate_mock_data()

def load_data():
    df = st.session_state.demo_df.copy()
    if not df.empty: 
        df['日付'] = pd.to_datetime(df['日付'])
        df['名前'] = df['名前'].astype(str).str.replace(r'[\s ]+', '', regex=True)
    return df

def save_data(df):
    if not df.empty:
        save_df = df.copy()
        save_df['日付'] = pd.to_datetime(save_df['日付']).dt.strftime('%Y-%m-%d')
        save_df = save_df.fillna("")
        st.session_state.demo_df = save_df
    else:
        st.session_state.demo_df = pd.DataFrame(columns=['日付', '名前', '学年', '入室時間', '退室時間', '利用時間（時間）'])

if "form_key" not in st.session_state: st.session_state.form_key = 0

GRADES = ["--選択--"] + [f"小{i}" for i in range(1, 7)] + [f"中{i}" for i in range(1, 4)] + [f"高{i}" for i in range(1, 4)] + ["既卒/その他"]

menu = st.radio("メニュー", ["一括入力", "1件ずつ", "ランキング", "分析", "管理"], horizontal=True, label_visibility="collapsed")

if st.session_state.sys_msg:
    st.success(st.session_state.sys_msg)
    st.session_state.sys_msg = None
if st.session_state.sys_err:
    st.error(st.session_state.sys_err)
    st.session_state.sys_err = None

df_check = load_data()
today_date = jst_now.date()
first_day = today_date.replace(day=1)
recorded_dates = set(pd.to_datetime(df_check['日付']).dt.date) if not df_check.empty else set()
missing_dates = []
curr_d = first_day
while curr_d < today_date:
    if curr_d.weekday() != 6:
        if curr_d not in recorded_dates: missing_dates.append(curr_d)
    curr_d += timedelta(days=1)

missing_warning_html = ""
if missing_dates:
    weekdays_ja = ["月", "火", "水", "木", "金", "土", "日"]
    missing_str = "、 ".join([f"{d.month}/{d.day}({weekdays_ja[d.weekday()]})" for d in missing_dates])
    missing_warning_html = f"<div style='background-color: rgba(220, 38, 38, 0.1); border-left: 4px solid #DC2626; padding: 12px 15px; border-radius: 4px; margin-bottom: 20px;'><p style='color:#DC2626; font-weight:bold; margin:0;'>[未入力アラート] 今月の未入力日: {missing_str}</p></div>"

if menu == "一括入力":
    st.markdown("<div class='main-title'>BATCH ENTRY</div>", unsafe_allow_html=True)
    if missing_warning_html: st.markdown(missing_warning_html, unsafe_allow_html=True)
    
    f_date_batch = st.date_input("利用日 (全員共通)", jst_now.date(), max_value=jst_now.date())
    if "batch_data" not in st.session_state: st.session_state.batch_data = [{"学年": "--選択--", "氏名": "", "開始時間": "", "終了時間": ""} for _ in range(25)]
    df_empty = pd.DataFrame(st.session_state.batch_data)
    
    edited_df = st.data_editor(
        df_empty,
        column_config={
            "学年": st.column_config.SelectboxColumn("学年 (必須)", options=GRADES, width="small"),
            "氏名": st.column_config.TextColumn("氏名 (必須)", width="medium"),
            "開始時間": st.column_config.TextColumn("開始時間 (例:1223)", width="small"),
            "終了時間": st.column_config.TextColumn("終了時間 (例:1530)", width="small"),
        },
        column_order=["学年", "氏名", "開始時間", "終了時間"], num_rows="dynamic", use_container_width=True, height=500, key=f"editor_{st.session_state.form_key}"
    )
    
    if st.button("表のデータをすべて保存する", type="primary", use_container_width=True):
        valid_rows = edited_df[edited_df["氏名"].str.strip() != ""]
        if valid_rows.empty: st.error("氏名が入力されている行がありません。")
        else:
            new_records, error_msgs = [], []
            df_current = load_data()
            for idx, row in valid_rows.iterrows():
                name = row["氏名"].replace(" ", "").replace(" ", "")
                grade_input = row.get("学年")
                if pd.isna(grade_input) or grade_input == "--選択--" or not grade_input:
                    error_msgs.append(f"{name}さん (学年が選択されていません)"); continue
                in_dt_time, out_dt_time = parse_custom_time(row["開始時間"]), parse_custom_time(row["終了時間"])
                if in_dt_time is None or out_dt_time is None:
                    error_msgs.append(f"{name}さん (開始・終了時間を正しく入力してください)"); continue
                if not is_special_period(f_date_batch) and in_dt_time.hour < 12:
                    error_msgs.append(f"{name}さん (通常期間は12時以降を入力してください)"); continue
                duration = calc_duration(in_dt_time, out_dt_time)
                if duration <= 0:
                    error_msgs.append(f"{name}さん (終了時間が開始時間より前になっています)"); continue
                in_str, out_str = in_dt_time.strftime("%H:%M"), out_dt_time.strftime("%H:%M")
                
                is_dup_current = not df_current[(df_current['日付'] == pd.to_datetime(f_date_batch)) & (df_current['名前'] == name) & (df_current['入室時間'] == in_str) & (df_current['退室時間'] == out_str)].empty
                is_dup_new = any(r['名前'] == name and r['入室時間'] == in_str and r['退室時間'] == out_str for r in new_records)
                if is_dup_current or is_dup_new:
                    error_msgs.append(f"{name}さん (既に同じ記録が登録されています)"); continue
                new_records.append({'日付': pd.to_datetime(f_date_batch), '名前': name, '学年': grade_input, '入室時間': in_str, '退室時間': out_str, '利用時間（時間）': duration})
            
            if error_msgs:
                for err in error_msgs: st.error(f"エラー: {err}")
            if new_records:
                df = pd.concat([df_current, pd.DataFrame(new_records)], ignore_index=True)
                save_data(df)
                st.session_state.batch_data = [{"学年": "--選択--", "氏名": "", "開始時間": "", "終了時間": ""} for _ in range(25)]
                st.session_state.form_key += 1
                st.session_state.sys_msg = f"{len(new_records)}名分の記録を一括保存しました。"
                st.rerun()

elif menu == "1件ずつ":
    st.markdown("<div class='main-title'>SINGLE ENTRY</div>", unsafe_allow_html=True)
    if missing_warning_html: st.markdown(missing_warning_html, unsafe_allow_html=True)
    
    df_history = load_data()
    user_list = ["-- 新規入力 (直接入力してください) --"]
    recent_users = pd.DataFrame()
    if not df_history.empty:
        recent_users = df_history[['名前', '学年']].drop_duplicates(subset=['名前']).dropna()
        user_list += recent_users['名前'].tolist()

    selected_user = st.selectbox("過去の利用者検索 (自動入力)", user_list)
    if selected_user != "-- 新規入力 (直接入力してください) --":
        default_name = selected_user
        try:
            default_grade = recent_users[recent_users['名前'] == selected_user]['学年'].values[0]
            if not default_grade: default_grade = "--選択--"
        except: default_grade = "--選択--"
    else:
        default_name, default_grade = "", "--選択--"

    col1, col2 = st.columns([1, 1])
    with col1: f_date = st.date_input("利用日", jst_now.date(), max_value=jst_now.date())
    with col2: 
        g_index = GRADES.index(default_grade) if default_grade in GRADES else 0
        f_grade = st.selectbox("学年 (必須)", GRADES, index=g_index)
        
    k_name = f"name_{st.session_state.form_key}"
    f_name = st.text_input("氏名 (必須)", value=default_name, key=k_name, placeholder="例: 山田太郎")

    in_key, out_key = f"single_in_{st.session_state.form_key}", f"single_out_{st.session_state.form_key}"
    if in_key not in st.session_state: st.session_state[in_key] = (jst_now - timedelta(hours=1)).strftime("%H:%M")
    if out_key not in st.session_state: st.session_state[out_key] = jst_now.strftime("%H:%M")

    col_in, col_out = st.columns(2)
    with col_in: in_time_str = st.text_input("開始時間 (必須)", key=in_key, on_change=format_time_input, args=(in_key,))
    with col_out: out_time_str = st.text_input("終了時間 (必須)", key=out_key, on_change=format_time_input, args=(out_key,))

    st.markdown("<hr style='margin-top:20px; margin-bottom:20px;'>", unsafe_allow_html=True)
    if st.button("この内容で記録する", use_container_width=True, type="primary"):
        f_name_clean = f_name.replace(" ", "").replace(" ", "")
        in_time, out_time = parse_custom_time(in_time_str), parse_custom_time(out_time_str)
        if not f_name_clean: st.error("氏名を入力してください。")
        elif f_grade == "--選択--": st.error("学年を選択してください。")
        elif in_time is None or out_time is None: st.error("開始時間と終了時間を正しく入力してください。")
        elif not is_special_period(f_date) and in_time.hour < 12: st.error("通常期間は12時以降を入力してください。")
        else:
            duration = calc_duration(in_time, out_time)
            if duration <= 0: st.error("終了時間は開始時間以降に設定してください")
            else:
                df = load_data()
                in_str, out_str = in_time.strftime("%H:%M"), out_time.strftime("%H:%M")
                is_dup = not df[(df['日付'] == pd.to_datetime(f_date)) & (df['名前'] == f_name_clean) & (df['入室時間'] == in_str) & (df['退室時間'] == out_str)].empty
                if is_dup: st.error("この記録は既に登録されています。")
                else:
                    new_row = pd.DataFrame([{'日付': pd.to_datetime(f_date), '名前': f_name_clean, '学年': f_grade, '入室時間': in_str, '退室時間': out_str, '利用時間（時間）': duration}])
                    df = pd.concat([df, new_row], ignore_index=True)
                    save_data(df)
                    st.session_state.form_key += 1 
                    st.session_state.sys_msg = f"{f_name_clean}さんの記録（{in_str} 〜 {out_str}）を保存しました。"
                    st.rerun()

elif menu == "ランキング":
    st.markdown("<div class='main-title'>STUDY HOURS RANKING</div>", unsafe_allow_html=True)
    df = load_data()

    def render_premium_cards(agg):
        if agg.empty: return
        html = "<div class='flex-container'>"
        top_rows = agg[agg['順位'] <= 3]
        for i, row in top_rows.iterrows():
            rank_val, name, time_val = row['順位'], row['名前'], row['利用時間（時間）']
            grade_disp = row['学年'] if pd.notnull(row['学年']) and row['学年'] != "" else "学年未設定"
            
            if rank_val == 1:
                badge = "<div class='rank-badge badge-gold'>1位</div>"
            elif rank_val == 2:
                badge = "<div class='rank-badge badge-silver'>2位</div>"
            elif rank_val == 3:
                badge = "<div class='rank-badge badge-bronze'>3位</div>"
            else:
                badge = f"<div class='rank-badge badge-normal'>{rank_val}位</div>"
                
            html += f"<div class='rank-card'>{badge}<div class='rank-grade'>{grade_disp}</div><div class='rank-name'>{name}</div><div class='time-display'><span class='time-val'>{time_val:.1f}</span><span class='time-unit'>HOURS</span></div></div>"
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    def render_section_ranking(full_agg, target_grades, section_title):
        section_df = full_agg[full_agg['学年'].isin(target_grades)].reset_index(drop=True)
        st.markdown(f"<div class='section-title'>{section_title}</div>", unsafe_allow_html=True)
        if section_df.empty: st.info("集計データがありません。"); return
        section_df['順位'] = section_df['利用時間（時間）'].rank(method='min', ascending=False).astype(int)
        render_premium_cards(section_df)
        st.dataframe(section_df[['順位', '名前', '学年', '利用時間（時間）']], use_container_width=True, hide_index=True, column_config={
            "順位": st.column_config.NumberColumn("順位"), "名前": st.column_config.TextColumn("氏名"), "学年": st.column_config.TextColumn("学年"),
            "利用時間（時間）": st.column_config.ProgressColumn("累計学習時間", format="%.1f h", min_value=0, max_value=float(section_df['利用時間（時間）'].max() if section_df['利用時間（時間）'].max() > 0 else 1))
        })

    if not df.empty:
        jst_today = pd.Timestamp(jst_now.date())
        first_day_of_this_month = jst_today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - pd.Timedelta(days=1)
        last_month_num = last_day_of_last_month.month

        tab1, tab2, tab3, tab4 = st.tabs(["今月の集計", f"{last_month_num}月の集計", "直近3ヶ月", "累計"])
        def get_agg(target_df):
            if target_df.empty: return pd.DataFrame()
            return target_df.groupby(['名前', '学年'])['利用時間（時間）'].sum().reset_index().sort_values(by='利用時間（時間）', ascending=False).reset_index(drop=True)

        df_vp = df[df['日付'] <= jst_today]
        df_this_month = df_vp[(df_vp['日付'].dt.year == jst_today.year) & (df_vp['日付'].dt.month == jst_today.month)]
        first_day_of_last_month = last_day_of_last_month.replace(day=1)
        df_last_month = df_vp[(df_vp['日付'] >= first_day_of_last_month) & (df_vp['日付'] <= last_day_of_last_month)]
        df_3months = df_vp[df_vp['日付'] >= (jst_today - pd.DateOffset(months=3))]
        
        for tab, agg_data, period_name in zip([tab1, tab2, tab3, tab4], [get_agg(df_this_month), get_agg(df_last_month), get_agg(df_3months), get_agg(df_vp)], ["今月", f"{last_month_num}月", "直近3ヶ月", "累計"]):
            with tab:
                if agg_data.empty: st.info("データがありません。")
                else:
                    render_section_ranking(agg_data, [f"小{i}" for i in range(1, 7)], "小学生の部")
                    render_section_ranking(agg_data, [f"中{i}" for i in range(1, 4)], "中学生の部")
                    render_section_ranking(agg_data, ["高1", "高2"], "高1・高2の部")
                    render_section_ranking(agg_data, ["高3", "既卒/自由/その他", ""], "高3・その他の部")
    else: st.info("データがありません。最初の記録を登録してください。")

elif menu == "分析":
    st.markdown("<div class='main-title'>ANALYTICS DASHBOARD</div>", unsafe_allow_html=True)
    df_ana = load_data()
    jst_today = pd.Timestamp(jst_now.date())

    if not df_ana.empty:
        # 年間利用トレンドグラフの追加
        st.markdown("<div class='section-title'>年間利用トレンド（過去12ヶ月）</div>", unsafe_allow_html=True)
        df_trend = df_ana.copy()
        df_trend['年月'] = df_trend['日付'].dt.strftime('%Y-%m')
        trend_agg = df_trend.groupby('年月').agg(月間総学習時間=('利用時間（時間）', 'sum')).reset_index()
        trend_agg = trend_agg.sort_values('年月')
        st.bar_chart(trend_agg.set_index('年月')['月間総学習時間'])

        this_month_start = jst_today.replace(day=1)
        last_month_start = (this_month_start - pd.Timedelta(days=1)).replace(day=1)
        last_month_end = this_month_start - pd.Timedelta(days=1)
        two_months_ago_start = (last_month_start - pd.Timedelta(days=1)).replace(day=1)
        two_months_ago_end = last_month_start - pd.Timedelta(days=1)
        last_month_today = jst_today - pd.DateOffset(months=1)

        st.markdown(f"<div class='section-title'>先月の確定実績（前々月比）</div>", unsafe_allow_html=True)
        df_last_f = df_ana[(df_ana['日付'] >= last_month_start) & (df_ana['日付'] <= last_month_end)]
        df_2mo_f = df_ana[(df_ana['日付'] >= two_months_ago_start) & (df_ana['日付'] <= two_months_ago_end)]
        
        hours_last = df_last_f['利用時間（時間）'].sum()
        hours_2mo = df_2mo_f['利用時間（時間）'].sum()
        diff_hours_last = hours_last - hours_2mo
        pct_hours_last = (diff_hours_last / hours_2mo * 100) if hours_2mo > 0 else (100 if hours_last > 0 else 0)
        
        users_last = df_last_f['名前'].nunique()
        users_2mo = df_2mo_f['名前'].nunique()
        diff_users_last = users_last - users_2mo
        pct_users_last = (diff_users_last / users_2mo * 100) if users_2mo > 0 else (100 if users_last > 0 else 0)
        
        col_met_l1, col_met_l2, col_met_l3 = st.columns(3)
        col_met_l1.metric(f"{last_month_start.month}月の総学習時間", f"{hours_last:.1f} 時間", f"{pct_hours_last:+.1f}% ({diff_hours_last:+.1f} 時間)")
        col_met_l2.metric(f"{last_month_start.month}月の利用者数", f"{users_last} 名", f"{pct_users_last:+.1f}% ({diff_users_last:+d} 名)")
        if users_last > 0:
            avg_last = hours_last / users_last
            avg_2mo = hours_2mo / users_2mo if users_2mo > 0 else 0
            diff_avg_last = avg_last - avg_2mo
            pct_avg_last = (diff_avg_last / avg_2mo * 100) if avg_2mo > 0 else (100 if avg_last > 0 else 0)
            col_met_l3.metric("1人あたり平均学習時間", f"{avg_last:.1f} 時間", f"{pct_avg_last:+.1f}% ({diff_avg_last:+.1f} 時間)")

        st.markdown("<div class='section-title'>今月の進捗速報（前月同日時点との比較）</div>", unsafe_allow_html=True)
        df_this_p = df_ana[(df_ana['日付'] >= this_month_start) & (df_ana['日付'] <= jst_today)]
        df_last_p = df_ana[(df_ana['日付'] >= last_month_start) & (df_ana['日付'] <= last_month_today)]
        
        hours_this_p = df_this_p['利用時間（時間）'].sum()
        hours_last_p = df_last_p['利用時間（時間）'].sum()
        diff_hours_p = hours_this_p - hours_last_p
        pct_hours_p = (diff_hours_p / hours_last_p * 100) if hours_last_p > 0 else (100 if hours_this_p > 0 else 0)
        
        users_this_p = df_this_p['名前'].nunique()
        users_last_p = df_last_p['名前'].nunique()
        diff_users_p = users_this_p - users_last_p
        pct_users_p = (diff_users_p / users_last_p * 100) if users_last_p > 0 else (100 if users_this_p > 0 else 0)
        
        col_met_p1, col_met_p2, col_met_p3 = st.columns(3)
        col_met_p1.metric(f"{this_month_start.month}月(本日迄)の総学習時間", f"{hours_this_p:.1f} 時間", f"{pct_hours_p:+.1f}% ({diff_hours_p:+.1f} 時間)")
        col_met_p2.metric(f"{this_month_start.month}月(本日迄)の利用者数", f"{users_this_p} 名", f"{pct_users_p:+.1f}% ({diff_users_p:+d} 名)")
        if users_this_p > 0:
            avg_this_p = hours_this_p / users_this_p
            avg_last_p = hours_last_p / users_last_p if users_last_p > 0 else 0
            diff_avg_p = avg_this_p - avg_last_p
            pct_avg_p = (diff_avg_p / avg_last_p * 100) if avg_last_p > 0 else (100 if avg_this_p > 0 else 0)
            col_met_p3.metric("1人あたり平均学習時間", f"{avg_this_p:.1f} 時間", f"{pct_avg_p:+.1f}% ({diff_avg_p:+.1f} 時間)")

        today_d = jst_today.day
        next_month_first = (jst_today.replace(day=1) + timedelta(days=32)).replace(day=1)
        days_in_month = (next_month_first - timedelta(days=1)).day
        proj_hours_this_month = hours_this_p / today_d * days_in_month if today_d > 0 else 0
        growth_rate_h = pct_hours_p / 100.0 if pct_hours_p != 100 else 0
        next_month_h = proj_hours_this_month * (1 + max(min(growth_rate_h, 0.15), -0.15))
        next_month_u = users_this_p * (1 + max(min((pct_users_p / 100.0), 0.1), -0.1))
        
        st.markdown(f"""
        <div style='background-color: var(--secondary-background-color); border-left: 4px solid var(--primary-color); padding: 20px; border-radius: 8px; margin-top: 20px;'>
            <div style='font-weight: 800; color: var(--text-color); margin-bottom: 8px; font-size: 1.1rem;'>翌月利用予測（直近トレンドからの推計）</div>
            <div style='display: flex; gap: 40px; margin-top: 10px;'>
                <div>
                    <div style='font-size: 0.85rem; color: var(--text-color); opacity: 0.7; font-weight: 600;'>推定総学習時間</div>
                    <div style='color: var(--primary-color); font-size: 1.8rem; font-weight: 900;'>{next_month_h:.0f} <span style='font-size: 1rem; font-weight: 600; opacity: 0.8;'>HOURS</span></div>
                </div>
                <div>
                    <div style='font-size: 0.85rem; color: var(--text-color); opacity: 0.7; font-weight: 600;'>推定来室者数</div>
                    <div style='color: var(--primary-color); font-size: 1.8rem; font-weight: 900;'>{int(next_month_u)} <span style='font-size: 1rem; font-weight: 600; opacity: 0.8;'>USERS</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else: st.info("データが蓄積されると前月比の利用率が表示されます。")
        
    st.markdown("<hr style='margin: 30px 0; border-color: rgba(128,128,128,0.2);'>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["混雑状況", "生徒個別", "来週の予測"])
    def get_active_slots(in_str, out_str, slots_list):
        def parse_time(t_str):
            t_str = str(t_str).strip()
            if "コマ" in t_str:
                try: return datetime.strptime(f"{13 + int((int(t_str.replace('コマ', '')) - 1) * 1.5):02d}:00", "%H:%M").time()
                except: return None
            try:
                parts = t_str.split(":")
                if len(parts) >= 2: return datetime.strptime(f"{int(parts[0]):02d}:{int(parts[1]):02d}", "%H:%M").time()
            except: pass
            return None
        in_t, out_t = parse_time(in_str), parse_time(out_str)
        if not in_t or not out_t: return []
        slots = []
        for slot_str in slots_list:
            h = int(slot_str[:2])
            slot_start = datetime.strptime(f"{h:02d}:00", "%H:%M").time()
            slot_end = datetime.strptime(f"{h+1:02d}:00", "%H:%M").time() if h < 22 else datetime.strptime("23:59", "%H:%M").time()
            if in_t < slot_end and out_t > slot_start: slots.append(slot_str)
        return slots

    with tab1:
        st.markdown("<div class='section-title'>曜日・時間帯別の混雑状況</div>", unsafe_allow_html=True)
        if not df_ana.empty:
            df_ana['年月'] = pd.to_datetime(df_ana['日付']).dt.strftime('%Y年%m月')
            month_options = ["累計"] + sorted(df_ana['年月'].dropna().unique().tolist(), reverse=True)
            selected_period = st.selectbox("集計対象を選択", month_options)
            target_df = df_ana if selected_period == "累計" else df_ana[df_ana['年月'] == selected_period]
            current_time_slots = get_time_slots_for_period(selected_period)
            weekdays = ["月", "火", "水", "木", "金", "土", "日"]
            heatmap_data = pd.DataFrame(0, index=weekdays, columns=current_time_slots)
            for _, row in target_df.iterrows():
                if pd.isnull(row['日付']) or not row['入室時間'] or not row['退室時間']: continue
                try:
                    wd = weekdays[pd.to_datetime(row['日付']).weekday()]
                    for slot in get_active_slots(row['入室時間'], row['退室時間'], current_time_slots): heatmap_data.loc[wd, slot] += 1
                except: continue
            max_val = max(heatmap_data.values.max(), 1)
            html = "<div class='heatmap-container'><table class='modern-table'>"
            html += "<tr><th class='sticky-col'>曜日</th>"
            for tb in current_time_slots: html += f"<th>{tb[:2]}時台</th>"
            html += "</tr>"
            for wd in weekdays:
                html += f"<tr><th class='sticky-col'>{wd}</th>"
                for tb in current_time_slots:
                    val = heatmap_data.loc[wd, tb]
                    ratio = val / max_val if max_val > 0 else 0
                    bg_color = f"rgba(37, 99, 235, {ratio * 0.8})" if val > 0 else "transparent"
                    font_color = "#FFFFFF" if ratio > 0.4 else "var(--text-color)"
                    border_style = "border: 1px solid rgba(128,128,128,0.1);" if val == 0 else "border: none;"
                    val_str = val if val > 0 else ""
                    html += f"<td style='background-color: {bg_color}; color: {font_color}; {border_style}'>{val_str}</td>"
                html += "</tr>"
            html += "</table></div>"
            st.markdown(html, unsafe_allow_html=True)
        else: st.info("集計するデータがありません。")

    with tab2:
        st.markdown("<div class='section-title'>生徒個別 学習時間推移</div>", unsafe_allow_html=True)
        if not df_ana.empty:
            unique_names = [n for n in df_ana['名前'].dropna().unique().tolist() if str(n).strip() != ""]
            if unique_names:
                selected_name = st.selectbox("生徒名で検索", ["-- 選択してください --"] + unique_names)
                if selected_name != "-- 選択してください --":
                    student_df = df_ana[df_ana['名前'] == selected_name].copy()
                    student_df['日付'] = pd.to_datetime(student_df['日付'])
                    sm_df = student_df[student_df['日付'] >= jst_today.replace(day=1)]
                    total_h = sm_df['利用時間（時間）'].sum()
                    st.markdown(f"<div style='background-color: var(--secondary-background-color); padding: 20px; border-radius: 8px; border-left: 4px solid var(--primary-color); margin-bottom: 20px;'><div style='font-size: 1.1rem; color: var(--text-color); font-weight: bold;'>{selected_name} さんの今月の学習時間</div><div style='font-size: 2.5rem; font-weight: 900; color: var(--text-color);'>{total_h:.1f} <span style='font-size: 1rem; font-weight: normal;'>時間</span></div></div>", unsafe_allow_html=True)
                    st.markdown("##### 日別の学習推移（今月）")
                    if not sm_df.empty:
                        daily_sum = sm_df.groupby('日付')['利用時間（時間）'].sum().reset_index()
                        daily_sum['日付ラベル'] = daily_sum['日付'].dt.strftime('%m/%d')
                        st.bar_chart(daily_sum.set_index('日付ラベル')['利用時間（時間）'])
                    else: st.info("今月の記録はまだありません。")
                    st.markdown("##### 直近の記録一覧")
                    display_history = student_df.sort_values('日付', ascending=False).head(10)
                    display_history['日付'] = display_history['日付'].dt.strftime('%Y/%m/%d')
                    st.dataframe(display_history[['日付', '入室時間', '退室時間', '利用時間（時間）']], use_container_width=True, hide_index=True)
            else: st.info("検索できる生徒データがありません。")
        else: st.info("集計するデータがありません。")

    with tab3:
        st.markdown("<div class='section-title'>来週の混雑予測（推計モデル適用）</div>", unsafe_allow_html=True)
        st.markdown("<p style='color: var(--text-color); opacity: 0.8; font-size: 0.95rem; line-height: 1.5;'>直近4週間の実績データから、回帰的な手法を用いて来週の各時間帯の平均来室人数を推計しています。</p>", unsafe_allow_html=True)
        if not df_ana.empty:
            test_mult, before_mult = learn_multipliers(df_ana)
            df_recent = df_ana[pd.to_datetime(df_ana['日付']) >= (jst_today - pd.Timedelta(days=28))]
            target_dates = [jst_today + timedelta(days=i) for i in range(1, 8)]
            has_test = any(get_period_status(dt) == "test" for dt in target_dates)
            has_before = any(get_period_status(dt) == "before_test" for dt in target_dates)
            
            if has_test or has_before:
                msg_parts = []
                if has_test: msg_parts.append("「テスト期間」")
                if has_before: msg_parts.append("「テスト1週間前」")
                st.markdown(f"<div style='background-color: rgba(220, 38, 38, 0.1); border-left: 4px solid #DC2626; padding: 15px; margin-bottom: 20px; border-radius: 4px;'><p style='color:#DC2626; font-weight:bold; margin:0;'>[アラート] 来週は{' または '.join(msg_parts)}に該当する日が含まれるため、予測モデルに変動係数が適用されています。</p></div>", unsafe_allow_html=True)

            if not df_recent.empty:
                pred_time_slots = get_time_slots_for_period((jst_today + pd.Timedelta(days=7)).strftime('%Y年%m月'))
                weekdays = ["月", "火", "水", "木", "金", "土", "日"]
                predict_data = pd.DataFrame(0.0, index=weekdays, columns=pred_time_slots)

                for _, row in df_recent.iterrows():
                    if pd.isnull(row['日付']) or not row['入室時間'] or not row['退室時間']: continue
                    try:
                        dt = pd.to_datetime(row['日付'])
                        wd = weekdays[dt.weekday()]
                        status = get_period_status(dt)
                        div_factor = test_mult if status == "test" else (before_mult if status == "before_test" else 1.0)
                        for slot in get_active_slots(row['入室時間'], row['退室時間'], pred_time_slots): predict_data.loc[wd, slot] += (0.25 / div_factor)
                    except: continue

                for dt in target_dates:
                    wd, status = weekdays[dt.weekday()], get_period_status(dt)
                    mult = test_mult if status == "test" else (before_mult if status == "before_test" else 1.0)
                    predict_data.loc[wd] = predict_data.loc[wd] * mult

                html = "<div class='heatmap-container'><table class='modern-table'>"
                html += "<tr><th class='sticky-col'>曜日</th>"
                for tb in pred_time_slots: html += f"<th>{tb[:2]}時台</th>"
                html += "</tr>"

                for wd in weekdays:
                    html += f"<tr><th class='sticky-col'>{wd}</th>"
                    for tb in pred_time_slots:
                        val = predict_data.loc[wd, tb]
                        ratio = min(val / 20.0, 1.0)
                        rounded_val = int(round(val))
                        if rounded_val >= 20: bg_color, font_color, display_val = "rgba(220, 38, 38, 0.9)", "#FFFFFF", "満席"
                        elif rounded_val >= 15: bg_color, font_color, display_val = f"rgba(234, 88, 12, {max(0.6, ratio)})", "#FFFFFF", f"約{rounded_val}人"
                        elif rounded_val > 0: bg_color, font_color, display_val = f"rgba(37, 99, 235, {ratio * 0.8})", ("#FFFFFF" if ratio > 0.4 else "var(--text-color)"), f"約{rounded_val}人"
                        else: bg_color, font_color, display_val = "transparent", "var(--text-color)", "-"
                        border_style = "border: 1px solid rgba(128,128,128,0.1);" if rounded_val == 0 else "border: none;"
                        html += f"<td style='background-color: {bg_color}; color: {font_color}; {border_style}'>{display_val}</td>"
                    html += "</tr>"
                html += "</table></div>"
                st.markdown(html, unsafe_allow_html=True)
            else: st.info("直近4週間のデータがないため、予測を計算できません。")
        else: st.info("集計するデータがありません。")

elif menu == "管理":
    st.markdown("<div class='main-title'>ADMIN PANEL</div>", unsafe_allow_html=True)
    df_manage = load_data()
    
    if not df_manage.empty:
        tab_edit, tab_del = st.tabs(["1件ずつ編集", "複数の一括削除"])
        options = []
        for i in reversed(df_manage.index):
            row = df_manage.loc[i]
            d_str = row['日付'].strftime('%m/%d') if pd.notnull(row['日付']) else "不明"
            options.append((str(i), f"{d_str} | {row['名前']} ({row['入室時間']} - {row['退室時間']})"))
            
        with tab_del:
            st.markdown("##### まとめて削除")
            selected_dels = st.multiselect("削除する記録を選択してください", options, format_func=lambda x: x[1])
            if st.button("選択した記録を完全に削除", type="primary"):
                if selected_dels:
                    indices_to_drop = [int(x[0]) for x in selected_dels]
                    df_manage = df_manage.drop(indices_to_drop).reset_index(drop=True)
                    save_data(df_manage)
                    st.session_state.sys_msg = f"{len(indices_to_drop)}件の記録を削除しました。"
                    st.rerun()
                else: st.warning("削除する記録が選択されていません。")

        with tab_edit:
            st.markdown("##### 記録の編集")
            selected_mng = st.selectbox("編集する記録", [("-1", "-- 選択してください --")] + options[:50], format_func=lambda x: x[1])
            if selected_mng[0] != "-1":
                target_idx = int(selected_mng[0])
                target_row = df_manage.loc[target_idx]
                st.markdown("<div style='margin-top: 10px; padding: 25px; border-radius: 8px; background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.2);'>", unsafe_allow_html=True)
                
                default_date = target_row['日付'].date() if pd.notnull(target_row['日付']) else jst_now.date()
                edit_date = st.date_input("利用日", default_date)
                edit_name = st.text_input("氏名 (必須)", value=str(target_row['名前']), placeholder="例: 山田太郎")
                
                edit_in_key, edit_out_key = f"edit_in_{target_idx}_{target_row['名前']}", f"edit_out_{target_idx}_{target_row['名前']}"
                if edit_in_key not in st.session_state: st.session_state[edit_in_key] = str(target_row['入室時間'])
                if edit_out_key not in st.session_state: st.session_state[edit_out_key] = str(target_row['退室時間'])

                col_in, col_out = st.columns(2)
                with col_in: edit_in_str = st.text_input("開始時間 (例: 1223, 全角OK)", key=edit_in_key, on_change=format_time_input, args=(edit_in_key,))
                with col_out: edit_out_str = st.text_input("終了時間 (例: 1530, 全角OK)", key=edit_out_key, on_change=format_time_input, args=(edit_out_key,))

                current_grade = str(target_row['学年']) if str(target_row['学年']) else "--選択--"
                edit_grade = st.selectbox("学年 (必須)", GRADES, index=(GRADES.index(current_grade) if current_grade in GRADES else 0))
                
                st.markdown("<br>", unsafe_allow_html=True)
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("この内容で上書き保存", use_container_width=True, type="primary"):
                        edit_name_clean = edit_name.replace(" ", "").replace(" ", "")
                        edit_in, edit_out = parse_custom_time(edit_in_str), parse_custom_time(edit_out_str)
                        if edit_name_clean:
                            if edit_grade == "--選択--": st.error("学年を選択してください。")
                            elif edit_in is None or edit_out is None: st.error("開始と終了時間を正しく入力してください。")
                            elif not is_special_period(edit_date) and edit_in.hour < 12: st.error("通常期間は12時以降を入力してください。")
                            else:
                                duration = calc_duration(edit_in, edit_out)
                                if duration <= 0: st.error("終了時間は開始時間以降に設定してください")
                                else:
                                    df_manage.at[target_idx, '日付'] = pd.to_datetime(edit_date)
                                    df_manage.at[target_idx, '名前'] = edit_name_clean
                                    df_manage.at[target_idx, '学年'] = edit_grade
                                    df_manage.at[target_idx, '入室時間'] = edit_in.strftime("%H:%M")
                                    df_manage.at[target_idx, '退室時間'] = edit_out.strftime("%H:%M")
                                    df_manage.at[target_idx, '利用時間（時間）'] = duration
                                    save_data(df_manage)
                                    st.session_state.sys_msg = "記録を更新しました。"
                                    st.rerun()
                        else: st.error("氏名を入力してください。")
                with col_btn2:
                    if st.button("この記録を完全に削除", use_container_width=True):
                        df_manage = df_manage.drop(target_idx).reset_index(drop=True)
                        save_data(df_manage)
                        st.session_state.sys_msg = "削除しました。"
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
    else: st.info("変更・削除できるデータがありません。")
