fundamentals = {
    "MSFT": "stable",
    "QCOM": "stable",
    "ADBE": "stable",
}


manual_valuation_status = {
    "MSFT": "fair",
    "QCOM": "attractive",
    "ADBE": "attractive",
}


historical_medians = {
    "MSFT": 32,
    "QCOM": 18,
    "ADBE": 28,
}


reference_prices = {
    "MSFT": 550,
    "QCOM": 175,
    "ADBE": 280,
}


price_changes = {
    "MSFT": 0.12,
    "QCOM": 0.09,
    "ADBE": -0.05,
}


intrinsic_value_changes = {
    "MSFT": 0.10,
    "QCOM": 0.08,
    "ADBE": 0.02,
}


total_account_value = 50000

# 测试data for quality - mock data
quality_inputs = {
    "MSFT": {
        "revenue_growth": 0.12,
        "eps_growth": 0.15,
        "fcf_margin": 0.30,
        "debt_to_equity": 0.40,
    },

    "QCOM": {
        "revenue_growth": 0.10,
        "eps_growth": 0.12,
        "fcf_margin": 0.22,
        "debt_to_equity": 0.75,
    },

    "ADBE": {
        "revenue_growth": 0.11,
        "eps_growth": 0.13,
        "fcf_margin": 0.35,
        "debt_to_equity": 0.55,
    },
}