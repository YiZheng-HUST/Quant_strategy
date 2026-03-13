import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import datetime

def main():
    ticker_a = "513300.SS"  # A股纳斯达克100 ETF
    ticker_us = "QQQ"       # 美股纳斯达克100 ETF

    print(f"1. 正在下载 {ticker_a} 和 {ticker_us} 过去一年的历史收盘价...")
    try:
        data = yf.download([ticker_a, ticker_us], period="1y")['Close']
        df = data.ffill().dropna()
    except Exception as e:
        print(f"数据下载失败: {e}")
        return

    print("2. 正在初始化 CurrencyConverter 并进行逐日汇率转换...")
    # fallback_on_missing_rate=True 极其重要：用于处理周末和中美两国的节假日
    cc = CurrencyConverter(fallback_on_missing_rate=True)
    
    # 提取 yfinance 返回的日期索引，逐日获取 USD -> CNY 汇率
    rates = []
    for date in df.index:
        try:
            d = date.date()
            # 转换 1 美元 对应的人民币
            rate = cc.convert(1, 'USD', 'CNY', date=d)
            rates.append(rate)
        except Exception as e:
            # 万一遇到极端缺失数据，使用上一个有效汇率
            rates.append(rates[-1] if len(rates) > 0 else 7.1)

    df['USD_CNY_Rate'] = rates

    print("3. 正在计算 QQQ 的人民币等效净值并进行归一化...")
    # 将 QQQ 的美元价格乘以当天的真实汇率，得到 QQQ 的“人民币理论净值”
    df['QQQ_CNY'] = df[ticker_us] * df['USD_CNY_Rate']

    # 归一化：将第一天的价格统一设定为 100
    df_normalized_a = (df[ticker_a] / df[ticker_a].iloc[0]) * 100
    df_normalized_qqq_cny = (df['QQQ_CNY'] / df['QQQ_CNY'].iloc[0]) * 100

    # 现在的差值，剔除了汇率干扰，是纯粹的“境内溢价 + 基金摩擦损耗”
    pure_difference = df_normalized_a - df_normalized_qqq_cny

    print("4. 正在生成可视化图表...")
    plt.figure(figsize=(12, 6))

    plt.plot(df.index, df_normalized_a, label='513300.SS (A股ETF实盘价)', color='#e74c3c', linewidth=2)
    plt.plot(df.index, df_normalized_qqq_cny, label='QQQ_CNY (美股QQQ 汇率折算后理论价)', color='#2980b9', linewidth=2)
    
    # 纯粹的溢价与误差曲线
    plt.plot(df.index, pure_difference, label='绝对偏离度 (纯溢价与损耗)', color='purple', linestyle='--', alpha=0.8)

    # 解决 Linux 中文字体显示问题
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    plt.title('A股纳指ETF vs QQQ(已剔除汇率因素) 绝对偏离度分析', fontsize=14)
    plt.xlabel('日期', fontsize=12)
    plt.ylabel('归一化净值 (起点=100)', fontsize=12)
    plt.legend(loc='upper left', fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    file_name = 'nasdaq_pure_premium_analysis.png'
    plt.savefig(file_name, dpi=300)
    print(f"成功！图表已保存为: {file_name}")
    plt.show()

if __name__ == "__main__":
    main()