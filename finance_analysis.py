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

# 解决 matplotlib 中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS'] # Windows用SimHei, Mac用Arial Unicode MS
plt.rcParams['axes.unicode_minus'] = False

def fetch_and_save_data():
    # 确保 raw_data 文件夹存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"已创建文件夹: {DATA_DIR}")

    # 定义带有当天日期后缀的文件路径
    file_513300 = os.path.join(DATA_DIR, f"513300_{END_DATE}.csv")
    file_qqq = os.path.join(DATA_DIR, f"QQQ_{END_DATE}.csv")

    # ================= 获取 513300 数据 =================
    if os.path.exists(file_513300):
        print(f"检测到本地缓存 {file_513300}，正在直接读取...")
        df_513300 = pd.read_csv(file_513300)
    else:
        print(f"正在联网获取 纳斯达克ETF (513300) 数据 ({START_DATE} - {END_DATE})...")
        df_513300 = ak.fund_etf_hist_em(symbol="513300", period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df_513300.to_csv(file_513300, index=False, encoding="utf-8-sig")
        print(f"513300 数据已保存至 {file_513300}")

    # ================= 获取 QQQ 数据 =================
    if os.path.exists(file_qqq):
        print(f"检测到本地缓存 {file_qqq}，正在直接读取...")
        df_qqq = pd.read_csv(file_qqq)
    else:
        print(f"正在联网获取 美股 QQQ 数据 ({START_DATE} - {END_DATE})...")
        df_qqq = ak.stock_us_hist(symbol="105.QQQ", period="daily", start_date=START_DATE, end_date=END_DATE, adjust="qfq")
        df_qqq.to_csv(file_qqq, index=False, encoding="utf-8-sig")
        print(f"QQQ 数据已保存至 {file_qqq}")
    
    return df_513300, df_qqq

def process_and_plot(df_513300, df_qqq):
    print("正在处理数据与转换汇率...")
    # 提取需要的列并重命名
    df_a = df_513300[['日期', '收盘']].copy()
    df_a.columns = ['Date', '513300_Close']
    df_a['Date'] = pd.to_datetime(df_a['Date'])

    df_u = df_qqq[['日期', '收盘']].copy()
    df_u.columns = ['Date', 'QQQ_Close_USD']
    df_u['Date'] = pd.to_datetime(df_u['Date'])

    # 将两个数据集合并，使用 inner join 确保只对比双方都开盘的交易日
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

    # 计算偏差 (国内ETF相对净值的超额/折价程度，单位为百分点)
    df_merged['Deviation_%'] = (df_merged['513300_Norm'] - df_merged['QQQ_CNY_Norm']) * 100

    print("开始绘制图表...")
    # 创建上下两个子图
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

    # 绘制图1：归一化走势对比
    ax1.plot(df_merged['Date'], df_merged['513300_Norm'], label='513300 (国内ETF)', color='red', linewidth=2)
    ax1.plot(df_merged['Date'], df_merged['QQQ_CNY_Norm'], label='QQQ (人民币计价)', color='blue', linewidth=2, linestyle='--')
    
    # 动态将日期更新到标题中
    title_text = f'纳斯达克ETF (513300) vs 美股 QQQ 走势对比\n({df_merged["Date"].iloc[0].strftime("%Y-%m-%d")} 至 {df_merged["Date"].iloc[-1].strftime("%Y-%m-%d")})'
    ax1.set_title(title_text, fontsize=14)
    
    ax1.set_ylabel('累计净值增长 (基准=1.0)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # 绘制图2：偏差走势
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] >= 0), color='red', alpha=0.5, label='513300 溢价/超额收益')
    ax2.fill_between(df_merged['Date'], df_merged['Deviation_%'], 0, 
                     where=(df_merged['Deviation_%'] < 0), color='green', alpha=0.5, label='513300 相对回撤')
    ax2.set_ylabel('相对偏差 (%)', fontsize=12)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.legend(loc='upper left', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    df_a, df_u = fetch_and_save_data()
    process_and_plot(df_a, df_u)