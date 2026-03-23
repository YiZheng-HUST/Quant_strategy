import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from curl_cffi import requests

# ================= Configuration =================
# ^IXIC: Nasdaq Composite Index
# ^GSPC: S&P 500 Index
TICKERS = ['^QQQ', '^SPY']
PERIOD = "1y"  # Fetch data for the past 1 year
# ===============================================

def fetch_and_plot_indices():
    print(f"Fetching data for {TICKERS} over the past {PERIOD}...")

    session = requests.Session(impersonate="edge99")
    ticker = yf.Ticker('SPY', session=session)

    print(ticker.history(period="1y"))
    exit(0)
    
    # yf.download can fetch multiple tickers at once
    # group_by='ticker' is optional but helps organize columns if you need more than just 'Close'
    # data = yf.download(TICKERS, period=PERIOD)
    print(data)
    
    # We use 'Close' (or 'Adj Close') for the price trend
    # If the returned data has a MultiIndex column structure, extract the 'Close' prices
    if isinstance(data.columns, pd.MultiIndex):
        df_close = data['Close']
    else:
        df_close = data
        
    # Drop any potential missing values (e.g., non-trading days)
    df_close = df_close.dropna()
    
    print("Normalizing data...")
    # Normalize: Divide all rows by the first row's values to set the starting point to 1.0
    df_norm = df_close / df_close.iloc[0]
    
    print("Generating chart...")
    plt.figure(figsize=(12, 6))
    
    # Plot Nasdaq
    plt.plot(df_norm.index, df_norm['^IXIC'], label='Nasdaq (^IXIC)', color='blue', linewidth=2)
    # Plot S&P 500
    plt.plot(df_norm.index, df_norm['^GSPC'], label='S&P 500 (^GSPC)', color='red', linewidth=2)
    
    # Chart styling
    plt.title('Normalized Performance: Nasdaq vs S&P 500 (1-Year Trend)', fontsize=14)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Cumulative Growth (Base=1.0)', fontsize=12)
    
    # Add a horizontal line at 1.0 to easily see the breakeven point
    plt.axhline(y=1.0, color='black', linestyle='--', alpha=0.5)
    
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    fetch_and_plot_indices()