from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order

class SP500DummyStrategy(Strategy):
    def __init__(self):
        # Parametri configurabili della strategia
        self.symbol = "SPY"
        self.start_date = "2025-03-26"
        self.end_date = "2025-03-26"
        self.initial_cash = 100000

        # Stato interno
        self.entry_price = None
        self.position_open = False
        self.closed = False

    def get_config(self):
        """Restituisce un dict con i parametri principali della strategia"""
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash
        }

    def on_bar(self, bar):
        """
        Logica della strategia:
        - Compra al primo bar della giornata
        - Dopo le 12:00, se il prezzo è sotto l'entry, vende
        - Altrimenti chiude alla fine della giornata
        """
        orders = []

        if not self.position_open:
            self.entry_price = bar.open
            orders.append(Order(side="BUY", qty=1, order_type="MARKET"))
            self.position_open = True

        elif not self.closed and bar.timestamp.hour >= 12:
            if bar.close < self.entry_price:
                orders.append(Order(side="SELL", qty=1, order_type="MARKET"))
                self.closed = True

        elif not self.closed and bar.timestamp.hour == 15 and bar.timestamp.minute == 59:
            orders.append(Order(side="SELL", qty=1, order_type="MARKET"))
            self.closed = True

        return orders
