import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os
import matplotlib.ticker as ticker
import matplotlib.dates as mdates


# 全局图表样式设置
plt.style.use('seaborn-v0_8-whitegrid')

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


def calculate_rolling_sharpe_ratio(portfolio_series, risk_free_rate=0.02, trading_days=252):
    """
    计算滚动夏普比率（窗口为 trading_days）的均值。
    risk_free_rate: 无风险利率基准（默认2%）
    trading_days: 滚动时间窗口及一年交易天数（默认252天）
    """
    # 逆向推导组合的每日涨跌幅
    daily_returns = portfolio_series.pct_change().dropna()
    
    # 如果数据不足一个完整的滚动窗口，直接报错
    if len(portfolio_series) <= trading_days:
        raise ValueError(f"portfolio_series len = {len(portfolio_series)}, less than trading_days = {trading_days}")

    # 1. 计算滚动一年的收益率 (相隔 trading_days 的变化率)
    rolling_return = portfolio_series.pct_change(periods=trading_days).dropna()
    
    # 2. 计算滚动一年的年化波动率
    rolling_vol = daily_returns.rolling(window=trading_days).std().dropna() * np.sqrt(trading_days)
    rolling_vol = rolling_vol.replace(0, np.nan) # 防止绝对无波动时除以 0
    
    # 3. 得到滚动夏普比率序列，利用 Pandas 索引自动对齐相除
    rolling_sharpe = (rolling_return - risk_free_rate) / rolling_vol

    # 返回滚动夏普序列的均值作为最终评价指标
    return rolling_sharpe


def calculate_sortino_ratio(portfolio_series, risk_free_rate=0.02, trading_days=252):
    """
    计算年化索提诺比率。
    risk_free_rate: 无风险利率基准（默认2%）
    trading_days: 一年交易天数（默认252天）
    """
    # 逆向推导组合的每日涨跌幅
    daily_returns = portfolio_series.pct_change().dropna()
    
    # 计算年化收益率 (CAGR)
    total_return = portfolio_series.iloc[-1] / portfolio_series.iloc[0]
    annualized_return = total_return ** (trading_days / len(portfolio_series)) - 1
    
    # 将年化无风险利率折算为每日基准
    daily_rf = (1 + risk_free_rate) ** (1 / trading_days) - 1
    
    # 计算下行落差 (如果当日收益大于 daily_rf，则记为0)
    downside_diff = np.minimum(0, daily_returns - daily_rf)
    
    # 计算年化下行波动率
    downside_vol = np.sqrt(np.mean(downside_diff ** 2)) * np.sqrt(trading_days)
    
    # 容错处理：防止无下行波动导致除以零
    if downside_vol == 0:
        return 0.0
        
    sortino_ratio = (annualized_return - risk_free_rate) / downside_vol
    return sortino_ratio


def calculate_underwater_time(portfolio_series):
    """
    计算净值从创新高到再次创新高所需的时间（水下时间），返回统计周期中的最大值。
    """
    peak_dates = []  # 记录每个创新高的时间点
    underwater_durations = []  # 记录每次水下持续的时间

    # 1. 找到所有创新高的时间点
    rolling_max = portfolio_series.cummax()
    is_new_peak = portfolio_series == rolling_max
    peak_dates = portfolio_series[is_new_peak].index.tolist()

    # 2. 计算每次创新高后，到下一次创新高之间的时间差
    for i in range(len(peak_dates) - 1):
        time_delta = peak_dates[i+1] - peak_dates[i]
        underwater_durations.append(time_delta.days)  # 转换为天数

    # 3. 返回最大水下持续时间 (如果列表为空，则说明一直创新高，返回 0)
    if underwater_durations:
        max_underwater_time = max(underwater_durations)
    else:
        max_underwater_time = 0

    return max_underwater_time

