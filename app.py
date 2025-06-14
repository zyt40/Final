import streamlit as st
import pandas as pd
import numpy as np
from 張妍婷.order_Lo8 import Record
from 張妍婷.indicator import KBar
from 張妍婷.chart import ChartOrder_MA, ChartOrder_RSI_1, ChartOrder_RSI_2, ChartOrder_BBANDS
import plotly.graph_objects as go
from talib import SMA, RSI, BBANDS, MACD
import itertools

st.set_page_config(layout="wide")
st.title("📈 技術指標策略回測與最佳化平台")

st.sidebar.header("資料設定")
df = pd.read_excel("kbars_2330_2022-01-01-2024-04-09.xlsx")
df['time'] = pd.to_datetime(df['time'])
min_date = df['time'].min().date()
max_date = df['time'].max().date()
start_date = st.sidebar.date_input("選擇開始日期", value=min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("選擇結束日期", value=max_date, min_value=min_date, max_value=max_date)

df.set_index('time', inplace=True)
df.sort_index(inplace=True)
df = df.loc[start_date:end_date]

if df.empty:
    st.error("⚠️ 資料篩選結果為空，請重新選擇日期範圍。")
    st.stop()

KBar_dic = df.to_dict(orient="list")
for k in KBar_dic:
    KBar_dic[k] = np.array(KBar_dic[k])
KBar_dic['product'] = np.repeat('demo', len(df))

Date = df.index[0].strftime("%Y%m%d")
kbar = KBar(Date, 60)
for t, p, v in zip(df.index, df['close'], df['volume']):
    kbar.AddPrice(t, p, v)
KBar_dic = {key: kbar.TAKBar[key] for key in kbar.TAKBar}
KBar_dic['product'] = np.repeat('demo', len(KBar_dic['open']))

df_ind = pd.DataFrame(KBar_dic)

st.sidebar.header("功能選擇")
mode = st.sidebar.radio("選擇功能模式", ["技術指標視覺化", "策略回測", "參數最佳化"])

if mode == "技術指標視覺化":
    st.header("📊 技術指標視覺化")
    indicators = st.multiselect("請選擇要疊加的指標", ["MA", "RSI", "BBANDS", "MACD"])
    if "MA" in indicators:
        KBar_dic['MA_long'] = SMA(KBar_dic, timeperiod=20)
        KBar_dic['MA_short'] = SMA(KBar_dic, timeperiod=5)
    if "RSI" in indicators:
        KBar_dic['RSI'] = RSI(KBar_dic, timeperiod=14)
        KBar_dic['Middle'] = np.array([50]*len(KBar_dic['time']))
    if "BBANDS" in indicators:
        KBar_dic['Upper'], KBar_dic['Middle'], KBar_dic['Lower'] = BBANDS(KBar_dic, timeperiod=20)
    if "MACD" in indicators:
        KBar_dic['macd'], KBar_dic['macdsignal'], KBar_dic['macdhist'] = MACD(KBar_dic, fastperiod=12, slowperiod=26, signalperiod=9)

    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=KBar_dic['time'], open=KBar_dic['open'], high=KBar_dic['high'], low=KBar_dic['low'], close=KBar_dic['close'], name='K線'))
    if 'MA_long' in KBar_dic:
        fig.add_trace(go.Scatter(x=KBar_dic['time'], y=KBar_dic['MA_long'], mode='lines', name='MA_long'))
    if 'MA_short' in KBar_dic:
        fig.add_trace(go.Scatter(x=KBar_dic['time'], y=KBar_dic['MA_short'], mode='lines', name='MA_short'))
    if 'Upper' in KBar_dic and 'Lower' in KBar_dic:
        fig.add_trace(go.Scatter(x=KBar_dic['time'], y=KBar_dic['Upper'], mode='lines', name='BB_Upper'))
        fig.add_trace(go.Scatter(x=KBar_dic['time'], y=KBar_dic['Lower'], mode='lines', name='BB_Lower'))
    fig.update_layout(title='互動式K線圖', xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

elif mode == "策略回測":
    st.header("📈 策略模擬回測")
    strategy = st.selectbox("選擇策略", ["MA策略", "RSI順勢", "RSI逆勢", "布林通道", "MACD策略"])
    OrderRecord = Record()
    stoploss = st.slider("移動停損點數", 5, 50, 10)

    if strategy == "MA策略":
        ma_short = st.slider("短期MA", 2, 30, 5)
        ma_long = st.slider("長期MA", 10, 120, 20)
        KBar_dic['MA_short'] = SMA(KBar_dic, timeperiod=ma_short)
        KBar_dic['MA_long'] = SMA(KBar_dic, timeperiod=ma_long)
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['MA_long'][n-1]): continue
            if OrderRecord.GetOpenInterest() == 0:
                if KBar_dic['MA_short'][n-1] <= KBar_dic['MA_long'][n-1] and KBar_dic['MA_short'][n] > KBar_dic['MA_long'][n]:
                    OrderRecord.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] - stoploss
                elif KBar_dic['MA_short'][n-1] >= KBar_dic['MA_long'][n-1] and KBar_dic['MA_short'][n] < KBar_dic['MA_long'][n]:
                    OrderRecord.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] + stoploss
            elif OrderRecord.GetOpenInterest() > 0 and KBar_dic['close'][n] < stop:
                OrderRecord.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif OrderRecord.GetOpenInterest() < 0 and KBar_dic['close'][n] > stop:
                OrderRecord.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
        ChartOrder_MA(KBar_dic, OrderRecord.GetTradeRecord())

    elif strategy == "RSI順勢":
        long = st.slider("長期RSI", 10, 30, 14)
        short = st.slider("短期RSI", 2, 10, 5)
        KBar_dic['RSI_long'] = RSI(KBar_dic, timeperiod=long)
        KBar_dic['RSI_short'] = RSI(KBar_dic, timeperiod=short)
        KBar_dic['Middle'] = np.array([50]*len(KBar_dic['time']))
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['RSI_long'][n-1]): continue
            if OrderRecord.GetOpenInterest() == 0:
                if KBar_dic['RSI_short'][n-1] <= KBar_dic['RSI_long'][n-1] and KBar_dic['RSI_short'][n] > KBar_dic['RSI_long'][n] and KBar_dic['RSI_long'][n] > 50:
                    OrderRecord.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] - stoploss
                elif KBar_dic['RSI_short'][n-1] >= KBar_dic['RSI_long'][n-1] and KBar_dic['RSI_short'][n] < KBar_dic['RSI_long'][n] and KBar_dic['RSI_long'][n] < 50:
                    OrderRecord.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] + stoploss
            elif OrderRecord.GetOpenInterest() > 0 and KBar_dic['close'][n] < stop:
                OrderRecord.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif OrderRecord.GetOpenInterest() < 0 and KBar_dic['close'][n] > stop:
                OrderRecord.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
        ChartOrder_RSI_1(KBar_dic, OrderRecord.GetTradeRecord())

    elif strategy == "RSI逆勢":
        period = st.slider("RSI期數", 5, 30, 14)
        ceil = st.slider("超買界線", 70, 90, 80)
        floor = st.slider("超賣界線", 10, 30, 20)
        KBar_dic['RSI'] = RSI(KBar_dic, timeperiod=period)
        KBar_dic['Ceil'] = np.array([ceil]*len(KBar_dic['time']))
        KBar_dic['Floor'] = np.array([floor]*len(KBar_dic['time']))
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['RSI'][n-1]): continue
            if OrderRecord.GetOpenInterest() == 0:
                if KBar_dic['RSI'][n-1] <= floor and KBar_dic['RSI'][n] > floor:
                    OrderRecord.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] - stoploss
                elif KBar_dic['RSI'][n-1] >= ceil and KBar_dic['RSI'][n] < ceil:
                    OrderRecord.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] + stoploss
            elif OrderRecord.GetOpenInterest() > 0 and (KBar_dic['close'][n] < stop or KBar_dic['RSI'][n] > ceil):
                OrderRecord.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif OrderRecord.GetOpenInterest() < 0 and (KBar_dic['close'][n] > stop or KBar_dic['RSI'][n] < floor):
                OrderRecord.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
        ChartOrder_RSI_2(KBar_dic, OrderRecord.GetTradeRecord())

    elif strategy == "布林通道":
        period = st.slider("BBANDS期數", 10, 60, 20)
        KBar_dic['Upper'], KBar_dic['Middle'], KBar_dic['Lower'] = BBANDS(KBar_dic, timeperiod=period)
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['Middle'][n-1]): continue
            if OrderRecord.GetOpenInterest() == 0:
                if KBar_dic['close'][n-1] <= KBar_dic['Lower'][n-1] and KBar_dic['close'][n] > KBar_dic['Lower'][n]:
                    OrderRecord.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] - stoploss
                elif KBar_dic['close'][n-1] >= KBar_dic['Upper'][n-1] and KBar_dic['close'][n] < KBar_dic['Upper'][n]:
                    OrderRecord.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] + stoploss
            elif OrderRecord.GetOpenInterest() > 0 and KBar_dic['close'][n] < stop:
                OrderRecord.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif OrderRecord.GetOpenInterest() < 0 and KBar_dic['close'][n] > stop:
                OrderRecord.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
        ChartOrder_BBANDS(KBar_dic, OrderRecord.GetTradeRecord())

    elif strategy == "MACD策略":
        fast = st.slider("快線週期", 5, 20, 12)
        slow = st.slider("慢線週期", 10, 30, 26)
        signal = st.slider("訊號週期", 5, 20, 9)
        KBar_dic['macd'], KBar_dic['macdsignal'], KBar_dic['macdhist'] = MACD(KBar_dic, fastperiod=fast, slowperiod=slow, signalperiod=signal)
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['macd'][n-1]) or np.isnan(KBar_dic['macdsignal'][n-1]): continue
            if OrderRecord.GetOpenInterest() == 0:
                if KBar_dic['macd'][n-1] <= KBar_dic['macdsignal'][n-1] and KBar_dic['macd'][n] > KBar_dic['macdsignal'][n]:
                    OrderRecord.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] - stoploss
                elif KBar_dic['macd'][n-1] >= KBar_dic['macdsignal'][n-1] and KBar_dic['macd'][n] < KBar_dic['macdsignal'][n]:
                    OrderRecord.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                    stop = KBar_dic['open'][n+1] + stoploss
            elif OrderRecord.GetOpenInterest() > 0 and KBar_dic['close'][n] < stop:
                OrderRecord.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif OrderRecord.GetOpenInterest() < 0 and KBar_dic['close'][n] > stop:
                OrderRecord.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)

        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=KBar_dic['time'], open=KBar_dic['open'], high=KBar_dic['high'], low=KBar_dic['low'], close=KBar_dic['close'], name='K線'))
        for record in OrderRecord.GetTradeRecord():
            direction = record[0]
            color = 'red' if direction == 'Buy' else 'green'
            fig.add_trace(go.Scatter(x=[record[2]], y=[record[3]], mode='markers', marker=dict(size=10, color=color), name=direction))
        fig.update_layout(title='MACD策略回測圖', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 策略績效")
    st.metric("總淨利潤", f"{OrderRecord.GetTotalProfit():.2f}")
    st.metric("勝率", f"{OrderRecord.GetWinRate()*100:.2f}%")
    st.metric("最大回落 MDD", f"{OrderRecord.GetMDD():.2f}")

elif mode == "參數最佳化":
    st.header("🔍 策略參數最佳化 - MA策略")
    short_range = st.slider("短期MA範圍", 2, 20, (5, 10))
    long_range = st.slider("長期MA範圍", 20, 100, (30, 60))
    results = []
    for short, long in itertools.product(range(short_range[0], short_range[1]+1), range(long_range[0], long_range[1]+1)):
        if short >= long:
            continue
        KBar_dic['MA_short'] = SMA(KBar_dic, timeperiod=short)
        KBar_dic['MA_long'] = SMA(KBar_dic, timeperiod=long)
        R = Record()
        for n in range(1, len(KBar_dic['time']) - 1):
            if np.isnan(KBar_dic['MA_long'][n-1]): continue
            if R.GetOpenInterest() == 0:
                if KBar_dic['MA_short'][n-1] <= KBar_dic['MA_long'][n-1] and KBar_dic['MA_short'][n] > KBar_dic['MA_long'][n]:
                    R.Order('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
                elif KBar_dic['MA_short'][n-1] >= KBar_dic['MA_long'][n-1] and KBar_dic['MA_short'][n] < KBar_dic['MA_long'][n]:
                    R.Order('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif R.GetOpenInterest() > 0:
                R.Cover('Sell', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
            elif R.GetOpenInterest() < 0:
                R.Cover('Buy', 'demo', KBar_dic['time'][n+1], KBar_dic['open'][n+1], 1)
        results.append((short, long, R.GetTotalProfit(), R.GetWinRate(), R.GetMDD()))
    df_result = pd.DataFrame(results, columns=['短期MA', '長期MA', '總淨利', '勝率', 'MDD']).sort_values(by='總淨利', ascending=False)
    st.dataframe(df_result)
    st.success(f"最佳組合：短期MA={df_result.iloc[0]['短期MA']}, 長期MA={df_result.iloc[0]['長期MA']}, 淨利={df_result.iloc[0]['總淨利']:.2f}")
