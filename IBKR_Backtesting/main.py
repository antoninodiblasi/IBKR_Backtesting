# main.py

import pandas as pd
from IBKR_Backtesting.strategies.dummy_strategy import SP500DummyStrategy
from IBKR_Backtesting.engine.backtest import BacktestEngine
from IBKR_Backtesting.utils.plotting import plot_backtest
from IBKR_Backtesting.utils.ibkr_client import IBKRClient
from IBKR_Backtesting.utils.data_handler import prepare_dataframe, merge_bidask_to_bars


if __name__ == "__main__":
    # ==============================
    # INIZIALIZZA STRATEGIA E CONFIG
    # ==============================
    strategy = SP500DummyStrategy()
    cfg = strategy.get_config()

    print("=" * 60)
    print(f"Backtest run for {cfg['symbol']}")
    print(f"Date range: {cfg['start_date']} → {cfg['end_date']}")
    print(f"Initial cash: {cfg['initial_cash']}")
    print("=" * 60)

    # ==============================
    # CONNESSIONE IBKR
    # ==============================
    client = IBKRClient(
        host=cfg.get("host", "127.0.0.1"),
        port=cfg.get("port", 7497),
        client_id=cfg.get("client_id", 1)
    )

    # ==============================
    # CALCOLO PARAMETRI PER IBKR
    # ==============================
    start_dt = pd.to_datetime(cfg["start_date"])
    end_dt = pd.to_datetime(cfg["end_date"])
    days = (end_dt - start_dt).days + 1
    duration_str = f"{days} D"

    # IBKR vuole endDateTime al giorno successivo
    end_datetime = (end_dt + pd.Timedelta(days=1)).strftime("%Y%m%d %H:%M:%S")

    # ==============================
    # DOWNLOAD BARRE OHLCV
    # ==============================
    raw_df = client.get_historical_data(
        symbol=cfg["symbol"],
        exchange=cfg["exchange"],
        currency=cfg["currency"],
        end_datetime=end_datetime,
        duration=duration_str,
        bar_size=cfg["bar_size"]
    )
    bars = prepare_dataframe(raw_df)

    print("\n[CHECK] Preview of downloaded bars:")
    print(f"Range effettivo: {bars['timestamp'].min()} → {bars['timestamp'].max()}")
    print(bars.head())
    print(bars.tail())

    # ==============================
    # DOWNLOAD TICK BID/ASK (opzionale)
    # ==============================
    print("\n[INFO] Scarico tick BID/ASK da IBKR...")
    ticks = client.get_historical_bidask_ticks(
        symbol=cfg["symbol"],
        exchange=cfg["exchange"],
        currency=cfg["currency"],
        start_dt=start_dt.strftime("%Y%m%d %H:%M:%S"),
        end_dt=end_dt.strftime("%Y%m%d %H:%M:%S"),
        batch_size=1000
    )

    if not ticks.empty:
        ticks_file = f"book_{cfg['symbol']}_{cfg['start_date']}_{cfg['end_date']}.csv"
        ticks.to_csv(ticks_file, index=False)
        print(f"[INFO] Salvati {len(ticks)} tick BID/ASK in {ticks_file}")

        # Merge dei tick BID/ASK con le barre OHLCV
        data = merge_bidask_to_bars(bars, ticks, on_col="timestamp")
    else:
        print("[WARN] Nessun tick BID/ASK scaricato, uso solo OHLCV.")
        data = bars

    # ==============================
    # BACKTEST ENGINE
    # ==============================
    engine = BacktestEngine(
        strategy=strategy,
        data=data,
        symbol=cfg["symbol"],
        initial_cash=cfg["initial_cash"]
    )
    engine.run()

    equity_df, daily_df, metrics, orders, daily_store = engine.report()

    # ==============================
    # RISULTATI
    # ==============================
    print("\n[CHECK] Performance metrics:")
    for metrica, valore in metrics.items():
        print(f"{metrica:<20}: {valore}")

    # ==============================
    # PLOT RISULTATI
    # ==============================
    plot_backtest(
        price_df=data,
        equity_df=equity_df,
        orders=orders,
        start_date=cfg["start_date"],
        end_date=cfg["end_date"]
    )