# ==========================================
# 可视化 - 总体资产体检图
# ==========================================
def plot_portfolio_performance(portfolio_res, df_compare, mdd_value, mdd_date, sharpe, sortino, weights, asset_names, work_dir):
    import matplotlib.pyplot as plt
    import os
    
    fig, ax = plt.subplots(figsize=(19.2, 10.8))
    # 1. 绘制对照组（基准）资产并做归一化处理（计算为起始净值为1.0的曲线）
    if df_compare is not None and not df_compare.empty:
        for col in df_compare.columns:
            benchmark_series = df_compare[col].dropna()
            if not benchmark_series.empty:
                # 归一化：每日价格 / 初始价格
                normalized_benchmark = benchmark_series / benchmark_series.iloc[0]
                ax.plot(normalized_benchmark.index, normalized_benchmark.values, 
                         label=f'Benchmark: {col}', alpha=0.6, linestyle='--')

    # 2. 绘制你的投资组合净值曲线 (加粗并前置 zorder)
    ax.plot(portfolio_res.index, portfolio_res.values, 
             label='My Portfolio', color='red', linewidth=2.5, zorder=5)

    # 格式化权重信息
    weights_str = "\n".join([f" - {name}: {w:.0%}" for name, w in zip(asset_names, weights)])
    # 3. 在图表上标注最大回撤、夏普比率等关键指标
    info_text = (f"Max Drawdown: {mdd_value:.2%}\n"
                 f"MDD Date: {mdd_date}\n"
                 f"Sharpe Ratio: {sharpe:.2f}\n"
                 f"Sortino Ratio: {sortino:.2f}\n"
                 f"Weights:\n{weights_str}")

    
    # 借助 bbox 绘制一个白色半透明的信息悬浮框，放置在左上角
    ax.text(0.02, 0.95, info_text, transform=ax.transAxes, fontsize=11,
                   verticalalignment='top', 
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='gray'))
    
    # 4. (可选) 在最大回撤日绘制特殊的标记点和箭头
    if mdd_date in portfolio_res.index:
        mdd_y = portfolio_res.loc[mdd_date]
        ax.scatter([mdd_date], [mdd_y], color='blue', s=60, zorder=6)
        ax.annotate('Max Drawdown', xy=(mdd_date, mdd_y), xytext=(15, -30),
                     textcoords='offset points', 
                     arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=.2", color='blue'))

    ax.set_title('Portfolio Performance vs Benchmarks')
    ax.set_xlabel('Date')
    ax.set_ylabel('Normalized Value (Base=1.0)')
    ax.legend(loc='upper right')
    ax.grid(True, linestyle=':', alpha=0.7)

    # 增加刻度线密度
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10, maxticks=25))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=15))

    # 设置 X轴 和 Y轴 刻度数字的字体大小
    ax.tick_params(axis='x', which='major', labelsize=8)
    ax.tick_params(axis='y', which='major', labelsize=8)

    fig.tight_layout()
    
    # 保存图像
    save_path = os.path.join(work_dir, "portfolio_performance.png")
    fig.savefig(save_path, dpi=100)
    plt.close(fig)
    
    return mdd_date

# ==========================================
# 可视化 - 成分股崩塌透视图
# ==========================================
def plot_component_trends(prices_df, mdd_date, save_dir):
    """
    绘制所有成分资产的归一化走势，并切入回撤基准线。
    """
    normalized_prices = prices_df / prices_df.iloc[0] * 100
    
    fig, ax = plt.subplots(figsize=(19.2, 10.8))
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

    # 增加刻度线密度：x轴(时间)使用 AutoDateLocator，y轴(数值)使用 MaxNLocator
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=10, maxticks=25))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=15))

    # 设置 X轴 和 Y轴 刻度数字的字体大小
    ax.tick_params(axis='x', which='major', labelsize=8)
    ax.tick_params(axis='y', which='major', labelsize=8)
    
    save_path = os.path.join(save_dir, 'component_trends.png')
    fig.tight_layout()
    fig.savefig(save_path, dpi=100)
    plt.close(fig)
    print(f"[+] 图 2 已保存至: {save_path}")
