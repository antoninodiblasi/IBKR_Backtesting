from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order


class SP500DummyStrategy(Strategy):
    """
    Strategia di test sullo SP500:
    - Compra al primo bar di ogni giornata
    - Vende dopo le 12:00 se il prezzo è sotto l'entry
    - Altrimenti chiude sempre sull'ultimo minuto della giornata
    """

    def __init__(self):
        # Parametri configurabili
        self.symbol = "SPY"
        self.start_date = "2025-04-01"
        self.end_date = "2025-04-03"
        self.initial_cash = 100000

        # Stato interno
        self.entry_price = None
        self.position_open = False
        self.closed = False
        self.current_day = None

    def get_config(self):
        """Restituisce un dict con i parametri principali della strategia"""
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "exchange": getattr(self, "exchange", "SMART"),
            "currency": getattr(self, "currency", "USD"),
            "bar_size": getattr(self, "bar_size", "1 min"),
        }

    def on_bar(self, bar):
        """
        Logica della strategia giornaliera:
        - Ogni giorno al primo bar apre posizione BUY
        - Dopo le 12:00, se prezzo < entry, chiude SELL
        - Se non chiusa prima, chiude sull’ultimo minuto della giornata
        """
        orders = []
        bar_day = bar.timestamp.date()

        # Reset dello stato se inizia un nuovo giorno
        if self.current_day != bar_day:
            self.current_day = bar_day
            self.entry_price = None
            self.position_open = False
            self.closed = False

        # Prima barra del giorno → compra
        if not self.position_open:
            self.entry_price = bar.open
            orders.append(Order(side="BUY", qty=1, order_type="MARKET"))
            self.position_open = True

        # Dopo le 12:00 → vendi se in perdita
        elif not self.closed and bar.timestamp.hour >= 12:
            if bar.close < self.entry_price:
                orders.append(Order(side="SELL", qty=1, order_type="MARKET"))
                self.closed = True

        # Ultima barra della giornata → vendi se non già chiuso
        elif not self.closed and bar.timestamp.hour == 15 and bar.timestamp.minute == 59:
            orders.append(Order(side="SELL", qty=1, order_type="MARKET"))
            self.closed = True

        return orders
