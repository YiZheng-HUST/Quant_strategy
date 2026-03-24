import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os


# ==========================================
# 数据读取、表头清洗与强制对齐
# ==========================================
def load_and_standardize_price_data(symbols: list, csv_dir: str, start_date: str, end_date: str):
    price_data = {}
    print(f"[*] 正在从 {csv_dir} 读取并清洗底层数据...")

    # 中英文对照字典（可根据需要扩充）
    header_mapping = {
        '日期': 'date', 
        '开盘': 'open', 
        '收盘': 'close', 
        '最高': 'high', 
        '最低': 'low', 
        '成交量': 'volume',
    }

    for sym in symbols:
        file_path = os.path.join(csv_dir, f"{sym}.csv")
        df = pd.read_csv(file_path)
        
        # 1. 表头清洗：先转小写，再匹配中文替换
        df.columns = [col.lower() for col in df.columns]
        df.rename(columns=header_mapping, inplace=True)
        
        # 2. 覆盖原始 CSV (保留清洗后的标准英文表头)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        # 3. 提取收盘价用于回测
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 兼容不同数据源可能存在的命名
        close_col = 'close' if 'close' in df.columns else '收盘'
        price_data[sym] = df[close_col]

    # 构建矩阵并强制执行时序对齐 (ffill & bfill 解决跨国节假日错位)
    prices = pd.DataFrame(price_data)
    prices = prices.loc[start_date:end_date].ffill().bfill()
    print("[+] 数据清洗与对齐完成。")
    prices.to_csv(os.path.join(csv_dir, 'clean_price_data.csv'))
    return prices

def load_and_standardize_bond_data(symbols: list, csv_dir: str, start_date: str, end_date: str):
    bond_data = {}
    print(f"[*] 正在从 {csv_dir} 读取并清洗底层数据...")

        # 中英文对照字典（可根据需要扩充）
    header_mapping = {
        '日期': 'date',
        '中国国债收益率2年': 'two_years_China_bond_rate',
        '中国国债收益率5年': 'five_years_China_bond_rate',
        '中国国债收益率10年': 'ten_years_China_bond_rate',
        '中国国债收益率30年': 'thirty_years_China_bond_rate',
        '美国国债收益率2年': 'two_years_US_bond_rate',
        '美国国债收益率5年': 'five_years_US_bond_rate',
        '美国国债收益率10年': 'ten_years_US_bond_rate',
        '美国国债收益率30年': 'thirty_years_US_bond_rate',
    }

    for sym in symbols:
        file_path = os.path.join(csv_dir, f"{sym}.csv")
        df = pd.read_csv(file_path)
        
        # 1. 表头清洗：先转小写，再匹配中文替换
        df.columns = [col.lower() for col in df.columns]
        df.rename(columns=header_mapping, inplace=True)
        
        # 2. 覆盖原始 CSV (保留清洗后的标准英文表头)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        # 3. 提取收盘价用于回测
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 兼容不同数据源可能存在的命名
        years_col = 'two_years_China_bond_rate'
        bond_data[sym] = df[years_col]
    
        # 构建矩阵并强制执行时序对齐 (ffill & bfill 解决跨国节假日错位)
    bond = pd.DataFrame(bond_data)
    bond = bond.loc[start_date:end_date].ffill().bfill()
    print("[+] 数据清洗与对齐完成。")
    bond.to_csv(os.path.join(csv_dir, 'clean_bond_data.csv'))
    return bond