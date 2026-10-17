import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import datetime
from dateutil.relativedelta import relativedelta
import time

# --- 富果 Fugle 套件 ---
try:
    from fugle_marketdata import RestClient
except ImportError:
    pass

# ================= 運算與資料獲取函數區 =================

FUGLE_API_KEY = "MjkwZTExZmEtOWJjMC00MDFmLTkwMDEtZjg5N2ZiYWY1ZTE3IDY1NTAwNDNiLTcxYWMtNGFmOC1iMmJlLWVmMjRhMWRmYTdhMw=="

@st.cache_data(ttl=60) 
def get_fugle_realtime_0050():
    """引擎零：富果 Fugle 盤中即時報價"""
    try:
        client = RestClient(api_key=FUGLE_API_KEY)
        quote = client.stock.intraday.quote(symbol="0050")
        
        price = quote.get('lastPrice') or quote.get('closePrice') or quote.get('lastTrade', {}).get('price')
        prev_close = quote.get('previousClose', price)
        volume = quote.get('total', {}).get('tradeVolume', 0)
        
        # 時間格式轉換邏輯
        raw_time = quote.get('lastTrade', {}).get('time') or quote.get('total', {}).get('time')
        trade_time = "最新即時"
        if raw_time:
            try:
                ts = int(raw_time)
                if ts > 10000000000000:  # 處理微秒 (16位數)
                    ts = ts / 1000000
                elif ts > 10000000000:   # 處理毫秒 (13位數)
                    ts = ts / 1000
                # 轉換為台灣時區的易讀格式
                trade_time = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                # 若為字串格式則直接切分
                trade_time = str(raw_time).replace('T', ' ').split('.')[0]
        
        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100
            return {
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "volume": volume,
                "time": trade_time
            }
    except Exception as e:
        return None
    return None

@st.cache_data(ttl=3600)
def get_twse_0050_data(months=7):
    """引擎一：直攻證交所抓取 0050 普通交易資料"""
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
    """引擎二：FinMind 抓取 50 檔成分股"""
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
    """引擎三：回測 10 年使用 yfinance"""
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

# ================= 頁面與資料處理 =================
st.set_page_config(layout="wide", page_title="0050 量化儀表板")
st.title("我的 0050 績效儀表板 📈")

# ⚡ 富果 Fugle 即時看板區塊 ⚡
st.header("⚡ 0050 盤中即時報價 (Powered by Fugle)")
fugle_data = get_fugle_realtime_0050()
if fugle_data:
    fc1, fc2, fc3 = st.columns(3)
    fc1.metric("0050 即時股價", f"{fugle_data['price']:.2f}", f"{fugle_data['change_pct']:.2f}%")
    fc2.metric("今日即時總量", f"{fugle_data['volume']:,} 張")
    fc3.metric("最後交易時間", f"{fugle_data['time']}")
else:
    st.warning("⚠️ 目前無法連線至富果 API
