
# 财务数据 → function → classification
def classify_pe(forward_pe):
    if forward_pe is None:
        return "unknown"

    if forward_pe <= 0:
        return "not meaningful"

    if forward_pe < 15:
        return "potentially attractive"

    if forward_pe < 25:
        return "reasonable"

    return "premium"