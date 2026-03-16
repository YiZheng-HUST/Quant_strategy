import os
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
from datetime import datetime, timedelta

# ================= 动态配置区域 =================
# 自动计算今天和一年前的日期
today = datetime.now()
one_year_ago = today - timedelta(days=365)

# 转换为 akshare 需要的 YYYYMMDD 格式
START_DATE = one_year_ago.strftime("%Y%m%d")
END_DATE = today.strftime("%Y%m%d")

# 数据保存文件夹设置
DATA_DIR = "raw_data"
# ============================================

# To solve the problem of displaying minus sign in matplotlib
plt.rcParams['axes.unicode_minus'] = False

def fetch_and_save_data():
    # Ensure the raw_data directory exists
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created directory: {DATA_DIR}")

    # Define file paths with the current date as a suffix
    file_513300 = os.path.join(DATA_DIR, f"513300_{END_DATE}.csv")
    file_qqq = os.path.join(DATA_DIR, f"QQQ_{END_DATE}.csv")

    # ================= Fetch 513300 data =================
    if os.path.exists(file_513300):
        print(f"Local cache {file_513300} detected, reading directly...")
        df_513300 = pd.read_csv(file_513300)
    else:
        print(f"Fetching Nasdaq ETF (513300) data online ({START_DATE} - {END_DATE})...")
        df_513300 = ak.fund_etf_hist_em(symbol="513300", period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df_513300.to_csv(file_513300, index=False, encoding="utf-8-sig")
        print(f"513300 data saved to {file_513300}")

    # ================= Fetch QQQ data =================
    if os.path.exists(file_qqq):
        print(f"Local cache {file_qqq} detected, reading directly...")
        df_qqq = pd.read_csv(file_qqq)
    else:
        print(f"Fetching US Stock QQQ data online ({START_DATE} - {END_DATE})...")
        df_qqq = ak.stock_us_hist(symbol="105.QQQ", period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df_qqq.to_csv(file_qqq, index=False, encoding="utf-8-sig")
        print(f"QQQ data saved to {file_qqq}")
    
    return df_513300, df_qqq

def process_and_plot(df_513300, df_qqq):
    print("Processing data and converting currency...")
    # Extract required columns and rename them
    df_a = df_513300[['日期', '收盘']].copy()
    df_a.columns = ['Date', '513300_Close']
    df_a['Date'] = pd.to_datetime(df_a['Date'])

    df_u = df_qqq[['日期', '收盘']].copy()
    df_u.columns = ['Date', 'QQQ_Close_USD']
    df_u['Date'] = pd.to_datetime(df_u['Date'])

    # Merge the two dataframes, using an inner join to ensure we only compare on trading days common to both
    df_merged = pd.merge(df_a, df_u, on='Date', how='inner')

    # 初始化汇率转换器
    cc = CurrencyConverter(fallback_on_missing_rate=True, fallback_on_wrong_date=True)

    # 定义汇率转换函数
    def convert_to_cny(row):
        try:
            return cc.convert(row['QQQ_Close_USD'], 'USD', 'CNY', date=row['Date'].date())
        except Exception as e:
            return None

    # 转换 QQQ 价格为人民币
    df_merged['QQQ_Close_CNY'] = df_merged.apply(convert_to_cny, axis=1)
    df_merged['QQQ_Close_CNY'] = df_merged['QQQ_Close_CNY'].ffill() # 填补可能缺失的汇率

    # 归一化处理：以合并后的第一天价格作为基准 (设为1)，计算累计收益走势
    base_513300 = df_merged['513300_Close'].iloc[0]
    base_qqq_cny = df_merged['QQQ_Close_CNY'].iloc[0]

    df_merged['513300_Norm'] = df_merged['513300_Close'] / base_513300
    df_merged['QQQ_CNY_Norm'] = df_merged['QQQ_Close_CNY'] / base_qqq_cny

    # Calculate deviation (premium/discount of domestic ETF relative to net asset value, in percentage points)
    df_merged['Deviation_%'] = (df_merged['513300_Norm'] - df_merged['QQQ_CNY_Norm']) * 100

    print("Start plotting...")
    # Create two subplots, one above the other
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

    # Plot 1: Normalized trend comparison
    ax1.plot(df_merged['Date'], df_merged['513300_Norm'], label='513300 (Domestic ETF)', color='red', linewidth=2)
    ax1.plot(df_merged['Date'], df_merged['QQQ_CNY_Norm'], label='QQQ (CNY based)', color='blue', linewidth=2, linestyle='--')
    
    # Dynamically update the date in the title
    title_text = f'Nasdaq ETF (513300) vs US Stock QQQ Trend Comparison\n({df_merged["Date"].iloc[0].strftime("%Y-%m-%d")} to {df_merged["Date"].iloc[-1].strftime("%Y-%m-%d")})'
    ax1.set_title(title_text, fontsize=14)
    
    ax1.set_ylabel('Normalized Growth (Base=1.0)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Deviation trend
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] >= 0), color='red', alpha=0.5, label='513300 Premium/Excess Return')
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] < 0), color='green', alpha=0.5, label='513300 Relative Drawdown')
    ax2.set_ylabel('Relative Deviation (%)', fontsize=12)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df_a, df_u = fetch_and_save_data()
    process_and_plot(df_a, df_u)