import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os
from akshare_data_fetch import A_SHARE_ETFS, US_SHARE_ETFS_EASTMONEY, US_SHARE_ETFS_SINA
from load_and_standardize_data import load_and_standardize_price_data, load_and_standardize_bond_data
from data_analysis_and_plot import calculate_max_drawdown, calculate_rolling_sharpe_ratio, calculate_sortino_ratio, calculate_underwater_time, plot_portfolio_performance, plot_component_trends


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

FRICTION_COST = {   "commission": 0.00005, # 券商佣金，双向收取
                    "stamp_duty": 0,  # 印花税，卖出单向收取
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
def run_backtest_engine(prices_df, initial_weights, annual_fees=None, enable_rebalance=True, rebalance_freq='M', friction_costs=FRICTION_COST, verbose=True):
    """
    计算净值曲线。
    rebalance_freq: 'M'(月度), 'Q'(季度), 'Y'(年度), 'W'(每周)
    annual_fees: list, 各ETF对应的年化费用率列表
    """
    if verbose:
        print(f"[*] 启动回测引擎... (再平衡机制: {'开启 (' + rebalance_freq + ')' if enable_rebalance else '关闭'})")
    
    daily_returns = prices_df.pct_change().dropna()
    portfolio_value = [1.0]
    initial_portfolio_value = 1.0
    current_weights = np.array(initial_weights).copy()
    
    # 获取时间周期索引，用于触发再平衡
    periods = daily_returns.index.to_period(rebalance_freq)

    for i in range(len(daily_returns)):
        asset_returns = daily_returns.iloc[i].values

        # 将年化费用均摊到252个交易日中并作为摩擦损耗扣除
        if annual_fees is not None:
            daily_fees = np.array(annual_fees) / 252.0
            asset_returns = asset_returns - daily_fees

        # 1. 计算当日总体涨跌幅
        # 权重 * 每日收益率
        today_return = np.sum(current_weights * asset_returns)
        
        # 2. 累加净值
        new_value = portfolio_value[-1] * (1 + today_return)

        portfolio_value.append(new_value)
        
        # 3. 权重自然漂移
        current_weights = current_weights * (1 + asset_returns) / (1 + today_return)
        
        # 4. 机械化再平衡指令拦截
        if enable_rebalance and i < len(daily_returns) - 1:
            # 如果今天和明天的周期不同（例如到了月末最后一天），触发权重重置
            if periods[i] != periods[i+1]:

                # 计算从当前漂移权重调整回初始权重所需的交易量 (Turnover)
                # turnover_weight 代表单向交易的权重之和（即卖出权重总和，也等于买入权重总和）
                turnover_weight = np.sum(np.maximum(0, current_weights - np.array(initial_weights)))

                # 卖出成本（印花税，单向）
                sell_cost = turnover_weight * friction_costs["stamp_duty"]

                # 双向成本（券商佣金 + 过户费 + 交易规费），乘以2因为买卖都收
                round_trip_cost = turnover_weight * 2 * (friction_costs["commission"] + friction_costs["transfer_fee"] + friction_costs["regulatory_fee"])

                # 从当日净值中扣除总摩擦成本
                total_friction_ratio = sell_cost + round_trip_cost
                new_value = new_value * (1 - total_friction_ratio)

                # 重置权重并更新扣除成本后的净值
                current_weights = np.array(initial_weights).copy()
                portfolio_value[-1] = new_value

    portfolio_series = pd.Series(portfolio_value[1:], index=daily_returns.index)
    return portfolio_series

def generate_weights(num_assets, step=0.01):
    steps = int(round(1.0 / step))
    def _generate(remaining_steps, remaining_assets):
        if remaining_assets == 1:
            yield [round(remaining_steps * step, 2)]
            return
        for i in range(remaining_steps + 1):
            for tail in _generate(remaining_steps - i, remaining_assets - 1):
                yield [round(i * step, 2)] + tail
    yield from _generate(steps, num_assets)

# ==========================================
# 策略优化搜索：寻找最佳权重组合
# ==========================================
def evaluate_portfolio(mdd_val: float, shp: pd.Series, srt: float, underwater: int):
    """
    评估投资组合表现是否满足预设标准。
    - 条件1: 最大回撤小于10%
    - 条件2: 滚动夏普比率序列中，超过80%的值要大于0.8
    - 条件3: 索提诺比率大于1.0
    - 条件4: 最大水下时间小于180天
    """
    # 条件1: 最大回撤为负数，因此 > -0.10 即代表跌幅小于 10%
    cond1 = mdd_val > -0.10

    # 条件2: 滚动夏普比率有80%的时间在0.8以上
    # shp是Series, (shp > 0.5)会返回一个布尔Series, .mean()计算True的比例
    cond2 = (shp > 0.8).mean() >= 0.8

    # 条件3: 索提诺比率大于1.0
    cond3 = srt > 1.0

    # 条件4: 最大水下时间小于180天
    cond4 = underwater < 180

    return cond1 and cond2 and cond3 and cond4

# ==========================================
# 主程序执行入口 (Main Execution)
# ==========================================
if __name__ == "__main__":
    # 配置参数
    WORK_DIR = '/home/yizheng/workpath/finance/stress_test_data/20210324-20260323/'

    # 选择投资组合与权重
    TARGET_SYMBOLS = [A_SHARE_ETFS['short_term_bond_haifutong_etf'], A_SHARE_ETFS['red_low_volatility_50_nanfang_etf'], A_SHARE_ETFS['nasdaq_huaxia_etf'], A_SHARE_ETFS['gold_huaan_etf']]
    WEIGHTS = [0.50, 0.20, 0.20, 0.10]

    # 提取各 ETF 的年化费用 (A股为管理费+托管费，美股为总费用)
    ANNUAL_FEES = [etf.get('total_fee', etf.get('management_fee', 0.0) + etf.get('trustee_fee', 0.0)) for etf in TARGET_SYMBOLS]

    # 选择对照组
    COMPARE_SYMBOLS = [A_SHARE_ETFS['csi_300_huatai_etf'], US_SHARE_ETFS_SINA['sp500']]

    # 设置日期
    START = '2021-03-24'
    END = '2026-03-23'

    # 数据抽取与清洗
    df_prices = load_and_standardize_price_data(TARGET_SYMBOLS, WORK_DIR, START, END, "clean_target_data")
    df_bond = load_and_standardize_bond_data(BOND_SYMBOLS, WORK_DIR, START, END, 'clean_bond_data')
    df_compare = load_and_standardize_price_data(COMPARE_SYMBOLS, WORK_DIR, START, END, "clean_compare_data")
    
    # 汇率转换
    df_prices = apply_currency_conversion(df_prices, foreign_symbols=FOREIGN_SYMBOLS)
    df_compare = apply_currency_conversion(df_compare, foreign_symbols=FOREIGN_SYMBOLS)

    # 提取动态无风险利率 (转化为小数)
    dynamic_rf = df_bond['treasury_bonds_yield'] / 100.0

    print(f"\n[*] 开始搜索满足条件的权重组合")
    found = False
    for test_weights in generate_weights(len(TARGET_SYMBOLS), 0.05):
        portfolio_res = run_backtest_engine(df_prices, test_weights, annual_fees=ANNUAL_FEES, enable_rebalance=True, rebalance_freq='W', friction_costs=FRICTION_COST, verbose=False)
        
        mdd_value, mdd_date, drawdown_series = calculate_max_drawdown(portfolio_res)
        rolling_sharpe = calculate_rolling_sharpe_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        sortino = calculate_sortino_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        underwater_days = calculate_underwater_time(portfolio_res)
        
        if evaluate_portfolio(mdd_value, rolling_sharpe, sortino, underwater_days):
            print(f"[+] 找到满足条件的权重! 权重: {test_weights}, MDD: {mdd_value:.2%}, Rolling_Sharpe_mean: {rolling_sharpe.mean():.2f}, Sortino: {sortino:.2f}")
            WEIGHTS = test_weights
            found = True
            break
            
    if not found:
        print("[-] 遍历完毕，未找到满足条件的权重组合。")
        exit(0)
    
    # 生成收益曲线，传入对照组及评价指标
    mdd_trigger_date = plot_portfolio_performance(portfolio_res, df_compare, mdd_value, mdd_date, rolling_sharpe.mean(), sortino, WEIGHTS, df_prices.columns, WORK_DIR)

    # 成份股走势分析
    plot_component_trends(df_prices, mdd_trigger_date, WORK_DIR)
    
    print("\n[√] 核心系统运行完毕，请在当前目录检查图表。")