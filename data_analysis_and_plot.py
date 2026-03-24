import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from currency_converter import CurrencyConverter
import os


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
