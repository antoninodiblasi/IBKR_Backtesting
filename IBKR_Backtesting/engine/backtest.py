# engine/backtest.py
import datetime as dt
from datetime import time, date
import pandas as pd

from IBKR_Backtesting.engine import order
from IBKR_Backtesting.engine.execution import ExecutionHandler
from IBKR_Backtesting.engine.portfolio import Portfolio
from IBKR_Backtesting.engine.order import Order
from IBKR_Backtesting.engine.bar import Bar


class BacktestEngine:
    """
    Motore di backtesting multiday.

    Funzionalità:
    - Itera sulle barre storiche (es. 1-min OHLCV + bid/ask se disponibile).
    - Richiama la strategia per generare ordini.
    - Simula l’esecuzione con ExecutionHandler.
    - Aggiorna portafoglio ed equity curve.
    - Registra snapshot giornalieri (Mark-to-Market alle 17:15).
    - Opzionale: forza chiusura posizioni a fine giornata.
    """

    def __init__(
        self,
        strategy,
        data: pd.DataFrame,
        symbol: str,
        initial_cash: float,
        slippage: float = 0.0,
        commission: float = 0.0,
        m2m_time: time = time(17, 15),
        market_close_time: time = time(17, 30),
        flatten_at_close: bool = False,
    ):
        """
        Parameters
        ----------
        strategy : object
            Strategia con metodo `on_bar(bar) -> list[Order]`.
        data : pd.DataFrame
            Dati storici con almeno:
            ['timestamp','open','high','low','close','volume'].
            Se presenti: ['bid','ask','mid'].
        symbol : str
            Ticker sottostante.
        initial_cash : float
            Capitale iniziale.
        slippage : float
            Slippage percentuale.
        commission : float
            Commissione fissa per trade.
        m2m_time : datetime.time
            Orario per il Mark-to-Market giornaliero.
        market_close_time : datetime.time
            Orario di chiusura mercato (default 17:30).
        flatten_at_close : bool
            Se True forza flat a fine giornata.
        """
        self.strategy = strategy
        self.data = data
        self.symbol = symbol
        self.initial_cash = float(initial_cash)

        # Oggetti interni
        self.portfolio = Portfolio(cash=self.initial_cash)
        self.execution = ExecutionHandler(self.portfolio, slippage, commission)

        # Storage
        self.filled_orders = []   # ordini eseguiti
        self.equity_curve = []    # equity intraday
        self.daily_store = []     # record giornalieri (M2M + chiusure)

        # Configurazioni giornaliere
        self.m2m_time = m2m_time
        self.market_close_time = market_close_time
        self.flatten_at_close = bool(flatten_at_close)

        # Stato interno
        self._last_day: date | None = None
        self._m2m_done_for_day: set[date] = set()

    # -------------------------------------------------------------------------
    # METODI INTERNI
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_bar_price(bar) -> float:
        """Determina prezzo di riferimento (mid se disponibile, altrimenti close)."""
        if hasattr(bar, "mid") and bar.mid is not None:
            return float(bar.mid)
        if hasattr(bar, "close") and bar.close is not None:
            return float(bar.close)
        return float("nan")

    def _snapshot(self, px: float, ts: dt.datetime) -> dict:
        """
        Registra snapshot equity e lo salva nell’equity_curve.

        Args:
            px (float): Prezzo di riferimento del simbolo.
            ts (datetime.datetime): Timestamp associato allo snapshot.

        Returns:
            dict: Snapshot dell'equity registrata.
        """
        snap = self.portfolio.snapshot_equity({self.symbol: px}, ts)
        self.equity_curve.append(snap)
        return snap

    def _ensure_m2m(self, bar):
        """Assicura Mark-to-Market alla prima barra >= m2m_time."""
        d = bar.timestamp.date()
        if d not in self._m2m_done_for_day and bar.timestamp.time() >= self.m2m_time:
            px = self._get_bar_price(bar)
            m2m_snap = self._snapshot(px, bar.timestamp)
            self.daily_store.append({
                "date": d,
                "timestamp": bar.timestamp,
                "equity_m2m": m2m_snap["equity"],
                "note": "m2m"
            })
            self._m2m_done_for_day.add(d)

    def _close_day(self, bar):
        """
        Chiusura di fine giornata:
        - Flat forzato se richiesto
        - M2M se non già fatto
        - Registra marker di chiusura
        """
        current_date = bar.timestamp.date()

        # Flat forzato
        if self.flatten_at_close:
            pos = self._get_position(self.symbol)
            if pos != 0:
                side = "SELL" if pos > 0 else "BUY"
                qty = abs(pos)
                close_order = Order(
                    self.symbol, side, qty,
                    float(self._get_bar_price(bar)),
                    bar.timestamp,
                    "MARKET"
                )
                filled, exec_price = self.execution.execute_order(order, bar)
                if filled:
                    close_order.timestamp = bar.timestamp
                    close_order.price = exec_price
                    self.filled_orders.append(close_order)
                    self._snapshot(self._get_bar_price(bar), bar.timestamp)

        # Se M2M non fatto prima, fallo ora
        if current_date not in self._m2m_done_for_day:
            px = self._get_bar_price(bar)
            m2m_snap = self._snapshot(px, bar.timestamp)
            self._m2m_done_for_day.add(current_date)
            self.daily_store.append({
                "date": current_date,
                "timestamp": bar.timestamp,
                "equity_m2m": m2m_snap["equity"],
                "note": "m2m_at_close"
            })

        # Marker di chiusura
        self.daily_store.append({
            "date": current_date,
            "timestamp": bar.timestamp,
            "equity_close": self.equity_curve[-1]["equity"],
            "note": "close"
        })

    def _day_changed(self, current_ts: dt.datetime) -> bool:
        """Rileva cambio giorno per gestire multiday."""
        cd = current_ts.date()
        changed = self._last_day is not None and cd != self._last_day
        self._last_day = cd
        return changed

    def _get_position(self, symbol: str) -> int:
        """Ritorna posizione corrente del portafoglio sul simbolo."""
        if hasattr(self.portfolio, "get_position"):
            return int(self.portfolio.get_position(symbol))
        if hasattr(self.portfolio, "positions"):
            return int(self.portfolio.positions.get(symbol, 0))
        return 0

    # -------------------------------------------------------------------------
    # API PRINCIPALI
    # -------------------------------------------------------------------------

    def run(self):
        """Esegue il backtest iterando sulle barre."""
        if len(self.data) == 0:
            return

        # Snapshot iniziale
        first = self.data.iloc[0]
        self._last_day = first.timestamp.date()
        self._snapshot(self._get_bar_price(first), first.timestamp)

        # Loop principale
        for bar in self.data.itertuples(index=False, name="Bar"):  # type: Bar
            ts = (
                bar.timestamp.to_pydatetime()
                if hasattr(bar.timestamp, "to_pydatetime")
                else bar.timestamp
            )

            if self._day_changed(ts):
                pass

            orders = self.strategy.on_bar(bar) or []
            for _order in orders:
                filled, exec_price = self.execution.execute_order(_order, bar)
                if filled:
                    _order.timestamp = ts
                    _order.price = exec_price
                    self.filled_orders.append(_order)

            self._snapshot(self._get_bar_price(bar), ts)
            self._ensure_m2m(bar)

            if ts.time() >= self.market_close_time:
                self._close_day(bar)

        # --- FIX: chiudi anche l’ultimo giorno ---
        last_bar = self.data.iloc[-1]
        self._close_day(last_bar)

    def report(self):
        import pandas as pd
        import numpy as np

        # -------------------------
        # 1. Equity intraday
        # -------------------------
        eq = pd.DataFrame(self.equity_curve)

        if not eq.empty:
            eq["timestamp"] = pd.to_datetime(eq["timestamp"])
            eq = eq.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
        else:
            eq = pd.DataFrame(columns=["timestamp", "equity", "cash", "positions"])

        # Allineo equity agli stessi timestamp delle barre
        px_ts = pd.to_datetime(self.data["timestamp"])
        equity_df = (
            eq.set_index("timestamp")
            .reindex(px_ts)
            .ffill()
            .rename_axis("timestamp")
            .reset_index()
        )

        # -------------------------
        # 2. Equity daily
        # -------------------------
        if not equity_df.empty:
            daily_df = (
                equity_df.set_index("timestamp")["equity"]
                .resample("1D").last()
                .dropna()
                .reset_index()
            )
        else:
            daily_df = pd.DataFrame(columns=["timestamp", "equity"])

        # -------------------------
        # 3. Metriche base
        # -------------------------
        if not equity_df.empty:
            start_eq = float(equity_df["equity"].iloc[0])
            end_eq = float(equity_df["equity"].iloc[-1])
            total_pnl = end_eq - start_eq
            ret_series = equity_df["equity"].pct_change().dropna()
            max_dd = float(((equity_df["equity"].cummax() - equity_df["equity"]) / equity_df["equity"].cummax()).max())
            sharpe = float(np.sqrt(252) * ret_series.mean() / (ret_series.std() + 1e-12))
        else:
            start_eq = end_eq = total_pnl = max_dd = sharpe = 0.0

        metrics = {
            "Start Equity": start_eq,
            "End Equity": end_eq,
            "Total PnL": total_pnl,
            "Max Drawdown": max_dd,
            "Sharpe Ratio": sharpe,
        }

        # -------------------------
        # 4. daily_store (se serve per salvataggi Excel o altre elaborazioni)
        # -------------------------
        daily_store = {
            "equity": daily_df,
            # puoi aggiungere altri breakdown giornalieri qui
        }

        # -------------------------
        # 5. Return coerente
        # -------------------------
        return equity_df, daily_df, metrics, self.filled_orders, daily_store
