from __future__ import annotations

from typing import List
from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order


class BuyHoldStrategy(Strategy):
    """
    Buy & Hold:
    - Compra N contratti al primo bar del periodo.
    - Tiene la posizione aperta.
    - Vende tutto all’ultimo bar del periodo.
    """

    def __init__(self, symbol: str = "RACE", start_date="2025-01-02", end_date="2025-01-03"):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = 100_000
        self.qty = 10  # numero contratti

        self.has_bought = False

    def get_config(self) -> dict:
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "exchange": getattr(self, "exchange", "SMART"),
            "currency": getattr(self, "currency", "USD"),
            "bar_size": getattr(self, "bar_size", "1 min"),
        }

    def on_bar(self, bar) -> List[Order]:
        orders: List[Order] = []

        # Primo bar → BUY qty
        if not self.has_bought and bar.timestamp.date().strftime("%Y-%m-%d") == self.start_date:
            if bar.timestamp.hour == 9 and bar.timestamp.minute == 30:
                orders.append(Order(
                    symbol=self.symbol,
                    side="BUY",
                    qty=self.qty,
                    order_type="MARKET"
                ))
                self.has_bought = True

        # Ultimo bar del periodo → SELL qty
        if (bar.timestamp.date().strftime("%Y-%m-%d") == self.end_date
            and bar.timestamp.hour == 17
            and bar.timestamp.minute == 0):
            orders.append(Order(
                symbol=self.symbol,
                side="SELL",
                qty=self.qty,
                order_type="MARKET"
            ))

        return orders
