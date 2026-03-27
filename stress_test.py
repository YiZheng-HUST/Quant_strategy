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
def run_backtest_engine(prices_df, initial_weights, annual_fees=None, enable_rebalance=True, rebalance_freq='M', friction_costs=FRICTION_COST, verbose=True, use_ma_strategy=True):
    """
    计算净值曲线。
    rebalance_freq: 'M'(月度), 'Q'(季度), 'Y'(年度), 'W'(每周)
    annual_fees: list, 各ETF对应的年化费用率列表
    use_ma_strategy: bool, 是否启用均线择时策略。若为True，则忽略 enable_rebalance 和 rebalance_freq。
    """
    ma_strategy_status = "启用均线择时" if use_ma_strategy else f"关闭均线择时 (再平衡机制: {'开启 (' + rebalance_freq + ')' if enable_rebalance else '关闭'})"
    if verbose:
        print(f"[*] 启动回测引擎... ({ma_strategy_status})")

    # --- 策略设置与数据对齐 ---
    if use_ma_strategy:
        sma20 = prices_df.rolling(window=20).mean()
        sma60 = prices_df.rolling(window=60).mean()
        
        # 使用Panel/concat结构化数据并对齐，dropna确保所有指标都有效
        panel = pd.concat({
            'prices': prices_df,
            'returns': prices_df.pct_change(),
            'sma20': sma20,
            'sma60': sma60
        }, axis=1).dropna()
        
        prices = panel['prices']
        daily_returns = panel['returns']
        sma20 = panel['sma20']
        sma60 = panel['sma60']
    else:
        daily_returns = prices_df.pct_change().dropna()

    # --- 回测初始化 ---
    if daily_returns.empty:
        if verbose: print("[!] 数据周期不足60天，无法启用均线策略。")
        return pd.Series(dtype=float)

    portfolio_value = [1.0]
    current_weights = np.array(initial_weights).copy()
    is_held = np.ones(len(initial_weights), dtype=bool) # 跟踪持仓状态
    periods = daily_returns.index.to_period(rebalance_freq)

    # --- 主循环 ---
    for i in range(len(daily_returns)):
        today_index = daily_returns.index[i]
        asset_returns = daily_returns.iloc[i].values

        if annual_fees is not None:
            daily_fees = np.array(annual_fees) / 252.0
            asset_returns = asset_returns - daily_fees

        rebalance_needed = False
        target_weights = current_weights

        # --- 均线择时策略逻辑 ---
        if use_ma_strategy:
            new_is_held = is_held.copy()
            for j in range(len(initial_weights)):
                price_today = prices.iloc[i, j]
                sma60_today = sma60.iloc[i, j]
                
                # 卖出信号: 价格跌破SMA60
                if is_held[j] and price_today < sma60_today:
                    new_is_held[j] = False
                # 买入信号: SMA20上穿SMA60 (金叉)
                elif not is_held[j] and i > 0:
                    sma20_today = sma20.iloc[i, j]
                    sma20_yesterday = sma20.iloc[i-1, j]
                    sma60_yesterday = sma60.iloc[i-1, j]
                    if sma20_yesterday <= sma60_yesterday and sma20_today > sma60_today:
                        new_is_held[j] = True
            
            if not np.array_equal(is_held, new_is_held):
                is_held = new_is_held
                rebalance_needed = True
                
                # 根据持仓状态，重新计算目标权重
                held_initial_weights = np.array(initial_weights) * is_held
                total_held_weight = np.sum(held_initial_weights)
                if total_held_weight > 0:
                    target_weights = held_initial_weights / total_held_weight
                else: # 全部卖出，现金持有
                    target_weights = np.zeros_like(initial_weights)
        
        # --- 原有周期性再平衡逻辑 ---
        elif enable_rebalance and i < len(daily_returns) - 1 and periods[i] != periods[i+1]:
            rebalance_needed = True
            target_weights = np.array(initial_weights)

        # --- 投资组合净值计算 ---
        # 1. 使用再平衡前的权重计算当日收益
        today_return = np.sum(current_weights * asset_returns)
        new_value = portfolio_value[-1] * (1 + today_return)

        # 2. 计算权重自然漂移
        drifted_weights = current_weights * (1 + asset_returns) / (1 + today_return) if (1 + today_return) != 0 else np.zeros_like(current_weights)

        # 3. 如果需要再平衡，则计算成本并更新权重
        if rebalance_needed:
            turnover_weight = np.sum(np.maximum(0, drifted_weights - target_weights))
            
            sell_cost = turnover_weight * friction_costs["stamp_duty"]
            round_trip_cost = turnover_weight * 2 * (friction_costs["commission"] + friction_costs["transfer_fee"] + friction_costs["regulatory_fee"])
            total_friction_ratio = sell_cost + round_trip_cost
            
            new_value *= (1 - total_friction_ratio) # 从当日净值中扣除总摩擦成本
            current_weights = target_weights.copy()
        else:
            current_weights = drifted_weights

        portfolio_value.append(new_value)

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
def evaluate_portfolio(mdd_val: float, shp: pd.Series, srt: float, underwater: int, portfolio_res: pd.Series):
    """
    评估投资组合表现是否满足预设标准。
    - 条件1: 最大回撤小于10%
    - 条件2: 滚动夏普比率序列中，超过80%的值要大于0.8
    - 条件3: 索提诺比率大于1.0
    - 条件4: 最大水下时间小于180天
    """
    # 条件1: 最大回撤
    cond1 = mdd_val > -0.10

    # 条件2: 滚动夏普比率
    cond2 = (shp > 0.8).mean() >= 0.8
    
    # 条件3: 索提诺比率
    cond3 = srt > 1.0

    # 条件4: 最大水下时间
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

    print(f"\n[*] 开始使用均线策略搜索满足条件的权重组合...")
    found = False
    for test_weights in generate_weights(len(TARGET_SYMBOLS), 0.05):
        portfolio_res = run_backtest_engine(prices_df=df_prices, 
                                            initial_weights=test_weights, 
                                            annual_fees=ANNUAL_FEES, 
                                            enable_rebalance=True,
                                            rebalance_freq='W', 
                                            friction_costs=FRICTION_COST, 
                                            verbose=False, 
                                            use_ma_strategy=False)
        
        if portfolio_res.empty:
            continue

        mdd_value, mdd_date, drawdown_series = calculate_max_drawdown(portfolio_res)
        rolling_sharpe = calculate_rolling_sharpe_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        sortino = calculate_sortino_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        underwater_days = calculate_underwater_time(portfolio_res)
        
        if not rolling_sharpe.empty and evaluate_portfolio(mdd_value, rolling_sharpe, sortino, underwater_days, portfolio_res):
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