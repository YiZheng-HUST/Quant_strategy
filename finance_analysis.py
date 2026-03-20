import os
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
from datetime import datetime, timedelta

# ================= Dynamic Config Area =================
today = datetime.now()
one_year_ago = today - timedelta(days=365)

START_DATE = one_year_ago.strftime("%Y%m%d")
END_DATE = today.strftime("%Y%m%d")

DATA_DIR = "raw_data/"

# Define lists for Chinese ETFs
A_SHARE_ETFS = ["513300", # 纳斯达克ETF
                "513500", # 标普500ETF
                "518880", # 华安黄金ETF
                "515450", # 红利低波50ETF
                "513360", # 短融ETF海富通
                "510880", # 红利ETF华泰柏瑞
                "512480", # 半导体ETF
                ]

# Define lists for American ETFs east money
US_SHARE_ETFS_EASTMONEY = [ "105.QQQ", # 纳斯达克
                            "106.SPY", # 标普500
                            "106.DIA", # 道琼斯
                            "106.GLD", # 黄金
                            "105.SHY", # 短期美债
                            "105.IEF", # 中期美债
                            "105.TLT", # 长期美债
                            ]

# Define lists for American ETFs sina
US_SHARE_ETFS_SINA = [  "QQQ", # 纳斯达克
                        "SPY", # 标普500
                        "DIA", # 道琼斯
                        "GLD", # 黄金
                        "SHY", # 短期美债
                        "IEF", # 中期美债
                        "TLT", # 长期美债
                        ]

# Define data source
DATA_SOURCE = ["eastmoney", # 东方财富
               "sina",      # 新浪
               "tencent"]   # 腾讯
# =======================================================

def fetch_and_save_data(a_etf_list, us_etf_list, data_source: str, start_date, end_date):
    dir_path = os.path.join(DATA_DIR, END_DATE)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"Created directory: {dir_path}")

    a_data = {}
    us_data = {}

    # Fetch A-Share ETFs
    for symbol in a_etf_list:
        file_path = os.path.join(dir_path, f"{symbol}_{end_date}.csv")
        if os.path.exists(file_path):
            print(f"Found local cache for {symbol}. Loading...")
            a_data[symbol] = pd.read_csv(file_path)
        else:
            print(f"Fetching data for A-share ETF {symbol} ({start_date} - {end_date})...")
            if data_source == "eastmoney":
                df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq") # 东方财富接口
            elif data_source == "sina":
                df = ak.stock_zh_a_daily(symbol="sh" + symbol, start_date=start_date, end_date=end_date, adjust="qfq") # 新浪接口，沪市为例
            elif data_source == "tencent":
                df = ak.stock_zh_a_hist(symbol="sh" + symbol, start_date=start_date, end_date=end_date, adjust="qfq") # 腾讯接口，沪市为例
            else:
                raise ValueError("Invalid data source.")

            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            a_data[symbol] = df
            print(f"Saved {symbol} data to {file_path}")

    # Fetch US-Share ETFs
    for symbol in us_etf_list:
        file_path = os.path.join(dir_path, f"{symbol}_{end_date}.csv")
        if os.path.exists(file_path):
            print(f"Found local cache for {symbol}. Loading...")
            us_data[symbol] = pd.read_csv(file_path)
        else:
            print(f"Fetching data for US ETF {symbol} ({start_date} - {end_date})...")
            if data_source == "eastmoney":
                df = ak.stock_us_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
            elif data_source == "sina":
                df = ak.stock_us_daily(symbol=symbol, adjust="qfq") # 新浪接口，沪市为例
            df.to_csv(file_path, index=False, encoding="utf-8-sig")
            us_data[symbol] = df
            print(f"Saved {symbol} data to {file_path}")
    
    return a_data, us_data

def process_and_plot(a_data_dict, us_data_dict, a_target, us_target):
    print("Processing data and converting currency...")
    
    # Extract the specific dataframes we want to plot
    df_a_raw = a_data_dict[a_target]
    df_u_raw = us_data_dict[us_target]

    # Map akshare's Chinese headers to English
    df_a = df_a_raw[['日期', '收盘']].copy()
    df_a.columns = ['Date', f'{a_target}_Close']
    df_a['Date'] = pd.to_datetime(df_a['Date'])

    df_u = df_u_raw[['日期', '收盘']].copy()
    df_u.columns = ['Date', f'{us_target}_Close_USD']
    df_u['Date'] = pd.to_datetime(df_u['Date'])

    # Merge datasets using inner join to match trading days
    df_merged = pd.merge(df_a, df_u, on='Date', how='inner')

    # Initialize currency converter
    cc = CurrencyConverter(fallback_on_missing_rate=True, fallback_on_wrong_date=True)

    def convert_to_cny(row):
        try:
            return cc.convert(row[f'{us_target}_Close_USD'], 'USD', 'CNY', date=row['Date'].date())
        except Exception:
            return None

    # Convert USD to CNY
    df_merged[f'{us_target}_Close_CNY'] = df_merged.apply(convert_to_cny, axis=1)
    df_merged[f'{us_target}_Close_CNY'] = df_merged[f'{us_target}_Close_CNY'].ffill() 

    # Normalize data (base = 1.0)
    base_a = df_merged[f'{a_target}_Close'].iloc[0]
    base_u_cny = df_merged[f'{us_target}_Close_CNY'].iloc[0]

    df_merged['A_Norm'] = df_merged[f'{a_target}_Close'] / base_a
    df_merged['U_CNY_Norm'] = df_merged[f'{us_target}_Close_CNY'] / base_u_cny

    # Calculate deviation (Premium/Discount) in percentage points
    df_merged['Deviation_%'] = (df_merged['A_Norm'] - df_merged['U_CNY_Norm']) * 100

    print("Generating charts...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

    # Plot 1: Normalized Trend
    ax1.plot(df_merged['Date'], df_merged['A_Norm'], label=f'{a_target} (A-Share)', color='red', linewidth=2)
    ax1.plot(df_merged['Date'], df_merged['U_CNY_Norm'], label=f'{us_target} (USD to CNY)', color='blue', linewidth=2, linestyle='--')
    
    start_str = df_merged["Date"].iloc[0].strftime("%Y-%m-%d")
    end_str = df_merged["Date"].iloc[-1].strftime("%Y-%m-%d")
    ax1.set_title(f'Normalized Performance: {a_target} vs {us_target}\n({start_str} to {end_str})', fontsize=14)
    ax1.set_ylabel('Cumulative Growth (Base=1.0)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Deviation
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] >= 0), color='red', alpha=0.5, label='Premium / Outperformance')
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] < 0), color='green', alpha=0.5, label='Discount / Underperformance')
    ax2.set_ylabel('Deviation (%)', fontsize=12)
    ax2.set_xlabel('Date', fontsize=12)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # Fetch all data from the lists
    dict_a, dict_u = fetch_and_save_data(A_SHARE_ETFS, US_SHARE_ETFS_SINA, DATA_SOURCE[1], START_DATE, END_DATE)
    

    # Plot the first item in each list by default
    process_and_plot(dict_a, dict_u, A_SHARE_ETFS[0], US_SHARE_ETFS_SINA[0])