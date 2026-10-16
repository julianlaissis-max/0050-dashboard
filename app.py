import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
from dateutil.relativedelta import relativedelta
import time

# ----------------- 運算與資料獲取函數區 -----------------

@st.cache_data(ttl=3600)
def get_twse_0050_data(months=7):
    """直攻證交所抓取 0050 普通交易資料"""
    today = datetime.date.today()
    dfs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(months):
        target_month = today - relativedelta(months=i)
        date_str = target_month.strftime('%Y%m01')
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo=0050"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            data = res.json()
            if data.get('stat') == 'OK':
                df = pd.DataFrame(data['data'], columns=data['fields'])
                dfs.append(df)
        except Exception:
            pass
        time.sleep(1)
    
    if not dfs: return pd.DataFrame()
        
    df = pd.concat(dfs, ignore_index=True)
    def convert_date(d_str):
        parts = d_str.split('/')
        return f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
    
    df['Date'] = pd.to_datetime(df['日期'].apply(convert_date))
    df['Close'] = df['收盤價'].str.replace(',', '').astype(float)
    df['Volume'] = df['成交股數'].str.replace(',', '').astype(float)
    df = df.sort_values('Date').set_index('Date')
    df = df[~df.index.duplicated(keep='last')]
    return df

@st.cache_data(ttl=3600)
def get_stock_data(stock_id, days=200):
    """FinMind 抓取 50 檔成分股"""
    start_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset": "TaiwanStockPrice", "data_id": stock_id, "start_date": start_date}
    for _ in range(3):
        try:
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            if data.get('status') == 200 and len(data.get('data', [])) > 0:
                df = pd.DataFrame(data['data'])
                df['Close'] = df['close']
                df['Volume'] = df['Trading_Volume']
                return df
        except Exception:
            time.sleep(1)
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_pe_ratio(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get('trailingPE') or info.get('forwardPE') or 0
    except:
        return 0

def compute_rsi(data, window=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/window, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600)
def backtest_0050_strategy():
    """回測 10 年使用 yfinance，並回傳今日實際狀況對比數值"""
    ticker = yf.Ticker("0050.TW")
    df = ticker.history(period="10y", auto_adjust=False).dropna(subset=['Close'])
    if len(df) < 60: return None
    df['20MA'] = df['Close'].rolling(window=20).mean()
    df['RSI_7'] = compute_rsi(df['Close'], window=7)
    df['RSI_14'] = compute_rsi(df['Close'], window=14)
    
    current_price = df['Close'].iloc[-1]
    current_20ma = df['20MA'].iloc[-1]
    current_rsi7 = df['RSI_7'].iloc[-1]
    current_rsi14 = df['RSI_14'].iloc[-1]
    
    df['Future_5d_Return'] = df['Close'].shift(-5) / df['Close'] - 1
    condition = (df['Close'] < df['20MA']) & (df['RSI_14'] < 40)
    target_days = df[condition].dropna(subset=['Future_5d_Return'])
    occurrences = len(target_days)
    win_rate = (target_days['Future_5d_Return'] > 0).mean() * 100 if occurrences > 0 else 0
    avg_return = target_days['Future_5d_Return'].mean() * 100 if occurrences > 0 else 0
    
    return {
        "occurrences": occurrences, "win_rate": win_rate, "avg_return": avg_return,
        "current_price": current_price, "current_20ma": current_20ma,
        "current_rsi7": current_rsi7, "current_rsi14": current_rsi14
    }

def highlight_ma(row):
    styles = [''] * len(row) 
    price = row['最新價格']
    for idx, col in enumerate(row.index):
        if col in ['5MA', '10MA', '20MA', '60MA']:
            ma_val = row[col]
            if ma_val > 0: 
                if price > ma_val: styles[idx] = 'color: #ff4b4b; font-weight: bold;'
                elif price < ma_val: styles[idx] = 'color: #09ab3b; font-weight: bold;'
    return styles

# ----------------- 頁面與資料處理 -----------------
st.set_page_config(layout="wide", page_title="0050 量化儀表板")
st.title("我的 0050 績效儀表板 📈")

components = {
    "代號": ["2330.TW", "2454.TW", "2308.TW", "2317.TW", "3711.TW", "2303.TW", "1303.TW", "2383.TW", "3037.TW", "2881.TW", 
           "2891.TW", "2882.TW", "3017.TW", "2887.TW", "2345.TW", "2327.TW", "2382.TW", "2885.TW", "2884.TW", "2360.TW", 
           "2357.TW", "2886.TW", "2883.TW", "2890.TW", "3008.TW", "3443.TW", "2412.TW", "3653.TW", "2408.TW", "6669.TW", 
           "2059.TW", "3231.TW", "2301.TW", "2344.TW", "2892.TW", "2880.TW", "2368.TW", "4958.TW", "1216.TW", "6446.TWO", 
           "3665.TW", "8046.TW", "2395.TW", "2449.TW", "5880.TW", "7769.TWO", "2603.TW", "4904.TW", "3045.TW", "6505.TW"],
    "名稱": ["台積電", "聯發科", "台達電", "鴻海", "日月光投控", "聯電", "南亞", "台光電", "欣興", "富邦金", 
           "中信金", "國泰金", "奇鋐", "台新新光金", "智邦", "國巨", "廣達", "元大金", "玉山金", "致茂", 
           "華碩", "兆豐金", "凱基金", "永豐金", "大立光", "創意", "中華電", "健策", "南亞科", "緯穎", 
           "川湖", "緯創", "光寶科", "華邦電", "第一金", "華南金", "金像電", "臻鼎-KY", "統一", "藥華藥", 
           "貿聯-KY", "南電", "研華", "京元電子", "合庫金", "鴻勁", "長榮", "遠傳", "台灣大", "台塑化"],
    "產業別": ["半導體", "半導體", "電子零組件", "其他電子", "半導體", "半導體", "塑膠工業", "電子零組件", "電子零組件", "金融保險", 
            "金融保險", "金融保險", "電腦及週邊", "金融保險", "通信網路", "電子零組件", "電腦及週邊", "金融保險", "金融保險", "其他電子", 
            "電腦及週邊", "金融保險", "金融保險", "金融保險", "光電業", "半導體", "通信網路", "電子零組件", "半導體", "電腦及週邊", 
            "電子零組件", "電腦及週邊", "電腦及週邊", "半導體", "金融保險", "金融保險", "電子零組件", "電子零組件", "食品工業", "生技醫療", 
            "電子零組件", "電子零組件", "電腦及週邊", "半導體", "金融保險", "半導體", "航運業", "通信網路", "通信網路", "油電燃氣"],
    "權重(%)": [56.66, 5.99, 3.02, 2.85, 2.13, 1.49, 1.45, 1.44, 1.38, 1.29, 1.25, 1.06, 1.02, 0.95, 0.94, 0.86, 0.82, 0.80, 0.75, 0.71, 
             0.64, 0.61, 0.59, 0.58, 0.58, 0.58, 0.56, 0.56, 0.55, 0.55, 0.53, 0.53, 0.50, 0.48, 0.45, 0.44, 0.42, 0.42, 0.38, 0.37, 
             0.35, 0.33, 0.30, 0.30, 0.29, 0.29, 0.28, 0.19, 0.18, 0.14]
}
df_comp = pd.DataFrame(components)

# 先在背景抓資料
progress_bar = st.progress(0)
status_text = st.empty()
status_text.text("📡 正在向台灣證交所與 API 連線，獲取最新官方精確資料...")

# 抓取 0050
df_0050_full = get_twse_0050_data(months=7)

# 抓取成分股
basic_results, tech_results = [], []
for index, row in df_comp.iterrows():
    stock_id = row["代號"].split(".")[0]
    df_stock = get_stock_data(stock_id, days=200)
    pe_ratio = get_pe_ratio(row["代號"])
        
    if not df_stock.empty and len(df_stock) >= 60:
        today_p = df_stock['close'].iloc[-1]
        yest_p = df_stock['close'].iloc[-2]
        change_pct = (today_p - yest_p) / yest_p * 100
        today_vol = int(df_stock['Trading_Volume'].iloc[-1] / 1000)
        yest_vol = int(df_stock['Trading_Volume'].iloc[-2] / 1000)
        vol_change_pct = (today_vol - yest_vol) / yest_vol * 100 if yest_vol > 0 else 0
        ma5 = df_stock['close'].rolling(window=5).mean().iloc[-1]
        ma10 = df_stock['close'].rolling(window=10).mean().iloc[-1]
        ma20 = df_stock['close'].rolling(window=20).mean().iloc[-1]
        ma60 = df_stock['close'].rolling(window=60).mean().iloc[-1]
        rsi_14 = compute_rsi(df_stock['close'], window=14).iloc[-1]
        rsi_7 = compute_rsi(df_stock['close'], window=7).iloc[-1]
    else:
        today_p = yest_p = change_pct = today_vol = vol_change_pct = ma5 = ma10 = ma20 = ma60 = rsi_14 = rsi_7 = 0
        
    basic_results.append({"股票名稱": row["名稱"], "產業別": row["產業別"], "權重(%)": row["權重(%)"], "最新價格": round(today_p, 2), "今日漲跌幅(%)": round(change_pct, 2)})
    tech_results.append({"股票名稱": row["名稱"], "最新價格": today_p, "本益比": round(pe_ratio, 2), "RSI(7日)": round(rsi_7, 2), "RSI(14日)": round(rsi_14, 2), "今日成交量(張)": today_vol, "成交量增減(%)": vol_change_pct, "5MA": ma5, "10MA": ma10, "20MA": ma20, "60MA": ma60})
    progress_bar.progress((index + 1) / len(df_comp))

# 資料準備完成，清除進度條
progress_bar.empty()
status_text.empty()

df_basic = pd.DataFrame(basic_results)
df_tech = pd.DataFrame(tech_results)
df_merged = pd.merge(df_basic, df_tech.drop(columns=['最新價格']), on="股票名稱")

# ================= 產生 AI 動態摘要 (Executive Summary) =================
if not df_0050_full.empty:
    p_0050 = df_0050_full['Close'].iloc[-1]
    ma5_0050 = df_0050_full['Close'].rolling(5).mean().iloc[-1]
    ma10_0050 = df_0050_full['Close'].rolling(10).mean().iloc[-1]
    ma20_0050 = df_0050_full['Close'].rolling(20).mean().iloc[-1]
    ma60_0050 = df_0050_full['Close'].rolling(60).mean().iloc[-1]
    rsi14_0050 = compute_rsi(df_0050_full['Close'], 14).iloc[-1]
    vol_0050 = df_0050_full['Volume'].iloc[-1] / 1000
    vol20_0050 = df_0050_full['Volume'].rolling(20).mean().iloc[-1] / 1000
    
    # 判斷 0050 均線狀態
    broken_mas = []
    stand_mas = []
    
    if p_0050 < ma5_0050:
        broken_mas.append("5日週")
    else:
        stand_mas.append("5日週")
        
    if p_0050 < ma10_0050:
        broken_mas.append("10日雙週")
    else:
        stand_mas.append("10日雙週")
        
    if p_0050 < ma20_0050:
        broken_mas.append("20日月")
    else:
        stand_mas.append("20日月")
        
    if p_0050 < ma60_0050:
        broken_mas.append("60日季")
    else:
        stand_mas.append("60日季")
    
    str_broken = "、".join(broken_mas) + "線" if broken_mas else "無"
    str_stand = "、".join(stand_mas) + "線" if stand_mas else "無"
    vol_status = "放量" if vol_0050 > vol20_0050 else "量縮"
    
    # 成分股分析
    above_5_up = df_merged[(df_merged['最新價格'] > df_merged['5MA']) & (df_merged['今日漲跌幅(%)'] > 0)]
    below_5_down = df_merged[(df_merged['最新價格'] < df_merged['5MA']) & (df_merged['今日漲跌幅(%)'] < 0)]
    top_above_5_sec = above_5_up['產業別'].value_counts().idxmax() if not above_5_up.empty else "無明顯強勢板塊"
    top_below_5_sec = below_5_down['產業別'].value_counts().idxmax() if not below_5_down.empty else "無明顯弱勢板塊"
    
    above_10_up = df_merged[(df_merged['最新價格'] > df_merged['10MA']) & (df_merged['今日漲跌幅(%)'] > 0)]
    below_10_down = df_merged[(df_merged['最新價格'] < df_merged['10MA']) & (df_merged['今日漲跌幅(%)'] < 0)]
    top_above_10_sec = above_10_up['產業別'].value_counts().idxmax() if not above_10_up.empty else "無明顯強勢板塊"
    top_below_10_sec = below_10_down['產業別'].value_counts().idxmax() if not below_10_down.empty else "無明顯弱勢板塊"

    # 弱勢股估值分析
    high_pe_weak = df_merged[(df_merged['最新價格'] < df_merged['20MA']) & (df_merged['本益比'] > 25)]
    
    # RSI 分析
    rsi_weak = df_merged[(df_merged['RSI(14日)'] < 40) | (df_merged['RSI(7日)'] < 40)]
    rsi_weak_sectors = list(rsi_weak['產業別'].value_counts().head(2).index)
    
    st.success("### 🔥 今日盤勢速報 (Executive Summary)")
    st.markdown(f"""
    * **0050 大盤狀態：** 目前收盤價 ({p_0050:.2f}) 跌破了 **{str_broken}**，站上 **{str_stand}**。今日呈現 **{vol_status}** 格局（成交量 {vol_0050:,.0f} 張 vs 20日均量 {vol20_0050:,.0f} 張），RSI(14) 為 **{rsi14_0050:.1f}**。
    * **短線 (5MA) 多空交戰：** 站上 5MA 且上漲的強勢股中，以 **{top_above_5_sec}** ({len(above_5_up)}家) 表現最佳；跌破 5MA 且下跌的弱勢股，則由 **{top_below_5_sec}** ({len(below_5_down)}家) 領跌。
    * **波段 (10MA) 多空交戰：** 站上 10MA 且上漲以 **{top_above_10_sec}** ({len(above_10_up)}家) 居多；跌破 10MA 且下跌則以 **{top_below_10_sec}** ({len(below_10_down)}家) 居多。
    * **弱勢股估值體檢：** 跌破 20日均線的成分股中，有 **{len(high_pe_weak)} 家** 的本益比仍高於 25 倍，顯示這些高估值個股近期明顯面臨修正與獲利了結的壓力。
    * **籌碼與動能 (RSI)：** 目前有 **{len(rsi_weak)} 家** 成分股的 7日或 14日 RSI 跌入弱勢區 (<40)，主要集中在 **{'、'.join(rsi_weak_sectors) if rsi_weak_sectors else '無'}** 產業，代表這些板塊近期籌碼較為沉重，需等待量縮打底。
    """)
st.divider()

# ================= 0050 專屬技術指標區塊 =================
if not df_0050_full.empty and len(df_0050_full) >= 60:
    st.header("🎯 元大台灣50 (0050) 技術指標")
    latest_price = df_0050_full['Close'].iloc[-1]
    yesterday_price = df_0050_full['Close'].iloc[-2]
    change_0050 = (latest_price - yesterday_price) / yesterday_price * 100
    
    ma5 = df_0050_full['Close'].rolling(window=5).mean().iloc[-1]
    ma20 = df_0050_full['Close'].rolling(window=20).mean().iloc[-1]
    ma60 = df_0050_full['Close'].rolling(window=60).mean().iloc[-1]
    rsi_14 = compute_rsi(df_0050_full['Close'], window=14).iloc[-1]
    
    vol_lots = int(df_0050_full['Volume'].iloc[-1] / 1000)
    vol_20ma_lots = df_0050_full['Volume'].rolling(window=20).mean().iloc[-1] / 1000
    
    indicators_data = {
        "項目": ["收盤價", "5 日（週線）", "20 日（月線）", "60 日（季線）", "RSI (14)", "成交量 (張)", "20 日均量 (張)"],
        "數值": [f"{latest_price:.2f}", f"{ma5:.2f}", f"{ma20:.2f}", f"{ma60:.2f}", f"{rsi_14:.2f}", f"{vol_lots:,}", f"{vol_20ma_lots:,.2f}"]
    }
    df_indicators = pd.DataFrame(indicators_data)

    col_a, col_b = st.columns([1, 1.5])
    with col_a:
        st.metric(label="0050 最新收盤價", value=f"{latest_price:.2f}", delta=f"{change_0050:.2f}%")
        st.info("💡 **小提示：** 0050 最新動態請參考上方之 Executive Summary 速報！")
    with col_b:
        st.markdown("**指標數值**")
        st.dataframe(df_indicators, hide_index=True, use_container_width=True)
st.divider()

# ================= 總體表現掃描區塊 =================
st.header("🌟 成分股總體掃描 (Macro Overview)")

up_count = (df_basic['今日漲跌幅(%)'] > 0).sum()
down_count = (df_basic['今日漲跌幅(%)'] < 0).sum()
flat_count = (df_basic['今日漲跌幅(%)'] == 0).sum()
vol_up_count = (df_tech['成交量增減(%)'] > 0).sum()

above_5 = (df_tech['最新價格'] > df_tech['5MA']).sum()
below_5 = (df_tech['最新價格'] < df_tech['5MA']).sum()
above_10 = (df_tech['最新價格'] > df_tech['10MA']).sum()
below_10 = (df_tech['最新價格'] < df_tech['10MA']).sum()
above_20 = (df_tech['最新價格'] > df_tech['20MA']).sum()
below_20 = (df_tech['最新價格'] < df_tech['20MA']).sum()
above_60 = (df_tech['最新價格'] > df_tech['60MA']).sum()
below_60 = (df_tech['最新價格'] < df_tech['60MA']).sum()

pe_high = (df_tech['本益比'] > 25).sum()
pe_low = ((df_tech['本益比'] < 20) & (df_tech['本益比'] > 0)).sum()

st.subheader("1️⃣ 基本與籌碼動能")
c1, c2, c3, c4 = st.columns(4)
c1.metric("上漲家數", f"{up_count} 家")
c2.metric("下跌家數", f"{down_count} 家")
c3.metric("平盤家數", f"{flat_count} 家")
c4.metric("成交量量增家數", f"{vol_up_count} 家")

st.subheader("2️⃣ 均線多空交戰 (高於 vs 跌破)")
c5, c6, c7, c8 = st.columns(4)
c5.metric("5MA (週線)", f"高於:{above_5} / 跌破:{below_5}")
c6.metric("10MA (雙週線)", f"高於:{above_10} / 跌破:{below_10}")
c7.metric("20MA (月線)", f"高於:{above_20} / 跌破:{below_20}")
c8.metric("60MA (季線)", f"高於:{above_60} / 跌破:{below_60}")

st.subheader("3️⃣ 估值家數分佈")
c9, c10 = st.columns(2)
c9.metric("🔥 偏貴/高成長 (P/E > 25)", f"{pe_high} 家")
c10.metric("💰 合理/便宜 (P/E < 20)", f"{pe_low} 家")

st.divider()

# ================= 視覺化板塊與細項區塊 =================
col1, col2 = st.columns(2)
with col1:
    st.subheader("📊 產業板塊總體表現")
    sector_group = df_basic.groupby('產業別').agg(總權重_佔比=('權重(%)', 'sum'), 平均漲跌幅=('今日漲跌幅(%)', 'mean'), 上漲家數=('今日漲跌幅(%)', lambda x: (x > 0).sum()), 下跌家數=('今日漲跌幅(%)', lambda x: (x < 0).sum())).reset_index()
    sector_group['平均漲跌幅'] = sector_group['平均漲跌幅'].round(2)
    sector_group = sector_group.sort_values(by='總權重_佔比', ascending=False)
    
    st.dataframe(
        sector_group,
        column_config={
            "總權重_佔比": st.column_config.ProgressColumn("權重佔比 (%)", format="%.2f", min_value=0, max_value=70),
            "平均漲跌幅": st.column_config.NumberColumn("平均漲跌幅 (%)", format="%.2f %%")
        },
        use_container_width=True, hide_index=True
    )

with col2:
    st.subheader("🔍 核心成分股細項表現")
    st.dataframe(df_basic[['股票名稱', '產業別', '權重(%)', '最新價格', '今日漲跌幅(%)']], use_container_width=True)

st.divider()

st.subheader("📈 技術面與籌碼掃描 (MA & Volume)")
st.write("目前價格高於均線顯示紅色，低於均線顯示綠色：")

format_dict = {'最新價格': '{:.2f}', '成交量增減(%)': '{:.2f}', '5MA': '{:.2f}', '10MA': '{:.2f}', '20MA': '{:.2f}', '60MA': '{:.2f}'}
tech_display_df = df_tech[['股票名稱', '最新價格', '今日成交量(張)', '成交量增減(%)', '5MA', '10MA', '20MA', '60MA']]
styled_tech_df = tech_display_df.style.apply(highlight_ma, axis=1).format(format_dict)
st.dataframe(styled_tech_df, use_container_width=True)

st.divider()

col3, col4 = st.columns(2)
with col3:
    st.write("🔥 **本益比 > 25 倍 (偏貴/高成長)**")
    st.dataframe(df_tech[df_tech['本益比'] > 25][['股票名稱', '最新價格', '本益比', 'RSI(7日)', 'RSI(14日)']], hide_index=True, use_container_width=True)

with col4:
    st.write("💰 **本益比 < 20 倍 (合理/便宜)**")
    st.dataframe(df_tech[(df_tech['本益比'] < 20) & (df_tech['本益比'] > 0)][['股票名稱', '最新價格', '本益比', 'RSI(7日)', 'RSI(14日)']], hide_index=True, use_container_width=True)

st.divider()

st.subheader("🔮 歷史機率預測 (以 0050 為例)")
st.write("利用過去 10 年的歷史數據，驗證特定條件下的上漲機率。")
st.info("💡 **測試情境：** 當 0050 短線轉弱 (收盤價跌破 20MA) 且指標超賣 (RSI 14日 < 40) 時，買進抱 5 天。")

res = backtest_0050_strategy()

if res and res['occurrences'] > 0:
    c1, c2, c3 = st.columns(3)
    c1.metric(label="過去10年發生次數", value=f"{res['occurrences']} 次")
    c2.metric(label="未來 5 天上漲機率 (勝率)", value=f"{res['win_rate']:.1f}%")
    c3.metric(label="平均預期報酬率", value=f"{res['avg_return']:.2f}%")
    
    # ======== 這裡就是剛才不小心遺失的「今日對比訊號區塊」，已經完全補回！ ========
    st.write("---")
    st.write("🎯 **今日 0050 實際狀況對比：**")
    
    price_status = "🟢 尚未跌破" if res['current_price'] >= res['current_20ma'] else "🔴 已跌破 20MA"
    rsi_status = "🟢 尚未超賣" if res['current_rsi14'] >= 40 else "🔴 已進入超賣區"
    
    st.write(f"- **價格與均線：** 目前收盤價為 **{res['current_price']:.2f}**，20MA 為 **{res['current_20ma']:.2f}** ➔ {price_status}")
    st.write(f"- **動能指標：** 7日 RSI 為 **{res['current_rsi7']:.2f}**，14日 RSI 為 **{res['current_rsi14']:.2f}** ➔ {rsi_status}")
    
    if res['current_price'] < res['current_20ma'] and res['current_rsi14'] < 40:
        st.success("✨ **訊號觸發！** 目前 0050 完全符合測試情境，你可以參考上方的歷史勝率來決定是否佈局。")
    else:
        st.warning("⏳ **持續觀察中：** 目前尚未完全滿足跌破 20MA 且 RSI < 40 的條件，建議耐心等待資金買點。")
else:
    st.warning("歷史資料不足或沒有符合此條件的紀錄。")