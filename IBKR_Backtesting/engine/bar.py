# engine/bar.py
from typing import NamedTuple
import datetime as dt

class Bar(NamedTuple):
    """
    Rappresenta una singola barra di mercato.
    Usata come output di DataFrame.itertuples() per tipizzazione forte.
    """
    symbol: str
    timestamp: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    mid: float | None = None  # opzionale, default None
