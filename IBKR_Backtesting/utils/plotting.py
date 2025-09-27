# utils/plotting.py
import matplotlib.ticker as mticker
from matplotlib import pyplot as plt


def plot_backtest(price_df, equity_df, orders, start_date, end_date):
    """
    Plotta i risultati del backtest in due pannelli:
    1. Andamento del prezzo con segnali BUY/SELL
    2. Equity curve del portafoglio

    Args:
        price_df (pd.DataFrame): dati storici con colonne ['timestamp', 'close']
        equity_df (pd.DataFrame): storico equity con indice datetime e colonna 'equity'
        orders (list[Order]): lista di ordini eseguiti (BUY/SELL)
        start_date (str): data di inizio (formato 'YYYY-MM-DD')
        end_date (str): data di fine (formato 'YYYY-MM-DD')
    """

    # Filtro il DataFrame dei prezzi nel range richiesto
    mask = (price_df["timestamp"].dt.strftime("%Y-%m-%d") >= start_date) & \
           (price_df["timestamp"].dt.strftime("%Y-%m-%d") <= end_date)
    price_df = price_df[mask]

    # Creo due sottopannelli (prezzi e equity)
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # --- Pannello 1: Prezzo + ordini
    axes[0].plot(price_df["timestamp"], price_df["close"], label="Price", color="black")

    for order in orders:
        # Mostriamo BUY/SELL solo se rientrano nel periodo richiesto
        if start_date <= order.timestamp.strftime("%Y-%m-%d") <= end_date:
            if order.side == "BUY":
                axes[0].scatter(order.timestamp, order.price,
                                color="green", marker="^", s=100, label="BUY")
            else:
                axes[0].scatter(order.timestamp, order.price,
                                color="red", marker="v", s=100, label="SELL")

    axes[0].set_title(f"{start_date} → {end_date} | Price with Orders")
    axes[0].set_ylabel("Price (USD)")
    axes[0].legend()

    # --- Pannello 2: Equity curve
    axes[1].plot(equity_df.index, equity_df["equity"], label="Equity", color="blue")
    axes[1].set_title("Equity Curve")
    axes[1].set_xlabel("Time")
    axes[1].set_ylabel("Portfolio Value (USD)")

    # Formatter per valori più leggibili (senza notazione scientifica)
    axes[1].yaxis.set_major_formatter(mticker.StrMethodFormatter('{x:,.0f}'))

    axes[1].legend()

    plt.tight_layout()
    plt.show()
