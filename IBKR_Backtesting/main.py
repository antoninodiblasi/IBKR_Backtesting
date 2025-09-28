# main.py
from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
import pandas as pd

from IBKR_Backtesting.strategies.dummy_strategy import BuyHoldStrategy
from IBKR_Backtesting.engine.backtest import BacktestEngine
from IBKR_Backtesting.utils.plotting import plot_backtest
from IBKR_Backtesting.utils.ibkr_client import IBKRClient
from IBKR_Backtesting.utils.data_handler import prepare_dataframe, merge_bidask_to_bars


# =============================================================================
# Utility di stampa
# =============================================================================
def _hr(title: str | None = None) -> None:
    """Stampa una riga di separazione con titolo opzionale."""
    line = "=" * 70
    if title:
        print(f"\n{line}\n{title}\n{line}")
    else:
        print(f"\n{line}")


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
def fetch_bars(client: IBKRClient, cfg: dict) -> pd.DataFrame:
    """
    Scarica barre OHLCV da IBKR e le filtra al range richiesto.
    """
    start_dt = pd.to_datetime(cfg["start_date"])
    end_dt = pd.to_datetime(cfg["end_date"])
    days = (end_dt - start_dt).days + 1
    duration_str = f"{days} D"
    end_datetime = (end_dt + pd.Timedelta(days=1)).strftime("%Y%m%d %H:%M:%S")

    _info("Scarico barre OHLCV...")
    raw_df = client.get_historical_data(
        symbol=cfg["symbol"],
        exchange=cfg["exchange"],
        currency=cfg["currency"],
        end_datetime=end_datetime,
        duration=duration_str,
        bar_size=cfg["bar_size"],
    )

    bars = prepare_dataframe(raw_df)
    _require_non_empty(bars, "Barre OHLCV")

    # Filtro dati al range richiesto (difesa contro IBKR che può dare extra giorni)
    bars = bars[(bars["timestamp"] >= start_dt) & (bars["timestamp"] <= end_dt)].copy()

    _hr("Preview OHLCV")
    print(f"Range effettivo: {bars['timestamp'].min()} → {bars['timestamp'].max()}")
    print(bars.head())
    print(bars.tail())

    return bars


# =============================================================================
# Download tick BID/ASK e merge con barre
# =============================================================================
def fetch_and_merge_ticks(client: IBKRClient, cfg: dict, bars: pd.DataFrame) -> pd.DataFrame:
    """
    Scarica i tick BID/ASK e li unisce alle barre OHLCV.
    Se non ci sono tick, ritorna solo le barre.
    """
    _info("Scarico tick BID/ASK da IBKR...")
    ticks = client.get_historical_bidask_ticks(
        symbol=cfg["symbol"],
        exchange=cfg["exchange"],
        currency=cfg["currency"],
        start_dt=pd.to_datetime(cfg["start_date"]).strftime("%Y%m%d %H:%M:%S"),
        end_dt=pd.to_datetime(cfg["end_date"]).strftime("%Y%m%d %H:%M:%S"),
        batch_size=1000,
    )

    if ticks.empty:
        _warn("Nessun tick BID/ASK scaricato. Uso solo OHLCV.")
        return bars

    # Salvataggio tick scaricati (utile per debug o analisi offline)
    out_file = Path(f"book_{cfg['symbol']}_{cfg['start_date']}_{cfg['end_date']}.csv")
    ticks.to_csv(out_file, index=False)
    _info(f"Salvati {len(ticks)} tick BID/ASK in {out_file.name}")

    # Merge OHLCV + tick
    data = merge_bidask_to_bars(bars, ticks, on_col="timestamp")
    _require_non_empty(data, "Dataset unito OHLCV+BID/ASK")

    # Filtro anche qui (difesa ridondante)
    start_dt = pd.to_datetime(cfg["start_date"])
    end_dt = pd.to_datetime(cfg["end_date"])
    data = data[(data["timestamp"] >= start_dt) & (data["timestamp"] <= end_dt)].copy()

    return data


# =============================================================================
# Backtest runner
# =============================================================================
def run_backtest(strategy: BuyHoldStrategy, data: pd.DataFrame, cfg: dict):
    """
    Crea ed esegue un backtest, restituisce equity_df, metrics, orders.
    """
    engine = BacktestEngine(
        strategy=strategy,
        data=data,
        symbol=cfg["symbol"],
        initial_cash=cfg["initial_cash"],
    )

    _info("Avvio backtest...")
    t0 = perf_counter()
    engine.run()
    dt_run = perf_counter() - t0
    _info(f"Backtest completato in {dt_run:.2f}s")

    equity_df, metrics, orders = engine.report()
    return equity_df, metrics, orders


# =============================================================================
# Entry point
# =============================================================================
if __name__ == "__main__":
    # 1) Strategia e configurazione
    strategy = BuyHoldStrategy()
    cfg = strategy.get_config()

    _hr("Backtest configuration")
    print(f"Symbol       : {cfg['symbol']}")
    print(f"Date range   : {cfg['start_date']} → {cfg['end_date']}")
    print(f"Initial cash : {cfg['initial_cash']}")
    print(f"Exchange     : {cfg.get('exchange', 'SMART')}")
    print(f"Currency     : {cfg.get('currency', 'USD')}")
    print(f"Bar size     : {cfg.get('bar_size', '1 min')}")

    # 2) Connessione IBKR
    client = IBKRClient(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 7497),
        client_id=cfg.get("client_id", 1),
    )

    # 3) Dati mercato
    bars = fetch_bars(client, cfg)
    data = fetch_and_merge_ticks(client, cfg, bars)

    # 4) Backtest
    equity_df, metrics, orders = run_backtest(strategy, data, cfg)

    # 5) Metriche
    _hr("Performance metrics")
    for k, v in metrics.items():
        print(f"{k:<22}: {v:.2f}")

    # 6) Plot risultati
    _hr("Plot")
    plot_backtest(
        price_df=data,
        equity_df=equity_df,
        orders=orders,
        start_date=cfg["start_date"],
        end_date=cfg["end_date"],
    )
