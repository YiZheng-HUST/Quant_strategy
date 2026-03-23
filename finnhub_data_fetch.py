import finnhub

# 1. 使用您的个人 API Key 初始化客户端
# (您需要在 Finnhub 官网免费注册一个账号来获取这个 Token)
finnhub_client = finnhub.Client(api_key="d709bo9r01qtb4r9v4m0d709bo9r01qtb4r9v4mg")

# 2. 获取标普 500 ETF (SPY) 的当前实时报价
print("获取 SPY 实时报价...")
quote = finnhub_client.quote('SPY')
print(f"当前价格: {quote['c']}")
print(f"今日最高: {quote['h']}, 今日最低: {quote['l']}")

# 3. 获取 QQQ 的基础档案信息
print("\n获取 QQQ 基本信息...")
profile = finnhub_client.company_profile2(symbol='QQQ')
print(f"名称: {profile.get('name')}")
print(f"上市交易所: {profile.get('exchange')}")