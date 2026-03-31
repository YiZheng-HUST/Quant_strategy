import pandas as pd
import numpy as np
from currency_converter import CurrencyConverter
from typing import List, Dict, Optional, Tuple
from akshare_data_fetch import A_SHARE_ETFS, US_SHARE_ETFS_EASTMONEY, US_SHARE_ETFS_SINA
from load_and_standardize_data import load_and_standardize_price_data, load_and_standardize_bond_data, load_and_standardize_fraction_sweep_data
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
def apply_currency_conversion(prices_df: pd.DataFrame, foreign_symbols: list, base_curr: str='USD', target_curr: str='CNY') -> pd.DataFrame:
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
    prices_df['FX_RATE'] = prices_df['FX_RATE'].ffill()
    
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
def run_backtest_engine(prices_df: pd.DataFrame, 
                        initial_weights: List[float], 
                        annual_fees: Optional[List[float]]=None, 
                        enable_rebalance: bool=True, 
                        rebalance_freq: str='M', 
                        friction_costs: Dict[str, float]=FRICTION_COST, 
                        verbose: bool=True, 
                        use_ma_strategy: bool=True, 
                        initial_capital: float=100000.0, 
                        df_fraction: Optional[pd.DataFrame]=None) -> pd.Series:
    """
    计算净值曲线。
    rebalance_freq: 'M'(月度), 'Q'(季度), 'Y'(年度), 'W'(每周)
    annual_fees: list, 各ETF对应的年化费用率列表
    use_ma_strategy: bool, 是否启用均线择时策略。若为True，则忽略 enable_rebalance 和 rebalance_freq。
    initial_capital: float, 初始资金（默认100万），用于计算真实交易份额和100份交易限制。
    df_fraction: pd.DataFrame, 闲置资金理财产品（如货币基金/短融ETF）的净值走势，闲置资金每日将以此产生收益。
    """
    ma_strategy_status = "启用均线择时" if use_ma_strategy else f"关闭均线择时 (再平衡机制: {'开启 (' + rebalance_freq + ')' if enable_rebalance else '关闭'})"
    if verbose:
        print(f"[*] 启动回测引擎... ({ma_strategy_status})")

    # --- 策略设置与数据对齐 ---
    if use_ma_strategy:
        if len(prices_df) < 200:
            if verbose: print("[!] 数据周期不足200天，无法启用均线策略。")
            return pd.Series(dtype=float)

        sma200 = prices_df.rolling(window=200).mean() # 计算200日均线
        
        # 使用Panel/concat结构化数据并对齐，dropna确保所有指标都有效
        panel = pd.concat({
            'prices': prices_df,
            'returns': prices_df.pct_change(),
            'sma200': sma200
        }, axis=1).dropna()
        
        prices = panel['prices']
        daily_returns = panel['returns']
        sma200 = panel['sma200']
        
        # 均线对齐后，第一天的真实价格位于原始 prices_df 的前一日
        start_index_in_prices_df = prices_df.index.get_loc(prices.index[0]) - 1
        initial_prices = prices_df.iloc[start_index_in_prices_df].values
    else:
        daily_returns = prices_df.pct_change().dropna()
        prices = prices_df.loc[daily_returns.index]
        initial_prices = prices_df.iloc[0].values

    if verbose:
        print(f"[*] df_fraction: ({df_fraction})")

    # 提取理财产品收益率序列 (对齐至交易日历)
    if df_fraction is not None and not df_fraction.empty:
        # 假设 df_fraction 包含理财产品归一化或打折后的净值，取第一列计算日收益
        fraction_returns = df_fraction.iloc[:, 0].pct_change().fillna(0)
        fraction_returns = fraction_returns.reindex(daily_returns.index).fillna(0)
    else:
        fraction_returns = pd.Series(0.0, index=daily_returns.index)

    # 依据初始资金计算初始份额建仓 (强制按100份规则买入)
    target_cap = initial_capital * np.array(initial_weights)
    if verbose:
        print(f"[*] target_cap: ({target_cap})")
    buy_friction_ratio = friction_costs["commission"] + friction_costs["transfer_fee"] + friction_costs["regulatory_fee"]
    if verbose:
        print(f"[*] buy_friction_ratio: ({buy_friction_ratio})")

    shares = np.floor(target_cap / (initial_prices * (1 + buy_friction_ratio)) / 100) * 100
    if verbose:
        print(f"[*] shares: ({shares})")
    
    invested_cap = np.sum(shares * initial_prices)
    if verbose:
        print(f"[*] invested_cap: ({invested_cap})")

    buy_costs = np.sum(invested_cap * buy_friction_ratio)
    if verbose:
        print(f"[*] buy_costs: ({buy_costs})")

    cash = initial_capital - invested_cap - buy_costs
    if verbose:
        print(f"[*] cash: ({cash})")
    portfolio_value = [initial_capital]

    periods = daily_returns.index.to_period(rebalance_freq)
    if verbose:
        print(f"[*] periods length: ({len(periods)})")

    # --- 主循环 ---
    for i in range(len(daily_returns)):
        today_prices = prices.iloc[i].values

        # 每日闲置现金自动结算理财收益
        cash *= (1 + fraction_returns.iloc[i])

        if annual_fees is not None:
            daily_fees = np.array(annual_fees) / 252.0
            fee_deduction = np.sum(shares * today_prices * daily_fees)
            cash -= fee_deduction

        rebalance_needed = False
        target_weights = None

        # --- 周期性再平衡检查 ---
        if enable_rebalance and i < len(daily_returns) - 1 and periods[i] != periods[i+1]:
            rebalance_needed = True
            
            # 默认的目标权重是初始的战略配置
            target_weights = np.array(initial_weights)

            # 如果启用均线策略，则在再平衡日进行判断，并用其作为过滤器
            if use_ma_strategy:
                is_bullish_filter = np.ones(len(initial_weights), dtype=bool)
                for j in range(len(initial_weights)):
                    price_today = today_prices[j]
                    sma200_today = sma200.iloc[i, j]
                    # 价格低于200日均线的资产，被视为空头市场，本次不持有
                    if price_today < sma200_today:
                        is_bullish_filter[j] = False
                
                # 将均线过滤器应用到目标权重上。
                # 对于被过滤的资产，目标权重变为0，其资金将以现金形式持有（因为总权重不再归一化为1）。
                target_weights = target_weights * is_bullish_filter

        # --- 触发真实交易执行 (附带100份最小交易单位限制) ---
        if rebalance_needed:
            current_total_value = np.sum(shares * today_prices) + cash
            if verbose:
                print(f"[*] current_total_value in period {i}: ({current_total_value})")
            target_cap_allocation = current_total_value * target_weights
            if verbose:
                print(f"[*] target_cap_allocation in period {i}: ({target_cap_allocation})")
            exact_target_shares = target_cap_allocation / today_prices
            if verbose:
                print(f"[*] exact_target_shares in period {i}: ({exact_target_shares})")
            delta_shares_exact = exact_target_shares - shares
            if verbose:
                print(f"[*] delta_shares_exact in period {i}: ({delta_shares_exact})")
            
            # 当偏离绝对值 >= 100 时才触发交易，且只交易 100 的整数倍
            trade_shares = np.trunc(delta_shares_exact / 100) * 100
            if verbose:
                print(f"[*] trade_shares in period {i}: ({trade_shares})")
            
            # 1. 优先处理卖出以释放资金
            sell_mask = trade_shares < 0
            if np.any(sell_mask):
                sell_shares = np.abs(trade_shares[sell_mask])
                sell_revenue = sell_shares * today_prices[sell_mask]
                if verbose:
                    print(f"[*] sell_revenue in period {i}: ({sell_revenue})")
                
                sell_friction_ratio = friction_costs["commission"] + friction_costs["transfer_fee"] + friction_costs["regulatory_fee"] + friction_costs["stamp_duty"]
                sell_costs = sell_revenue * sell_friction_ratio
                if verbose:
                    print(f"[*] sell_costs in period {i}: ({sell_costs})")
                
                cash += np.sum(sell_revenue - sell_costs)
                if verbose:
                    print(f"[*] cash after sold in period {i}: ({cash})")
                shares[sell_mask] -= sell_shares

            # 2. 再处理买入
            buy_mask = trade_shares > 0
            if np.any(buy_mask):
                buy_shares = trade_shares[buy_mask]
                buy_cost_basis = buy_shares * today_prices[buy_mask]
                if verbose:
                    print(f"[*] buy_cost_basis in period {i}: ({buy_cost_basis})")
                
                buy_friction_ratio = friction_costs["commission"] + friction_costs["transfer_fee"] + friction_costs["regulatory_fee"]
                buy_costs = buy_cost_basis * buy_friction_ratio
                if verbose:
                    print(f"[*] buy_costs in period {i}: ({buy_costs})")

                total_buy_needed = buy_cost_basis + buy_costs
                
                total_needed_cash = np.sum(total_buy_needed)
                if verbose:
                    print(f"[*] total_needed_cash in period {i}: ({total_needed_cash})")

                # 防止资金不足 (由于偏离整数导致)：按比例缩减买入请求并继续遵守100份限制
                if total_needed_cash > cash and total_needed_cash > 0:
                    if verbose:
                        print(f"[*] cach: {cash} < total_needed_cash: {total_needed_cash}")
                    scale_factor = cash / total_needed_cash
                    if verbose:
                        print(f"[*] scale_factor: {scale_factor}")

                    scaled_buy_shares = np.trunc((buy_shares * scale_factor) / 100) * 100
                    
                    buy_cost_basis = scaled_buy_shares * today_prices[buy_mask]
                    buy_costs = buy_cost_basis * buy_friction_ratio
                    total_buy_needed = buy_cost_basis + buy_costs
                    trade_shares[buy_mask] = scaled_buy_shares
                
                cash -= np.sum(total_buy_needed)
                if verbose:
                    print(f"[*] cash after buy in period {i}: ({cash})")
                shares[buy_mask] += trade_shares[buy_mask]
            if verbose:
                print(f"[*] shares in period {i}: ({shares})")
                print(f"[*] cash in period {i}: ({cash})")
                print("")

        # 计算当日收盘总净值
        current_value = np.sum(shares * today_prices) + cash
        portfolio_value.append(current_value)

    # 返回归一化的净值序列 (初始净值=1.0) 以兼容外部评估指标及出图逻辑
    portfolio_series = pd.Series(portfolio_value[1:], index=daily_returns.index)
    portfolio_series = portfolio_series / initial_capital

    return portfolio_series

