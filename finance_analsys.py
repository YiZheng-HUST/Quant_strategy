import yfinance as yf
from currency_converter import CurrencyConverter


def get_exchange_rate(base_currency, target_currency="CNY"):
    if base_currency == target_currency:
        return 1.0
    ticker_symbol = f"{base_currency}{target_currency}=X"
    # 获取最新价格
    data = yf.Ticker(ticker_symbol).history(period="1d")
    return data['Close'].iloc[-1]


if __name__ == "__main__":
    # data = yf.download("511360.SS", start="2025-01-01")  # 下载短融ETF数据
    # data.to_csv("my_market_data.csv")
    # usd_to_cny = get_exchange_rate("USD")
    c = CurrencyConverter()
    amount_cny = c.convert(100, 'USD', 'CNY')
    print(f"当前 100 美元约等于 {100 * amount_cny:.2f} 人民币")
