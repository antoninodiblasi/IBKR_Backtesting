# engine/backtest.py
import datetime as dt
from datetime import time, date
import numpy as np
import pandas as pd

from IBKR_Backtesting.engine.execution import ExecutionHandler
from IBKR_Backtesting.engine.portfolio import Portfolio


class BacktestEngine:
    """
    Motore di backtesting multi-asset e multi-day.

    Differenze principali rispetto alla versione single-asset:
    - Accetta più simboli e più DataFrame (uno per simbolo).
    - Allinea le barre dei simboli per timestamp.
    - Passa alla strategia un dict {symbol: bar} ad ogni tick di tempo.
    - Equity e snapshot basati sui prezzi di tutti i simboli.
    """

    def __init__(
        self,
        strategy,
        data: dict[str, pd.DataFrame],   # dizionario {symbol: DataFrame OHLCV}
        symbols: list[str],              # lista di simboli gestiti
        initial_cash: float,
        slippage: float = 0.0,
        commission: float = 0.0,
        impact_lambda: float = 0.0,
        m2m_time: time = time(17, 15),        # orario mark-to-market intraday
        market_close_time: time = time(17, 30),  # orario di chiusura sessione
        flatten_at_close: bool = False,         # chiudi posizioni a fine giornata
    ):
        # --- Strategia e simboli
        self.strategy = strategy
        self.symbols = symbols
        self.initial_cash = float(initial_cash)

        # --- Dati di mercato
        # Ogni DataFrame deve avere almeno: timestamp, open, high, low, close
        self.data = data

        # --- Oggetti core (gestione ordini e portafoglio)
        self.portfolio = Portfolio(cash=self.initial_cash)
        self.execution = ExecutionHandler(
            self.portfolio, slippage=slippage, commission=commission, impact_lambda=impact_lambda
        )

        # --- Storage risultati
        self.filled_orders = []   # lista di ordini eseguiti
        self.equity_curve = []    # snapshots intraday
        self.daily_store = []     # mark-to-market e chiusure giornaliere

        # --- Config temporali
        self.m2m_time = m2m_time
        self.market_close_time = market_close_time
        self.flatten_at_close = bool(flatten_at_close)

        # --- Stato interno
        self._last_day: date | None = None
        self._m2m_done_for_day: set[date] = set()

    # -------------------------------------------------------------------------
    # METODI DI SUPPORTO
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_bar_price(bar) -> float:
        """
        Restituisce il prezzo da usare per snapshot equity.
        Ordine di preferenza: mid → close → open → high → low.
        """
        for field in ("mid", "close", "open", "high", "low"):
            val = getattr(bar, field, None)
            if val is not None and not pd.isna(val):
                return float(val)
        return 0.0

    def _snapshot(self, prices: dict[str, float], ts: dt.datetime) -> dict:
        """
        Registra snapshot dell'equity del portafoglio con i prezzi correnti
        di tutti i simboli. Ritorna lo snapshot.
        """
        snap = self.portfolio.snapshot(prices, ts)
        self.equity_curve.append(snap)
        return snap

    def _day_changed(self, current_ts: dt.datetime) -> bool:
        """
        True se il giorno è cambiato rispetto alla barra precedente.
        Utile per reset giornalieri di logica strategia.
        """
        cd = current_ts.date()
        changed = self._last_day is not None and cd != self._last_day
        self._last_day = cd
        return changed

    # -------------------------------------------------------------------------
    # LOOP PRINCIPALE
    # -------------------------------------------------------------------------
    def run(self):
        """
        Esegue il backtest scorrendo tutte le barre dei simboli:
        - unisce i dati in un unico DataFrame ordinato per timestamp
        - ad ogni timestamp passa alla strategia un dict {symbol: bar}
        - esegue gli ordini ritornati dalla strategia
        - aggiorna portafoglio e equity
        """
        if not self.data:
            return

        # --- Unisci i dati dei vari simboli in un unico DataFrame con colonna 'symbol'
        all_bars = []
        for sym, df in self.data.items():
            df = df.copy()
            df["symbol"] = sym
            all_bars.append(df)
        merged = pd.concat(all_bars).sort_values("timestamp")

        # --- Iterazione per timestamp
        for ts, group in merged.groupby("timestamp"):
            # group = tutte le barre disponibili a quel timestamp
            bars_dict = {row.symbol: row for row in group.itertuples(index=False, name="Bar")}

            # Cambio giorno → hook per eventuali reset
            if self._day_changed(ts):
                pass

            # --- Strategia genera ordini
            orders = self.strategy.on_bar(bars_dict) or []

            # --- Prezzi correnti (per equity snapshot)
            prices = {sym: self._get_bar_price(bar) for sym, bar in bars_dict.items()}

            # --- Esecuzione ordini
            for order in orders:
                bar_ref = bars_dict.get(order.symbol)
                if bar_ref is None:  # simbolo non disponibile a quel timestamp
                    continue
                filled, exec_price = self.execution.execute_order(order, bar_ref)
                if filled:
                    order.timestamp = ts
                    order.price = exec_price
                    self.filled_orders.append(order)

            # --- Snapshot equity corrente
            self._snapshot(prices, ts)

            # --- Mark-to-Market se orario ≥ m2m_time
            d = ts.date()
            if d not in self._m2m_done_for_day and ts.time() >= self.m2m_time:
                snap = self._snapshot(prices, ts)
                self.daily_store.append({
                    "date": d,
                    "timestamp": ts,
                    "equity_m2m": snap["equity"],
                    "note": "m2m"
                })
                self._m2m_done_for_day.add(d)

            # --- Fine giornata
            if ts.time() >= self.market_close_time:
                self.daily_store.append({
                    "date": d,
                    "timestamp": ts,
                    "equity_close": self.equity_curve[-1]["equity"],
                    "note": "close"
                })

    # -------------------------------------------------------------------------
    # REPORT
    # -------------------------------------------------------------------------
    def report(self):
        """
        Restituisce:
        - equity_df : DataFrame con equity riallineata
        - metrics   : dizionario con metriche base
        - filled_orders : lista di ordini eseguiti
        """
        try:
            eq = pd.DataFrame(self.equity_curve)
            if not eq.empty:
                eq["timestamp"] = pd.to_datetime(eq["timestamp"])
                eq = eq.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
            else:
                eq = pd.DataFrame(columns=["timestamp", "equity", "cash", "positions"])

            # timeline completa
            all_ts = []
            for df in self.data.values():
                if not df.empty:
                    all_ts.append(df["timestamp"])
            if all_ts:
                px_ts = pd.to_datetime(sorted(set(pd.concat(all_ts))))
            else:
                px_ts = pd.DatetimeIndex([])

            # seed se serve
            if not eq.empty and not px_ts.empty and eq["timestamp"].iloc[0] > px_ts[0]:
                seed_row = pd.DataFrame([{
                    "timestamp": px_ts[0],
                    "equity": float(self.portfolio.cash),
                    "cash": float(self.portfolio.cash),
                    "positions": dict(self.portfolio._positions),
                }])
                eq = pd.concat([seed_row, eq], ignore_index=True)

            # riallinea equity
            if not px_ts.empty:
                equity_df = (
                    eq.set_index("timestamp")
                    .reindex(px_ts)
                    .ffill()
                    .bfill()
                    .rename_axis("timestamp")
                    .reset_index()
                )
            else:
                equity_df = eq.copy()

            # metriche
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

            print("[DEBUG] Report generato con equity_df:", equity_df.shape,
                  "| metrics:", metrics,
                  "| orders:", len(self.filled_orders))

            return equity_df, metrics, self.filled_orders

        except Exception as e:
            print("[ERROR] in BacktestEngine.report():", e)
            return pd.DataFrame(), {}, []
