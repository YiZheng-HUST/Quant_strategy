import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os
from akshare_data_fetch import A_SHARE_ETFS, US_SHARE_ETFS_EASTMONEY, US_SHARE_ETFS_SINA

# 全局图表样式设置
plt.style.use('seaborn-v0_8-whitegrid')

# ==========================================
# 数据读取、表头清洗与强制对齐
# ==========================================
def load_and_standardize_data(symbols, csv_dir, start_date, end_date):
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
    prices.to_csv(os.path.join(csv_dir, 'clean_data.csv'))
    return prices

# ==========================================
# 汇率穿透引擎
# ==========================================
def apply_currency_conversion(prices_df, foreign_symbols, base_curr='USD', target_curr='CNY'):
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
# 核心量化指标评测 (纯计算无图表)
# ==========================================
def calculate_max_drawdown(portfolio_series):
    """
    计算最大回撤及其发生的精确日期。
    返回: max_drawdown (负数), mdd_date (日期), drawdown_series (每日回撤序列)
    """
    rolling_max = portfolio_series.cummax()
    drawdown_series = (portfolio_series - rolling_max) / rolling_max
    max_drawdown = drawdown_series.min()
    mdd_date = drawdown_series.idxmin()
    return max_drawdown, mdd_date, drawdown_series

def calculate_sharpe_ratio(portfolio_series, risk_free_rate=0.02, trading_days=252):
    """
    计算年化夏普比率。
    risk_free_rate: 无风险利率基准（默认2%）
    trading_days: 一年交易天数（默认252天）
    """
    # 逆向推导组合的每日涨跌幅
    daily_returns = portfolio_series.pct_change().dropna()
    
    # 计算年化收益率 (CAGR)
    total_return = portfolio_series.iloc[-1] / portfolio_series.iloc[0]
    annualized_return = total_return ** (trading_days / len(portfolio_series)) - 1
    
    # 计算年化波动率
    annualized_vol = daily_returns.std() * np.sqrt(trading_days)
    
    # 容错处理：防止组合绝对无波动导致除以零
    if annualized_vol == 0:
        return 0.0
        
    sharpe_ratio = (annualized_return - risk_free_rate) / annualized_vol
    return sharpe_ratio

# ==========================================
# 可视化 - 总体资产体检图
# ==========================================
def plot_portfolio_performance(portfolio_series, save_dir):
    """
    绘制整体资金曲线及回撤阴影，并标记最大回撤点。
    """
    rolling_max = portfolio_series.cummax()
    drawdown = (portfolio_series - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    mdd_date = drawdown.idxmin()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(portfolio_series.index, portfolio_series, label='Portfolio Net Value', color='#1f77b4', linewidth=2.5)
    ax.fill_between(drawdown.index, rolling_max, portfolio_series, color='red', alpha=0.3, label='Drawdown Area')
    
    ax.scatter(mdd_date, portfolio_series.loc[mdd_date], color='red', s=100, zorder=5)
    ax.annotate(f'MDD: {max_drawdown*100:.2f}%\n({mdd_date.date()})', 
                xy=(mdd_date, portfolio_series.loc[mdd_date]), 
                xytext=(-100, -40), textcoords='offset points',
                arrowprops=dict(arrowstyle='->', color='red'), color='red', fontweight='bold')

    ax.set_title('Figure 1: Total Portfolio Performance', fontsize=15, fontweight='bold')
    ax.set_ylabel('Net Value (Base=1.0)', fontsize=12)
    ax.legend(loc='upper left')
    
    save_path = os.path.join(save_dir, 'portfolio_performance.png')
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig) # 释放内存
    print(f"[+] 图 1 已保存至: {save_path}")
    return mdd_date # 返回最大回撤日期供图 2 使用

# ==========================================
# 可视化 - 成分股崩塌透视图
# ==========================================
def plot_component_trends(prices_df, mdd_date, save_dir):
    """
    绘制所有成分资产的归一化走势，并切入回撤基准线。
    """
    normalized_prices = prices_df / prices_df.iloc[0] * 100
    
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ['#2ca02c', '#ff7f0e', '#9467bd', '#bcbd22']
    
    for i, sym in enumerate(prices_df.columns):
        color = colors[i % len(colors)]
        ax.plot(normalized_prices.index, normalized_prices[sym], label=sym, color=color, linewidth=1.5, alpha=0.8)

    # 垂直对齐最大回撤日
    ax.axvline(mdd_date, color='red', linestyle='--', linewidth=2, label='Portfolio MDD Trigger')

    ax.set_title('Figure 2: Normalized Component Trends (Base=100)', fontsize=15, fontweight='bold')
    ax.set_ylabel('Normalized Price', fontsize=12)
    ax.legend(loc='upper left', frameon=True)
    ax.axhline(100, color='black', linewidth=1)
    
    save_path = os.path.join(save_dir, 'component_trends.png')
    fig.tight_layout()
    fig.savefig(save_path, dpi=300)
    plt.close(fig)
    print(f"[+] 图 2 已保存至: {save_path}")

# ==========================================
# 主程序执行入口 (Main Execution)
# ==========================================
if __name__ == "__main__":
    # 配置参数
    WORK_DIR = '/home/yizheng/workpath/finance/stress_test_data/20250320-20260320/' 
    TARGET_SYMBOLS = [A_SHARE_ETFS['A_short_term_bond_etf'], A_SHARE_ETFS['A_red_etf_huatai'], US_SHARE_ETFS_SINA['nasdaq'], A_SHARE_ETFS['A_huaan_gold_etf']]
    WEIGHTS = [0.50, 0.20, 0.20, 0.10]
    START = '2025-03-20'
    END = '2026-03-20'

    # 抽取与清洗
    df_prices = load_and_standardize_data(TARGET_SYMBOLS, WORK_DIR, START, END)
    
    # 汇率转换
    df_prices = apply_currency_conversion(df_prices, foreign_symbols=US_SHARE_ETFS_SINA['nasdaq'])
    
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