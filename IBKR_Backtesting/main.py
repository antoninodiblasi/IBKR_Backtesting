# main.py
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
import pandas as pd

from IBKR_Backtesting.strategies.dummy_strategy import LongUcgHold
import IBKR_Backtesting.engine.backtest as bt
print("BacktestEngine loaded from:", bt.__file__)
print("BacktestEngine class:", bt.BacktestEngine)

from IBKR_Backtesting.utils.plotting import plot_backtest
from IBKR_Backtesting.utils.ibkr_client import IBKRClient
from IBKR_Backtesting.utils.data_handler import prepare_dataframe, merge_bidask_to_bars


# =============================================================================
# Utility di stampa
# =============================================================================
def _hr(title: str | None = None) -> None:
    """Stampa una linea di separazione con titolo opzionale."""
    line = "=" * 70
    print(f"\n{line}\n{title}\n{line}" if title else f"\n{line}")


def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def _require_non_empty(df: pd.DataFrame, what: str) -> None:
    """Verifica che un DataFrame non sia vuoto."""
    if df.empty:
        _fail(f"{what} vuoto: interrompo.")


# =============================================================================
# Download OHLCV da IBKR
# =============================================================================
def fetch_bars(client: IBKRClient, cfg: dict) -> dict[str, pd.DataFrame]:
    """
    Scarica barre OHLCV da IBKR per tutti i simboli.
    Ritorna un dict {symbol: DataFrame}.
    """
    start_dt = pd.to_datetime(cfg["start_date"])
    end_dt = pd.to_datetime(cfg["end_date"])
    days = (end_dt - start_dt).days + 1
    duration_str = f"{days} D"
    end_datetime = (end_dt + pd.Timedelta(days=1)).strftime("%Y%m%d %H:%M:%S")

    all_bars: dict[str, pd.DataFrame] = {}
    for sym in cfg["symbols"]:
        _info(f"Scarico barre OHLCV per {sym}...")
        raw_df = client.get_historical_data(
            symbol=sym,
            exchange=cfg["exchange"],
            currency=cfg["currency"],
            end_datetime=end_datetime,
            duration=duration_str,
            bar_size=cfg["bar_size"],
            what_to_show=cfg.get("what_to_show", "TRADES"),
            use_rth=cfg.get("use_rth", True),
        )

        bars = prepare_dataframe(raw_df)
        _require_non_empty(bars, f"Barre OHLCV {sym}")

        # Taglio dati extra che IBKR potrebbe restituire
        bars = bars[(bars["timestamp"] >= start_dt) & (bars["timestamp"] <= end_dt)].copy()
        all_bars[sym] = bars

        _hr(f"Preview OHLCV {sym}")
        print(f"Range effettivo: {bars['timestamp'].min()} → {bars['timestamp'].max()}")
        print(bars.head())
        print(bars.tail())

    return all_bars


# =============================================================================
# Download tick BID/ASK e merge
# =============================================================================
def fetch_and_merge_ticks(
    client: IBKRClient, cfg: dict, bars: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """
    Scarica tick BID/ASK per tutti i simboli e li unisce alle barre OHLCV.
    Se non disponibili, ritorna solo le barre.
    """
    all_data: dict[str, pd.DataFrame] = {}
    for sym, df in bars.items():
        _info(f"Scarico tick BID/ASK per {sym}...")
        ticks = client.get_historical_bidask_ticks(
            symbol=sym,
            exchange=cfg["exchange"],
            currency=cfg["currency"],
            start_dt=pd.to_datetime(cfg["start_date"]).strftime("%Y%m%d %H:%M:%S"),
            end_dt=pd.to_datetime(cfg["end_date"]).strftime("%Y%m%d %H:%M:%S"),
            use_rth=cfg.get("use_rth", True),
            batch_size=cfg.get("batch_size", 1000),
        )

        if ticks.empty:
            _warn(f"Nessun tick per {sym}. Uso solo OHLCV.")
            all_data[sym] = df
            continue

        # Salvo i tick scaricati (utile per debug/offline)
        out_file = Path(f"book_{sym}_{cfg['start_date']}_{cfg['end_date']}.csv")
        ticks.to_csv(out_file, index=False)
        _info(f"Salvati {len(ticks)} tick per {sym} in {out_file.name}")

        merged = merge_bidask_to_bars(
            bars_df=df,
            ticks_df=ticks,
            on_col=cfg.get("merge_on", "timestamp"),
            direction=cfg.get("merge_direction", "backward"),
            tolerance=cfg.get("merge_tolerance", "5min"),
        )
        _require_non_empty(merged, f"Dataset unito {sym}")
        all_data[sym] = merged

    return all_data


# =============================================================================
# Backtest runner
# =============================================================================
# =============================================================================
# Backtest runner
# =============================================================================
def run_backtest(strategy, data: dict[str, pd.DataFrame], cfg: dict):
    engine = bt.BacktestEngine(
        strategy=strategy,
        data=data,
        symbols=cfg["symbols"],
        initial_cash=cfg["initial_cash"],
        slippage=cfg.get("slippage", 0.0),
        commission=cfg.get("commission", 0.0),
        impact_lambda=cfg.get("impact_lambda", 0.0),
        m2m_time=cfg.get("m2m_time", pd.to_datetime("17:15").time()),
        market_close_time=cfg.get("market_close_time", pd.to_datetime("17:30").time()),
        flatten_at_close=cfg.get("flatten_at_close", False),
    )

    _info("Avvio backtest...")
    t0 = perf_counter()
    engine.run()
    _info(f"Backtest completato in {perf_counter() - t0:.2f}s")

    res = engine.report()                     # <-- non deve essere None
    if not isinstance(res, tuple) or len(res) != 3:
        raise RuntimeError(
            f"BacktestEngine.report() ha restituito {type(res)}; atteso 3-tuple"
        )

    equity_df, metrics, orders = res
    return equity_df, metrics, orders         # <-- ritorno esplicito

# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    # 1) Strategia e configurazione
    strategy = LongUcgHold()
    cfg = strategy.get_config()

    _hr("Backtest configuration")
    print(f"Strategy     : {strategy.__class__.__name__}")
    print(f"Symbols      : {', '.join(cfg['symbols'])}")
    print(f"Date range   : {cfg['start_date']} → {cfg['end_date']}")
    print(f"Initial cash : {cfg['initial_cash']}")
    print(f"Exchange     : {cfg['exchange']}")
    print(f"Currency     : {cfg['currency']}")
    print(f"Bar size     : {cfg['bar_size']}")

    # 2) Connessione IBKR
    client = IBKRClient(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 7497),
        client_id=cfg.get("client_id", 1),
    )

    # 3) Download dati
    bars = fetch_bars(client, cfg)
    data = fetch_and_merge_ticks(client, cfg, bars)

    # 4) Backtest
    equity_df, metrics, orders = run_backtest(strategy, data, cfg)

    # 5) Metriche di performance
    _hr("Performance metrics")
    for k, v in metrics.items():
        print(f"{k:<22}: {v:.2f}")

    # 6) Plot (solo primo simbolo per semplicità)
    if cfg.get("plot", True):
        sym0 = cfg["symbols"][0]
        _hr(f"Plot ({sym0} + equity curve)")
        plot_backtest(
            price_df=data[sym0],
            equity_df=equity_df,
            orders=orders,
            start_date=cfg["start_date"],
            end_date=cfg["end_date"],
            trading_start=cfg.get("trading_start", 9),
            trading_end=cfg.get("trading_end", 17),
            plot_orders=cfg.get("plot_orders", True),
        )
