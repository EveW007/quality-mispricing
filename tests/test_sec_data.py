import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from sec_data import normalized_sec_fundamentals


def _fact(value, end, concept_unit="USD"):
    return {"val": value, "end": end, "filed": "2026-02-01", "form": "10-K", "fp": "FY"}


def test_normalized_sec_fundamentals_builds_annual_fcf():
    payload = {
        "entityName": "Test Corp",
        "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [_fact(1000, "2025-12-31")]}},
                "NetIncomeLoss": {"units": {"USD": [_fact(100, "2025-12-31")]}},
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": [_fact(180, "2025-12-31")]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [_fact(30, "2025-12-31")]}
                },
            }
        },
    }
    result = normalized_sec_fundamentals("TEST", "0000000001", payload)
    assert result["annual"][-1]["free_cash_flow"] == 150
    assert result["source_tier"] == "primary"
