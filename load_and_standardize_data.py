import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os


# ==========================================
# 数据读取、表头清洗与强制对齐
# ==========================================
def load_and_standardize_price_data(symbols: list, csv_dir: str, start_date: str, end_date: str, name: str):
    target_path = os.path.join(csv_dir, f"{name}.csv")
    if os.path.exists(target_path):
        print(f"[*] 发现已清洗的缓存文件 {target_path}，直接读取...")
        prices = pd.read_csv(target_path, index_col='date', parse_dates=True)
        return prices

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
        file_path = os.path.join(csv_dir, f"{sym['symbol']}.csv")
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
        price_data[sym['symbol']] = df[close_col]

    # 构建矩阵并强制执行时序对齐 (ffill & bfill 解决跨国节假日错位)
    prices = pd.DataFrame(price_data)
    # 生成从 start_date 到 end_date 的连续自然日时间序列，检测并显露缺失日期
    full_date_range = pd.date_range(start=start_date, end=end_date)
    prices = prices.reindex(full_date_range).ffill().bfill()
    prices.index.name = 'date'
    print("[+] 数据清洗与对齐完成。")
    prices.to_csv(target_path)
    return prices

def load_and_standardize_fraction_sweep_data(symbols: list, csv_dir: str, start_date: str, end_date: str, name: str):
    target_path = os.path.join(csv_dir, f"{name}.csv")
    if os.path.exists(target_path):
        print(f"[*] 发现已清洗的缓存文件 {target_path}，直接读取...")
        prices = pd.read_csv(target_path, index_col='date', parse_dates=True)
        return prices

    price_data = {}
    print(f"[*] 正在从 {csv_dir} 读取并清洗底层数据(模拟理财产品)...")

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
        file_path = os.path.join(csv_dir, f"{sym['symbol']}.csv")
        df = pd.read_csv(file_path)
        
        # 1. 表头清洗：先转小写，再匹配中文替换
        df.columns = [col.lower() for col in df.columns]
        df.rename(columns=header_mapping, inplace=True)
        
        # 2. 覆盖原始 CSV (保留清洗后的标准英文表头)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        # 3. 提取收盘价用于处理
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        close_col = 'close' if 'close' in df.columns else '收盘'
        original_price = df[close_col]
        
        # 4. 对收益率进行处理，使其相比原始数据降低 25%
        daily_returns = original_price.pct_change().fillna(0)
        adj_returns = daily_returns * 0.9
        reconstructed_price = original_price.iloc[0] * (1 + adj_returns).cumprod()
        
        # 5. 将起点值归一化为 1.0
        final_price = reconstructed_price / reconstructed_price.iloc[0]
        price_data[sym['symbol']] = final_price

    # 构建矩阵并强制执行时序对齐 (ffill & bfill 解决跨国节假日错位)
    prices = pd.DataFrame(price_data)
    full_date_range = pd.date_range(start=start_date, end=end_date)
    prices = prices.reindex(full_date_range).ffill().bfill()
    prices.index.name = 'date'
    print("[+] 模拟理财产品数据处理与对齐完成。")
    prices.to_csv(target_path)
    return prices

def load_and_standardize_bond_data(symbols: list, csv_dir: str, start_date: str, end_date: str, name: str):
    target_path = os.path.join(csv_dir, f"{name}.csv")
    if os.path.exists(target_path):
        print(f"[*] 发现已清洗的缓存文件 {target_path}，直接读取...")
        bond = pd.read_csv(target_path, index_col='date', parse_dates=True)
        return bond

    bond_data = {}
    print(f"[*] 正在从 {csv_dir} 读取并清洗底层数据...")

    # 中英文对照字典（可根据需要扩充）
    header_mapping = {
        '日期': 'date',
        '中国国债收益率2年': 'two_years_china_bond_rate',
        '中国国债收益率5年': 'five_years_china_bond_rate',
        '中国国债收益率10年': 'ten_years_china_bond_rate',
        '中国国债收益率30年': 'thirty_years_china_bond_rate',
        '美国国债收益率2年': 'two_years_us_bond_rate',
        '美国国债收益率5年': 'five_years_us_bond_rate',
        '美国国债收益率10年': 'ten_years_us_bond_rate',
        '美国国债收益率30年': 'thirty_years_us_bond_rate',
    }

    for sym in symbols:
        file_path = os.path.join(csv_dir, f"{sym}.csv")
        df = pd.read_csv(file_path)
        
        # 1. 表头清洗：先转小写，再匹配中文替换
        df.columns = [col.lower() for col in df.columns]
        df.rename(columns=header_mapping, inplace=True)
        
        # 2. 覆盖原始 CSV (保留清洗后的标准英文表头)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        
        # 3. 设置index为date
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # 4. 提取两年期国债收益率曲线
        bond_data[sym] = df[header_mapping['中国国债收益率2年']]
    
    # 构建矩阵并强制执行时序对齐 (ffill & bfill 解决跨国节假日错位)
    bond = pd.DataFrame(bond_data)
    # 生成从 start_date 到 end_date 的连续自然日时间序列，检测并显露缺失日期
    full_date_range = pd.date_range(start=start_date, end=end_date)
    bond = bond.reindex(full_date_range).ffill().bfill()
    bond.index.name = 'date'
    print("[+] 数据清洗与对齐完成。")
    bond.to_csv(target_path)
    return bond