def generate_constrained_weights(bounds: list, step: float=0.05):
    """
    带边界约束的高效权重生成器 (深度优先搜索 + 动态剪枝)
    :param bounds: 列表的列表或元组，例如 [(0.3, 0.8), (0.1, 0.4), (0.1, 0.3), (0.0, 0.15)]
    :param step: 步长
    """
    num_assets = len(bounds)
    total_steps = int(round(1.0 / step))
    
    # 步骤 1: 将浮点数的比例边界，全部转化为“步数 (steps)”的绝对整数边界，抹平浮点误差
    step_bounds = []
    for min_val, max_val in bounds:
        min_steps = int(round(min_val / step))
        max_steps = int(round(max_val / step))
        step_bounds.append((min_steps, max_steps))

    def _generate(asset_index, remaining_steps):
        # 递归终点：处理到最后一个资产
        if asset_index == num_assets - 1:
            min_step, max_step = step_bounds[asset_index]
            # 只有当剩下的步数刚好落在最后一个资产的允许范围内，才是一组有效解
            if min_step <= remaining_steps <= max_step:
                yield [round(remaining_steps * step, 4)]
            return

        # 递归分支：当前资产的允许上下限
        min_step, max_step = step_bounds[asset_index]
        
        # 核心剪枝逻辑 (Branch and Bound)：
        # 计算“后面所有资产”最少需要消耗多少步，最多能吸收多少步
        min_absorbable = sum(b[0] for b in step_bounds[asset_index + 1:])
        max_absorbable = sum(b[1] for b in step_bounds[asset_index + 1:])
        
        # 动态收窄当前资产的遍历范围：
        # 1. 不能少于当前资产自身的下限，也不能让后面的资产“撑死”（超过 max_absorbable）
        start_i = max(min_step, remaining_steps - max_absorbable)
        # 2. 不能大于当前资产自身的上限，也不能让后面的资产“饿死”（不够 min_absorbable）
        end_i = min(max_step, remaining_steps - min_absorbable)

        # 只在这个被严格数学物理约束的范围内进行有效遍历
        for i in range(start_i, end_i + 1):
            for tail in _generate(asset_index + 1, remaining_steps - i):
                yield [round(i * step, 4)] + tail

    yield from _generate(0, total_steps)

