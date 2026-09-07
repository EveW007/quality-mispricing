import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from universe import parse_sp500_symbols


def test_parse_sp500_symbols_normalizes_dot_tickers():
    rows = "".join(f"<tr><td>T{i}</td></tr>" for i in range(449))
    html = (
        '<table id="constituents"><tr><th>Symbol</th></tr>'
        '<tr><td>BRK.B</td></tr>' + rows + "</table>"
    )
    symbols = parse_sp500_symbols(html)
    assert symbols[0] == "BRK-B"
    assert len(symbols) == 450
