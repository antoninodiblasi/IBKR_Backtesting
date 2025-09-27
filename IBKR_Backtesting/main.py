from IBKR_Backtesting.strategies.dummy_strategy import SP500DummyStrategy
from IBKR_Backtesting.engine.backtest import BacktestEngine
from IBKR_Backtesting.utils.plotting import plot_backtest
from IBKR_Backtesting.utils.ibkr_client import IBKRClient
from IBKR_Backtesting.utils.data_handler import prepare_dataframe

import pandas as pd

if __name__ == "__main__":
    # ==============================
    # INIZIALIZZA STRATEGIA
    # ==============================
    strategy = SP500DummyStrategy()  # contiene già symbol, date, cash, ecc.
    cfg = strategy.get_config()

    print("="*60)
    print(f"Backtest run for {cfg['symbol']}")
    print(f"Date range: {cfg['start_date']} → {cfg['end_date']}")
    print(f"Initial cash: {cfg['initial_cash']}")
    print("="*60)

    # ==============================
    # CONNESSIONE IBKR
    # ==============================
    client = IBKRClient(host="127.0.0.1", port=7497, client_id=1)

    # calcoliamo durata e fine
    start_dt = pd.to_datetime(strategy.start_date)
    end_dt = pd.to_datetime(strategy.end_date)
    days = (end_dt - start_dt).days + 1
    duration_str = f"{days} D"

    # end_datetime in formato IBKR (fine della giornata finale)
    end_datetime = (end_dt + pd.Timedelta(days=1)).strftime("%Y%m%d %H:%M:%S")

    # ==============================
    # DOWNLOAD DATI
    # ==============================
    raw_df = client.get_historical_data(
        symbol=strategy.symbol,
        exchange="SMART",
        currency="USD",
        end_datetime=end_datetime,   # <<< nuovo parametro
        duration=duration_str,
        bar_size="1 min"
    )

    data = prepare_dataframe(raw_df)

    print("\n[CHECK] Preview of downloaded DataFrame:")
    print(f"Range effettivo: {data['timestamp'].min()} → {data['timestamp'].max()}")
    print(data.head())
    print(data.tail())

    # ==============================
    # BACKTEST ENGINE
    # ==============================
    engine = BacktestEngine(
        strategy=strategy,
        data=data,
        symbol=strategy.symbol,
        initial_cash=strategy.initial_cash
    )
    engine.run()

    portfolio_df, metrics, orders = engine.report(initial_cash=strategy.initial_cash)

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
        equity_df=portfolio_df,
        orders=orders,
        start_date=strategy.start_date,
        end_date=strategy.end_date
    )
