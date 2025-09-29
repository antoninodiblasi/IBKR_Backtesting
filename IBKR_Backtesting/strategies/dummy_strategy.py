# strategies/long_ucg_hold.py
from __future__ import annotations

from typing import List
import pandas as pd
from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order


class LongUcgHold(Strategy):
    """
    Strategia Buy&Hold su singolo titolo UCG:
    - Compra al prezzo di apertura del primo giorno.
    - Vende al prezzo di chiusura dell’ultimo giorno.
    Funziona sia con dati daily che intraday.
    """

    def __init__(self,
        start_date: str = "2024-12-01",
        end_date: str = "2025-01-01",
        initial_cash: float = 100_000,
        exchange: str = "SMART",
        currency: str = "EUR",
        bar_size: str = "1 day",
        qty: int = 100,
        slippage: float = 0.0,
        commission: float = 0.0,
        use_rth: bool = True,
        what_to_show: str = "TRADES",
        plot: bool = True,
        plot_orders: bool = True,
    ):
        self.symbols = ["UCG"]
        self.start_date = pd.to_datetime(start_date).date()
        self.end_date = pd.to_datetime(end_date).date()
        self.initial_cash = float(initial_cash)
        self.exchange = exchange
        self.currency = currency
        self.bar_size = bar_size

        self.qty = int(qty)
        self.slippage = float(slippage)
        self.commission = float(commission)
        self.use_rth = use_rth
        self.what_to_show = what_to_show
        self.plot = plot
        self.plot_orders = plot_orders

        # Stato interno
        self.has_opened: bool = False
        self.has_closed: bool = False

    def get_config(self) -> dict:
        return {
            "symbols": self.symbols,
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "initial_cash": self.initial_cash,
            "exchange": self.exchange,
            "currency": self.currency,
            "bar_size": self.bar_size,
            "slippage": self.slippage,
            "commission": self.commission,
            "use_rth": self.use_rth,
            "what_to_show": self.what_to_show,
            "plot": self.plot,
            "plot_orders": self.plot_orders,
        }

    def on_bar(self, bars: dict) -> List[Order]:
        orders: List[Order] = []
        ucg_bar = bars.get("UCG")
        if ucg_bar is None:
            return orders

        bar_date = ucg_bar.timestamp.date()
        is_daily = ucg_bar.timestamp.hour == 0 and ucg_bar.timestamp.minute == 0

        # Apertura
        if (not self.has_opened) and (bar_date == self.start_date):
            print(f"[DEBUG] Sending BUY order on {ucg_bar.timestamp} @ {ucg_bar.open}")
            orders.append(Order(symbol="UCG", side="BUY", qty=self.qty, price=ucg_bar.open))
            self.has_opened = True

        # Chiusura
        if (not self.has_closed) and (bar_date == self.end_date):
            if (is_daily) or (ucg_bar.timestamp.hour == 17 and ucg_bar.timestamp.minute == 0):
                orders.append(Order(
                    symbol="UCG", side="SELL", qty=self.qty, price=ucg_bar.close
                ))
                self.has_closed = True

        return orders
