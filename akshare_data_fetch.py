import os
import random
import time
import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
from datetime import datetime, timedelta

import logging

# ================= Dynamic Config Area =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

today = datetime.now()
one_year_ago = today - timedelta(days=1825)

START_DATE = one_year_ago.strftime("%Y%m%d")
END_DATE = today.strftime("%Y%m%d")
DATA_DIR = "raw_data/"

# Define lists for Chinese ETFs
A_SHARE_ETFS = {
    "A_nasdaq_etf": "513300",  # 纳斯达克ETF
    "A_sp500_etf": "513500",  # 标普500ETF
    "A_red_low_volatility_50_etf": "515450",  # 红利低波50ETF
    "A_red_etf_huatai": "510880",  # 红利ETF华泰柏瑞
    "A_short_term_bond_etf": "511360",  # 短融ETF海富通
    "A_huaan_gold_etf": "518880",  # 华安黄金ETF
}

# Define lists for American ETFs east money
US_SHARE_ETFS_EASTMONEY = {
    "nasdaq": "105.QQQ",
    "sp500": "106.SPY",
    "dow_jones": "106.DIA",
    "gold": "106.GLD",
    "short_term_treasury": "105.SHY",
    "mid_term_treasury": "105.IEF",
    "long_term_treasury": "105.TLT",
}

US_SHARE_ETFS_SINA = {
    "nasdaq": "QQQ",
    "sp500": "SPY",
    "dow_jones": "DIA",
    "gold": "GLD",
    "short_term_treasury": "SHY",
    "mid_term_treasury": "IEF",
    "long_term_treasury": "TLT"}

# Define data source
DATA_SOURCE = ["eastmoney", # 东方财富
               "sina",      # 新浪
               "tencent"]   # 腾讯
# =======================================================

def fetch_price_data(a_etf_dict, us_etf_dict_eastmoney, us_etf_dict_sina, start_date, end_date):
    dir_path = os.path.join(DATA_DIR, END_DATE)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logging.info(f"Created directory: {dir_path}")

    a_data = {}
    us_data = {}

    # Fetch A-Share ETFs
    for name, symbol in a_etf_dict.items():
        file_path = os.path.join(dir_path, f"{name}_{end_date}.csv")
        if os.path.exists(file_path):
            logging.info(f"Found local cache for A-share ETF {name}. Loading...")
            a_data[name] = pd.read_csv(file_path)
        else:
            df = None
            try:
                logging.info(f"Fetching data for A-share ETF {symbol} from eastmoney ({start_date} - {end_date})...")
                df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq") # 东方财富接口
                time.sleep(random.uniform(1.0, 3.0)) # pause for 1-3 sec
            except Exception as e:
                logging.warning(f"Failed to fetch data from eastmoney for {symbol}: {e}. Trying sina...")
                try:
                    logging.info(f"Fetching data for A-share ETF {symbol} from sina ({start_date} - {end_date})...")
                    df = ak.stock_zh_a_daily(symbol="sh" + symbol, start_date=start_date, end_date=end_date, adjust="qfq") # 新浪接口，沪市为例
                    time.sleep(random.uniform(1.0, 3.0)) # pause for 1-3 sec
                except Exception as e2:
                    logging.warning(f"Failed to fetch data from sina for {symbol}: {e2}. Trying tencent...")
                    try:
                        logging.info(f"Fetching data for A-share ETF {symbol} from tencent ({start_date} - {end_date})...")
                        df = ak.stock_zh_a_hist(symbol="sh" + symbol, start_date=start_date, end_date=end_date, adjust="qfq") # 腾讯接口，沪市为例
                        time.sleep(random.uniform(1.0, 3.0)) # pause for 1-3 sec
                    except Exception as e3:
                        logging.error(f"Failed to fetch data from tencent for {symbol}: {e3}. All sources failed.")
            
            if df is not None:
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                a_data[name] = df
                logging.info(f"Saved A-share ETF {symbol} data to {file_path}")
    
    # Fetch US-Share ETFs
    for name, symbol in us_etf_dict_eastmoney.items():
        file_path = os.path.join(dir_path, f"{name}_{end_date}.csv")
        if os.path.exists(file_path):
            logging.info(f"Found local cache for US ETF {name}. Loading...")
            us_data[name] = pd.read_csv(file_path)
        else:
            try:
                logging.info(f"Fetching data for US ETF {symbol} from eastmoney ({start_date} - {end_date})...")
                df = ak.stock_us_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                time.sleep(random.uniform(1.0, 3.0)) # pause for 1-3 sec
            except Exception as e:
                logging.warning(f"Failed to fetch data from eastmoney for {symbol}: {e}. Trying sina...")
                symbol = us_etf_dict_sina[name] # sina symbol is different
                logging.info(f"Fetching data for US ETF {symbol} from sina ({start_date} - {end_date})...")
                df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
                time.sleep(random.uniform(1.0, 3.0)) # pause for 1-3 sec

            if df is not None:
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
                us_data[name] = df
                logging.info(f"Saved US-share ETF {symbol} data to {file_path}")

    return a_data, us_data

if __name__ == "__main__":
    # Fetch all data from the lists
    dict_a, dict_u = fetch_price_data(A_SHARE_ETFS, US_SHARE_ETFS_EASTMONEY, US_SHARE_ETFS_SINA, START_DATE, END_DATE)