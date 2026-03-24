# ==========================================
# akshare
# ==========================================

# Define lists for Chinese ETFs
A_SHARE_ETFS = {
    "A_nasdaq_etf": {"symbol": "513300", "management_fee": 0.006, "trustee_fee": 0.002},  # 纳斯达克ETF
    "A_sp500_etf": {"symbol": "513500", "management_fee": 0.006, "trustee_fee": 0.002},  # 标普500ETF
    "A_red_low_volatility_50_etf": {"symbol": "515450", "management_fee": 0.005, "trustee_fee": 0.001},  # 红利低波50ETF
    "A_red_etf_huatai": {"symbol": "510880", "management_fee": 0.005, "trustee_fee": 0.001},  # 红利ETF华泰柏瑞
    "A_short_term_bond_etf": {"symbol": "511360", "management_fee": 0.0015, "trustee_fee": 0.0005},  # 短融ETF海富通
    "A_huaan_gold_etf": {"symbol": "518880", "management_fee": 0.005, "trustee_fee": 0.001},  # 华安黄金ETF
    "A_hushen_300_huatai_etf": {"symbol": "510300", "management_fee": 0.0015, "trustee_fee": 0.0005},  # 华泰柏瑞沪深300ETF
}

# Define lists for American ETFs in eastmoney
US_SHARE_ETFS_EASTMONEY = {
    "nasdaq": {"symbol": "105.QQQ", "total_fee": 0.002},
    "sp500": {"symbol": "106.SPY", "total_fee": 0.0009},
    "dow_jones": {"symbol": "106.DIA", "total_fee": 0},
    "gold": {"symbol": "106.GLD", "total_fee": 0.004},
    "short_term_treasury": {"symbol": "105.SHY", "total_fee": 0},
    "mid_term_treasury": {"symbol": "105.IEF", "total_fee": 0},
    "long_term_treasury": {"symbol": "105.TLT", "total_fee": 0.0015},
}

# Define lists for American ETFs in sina
US_SHARE_ETFS_SINA = {
    "nasdaq": {"symbol": "QQQ", "total_fee": 0.002},
    "sp500": {"symbol": "SPY", "total_fee": 0.0009},
    "dow_jones": {"symbol": "DIA", "total_fee": 0},
    "gold": {"symbol": "GLD", "total_fee": 0.004},
    "short_term_treasury": {"symbol": "SHY", "total_fee": 0},
    "mid_term_treasury": {"symbol": "IEF", "total_fee": 0},
    "long_term_treasury": {"symbol": "TLT", "total_fee": 0.0015},
}