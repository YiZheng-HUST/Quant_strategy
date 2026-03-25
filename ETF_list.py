# ==========================================
# akshare
# ==========================================

# Define lists for Chinese ETFs
A_SHARE_ETFS = {
    # 10年以上ETF
    "sse_50_huaxia_etf": {"symbol": "510050", "management_fee": 0.0015, "trustee_fee": 0.0005},  # 上证50ETF华夏，2004-12-30
    "csi_300_huatai_etf": {"symbol": "510300", "management_fee": 0.0015, "trustee_fee": 0.0005},  # 沪深300ETF华泰柏瑞，2012-05-04
    "red_huatai_etf": {"symbol": "510880", "management_fee": 0.005, "trustee_fee": 0.001},  # 红利ETF华泰柏瑞，2006-11-17
    "gold_huaan_etf": {"symbol": "518880", "management_fee": 0.005, "trustee_fee": 0.001},  # 黄金ETF华安，2013-07-18
    "sp500_boshi_etf": {"symbol": "513500", "management_fee": 0.006, "trustee_fee": 0.002},  # 标普500ETF博时，2013-12-05
    "hang_seng_huaxia_etf": {"symbol": "159920", "management_fee": 0.006, "trustee_fee": 0.0015},  # 恒生ETF华夏，2012-08-09
    "nasdaq_guangfa_etf": {"symbol": "159941", "management_fee": 0.008, "trustee_fee": 0.002},  # 纳斯达克ETF广发，2015-05-20

    # 5年以上ETF
    "nasdaq_huaxia_etf": {"symbol": "513300", "management_fee": 0.006, "trustee_fee": 0.002},  # 纳斯达克ETF华夏，2020-10-22
    "red_low_volatility_50_nanfang_etf": {"symbol": "515450", "management_fee": 0.005, "trustee_fee": 0.001},  # 红利低波50ETF南方，2020-01-17
    "short_term_bond_haifutong_etf": {"symbol": "511360", "management_fee": 0.0015, "trustee_fee": 0.0005},  # 短融ETF海富通，2020-08-03
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