# strategies/buy_hold_strategy.py
from __future__ import annotations

from typing import List
import pandas as pd
from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order


class BuyHoldStrategy(Strategy):
    """
    Strategia Buy & Hold minimale.

    Logica:
    - Compra N contratti al primo bar valido del periodo.
    - Mantiene la posizione.
    - Vende tutto all’ultimo bar del periodo.
    """

    def __init__(
        self,
        symbol: str = "SPY",
        start_date: str = "2024-12-01",
        end_date: str = "2025-01-01",
        qty: int = 10,
        initial_cash: float = 100_000,
    ):
        self.symbol = symbol
        self.start_date = pd.to_datetime(start_date).date()
        self.end_date = pd.to_datetime(end_date).date()
        self.initial_cash = float(initial_cash)
        self.qty = int(qty)

        # Stato
        self.has_bought: bool = False
        self.has_sold: bool = False

    # ------------------------------------------------------------------
    # Config per il runner (usata in main.py)
    # ------------------------------------------------------------------
    def get_config(self) -> dict:
        return {
            "symbol": self.symbol,
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "initial_cash": self.initial_cash,
            "exchange": getattr(self, "exchange", "SMART"),
            "currency": getattr(self, "currency", "USD"),
            "bar_size": getattr(self, "bar_size", "1 min"),
        }

    # ------------------------------------------------------------------
    # Logica a ogni barra
    # ------------------------------------------------------------------
    def on_bar(self, bar) -> List[Order]:
        orders: List[Order] = []
        bar_date = bar.timestamp.date()

        # Primo bar del periodo → BUY qty
        if (not self.has_bought) and (bar_date == self.start_date):
            if bar.timestamp.hour == 9 and bar.timestamp.minute == 30:
                orders.append(Order(
                    symbol=self.symbol,
                    side="BUY",
                    qty=self.qty,
                    order_type="MARKET"
                ))
                self.has_bought = True

        # Ultimo bar del periodo → SELL qty
        if (not self.has_sold) and (bar_date == self.end_date):
            # Chiudiamo all’ultimo minuto utile (17:00)
            if bar.timestamp.hour == 17 and bar.timestamp.minute == 0:
                orders.append(Order(
                    symbol=self.symbol,
                    side="SELL",
                    qty=self.qty,
                    order_type="MARKET"
                ))
                self.has_sold = True

        return orders
