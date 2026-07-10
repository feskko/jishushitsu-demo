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

def is_special_period(dt_date):
    if dt_date is None: return False
    m = dt_date.month
    d = dt_date.day
    if (m == 3 and d >= 15) or (m == 4 and d <= 7): return True
    if (m == 7 and d >= 15) or m == 8: return True
    if m == 12 or (m == 1 and d <= 7): return True
    return False

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

st.set_page_config(page_title="Study Room Analytics", layout="wide", initial_sidebar_state="collapsed")
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
    doc.addEventListener('focusout', function(e) {{ if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {{ formatTimeInput(e.target); }} }}, true);
</script>
"""
components.html(js_code, height=0, width=0)

st.markdown("""
<style>
    /* Reset Streamlit Defaults */
    #MainMenu, header, footer, [data-testid="stToolbar"] {visibility: hidden !important; display: none !important;}
    .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; max-width: 1200px !important; }
    .stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: var(--background-color); }
    
    /* Core Typography */
    .app-header { font-weight: 900; color: var(--text-color); font-size: 2rem; letter-spacing: -0.5px; margin-bottom: 0.2rem; }
    .app-subheader { font-weight: 500; color: var(--text-color); opacity: 0.5; font-size: 0.9rem; letter-spacing: 1px; margin-bottom: 2rem; text-transform: uppercase; }
    .section-title { font-weight: 800; color: var(--text-color); margin-top: 3rem; margin-bottom: 1.5rem; font-size: 1.4rem; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px; }
    .section-title::before { content: ''; display: inline-block; width: 6px; height: 24px; background-color: var(--primary-color); border-radius: 4px; }
    
    /* Modern Navigation (Overrides Radio) */
    div[role="radiogroup"] { background-color: var(--secondary-background-color); padding: 6px; border-radius: 12px; display: inline-flex !important; flex-direction: row; flex-wrap: wrap; gap: 4px; border: 1px solid rgba(128,128,128,0.1); margin-bottom: 2rem; }
    div[role="radiogroup"] label { border-radius: 8px !important; padding: 10px 20px !important; margin: 0 !important; cursor: pointer; transition: all 0.2s ease; border: none !important; background-color: transparent; }
    div[role="radiogroup"] label:hover { background-color: rgba(128,128,128,0.05); }
    div[role="radiogroup"] label[data-checked="true"] { background-color: var(--background-color) !important; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    div[role="radiogroup"] label p { color: var(--text-color) !important; opacity: 0.7; font-weight: 600 !important; font-size: 0.9rem !important; margin: 0; }
    div[role="radiogroup"] label[data-checked="true"] p { opacity: 1; color: var(--primary-color) !important; }
    
    /* Custom KPI Cards */
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 2rem; }
    .kpi-card { background-color: var(--secondary-background-color); border-radius: 16px; padding: 24px; border: 1px solid rgba(128,128,128,0.1); display: flex; flex-direction: column; transition: transform 0.2s ease, box-shadow 0.2s ease; }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.04); }
    .kpi-label { font-size: 0.85rem; color: var(--text-color); opacity: 0.6; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
    .kpi-value-container { display: flex; align-items: baseline; gap: 8px; margin-bottom: 8px; }
    .kpi-value { font-size: 2.4rem; font-weight: 900; color: var(--text-color); letter-spacing: -1px; line-height: 1; }
    .kpi-unit { font-size: 1rem; font-weight: 600; color: var(--text-color); opacity: 0.5; }
    .kpi-trend { font-size: 0.85rem; font-weight: 600; padding: 4px 8px; border-radius: 6px; display: inline-flex; align-items: center; width: fit-content; }
    .kpi-trend.positive { background-color: rgba(16, 185, 129, 0.1); color: #10B981; }
    .kpi-trend.negative { background-color: rgba(239, 68, 68, 0.1); color: #EF4444; }
    .kpi-trend.neutral { background-color: rgba(128, 128, 128, 0.1); color: var(--text-color); opacity: 0.7; }
    
    /* Premium Ranking Cards (Top 3) */
    .top-rank-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-bottom: 2rem; }
    .top-rank-card { background: var(--secondary-background-color); border-radius: 20px; padding: 32px 24px; display: flex; flex-direction: column; align-items: center; border: 1px solid rgba(128,128,128,0.1); position: relative; overflow: hidden; }
    .top-rank-badge { position: absolute; top: 0; left: 50%; transform: translateX(-50%); padding: 6px 24px; border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; font-weight: 900; font-size: 0.9rem; letter-spacing: 1px; color: #FFF; }
    .badge-1 { background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%); }
    .badge-2 { background: linear-gradient(135deg, #94A3B8 0%, #64748B 100%); }
    .badge-3 { background: linear-gradient(135deg, #D97706 0%, #B45309 100%); }
    .top-rank-grade { font-size: 0.85rem; font-weight: 700; color: var(--text-color); opacity: 0.5; margin-top: 1rem; margin-bottom: 0.2rem; }
    .top-rank-name { font-size: 1.8rem; font-weight: 900; color: var(--text-color); margin-bottom: 1.5rem; letter-spacing: -0.5px; }
    .top-rank-time { background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%); padding: 12px 24px; border-radius: 12px; color: #FFF; display: flex; align-items: baseline; gap: 6px; width: 100%; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .time-v { font-size: 1.6rem; font-weight: 900; line-height: 1; }
    .time-u { font-size: 0.8rem; font-weight: 700; opacity: 0.7; }
    
    /* Custom Data Table (Replacing st.dataframe) */
    .custom-table-container { width: 100%; overflow-x: auto; border-radius: 12px; border: 1px solid rgba(128,128,128,0.1); background-color: var(--secondary-background-color); margin-bottom: 2rem; }
    .custom-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.95rem; }
    .custom-table th { background-color: rgba(128,128,128,0.03); color: var(--text-color); opacity: 0.6; font-weight: 600; padding: 16px 24px; border-bottom: 1px solid rgba(128,128,128,0.1); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .custom-table td { padding: 16px 24px; border-bottom: 1px solid rgba(128,128,128,0.05); color: var(--text-color); font-weight: 500; }
    .custom-table tbody tr:last-child td { border-bottom: none; }
    .custom-table tbody tr:hover { background-color: rgba(128,128,128,0.02); }
    .td-rank { font-weight: 800 !important; color: var(--primary-color) !important; width: 80px; }
    .td-name { font-weight: 700 !important; }
    .td-val { text-align: right; font-weight: 700 !important; font-variant-numeric: tabular-nums; }
    .bar-container { width: 100px; height: 6px; background-color: rgba(128,128,128,0.1); border-radius: 3px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 12px; }
    .bar-fill { height: 100%; background-color: var(--primary-color); border-radius: 3px; }
    
    /* Modern Heatmap */
    .heatmap-wrapper { overflow-x: auto; padding-bottom: 15px; border-radius: 12px; border: 1px solid rgba(128,128,128,0.1); background-color: var(--secondary-background-color); }
    .heatmap-table { width: 100%; border-collapse: separate; border-spacing: 2px; font-size: 0.85rem; min-width: 800px; padding: 12px; }
    .heatmap-table th { color: var(--text-color); opacity: 0.6; padding: 12px 8px; font-weight: 600; text-align: center; font-size: 0.8rem; }
    .heatmap-table th.sticky-col { position: sticky; left: 0; background-color: var(--secondary-background-color); z-index: 2; text-align: left; padding-left: 16px; }
    .heatmap-table td { padding: 12px 8px; border-radius: 4px; text-align: center; font-weight: 700; transition: filter 0.2s ease; border: 1px solid rgba(128,128,128,0.05); font-variant-numeric: tabular-nums; }
    .heatmap-table td:hover { filter: brightness(1.2); }
    
    /* Inputs Override */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { border-radius: 8px !important; border: 1px solid rgba(128,128,128,0.2) !important; background-color: var(--secondary-background-color) !important; transition: border-color 0.2s; }
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within { border-color: var(--primary-color) !important; box-shadow: 0 0 0 1px var(--primary-color) !important; }
    
    /* Hide specific st components to force custom look */
    div[data-testid="stMetric"] { display: none; }
</style>
""", unsafe_allow_html=True)

# Custom Components Functions
def render_kpi(title, value, unit, trend_val, trend_text):
    if trend_val > 0:
        trend_class = "positive"
        trend_arrow = "+"
    elif trend_val < 0:
        trend_class = "negative"
        trend_arrow = ""
    else:
        trend_class = "neutral"
        trend_arrow = ""
        
    html = f"""
    <div class="kpi-card">
        <div class="kpi-label">{title}</div>
        <div class="kpi-value-container">
            <div class="kpi-value">{value}</div>
            <div class="kpi-unit">{unit}</div>
        </div>
        <div class="kpi-trend {trend_class}">{trend_arrow}{trend_val:.1f}% {trend_text}</div>
    </div>
    """
    return html

def render_ranking_html(df):
    if df.empty:
        return "<p style='color: var(--text-color); opacity: 0.5; padding: 20px;'>No data available.</p>"
    
    max_val = df['利用時間（時間）'].max() if df['利用時間（時間）'].max() > 0 else 1
    
    html = "<div class='custom-table-container'><table class='custom-table'><thead><tr><th>Rank</th><th>Name</th><th>Grade</th><th style='text-align: right;'>Total Hours</th></tr></thead><tbody>"
    
    for _, row in df.iterrows():
        rank = int(row['順位'])
        name = row['名前']
        grade = row['学年'] if pd.notnull(row['学年']) and row['学年'] != "" else "-"
        val = float(row['利用時間（時間）'])
        pct = (val / max_val) * 100
        
        html += f"""
        <tr>
            <td class='td-rank'>#{rank}</td>
            <td class='td-name'>{name}</td>
            <td>{grade}</td>
            <td class='td-val'>
                <div class='bar-container'><div class='bar-fill' style='width: {pct}%;'></div></div>
                {val:.1f}h
            </td>
        </tr>
        """
    html += "</tbody></table></div>"
    return html

if "sys_msg" not in st.session_state: st.session_state.sys_msg = None
if "sys_err" not in st.session_state: st.session_state.sys_err = None

APP_PASSWORD = "demo" 
if "authenticated" not in st.session_state: st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<div style='text-align: center; margin-top: 15vh;'><div class='app-header'>STUDY ROOM SYSTEM</div><div class='app-subheader'>Management Platform</div></div>", unsafe_allow_html=True)
    with st.form("login_form", clear_on_submit=False):
        st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.6; margin-bottom: 24px; font-size: 0.9rem;'>Enter <b>demo</b> to access the dashboard.</p>", unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
        if submitted:
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else: st.error("Incorrect password.")
    st.stop()

def generate_mock_data():
    records = []
    base_date = jst_now.date() - timedelta(days=365)
    mock_students = [
        ("一ノ瀬 蓮", "高3"), ("二階堂 翼", "高3"), ("三鷹 隼人", "高3"), ("四方堂 暁", "高3"),
        ("五味 凌雅", "高2"), ("六条 響", "高2"), ("七瀬 奏多", "高2"), ("八神 律", "高2"),
        ("九条 瑛太", "高1"), ("十文字 颯", "高1"), ("百瀬 蓮", "高1"), ("千堂 魁", "高1"),
        ("明日香 詩", "中3"), ("氷室 玲", "中3"), ("神宮寺 蒼", "中3"), ("皇 斗真", "中3"),
        ("早乙女 湊", "中2"), ("西園寺 蓮", "中2"), ("如月 悠真", "中2"), ("藤堂 柊", "中2"),
        ("天宮 結愛", "中1"), ("月読 陽菜", "中1"), ("日向 澪", "中1"), ("星野 紬", "中1"),
        ("白銀 蓮", "小6"), ("黒鉄 翼", "小6"), ("赤城 隼", "小6"), ("青柳 湊", "小6"),
        ("紫苑 陽", "小5"), ("翡翠 葵", "小5"), ("琥珀 颯太", "小5"), ("珊瑚 結翔", "小5"),
        ("花咲 琴音", "小4"), ("雪村 莉子", "小4"), ("雨宮 律", "小4"), ("風間 杏", "小4"),
        ("東雲 蓮", "高3"), ("西条 翼", "高3"), ("南雲 隼人", "高3"), ("北条 暁", "高3"),
        ("一条 凌雅", "高2"), ("三条 響", "高2"), ("五条 奏多", "高2"), ("七条 律", "高2"),
        ("九十九 瑛太", "高1"), ("八十島 颯", "高1"), ("四十万 蓮", "高1"), ("五十嵐 魁", "高1"),
        ("白鳥 詩", "中3"), ("黒澤 玲", "中3"), ("赤松 蒼", "中3"), ("青木 斗真", "中3"),
        ("若葉 湊", "中2"), ("若松 蓮", "中2"), ("若菜 悠真", "中2"), ("若月 柊", "中2"),
        ("夏目 結愛", "中1"), ("冬月 陽菜", "中1"), ("春日 澪", "中1"), ("秋山 紬", "中1"),
        ("真田 蓮", "小6"), ("伊達 翼", "小6"), ("織田 隼", "小6"), ("豊臣 湊", "小6"),
        ("徳川 陽", "小5"), ("武田 葵", "小5"), ("上杉 颯太", "小5"), ("直江 結翔", "小5"),
        ("佐竹 琴音", "小4"), ("島津 莉子", "小4"), ("毛利 律", "小4"), ("長宗我部 杏", "小4"),
        ("宇喜多 蓮", "高2"), ("龍造寺 翼", "高2"), ("今川 隼人", "高1"), ("大内 暁", "高1")
    ]
    for i in range(366):
        curr_date = base_date + timedelta(days=i)
        if curr_date.weekday() == 6 and random.random() < 0.8: continue
        
        status = get_period_status(curr_date)
        growth = 1.0 + (i / 365.0) * 1.5
        
        if status == "test": base_u = random.randint(20, 30)
        elif status == "before_test": base_u = random.randint(15, 25)
        else: base_u = random.randint(5, 12)
        
        num_users = min(int(base_u * growth), len(mock_students))
        daily_users = random.sample(mock_students, num_users)
        
        for name, grade in daily_users:
            if status == "test" or status == "before_test":
                in_h = random.randint(13, 17)
                if curr_date.weekday() >= 5: in_h = random.randint(9, 14)
                out_h = min(in_h + random.randint(3, 6), 22)
            else:
                in_h = random.randint(16, 19)
                if curr_date.weekday() >= 5: in_h = random.randint(10, 15)
                out_h = min(in_h + random.randint(1, 3), 22)
                
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

GRADES = ["-- Select --"] + [f"小{i}" for i in range(1, 7)] + [f"中{i}" for i in range(1, 4)] + [f"高{i}" for i in range(1, 4)] + ["その他"]

# Global Header
st.markdown("<div class='app-header'>Study Room Analytics</div><div class='app-subheader'>Management & Analytics Platform</div>", unsafe_allow_html=True)

menu = st.radio("Navigation", ["Overview", "Leaderboard", "Batch Entry", "Single Entry", "Data Manager"], horizontal=True, label_visibility="collapsed")

if st.session_state.sys_msg:
    st.success(st.session_state.sys_msg)
    st.session_state.sys_msg = None
if st.session_state.sys_err:
    st.error(st.session_state.sys_err)
    st.session_state.sys_err = None

if menu == "Overview":
    st.markdown("<div class='section-title'>System Analytics</div>", unsafe_allow_html=True)
    df_ana = load_data()
    jst_today = pd.Timestamp(jst_now.date())

    if not df_ana.empty:
        this_month_start = jst_today.replace(day=1)
        last_month_start = (this_month_start - pd.Timedelta(days=1)).replace(day=1)
        last_month_end = this_month_start - pd.Timedelta(days=1)
        two_months_ago_start = (last_month_start - pd.Timedelta(days=1)).replace(day=1)
        two_months_ago_end = last_month_start - pd.Timedelta(days=1)
        last_month_today = jst_today - pd.DateOffset(months=1)

        df_last_f = df_ana[(df_ana['日付'] >= last_month_start) & (df_ana['日付'] <= last_month_end)]
        df_2mo_f = df_ana[(df_ana['日付'] >= two_months_ago_start) & (df_ana['日付'] <= two_months_ago_end)]
        hours_last = df_last_f['利用時間（時間）'].sum()
        hours_2mo = df_2mo_f['利用時間（時間）'].sum()
        pct_hours_last = (hours_last - hours_2mo) / hours_2mo * 100 if hours_2mo > 0 else 0
        users_last = df_last_f['名前'].nunique()
        users_2mo = df_2mo_f['名前'].nunique()
        pct_users_last = (users_last - users_2mo) / users_2mo * 100 if users_2mo > 0 else 0
        avg_last = hours_last / users_last if users_last > 0 else 0
        avg_2mo = hours_2mo / users_2mo if users_2mo > 0 else 0
        pct_avg_last = (avg_last - avg_2mo) / avg_2mo * 100 if avg_2mo > 0 else 0

        df_this_p = df_ana[(df_ana['日付'] >= this_month_start) & (df_ana['日付'] <= jst_today)]
        df_last_p = df_ana[(df_ana['日付'] >= last_month_start) & (df_ana['日付'] <= last_month_today)]
        hours_this_p = df_this_p['利用時間（時間）'].sum()
        hours_last_p = df_last_p['利用時間（時間）'].sum()
        pct_hours_p = (hours_this_p - hours_last_p) / hours_last_p * 100 if hours_last_p > 0 else 0

        # Custom KPI Grid
        kpi_html = f"""
        <div class="kpi-grid">
            {render_kpi("Total Hours (Last Month)", f"{hours_last:.1f}", "hrs", pct_hours_last, "vs previous")}
            {render_kpi("Active Users (Last Month)", f"{users_last}", "users", pct_users_last, "vs previous")}
            {render_kpi("Avg Time/User (Last Month)", f"{avg_last:.1f}", "hrs", pct_avg_last, "vs previous")}
            {render_kpi("MTD Total Hours (Current)", f"{hours_this_p:.1f}", "hrs", pct_hours_p, "vs MTD last month")}
        </div>
        """
        st.markdown(kpi_html, unsafe_allow_html=True)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("<div class='section-title'>Annual Trend</div>", unsafe_allow_html=True)
            df_trend = df_ana.copy()
            df_trend['年月'] = df_trend['日付'].dt.strftime('%Y-%m')
            trend_agg = df_trend.groupby('年月').agg(Total_Hours=('利用時間（時間）', 'sum')).reset_index()
            trend_agg = trend_agg.sort_values('年月')
            st.bar_chart(trend_agg.set_index('年月')['Total_Hours'], height=350)
            
        with col2:
            st.markdown("<div class='section-title'>Forecast Model</div>", unsafe_allow_html=True)
            today_d = jst_today.day
            next_month_first = (jst_today.replace(day=1) + timedelta(days=32)).replace(day=1)
            days_in_month = (next_month_first - timedelta(days=1)).day
            proj_hours_this_month = hours_this_p / today_d * days_in_month if today_d > 0 else 0
            growth_rate_h = pct_hours_p / 100.0 if pct_hours_p != 100 else 0
            next_month_h = proj_hours_this_month * (1 + max(min(growth_rate_h, 0.15), -0.15))
            
            st.markdown(f"""
            <div style='background-color: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.1); padding: 32px; border-radius: 16px; height: 350px; display: flex; flex-direction: column; justify-content: center;'>
                <div style='font-weight: 600; color: var(--text-color); opacity: 0.6; text-transform: uppercase; font-size: 0.85rem; margin-bottom: 12px;'>Estimated Next Month Load</div>
                <div style='color: var(--text-color); font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 8px;'>{next_month_h:.0f}</div>
                <div style='color: var(--primary-color); font-weight: 700; font-size: 1rem;'>Projected Hours</div>
                <div style='margin-top: 24px; padding-top: 24px; border-top: 1px solid rgba(128,128,128,0.1); font-size: 0.9rem; color: var(--text-color); opacity: 0.6; line-height: 1.5;'>
                    Based on current MTD performance and trailing 30-day growth trends.
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Traffic Heatmap (Forecast)</div>", unsafe_allow_html=True)
        test_mult, before_mult = learn_multipliers(df_ana)
        df_recent = df_ana[pd.to_datetime(df_ana['日付']) >= (jst_today - pd.Timedelta(days=28))]
        target_dates = [jst_today + timedelta(days=i) for i in range(1, 8)]
        
        if not df_recent.empty:
            pred_time_slots = get_time_slots_for_period((jst_today + pd.Timedelta(days=7)).strftime('%Y年%m月'))
            weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            predict_data = pd.DataFrame(0.0, index=weekdays, columns=pred_time_slots)

            def get_active_slots(in_str, out_str, slots_list):
                def parse_t(t_str):
                    t_str = str(t_str).strip()
                    try:
                        parts = t_str.split(":")
                        if len(parts) >= 2: return datetime.strptime(f"{int(parts[0]):02d}:{int(parts[1]):02d}", "%H:%M").time()
                    except: pass
                    return None
                in_t, out_t = parse_t(in_str), parse_t(out_str)
                if not in_t or not out_t: return []
                slots = []
                for slot_str in slots_list:
                    h = int(slot_str[:2])
                    slot_start = datetime.strptime(f"{h:02d}:00", "%H:%M").time()
                    slot_end = datetime.strptime(f"{h+1:02d}:00", "%H:%M").time() if h < 22 else datetime.strptime("23:59", "%H:%M").time()
                    if in_t < slot_end and out_t > slot_start: slots.append(slot_str)
                return slots

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

            html = "<div class='heatmap-wrapper'><table class='heatmap-table'>"
            html += "<tr><th class='sticky-col'>Day</th>"
            for tb in pred_time_slots: html += f"<th>{tb[:2]}:00</th>"
            html += "</tr>"
            for wd in weekdays:
                html += f"<tr><th class='sticky-col'>{wd}</th>"
                for tb in pred_time_slots:
                    val = predict_data.loc[wd, tb]
                    ratio = min(val / 20.0, 1.0)
                    rounded_val = int(round(val))
                    if rounded_val >= 20: bg_color, font_color, display_val = "rgba(239, 68, 68, 0.9)", "#FFF", "MAX"
                    elif rounded_val >= 15: bg_color, font_color, display_val = f"rgba(245, 158, 11, {max(0.6, ratio)})", "#FFF", f"{rounded_val}"
                    elif rounded_val > 0: bg_color, font_color, display_val = f"rgba(59, 130, 246, {ratio * 0.8})", ("#FFF" if ratio > 0.4 else "var(--text-color)"), f"{rounded_val}"
                    else: bg_color, font_color, display_val = "transparent", "var(--text-color)", ""
                    border = "1px solid rgba(128,128,128,0.05)" if rounded_val == 0 else "none"
                    html += f"<td style='background-color: {bg_color}; color: {font_color}; border: {border};'>{display_val}</td>"
                html += "</tr>"
            html += "</table></div>"
            st.markdown(html, unsafe_allow_html=True)
    else: st.info("No data available.")

elif menu == "Leaderboard":
    st.markdown("<div class='section-title'>Leaderboard Overview</div>", unsafe_allow_html=True)
    df = load_data()

    if not df.empty:
        jst_today = pd.Timestamp(jst_now.date())
        first_day_of_this_month = jst_today.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - pd.Timedelta(days=1)
        
        df_vp = df[df['日付'] <= jst_today]
        df_this_month = df_vp[(df_vp['日付'].dt.year == jst_today.year) & (df_vp['日付'].dt.month == jst_today.month)]
        
        def get_agg(target_df):
            if target_df.empty: return pd.DataFrame()
            return target_df.groupby(['名前', '学年'])['利用時間（時間）'].sum().reset_index().sort_values(by='利用時間（時間）', ascending=False).reset_index(drop=True)
            
        agg_data = get_agg(df_this_month)
        
        if not agg_data.empty:
            agg_data['順位'] = agg_data['利用時間（時間）'].rank(method='min', ascending=False).astype(int)
            top_rows = agg_data[agg_data['順位'] <= 3]
            
            html = "<div class='top-rank-grid'>"
            for i, row in top_rows.iterrows():
                rank = row['順位']
                name = row['名前']
                grade = row['学年'] if pd.notnull(row['学年']) and row['学年'] != "" else "-"
                val = row['利用時間（時間）']
                badge_class = f"badge-{rank}" if rank <= 3 else "badge-2"
                
                html += f"""
                <div class='top-rank-card'>
                    <div class='top-rank-badge {badge_class}'>Rank {rank}</div>
                    <div class='top-rank-grade'>{grade}</div>
                    <div class='top-rank-name'>{name}</div>
                    <div class='top-rank-time'><span class='time-v'>{val:.1f}</span><span class='time-u'>HRS</span></div>
                </div>
                """
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)
            
            st.markdown("<div class='section-title'>Full Rankings (Current Month)</div>", unsafe_allow_html=True)
            st.markdown(render_ranking_html(agg_data), unsafe_allow_html=True)
        else: st.info("No data for current month.")
    else: st.info("No data available.")

elif menu == "Batch Entry":
    st.markdown("<div class='section-title'>Batch Entry Module</div>", unsafe_allow_html=True)
    f_date_batch = st.date_input("Date (Applied to all)", jst_now.date(), max_value=jst_now.date())
    
    if "batch_data" not in st.session_state: st.session_state.batch_data = [{"学年": "-- Select --", "氏名": "", "開始時間": "", "終了時間": ""} for _ in range(25)]
    df_empty = pd.DataFrame(st.session_state.batch_data)
    
    edited_df = st.data_editor(
        df_empty,
        column_config={
            "学年": st.column_config.SelectboxColumn("Grade", options=GRADES, width="small"),
            "氏名": st.column_config.TextColumn("Full Name", width="medium"),
            "開始時間": st.column_config.TextColumn("Check In (e.g. 1530)", width="small"),
            "終了時間": st.column_config.TextColumn("Check Out (e.g. 1800)", width="small"),
        },
        column_order=["学年", "氏名", "開始時間", "終了時間"], num_rows="dynamic", use_container_width=True, height=500, key=f"editor_{st.session_state.form_key}"
    )
    
    if st.button("Commit Batch", type="primary"):
        valid_rows = edited_df[edited_df["氏名"].str.strip() != ""]
        if valid_rows.empty: st.error("No valid names entered.")
        else:
            new_records, error_msgs = [], []
            df_current = load_data()
            for idx, row in valid_rows.iterrows():
                name = row["氏名"].replace(" ", "").replace(" ", "")
                grade_input = row.get("学年")
                if pd.isna(grade_input) or grade_input == "-- Select --" or not grade_input:
                    error_msgs.append(f"{name}: Grade missing."); continue
                in_dt_time, out_dt_time = parse_custom_time(row["開始時間"]), parse_custom_time(row["終了時間"])
                if in_dt_time is None or out_dt_time is None:
                    error_msgs.append(f"{name}: Invalid time format."); continue
                duration = calc_duration(in_dt_time, out_dt_time)
                if duration <= 0:
                    error_msgs.append(f"{name}: Negative duration."); continue
                in_str, out_str = in_dt_time.strftime("%H:%M"), out_dt_time.strftime("%H:%M")
                
                is_dup_current = not df_current[(df_current['日付'] == pd.to_datetime(f_date_batch)) & (df_current['名前'] == name) & (df_current['入室時間'] == in_str) & (df_current['退室時間'] == out_str)].empty
                is_dup_new = any(r['名前'] == name and r['入室時間'] == in_str and r['退室時間'] == out_str for r in new_records)
                if is_dup_current or is_dup_new:
                    error_msgs.append(f"{name}: Duplicate record."); continue
                new_records.append({'日付': pd.to_datetime(f_date_batch), '名前': name, '学年': grade_input, '入室時間': in_str, '退室時間': out_str, '利用時間（時間）': duration})
            
            if error_msgs:
                for err in error_msgs: st.error(err)
            if new_records:
                df = pd.concat([df_current, pd.DataFrame(new_records)], ignore_index=True)
                save_data(df)
                st.session_state.batch_data = [{"学年": "-- Select --", "氏名": "", "開始時間": "", "終了時間": ""} for _ in range(25)]
                st.session_state.form_key += 1
                st.session_state.sys_msg = f"Successfully committed {len(new_records)} records."
                st.rerun()

elif menu == "Single Entry":
    st.markdown("<div class='section-title'>Single Entry Module</div>", unsafe_allow_html=True)
    df_history = load_data()
    user_list = ["-- New User --"]
    recent_users = pd.DataFrame()
    if not df_history.empty:
        recent_users = df_history[['名前', '学年']].drop_duplicates(subset=['名前']).dropna()
        user_list += recent_users['名前'].tolist()

    st.markdown("<div style='background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.1); padding: 32px; border-radius: 16px; margin-bottom: 2rem;'>", unsafe_allow_html=True)
    selected_user = st.selectbox("Search Past Users", user_list)
    if selected_user != "-- New User --":
        default_name = selected_user
        try:
            default_grade = recent_users[recent_users['名前'] == selected_user]['学年'].values[0]
            if not default_grade: default_grade = "-- Select --"
        except: default_grade = "-- Select --"
    else:
        default_name, default_grade = "", "-- Select --"

    col1, col2 = st.columns([1, 1])
    with col1: f_date = st.date_input("Date", jst_now.date(), max_value=jst_now.date())
    with col2: 
        g_index = GRADES.index(default_grade) if default_grade in GRADES else 0
        f_grade = st.selectbox("Grade", GRADES, index=g_index)
        
    k_name = f"name_{st.session_state.form_key}"
    f_name = st.text_input("Full Name", value=default_name, key=k_name)

    in_key, out_key = f"single_in_{st.session_state.form_key}", f"single_out_{st.session_state.form_key}"
    if in_key not in st.session_state: st.session_state[in_key] = (jst_now - timedelta(hours=1)).strftime("%H:%M")
    if out_key not in st.session_state: st.session_state[out_key] = jst_now.strftime("%H:%M")

    col_in, col_out = st.columns(2)
    with col_in: in_time_str = st.text_input("Check In", key=in_key, on_change=format_time_input, args=(in_key,))
    with col_out: out_time_str = st.text_input("Check Out", key=out_key, on_change=format_time_input, args=(out_key,))

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Submit Record", type="primary"):
        f_name_clean = f_name.replace(" ", "").replace(" ", "")
        in_time, out_time = parse_custom_time(in_time_str), parse_custom_time(out_time_str)
        if not f_name_clean: st.error("Name is required.")
        elif f_grade == "-- Select --": st.error("Grade is required.")
        elif in_time is None or out_time is None: st.error("Invalid time format.")
        else:
            duration = calc_duration(in_time, out_time)
            if duration <= 0: st.error("Check Out must be after Check In.")
            else:
                df = load_data()
                in_str, out_str = in_time.strftime("%H:%M"), out_time.strftime("%H:%M")
                is_dup = not df[(df['日付'] == pd.to_datetime(f_date)) & (df['名前'] == f_name_clean) & (df['入室時間'] == in_str) & (df['退室時間'] == out_str)].empty
                if is_dup: st.error("Record already exists.")
                else:
                    new_row = pd.DataFrame([{'日付': pd.to_datetime(f_date), '名前': f_name_clean, '学年': f_grade, '入室時間': in_str, '退室時間': out_str, '利用時間（時間）': duration}])
                    df = pd.concat([df, new_row], ignore_index=True)
                    save_data(df)
                    st.session_state.form_key += 1 
                    st.session_state.sys_msg = f"Record submitted for {f_name_clean}."
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif menu == "Data Manager":
    st.markdown("<div class='section-title'>Database Management</div>", unsafe_allow_html=True)
    df_manage = load_data()
    
    if not df_manage.empty:
        options = []
        for i in reversed(df_manage.index):
            row = df_manage.loc[i]
            d_str = row['日付'].strftime('%m/%d') if pd.notnull(row['日付']) else "N/A"
            options.append((str(i), f"{d_str} | {row['名前']} ({row['入室時間']} - {row['退室時間']})"))
            
        st.markdown("<div style='background: var(--secondary-background-color); border: 1px solid rgba(128,128,128,0.1); padding: 32px; border-radius: 16px; margin-bottom: 2rem;'>", unsafe_allow_html=True)
        selected_mng = st.selectbox("Select Record to Edit", [("-1", "-- Select --")] + options[:50], format_func=lambda x: x[1])
        if selected_mng[0] != "-1":
            target_idx = int(selected_mng[0])
            target_row = df_manage.loc[target_idx]
            
            default_date = target_row['日付'].date() if pd.notnull(target_row['日付']) else jst_now.date()
            edit_date = st.date_input("Date", default_date)
            edit_name = st.text_input("Name", value=str(target_row['名前']))
            
            edit_in_key, edit_out_key = f"edit_in_{target_idx}_{target_row['名前']}", f"edit_out_{target_idx}_{target_row['名前']}"
            if edit_in_key not in st.session_state: st.session_state[edit_in_key] = str(target_row['入室時間'])
            if edit_out_key not in st.session_state: st.session_state[edit_out_key] = str(target_row['退室時間'])

            col_in, col_out = st.columns(2)
            with col_in: edit_in_str = st.text_input("Check In", key=edit_in_key, on_change=format_time_input, args=(edit_in_key,))
            with col_out: edit_out_str = st.text_input("Check Out", key=edit_out_key, on_change=format_time_input, args=(edit_out_key,))

            current_grade = str(target_row['学年']) if str(target_row['学年']) else "-- Select --"
            edit_grade = st.selectbox("Grade", GRADES, index=(GRADES.index(current_grade) if current_grade in GRADES else 0))
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Update Record", use_container_width=True, type="primary"):
                    edit_name_clean = edit_name.replace(" ", "").replace(" ", "")
                    edit_in, edit_out = parse_custom_time(edit_in_str), parse_custom_time(edit_out_str)
                    if edit_name_clean and edit_grade != "-- Select --" and edit_in and edit_out:
                        duration = calc_duration(edit_in, edit_out)
                        if duration > 0:
                            df_manage.at[target_idx, '日付'] = pd.to_datetime(edit_date)
                            df_manage.at[target_idx, '名前'] = edit_name_clean
                            df_manage.at[target_idx, '学年'] = edit_grade
                            df_manage.at[target_idx, '入室時間'] = edit_in.strftime("%H:%M")
                            df_manage.at[target_idx, '退室時間'] = edit_out.strftime("%H:%M")
                            df_manage.at[target_idx, '利用時間（時間）'] = duration
                            save_data(df_manage)
                            st.session_state.sys_msg = "Record updated successfully."
                            st.rerun()
                        else: st.error("Invalid duration.")
                    else: st.error("Please fill all fields correctly.")
            with col_btn2:
                if st.button("Delete Record", use_container_width=True):
                    df_manage = df_manage.drop(target_idx).reset_index(drop=True)
                    save_data(df_manage)
                    st.session_state.sys_msg = "Record deleted."
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='section-title'>Batch Actions</div>", unsafe_allow_html=True)
        selected_dels = st.multiselect("Select records for bulk deletion", options, format_func=lambda x: x[1])
        if st.button("Delete Selected", type="primary"):
            if selected_dels:
                indices_to_drop = [int(x[0]) for x in selected_dels]
                df_manage = df_manage.drop(indices_to_drop).reset_index(drop=True)
                save_data(df_manage)
                st.session_state.sys_msg = f"{len(indices_to_drop)} records deleted."
                st.rerun()
            else: st.warning("No records selected.")
    else: st.info("Database is empty.")
