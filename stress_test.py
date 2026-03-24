import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os
from akshare_data_fetch import A_SHARE_ETFS, US_SHARE_ETFS_EASTMONEY, US_SHARE_ETFS_SINA
from load_and_standardize_data import load_and_standardize_price_data, load_and_standardize_bond_data
from data_analysis_and_plot import calculate_max_drawdown, calculate_sharpe_ratio, plot_portfolio_performance, plot_component_trends


# 全局定义区
FOREIGN_SYMBOLS = [ US_SHARE_ETFS_SINA['nasdaq']['symbol'], 
                    US_SHARE_ETFS_SINA['sp500']['symbol'], 
                    US_SHARE_ETFS_SINA['dow_jones']['symbol'], 
                    US_SHARE_ETFS_SINA['gold']['symbol'],
                    US_SHARE_ETFS_EASTMONEY['nasdaq']['symbol'], 
                    US_SHARE_ETFS_EASTMONEY['sp500']['symbol'], 
                    US_SHARE_ETFS_EASTMONEY['dow_jones']['symbol'], 
                    US_SHARE_ETFS_EASTMONEY['gold']['symbol'],]

BOND_SYMBOLS = ['treasury_bonds_yield']

FRICTION_COST = {"stamp_duty": 0.0005,  # 印花税，卖出单向收取
                 "transfer_fee": 0.00001,   # 过户费，双向收取
                 "regulatory_fee": 0.0000687}  # 交易规费，双向收取


# ==========================================
# 汇率穿透引擎
# ==========================================
def apply_currency_conversion(prices_df: pd.DataFrame, foreign_symbols: list, base_curr: str='USD', target_curr: str='CNY'):
    """
    调用本地 ECB 数据，将指定的海外资产列转换为目标本币计价。
    """
    print(f"[*] 正在执行 {base_curr} 到 {target_curr} 的汇率穿透计算...")
    c = CurrencyConverter(fallback_on_wrong_date=True)
    
    fx_rates = []
    for dt in prices_df.index:
        try:
            rate = c.convert(1, base_curr, target_curr, date=dt.date())
        except Exception:
            rate = np.nan
        fx_rates.append(rate)
        
    # 将汇率序列拼入 DataFrame 以利用 pandas 的 ffill 填补周末空缺
    prices_df['FX_RATE'] = fx_rates
    prices_df['FX_RATE'].ffill(inplace=True)
    
    # 转换指定的海外资产
    for sym in foreign_symbols:
        if sym in prices_df.columns:
            prices_df[sym] = prices_df[sym] * prices_df['FX_RATE']
            
    prices_df.drop(columns=['FX_RATE'], inplace=True)
    print(f"[+] 资产 {foreign_symbols} 已成功转换为 {target_curr} 计价。")
    return prices_df

# ==========================================
# 核心策略引擎 (带自定义再平衡)
# ==========================================
def run_backtest_engine(prices_df, initial_weights, enable_rebalance=True, rebalance_freq='M'):
    """
    计算净值曲线。
    rebalance_freq: 'M'(月度), 'Q'(季度), 'Y'(年度), 'W'(每周)
    """
    print(f"[*] 启动回测引擎... (再平衡机制: {'开启 (' + rebalance_freq + ')' if enable_rebalance else '关闭'})")
    
    daily_returns = prices_df.pct_change().dropna()
    portfolio_value = [1.0]
    current_weights = np.array(initial_weights).copy()
    
    # 获取时间周期索引，用于触发再平衡
    periods = daily_returns.index.to_period(rebalance_freq)

    for i in range(len(daily_returns)):
        # 1. 计算当日总体涨跌幅
        today_return = np.sum(current_weights * daily_returns.iloc[i].values)
        
        # 2. 累加净值
        new_value = portfolio_value[-1] * (1 + today_return)
        portfolio_value.append(new_value)
        
        # 3. 权重自然漂移
        current_weights = current_weights * (1 + daily_returns.iloc[i].values) / (1 + today_return)
        
        # 4. 机械化再平衡指令拦截
        if enable_rebalance and i < len(daily_returns) - 1:
            # 如果今天和明天的周期不同（例如到了月末最后一天），触发权重重置
            if periods[i] != periods[i+1]:
                current_weights = np.array(initial_weights).copy()

    portfolio_series = pd.Series(portfolio_value[1:], index=daily_returns.index)
    return portfolio_series

# ==========================================
# 主程序执行入口 (Main Execution)
# ==========================================
if __name__ == "__main__":
    # 配置参数
    WORK_DIR = '/home/yizheng/workpath/finance/stress_test_data/20210324-20260323/' 
    # TARGET_SYMBOLS = [A_SHARE_ETFS['A_short_term_bond_etf'], A_SHARE_ETFS['A_red_etf_huatai'], US_SHARE_ETFS_SINA['nasdaq'], A_SHARE_ETFS['A_huaan_gold_etf']]
    TARGET_SYMBOLS = [A_SHARE_ETFS['A_short_term_bond_etf'], A_SHARE_ETFS['A_red_etf_huatai'], A_SHARE_ETFS['A_nasdaq_etf'], A_SHARE_ETFS['A_huaan_gold_etf']]
    WEIGHTS = [0.50, 0.20, 0.20, 0.10]
    START = '2021-03-24'
    END = '2026-03-23'

    # 抽取与清洗
    df_prices = load_and_standardize_price_data(TARGET_SYMBOLS, WORK_DIR, START, END)
    df_bond = load_and_standardize_bond_data(BOND_SYMBOLS, WORK_DIR, START, END)
    
    # 汇率转换
    df_prices = apply_currency_conversion(df_prices, foreign_symbols=FOREIGN_SYMBOLS)
    
    # 运行策略引擎 (在这里，您可以自由切换再平衡开关，比如试着改成 rebalance_freq='Q' 看季度再平衡效果)
    portfolio_res = run_backtest_engine(df_prices, WEIGHTS, enable_rebalance=True, rebalance_freq='M')

    # 执行核心量化指标评测
    mdd_value, mdd_date, drawdown_series = calculate_max_drawdown(portfolio_res)
    print(f"max_drawdown value: {mdd_value}, date: {mdd_date}")

    sharpe = calculate_sharpe_ratio(portfolio_res, risk_free_rate=0.02)
    print(f"annualized_sharpe_ratio: {sharpe}")
    
    # 生成图像
    mdd_trigger_date = plot_portfolio_performance(portfolio_res, WORK_DIR)
    plot_component_trends(df_prices, mdd_trigger_date, WORK_DIR)
    
    print("\n[√] 核心系统运行完毕，请在当前目录检查图表。")