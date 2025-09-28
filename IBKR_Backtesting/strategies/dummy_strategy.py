from __future__ import annotations

from typing import List, Optional
from IBKR_Backtesting.engine.strategy import Strategy
from IBKR_Backtesting.engine.order import Order
# opzionale: se hai definito Bar come NamedTuple tipizzato
# from IBKR_Backtesting.engine.bar import Bar


class SP500DummyStrategy(Strategy):
    """
    Strategia di esempio, minimale e didattica, pronta per ambienti multi-asset.

    Regole:
    1) Compra 1 unità alla prima barra di ogni giornata.
    2) Dalle 12:00 in poi, se il close < entry_price, chiude la posizione (SELL).
    3) Se non ha chiuso prima, chiude alla barra di chiusura di sessione.

    Nota: la strategia produce soltanto ordini. L’esecuzione e il mark-to-market
    sono responsabilità dell’ExecutionHandler e del Portfolio.
    """

    # ---------------------------------------------------------------------
    # Parametri di base e stato
    # ---------------------------------------------------------------------
    def __init__(self) -> None:
        # Parametri configurabili per il backtest runner
        self.symbol: str = "SPY"
        self.start_date: str = "2025-04-01"
        self.end_date: str = "2025-04-03"
        self.initial_cash: float = 100_000

        # Orario di chiusura sessione usato SOLO come condizione di uscita.
        # Formato (hour, minute). Modifica se il tuo dataset è in altro timezone.
        self.session_close_hhmm: tuple[int, int] = (17, 0)

        # Stato interno per la singola giornata
        self.entry_price: Optional[float] = None
        self.position_open: bool = False
        self.closed_today: bool = False
        self.current_day = None  # tipo: date

    # ---------------------------------------------------------------------
    # Config per il runner (stampabile / loggable)
    # ---------------------------------------------------------------------
    def get_config(self) -> dict:
        return {
            "symbol": self.symbol,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_cash": self.initial_cash,
            "exchange": getattr(self, "exchange", "SMART"),
            "currency": getattr(self, "currency", "USD"),
            "bar_size": getattr(self, "bar_size", "1 min"),
            "session_close_hhmm": self.session_close_hhmm,
        }

    # ---------------------------------------------------------------------
    # Core: logica per-bar
    # - Input: una singola barra (bar) con campi timestamp, open, close, ecc.
    # - Output: lista di Order (può essere vuota)
    # ---------------------------------------------------------------------
    def on_bar(self, bar) -> List[Order]:
        orders: List[Order] = []

        # 1) Gestione “inizio nuova giornata”: reset stato
        bar_day = bar.timestamp.date()
        if self.current_day != bar_day:
            self.current_day = bar_day
            self.entry_price = None
            self.position_open = False
            self.closed_today = False

        # 2) Prima barra del giorno → apri long
        if not self.position_open:
            self.entry_price = float(bar.open)
            orders.append(Order(
                symbol=self.symbol,
                side="BUY",
                qty=1,
                order_type="MARKET"  # l’ExecutionHandler gestisce il fill
            ))
            self.position_open = True
            # Nessun ritorno anticipato: lasciamo che valuti anche le altre regole,
            # ma con stato appena aggiornato non scatteranno in questa stessa barra.

        # 3) Dalle 12:00 in poi, chiudi se in perdita rispetto all’entry
        elif not self.closed_today and bar.timestamp.hour >= 12:
            if self.entry_price is not None and float(bar.close) < self.entry_price:
                orders.append(Order(
                    symbol=self.symbol,
                    side="SELL",
                    qty=1,
                    order_type="MARKET"
                ))
                self.closed_today = True
                self.position_open = False

        # 4) Se non hai chiuso prima, chiudi alla barra di fine sessione
        if not self.closed_today and self._is_session_close(bar):
            orders.append(Order(
                symbol=self.symbol,
                side="SELL",
                qty=1,
                order_type="MARKET"
            ))
            self.closed_today = True
            self.position_open = False

        return orders

    # ---------------------------------------------------------------------
    # Helper: riconoscere la barra di chiusura sessione
    # ---------------------------------------------------------------------
    def _is_session_close(self, bar) -> bool:
        hh, mm = self.session_close_hhmm
        # Confronto su hour/minute per evitare dipendenze dal numero di barre al giorno
        return (bar.timestamp.hour == hh) and (bar.timestamp.minute == mm)
