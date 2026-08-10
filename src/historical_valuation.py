def compare_to_historical_pe(
    current_pe,
    historical_median_pe,
):
    if current_pe is None:
        return "unknown"

    if historical_median_pe is None:
        return "unknown"

    discount = current_pe / historical_median_pe - 1

    if discount <= -0.30:
        return "deep discount"

    if discount <= -0.15:
        return "discount"

    if discount <= 0.15:
        return "normal"

    if discount <= 0.30:
        return "premium"

    return "high premium"

historical_medians = {
    "MSFT": 32,
    "QCOM": 18,
    "ADBE": 28,
}

def calculate_pe_discount(
    current_pe,
    historical_median_pe,
):
    if current_pe is None:
        return None

    if historical_median_pe is None:
        return None

    return current_pe / historical_median_pe - 1