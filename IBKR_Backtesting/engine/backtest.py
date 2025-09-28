# engine/backtest.py
import datetime as dt
from datetime import time, date
import numpy as np
import pandas as pd

from IBKR_Backtesting.engine.execution import ExecutionHandler
from IBKR_Backtesting.engine.portfolio import Portfolio
from IBKR_Backtesting.engine.order import Order


class BacktestEngine:
    """
    Motore di backtesting multi-day.

    Funzionalità principali:
    - Itera sulle barre storiche (es. 1-min OHLCV + bid/ask se disponibili).
    - Chiama la strategia per generare ordini.
    - Simula l'esecuzione con ExecutionHandler e aggiorna il Portfolio.
    - Tiene traccia di equity intraday (snap a ogni barra).
    - Registra M2M giornaliero (es. 17:15) e chiusura di giornata.
    - Supporta la chiusura forzata delle posizioni alla fine della sessione.
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
        # Componenti principali
        self.strategy = strategy
        self.data = data
        self.symbol = symbol
        self.initial_cash = float(initial_cash)

        # Oggetti core
        self.portfolio = Portfolio(cash=self.initial_cash)
        self.execution = ExecutionHandler(self.portfolio, slippage, commission)

        # Storage
        self.filled_orders = []   # ordini eseguiti
        self.equity_curve = []    # equity intraday (snapshots)
        self.daily_store = []     # record giornalieri (M2M e chiusure)

        # Config temporali
        self.m2m_time = m2m_time
        self.market_close_time = market_close_time
        self.flatten_at_close = bool(flatten_at_close)

        # Stato interno per gestione giornate
        self._last_day: date | None = None
        self._m2m_done_for_day: set[date] = set()

    # -------------------------------------------------------------------------
    # METODI INTERNI
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_bar_price(bar) -> float:
        """
        Determina il prezzo da usare per snapshot equity.
        Ordine preferenza: mid → close → open → high → low.
        Mai NaN: se non trova nulla, restituisce 0.0.
        """
        for field in ("mid", "close", "open", "high", "low"):
            val = getattr(bar, field, None)
            if val is not None and not pd.isna(val):
                return float(val)
        return 0.0

    def _snapshot(self, px: float, ts: dt.datetime) -> dict:
        """
        Registra snapshot equity e lo aggiunge all’equity_curve.
        """
        prices = {self.symbol: px}
        snap = self.portfolio.snapshot(prices, ts)
        self.equity_curve.append(snap)
        return snap

    def _ensure_m2m(self, bar):
        """
        Registra un Mark-to-Market alla prima barra >= m2m_time.
        """
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
        Operazioni di chiusura giornata:
        - Flat forzato se richiesto.
        - M2M se non già fatto.
        - Marker finale di chiusura.
        """
        current_date = bar.timestamp.date()

        # Flat forzato
        if self.flatten_at_close:
            pos = self._get_position(self.symbol)
            if pos != 0:
                side = "SELL" if pos > 0 else "BUY"
                qty = abs(pos)
                close_order = Order(
                    symbol=self.symbol,
                    side=side,
                    qty=qty,
                    price=self._get_bar_price(bar),
                    timestamp=bar.timestamp,
                    order_type="MARKET"
                )
                filled, exec_price = self.execution.execute_order(close_order, bar)
                if filled:
                    close_order.timestamp = bar.timestamp
                    close_order.price = exec_price
                    self.filled_orders.append(close_order)
                    self._snapshot(self._get_bar_price(bar), bar.timestamp)

        # M2M se non già registrato
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

        # Marker chiusura
        self.daily_store.append({
            "date": current_date,
            "timestamp": bar.timestamp,
            "equity_close": self.equity_curve[-1]["equity"],
            "note": "close"
        })

    def _day_changed(self, current_ts: dt.datetime) -> bool:
        """True se il giorno è cambiato rispetto alla barra precedente."""
        cd = current_ts.date()
        changed = self._last_day is not None and cd != self._last_day
        self._last_day = cd
        return changed

    def _get_position(self, symbol: str) -> int:
        """Posizione netta attuale del portafoglio su un simbolo."""
        if hasattr(self.portfolio, "get_position"):
            return int(self.portfolio.get_position(symbol))
        if hasattr(self.portfolio, "positions"):
            return int(self.portfolio.positions.get(symbol, 0))
        return 0

    # -------------------------------------------------------------------------
    # LOOP PRINCIPALE
    # -------------------------------------------------------------------------

    def run(self):
        """Esegue il backtest scorrendo tutte le barre del dataset."""
        if len(self.data) == 0:
            return

        # Snapshot iniziale: solo cash
        first_ts = pd.to_datetime(self.data["timestamp"].iloc[0])
        first_px = float(self.data["close"].iloc[0])
        seed = self.portfolio.snapshot({self.symbol: first_px}, first_ts)
        self.equity_curve.append(seed)

        # Loop sulle barre
        for bar in self.data.itertuples(index=False, name="Bar"):
            ts = (
                bar.timestamp.to_pydatetime()
                if hasattr(bar.timestamp, "to_pydatetime")
                else bar.timestamp
            )


            # Cambio giorno
            if self._day_changed(ts):
                pass  # potresti resettare logica strategia

            # Strategia → genera ordini
            orders = self.strategy.on_bar(bar) or []
            for _order in orders:
                filled, exec_price = self.execution.execute_order(_order, bar)
                if filled:
                    _order.timestamp = ts
                    _order.price = exec_price
                    self.filled_orders.append(_order)

            # Snapshot equity continuo
            px_now = self._get_bar_price(bar)
            self._snapshot(px_now, ts)

            # Mark-to-Market se necessario
            self._ensure_m2m(bar)

            # Fine giornata
            if ts.time() >= self.market_close_time:
                self._close_day(bar)

        # Chiudi ultimo giorno
        last_bar = self.data.iloc[-1]
        self._close_day(last_bar)

    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------

    def report(self):
        """
        Restituisce:
        - equity_df (DataFrame con equity intraday riallineata)
        - metrics (dict con metriche base)
        - filled_orders (lista di ordini eseguiti)
        """
        # Equity intraday
        eq = pd.DataFrame(self.equity_curve)
        if not eq.empty:
            eq["timestamp"] = pd.to_datetime(eq["timestamp"])
            eq = eq.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
        else:
            eq = pd.DataFrame(columns=["timestamp", "equity", "cash", "positions"])

        # Timeline dei prezzi
        px_ts = pd.to_datetime(self.data["timestamp"])

        # Se equity parte dopo le barre → aggiungi seme
        if not eq.empty and eq["timestamp"].iloc[0] > px_ts.iloc[0]:
            seed_row = pd.DataFrame([{
                "timestamp": px_ts.iloc[0],
                "equity": float(self.portfolio.cash),
                "cash": float(self.portfolio.cash),
                "positions": dict(self.portfolio._positions),
            }])
            eq = pd.concat([seed_row, eq], ignore_index=True)

        # Equity riallineata a ogni barra
        equity_df = (
            eq.set_index("timestamp")
            .reindex(px_ts)
            .ffill()
            .bfill()
            .rename_axis("timestamp")
            .reset_index()
        )

        # Metriche base
        if not equity_df.empty:
            start_eq = float(equity_df["equity"].iloc[0])
            end_eq = float(equity_df["equity"].iloc[-1])
            total_pnl = end_eq - start_eq
            ret_series = equity_df["equity"].pct_change().dropna()
            max_dd = float(((equity_df["equity"].cummax() - equity_df["equity"]) /
                            equity_df["equity"].cummax()).max())
            sharpe = float(np.sqrt(252) * ret_series.mean() /
                           (ret_series.std() + 1e-12))
        else:
            start_eq = end_eq = total_pnl = max_dd = sharpe = 0.0

        metrics = {
            "Start Equity": start_eq,
            "End Equity": end_eq,
            "Total PnL": total_pnl,
            "Max Drawdown": max_dd,
            "Sharpe Ratio": sharpe,
        }

        return equity_df, metrics, self.filled_orders
