import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter

def get_clean_data():
    print("1. 正在通过 AKShare 获取 A 股 513300 数据...")
    # 获取 A 股 ETF 数据 (东方财富接口)
    # 注意：A 股代码直接写数字即可
    df_a = ak.fund_etf_hist_em(
        symbol="513300", 
        period="daily", 
        start_date="20230101", 
        end_date="20240312", 
        adjust="qfq"
    )
    
    # 清洗 A 股数据
    df_a = df_a[['日期', '收盘']].copy()
    df_a.rename(columns={'日期': 'Date', '收盘': '513300_CNY'}, inplace=True)
    df_a['Date'] = pd.to_datetime(df_a['Date'])
    df_a.set_index('Date', inplace=True)

    print("2. 正在通过 AKShare 获取美股 QQQ 数据...")
    # 获取美股数据 (东方财富美股接口)
    # 避坑指南：东方财富的美股接口通常需要加前缀，纳斯达克通常是 "105."
    df_us = ak.stock_us_hist(
        symbol="105.QQQ", 
        period="daily", 
        start_date="20230101", 
        end_date="20240312", 
        adjust="qfq"
    )
    
    # 清洗美股数据
    df_us = df_us[['日期', '收盘']].copy()
    df_us.rename(columns={'日期': 'Date', '收盘': 'QQQ_USD'}, inplace=True)
    df_us['Date'] = pd.to_datetime(df_us['Date'])
    df_us.set_index('Date', inplace=True)

    print("3. 正在合并两地数据...")
    # 使用 outer join 合并数据，处理中美节假日休市不同的情况
    # ffill() 表示用前一天的交易价格填充休市日的空白
    combined_df = df_a.join(df_us, how='outer').ffill().dropna()

    print("4. 正在通过 CurrencyConverter 获取历史汇率...")
    cc = CurrencyConverter(fallback_on_missing_rate=True)
    rates = []
    for date in combined_df.index:
        try:
            rates.append(cc.convert(1, 'USD', 'CNY', date=date.date()))
        except Exception:
            rates.append(rates[-1] if rates else 7.1)

    combined_df['USD_CNY_Rate'] = rates

    print("5. 计算真实购买力与归一化...")
    combined_df['QQQ_CNY'] = combined_df['QQQ_USD'] * combined_df['USD_CNY_Rate']

    df_normalized_a = (combined_df['513300_CNY'] / combined_df['513300_CNY'].iloc[0]) * 100
    df_normalized_qqq = (combined_df['QQQ_CNY'] / combined_df['QQQ_CNY'].iloc[0]) * 100
    pure_difference = df_normalized_a - df_normalized_qqq

    print("6. 绘制图表...")
    plt.figure(figsize=(12, 6))
    plt.plot(combined_df.index, df_normalized_a, label='513300 (A股ETF)', color='#e74c3c')
    plt.plot(combined_df.index, df_normalized_qqq, label='QQQ (汇率折算后)', color='#2980b9')
    plt.plot(combined_df.index, pure_difference, label='绝对偏离度 (场内溢价)', color='purple', linestyle='--')
    
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    
    plt.title('本地CSV读取：A股纳指ETF vs QQQ 绝对偏离度', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.5)
    plt.tight_layout()
    plt.savefig('csv_premium_analysis.png')
    print("图表已生成: csv_premium_analysis.png")
    
    return combined_df

if __name__ == "__main__":
    final_data = get_clean_data()
    print("\n数据清洗完成，前5行数据如下：")
    print(final_data.head())