# ==========================================
# 策略优化搜索：寻找最佳权重组合
# ==========================================
def evaluate_portfolio(mdd_val: float, shp: pd.Series, srt: float, underwater: int, portfolio_res: pd.Series) -> Tuple[bool, str]:
    """
    评估投资组合表现是否满足预设标准。
    - 条件1: 最大回撤
    - 条件2: 滚动夏普比率
    - 条件3: 索提诺比率
    - 条件4: 最大水下时间
    """
    MDD_VAL = -0.20
    SHARPE_RATIO = 0.6
    SHARPE_RATIO_PERCENTAGE = 0.55
    SORTINO_RATIO = 0.75
    UNDERWATER_TIME = 600

    reasons = []
    
    if not (mdd_val > MDD_VAL):
        reasons.append(f"最大回撤({mdd_val:.2%}) <= {MDD_VAL}")

    shp_ratio = (shp > SHARPE_RATIO).mean()
    if not (shp_ratio >= SHARPE_RATIO_PERCENTAGE):
        reasons.append(f"夏普 > {SHARPE_RATIO} 的占比({shp_ratio:.2%}) < {SHARPE_RATIO_PERCENTAGE}")
    
    if not (srt > SORTINO_RATIO):
        reasons.append(f"索提诺比率({srt:.2f}) <= {SORTINO_RATIO}")

    if not (underwater < UNDERWATER_TIME):
        reasons.append(f"最大水下时间({underwater}天) >= {UNDERWATER_TIME}天")
        
    return len(reasons) == 0, " | ".join(reasons)

# ==========================================
# 主程序执行入口 (Main Execution)
# ==========================================
if __name__ == "__main__":
    # 配置参数
    WORK_DIR = '/workspace/finance/stress_test_data/20160330-20260320/'

    # 碎片资金管理
    FRACTION_SWEEP = [
        A_SHARE_ETFS['short_term_bond_haifutong_etf']
    ]

    # 选ETF组合
    TARGET_SYMBOLS = [
        A_SHARE_ETFS['five_year_treasury_bond_guotai_etf'],
        A_SHARE_ETFS['red_huatai_etf'], 
        A_SHARE_ETFS['nasdaq_guangfa_etf'], 
        A_SHARE_ETFS['gold_huaan_etf']]
    
    # 约束权重
    TARGET_BOUNDS = [
        (0.00, 0.50),
        (0.00, 0.50),
        (0.00, 0.50),
        (0.00, 0.15)
    ]

    if len(TARGET_SYMBOLS) != len(TARGET_BOUNDS):
        raise ValueError(f"TARGET_SYMBOLS length: {len(TARGET_SYMBOLS)} not equal to TARGET_BOUNDS length: {len(TARGET_BOUNDS)}")

    WEIGHTS = [0.50, 0.20, 0.20, 0.10]

    # 提取各 ETF 的年化费用 (A股为管理费+托管费，美股为总费用)
    ANNUAL_FEES = [etf.get('total_fee', etf.get('management_fee', 0.0) + etf.get('trustee_fee', 0.0)) for etf in TARGET_SYMBOLS]

    # 选择对照组
    COMPARE_SYMBOLS = [A_SHARE_ETFS['csi_300_huatai_etf'], US_SHARE_ETFS_SINA['sp500']]

    # 设置日期
    START = '2016-03-30'
    END = '2026-03-20'

    # 数据抽取与清洗
    df_prices = load_and_standardize_price_data(TARGET_SYMBOLS, WORK_DIR, START, END, "clean_target_data")
    df_fraction = load_and_standardize_fraction_sweep_data(FRACTION_SWEEP, WORK_DIR, START, END, "clean_fraction_sweep_data")
    df_bond = load_and_standardize_bond_data(BOND_SYMBOLS, WORK_DIR, START, END, 'clean_bond_data')
    df_compare = load_and_standardize_price_data(COMPARE_SYMBOLS, WORK_DIR, START, END, "clean_compare_data")
    
    # 汇率转换
    df_prices = apply_currency_conversion(df_prices, foreign_symbols=FOREIGN_SYMBOLS)
    df_compare = apply_currency_conversion(df_compare, foreign_symbols=FOREIGN_SYMBOLS)

    # 提取动态无风险利率 (转化为小数)
    dynamic_rf = df_bond['treasury_bonds_yield'] / 100.0

    print(f"\n[*] 开始使用搜索满足条件的权重组合...")
    valid_portfolios = []

    for test_weights in generate_constrained_weights(TARGET_BOUNDS, 0.05):
        portfolio_res = run_backtest_engine(prices_df=df_prices, 
                                            initial_weights=test_weights, 
                                            annual_fees=ANNUAL_FEES, 
                                            enable_rebalance=True,
                                            rebalance_freq='M', 
                                            friction_costs=FRICTION_COST, 
                                            verbose=False, 
                                            use_ma_strategy=False,
                                            initial_capital=100000.0,
                                            df_fraction=df_fraction)
        
        if portfolio_res.empty:
            continue

        mdd_value, mdd_date, drawdown_series = calculate_max_drawdown(portfolio_res)
        rolling_sharpe = calculate_rolling_sharpe_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        sortino = calculate_sortino_ratio(portfolio_res, risk_free_rate=dynamic_rf)
        underwater_days, uw_start, uw_end = calculate_underwater_time(portfolio_res)
        
        if not rolling_sharpe.empty:
            is_pass, reason = evaluate_portfolio(mdd_value, rolling_sharpe, sortino, underwater_days, portfolio_res)
            if is_pass:
                final_return = portfolio_res.iloc[-1]
                
                # 将通过评估的组合指标全部打包记录，以便后续排名和调用
                valid_portfolios.append({
                    'weights': test_weights,
                    'portfolio_res': portfolio_res,
                    'mdd_value': mdd_value,
                    'mdd_date': mdd_date,
                    'rolling_sharpe': rolling_sharpe,
                    'sortino': sortino,
                    'underwater_days': underwater_days,
                    'uw_start': uw_start,
                    'uw_end': uw_end,
                    'final_return': final_return
                })
            else:
                print(f"[-] 权重组合 {test_weights} 被过滤，未通过原因: {reason}")
            
    if not valid_portfolios:
        print("[-] 遍历完毕，未找到满足条件的权重组合。")
        exit(0)

    # 统一打印所有符合条件的组合信息
    print(f"\n[+] 共找到 {len(valid_portfolios)} 个满足条件的组合，详情如下:")
    # 为了打印对齐，先对组合按最终收益排序
    valid_portfolios.sort(key=lambda x: x['final_return'], reverse=True)
    for p in valid_portfolios:
        print(f"  - 权重: {p['weights']}, 最终净值: {p['final_return']:.4f}, MDD: {p['mdd_value']:.2%}, 夏普均值: {p['rolling_sharpe'].mean():.2f}, 索提诺: {p['sortino']:.2f}, 水下天数: {p['underwater_days']}天")
        
    # 按照最终净值 (final_return) 降序排序，选出最高的一组
    valid_portfolios.sort(key=lambda x: x['final_return'], reverse=True)
    best_portfolio = valid_portfolios[0]
    
    # 重新赋值给全局变量，供绘图使用
    WEIGHTS = best_portfolio['weights']
    portfolio_res = best_portfolio['portfolio_res']
    mdd_value = best_portfolio['mdd_value']
    mdd_date = best_portfolio['mdd_date']
    rolling_sharpe = best_portfolio['rolling_sharpe']
    sortino = best_portfolio['sortino']
    underwater_days = best_portfolio['underwater_days']
    uw_start = best_portfolio['uw_start']
    uw_end = best_portfolio['uw_end']
    
    print(f"\n[+] 最终选定最佳组合! 权重: {WEIGHTS}, 最终净值: {best_portfolio['final_return']:.4f}, MDD: {mdd_value:.2%}, 夏普均值: {best_portfolio['rolling_sharpe'].mean():.2f}, 索提诺: {sortino:.2f}, 水下天数: {underwater_days}天")
    
    # 生成收益曲线，传入对照组及评价指标
    mdd_trigger_date = plot_portfolio_performance(portfolio_res, df_compare, mdd_value, mdd_date, rolling_sharpe.mean(), sortino, underwater_days, uw_start, uw_end, WEIGHTS, df_prices.columns, WORK_DIR)

    # 成份股走势分析
    plot_component_trends(df_prices, mdd_trigger_date, WORK_DIR)
    
    print("\n[√] 核心系统运行完毕，请在当前目录检查图表。")