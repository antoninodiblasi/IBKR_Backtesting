import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
from matplotlib import pyplot as plt


def _nearest_plot_idx(px_ts: np.ndarray, target_ts: np.datetime64) -> int | None:
    """
    Trova l'indice in px_ts (array ordinato di datetime64) più vicino a target_ts.
    Utile per associare marker degli ordini a un timestamp esistente.
    """
    if len(px_ts) == 0:
        return None

    i = np.searchsorted(px_ts, target_ts)

    # Bordi
    if i == 0:
        return 0
    if i >= len(px_ts):
        return len(px_ts) - 1

    # Confronto con vicino precedente e successivo
    prev_diff = abs(target_ts - px_ts[i - 1])
    next_diff = abs(px_ts[i] - target_ts)
    return i - 1 if prev_diff <= next_diff else i


def plot_backtest(price_df: pd.DataFrame,
                  equity_df: pd.DataFrame,
                  orders,
                  start_date: str,
                  end_date: str) -> None:
    """
    Visualizza i risultati del backtest in due pannelli:
    1. Prezzo con marker BUY/SELL
    2. Equity curve intraday (continua solo nelle trading hours)

    Parametri
    ---------
    price_df : DataFrame
        Dati OHLCV con colonna 'timestamp'
    equity_df : DataFrame
        Serie equity con colonne ['timestamp','equity']
    orders : list
        Lista di oggetti Order con attributi (timestamp, price, side)
    start_date, end_date : str
        Range temporale per la visualizzazione (YYYY-MM-DD)
    """
    # ------------------------------------------------------------------
    # 1. Filtra i dati nel range
    # ------------------------------------------------------------------
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    px = price_df[(price_df["timestamp"] >= start_ts) & (price_df["timestamp"] <= end_ts)].copy()
    eq = equity_df[(equity_df["timestamp"] >= start_ts) & (equity_df["timestamp"] <= end_ts)].copy()

    if px.empty or eq.empty:
        print("[WARN] Nessun dato valido per il plotting nel range selezionato.")
        return

    # ------------------------------------------------------------------
    # 2. Costruisci indice continuo solo trading hours (09:30–17:00)
    # ------------------------------------------------------------------
    px = px.reset_index(drop=True)
    plot_idx = []
    counter = 0
    for t in px["timestamp"]:
        if 9 <= t.hour < 17:   # trading hours
            plot_idx.append(counter)
            counter += 1
        else:
            plot_idx.append(None)  # fuori orario
    px["plot_idx"] = plot_idx
    px = px.dropna(subset=["plot_idx"])
    px["plot_idx"] = px["plot_idx"].astype(int)

    # Riallinea anche equity sugli stessi indici
    eq = eq.merge(px[["timestamp", "plot_idx"]], on="timestamp", how="inner")

    # ------------------------------------------------------------------
    # 3. Marker BUY/SELL
    # ------------------------------------------------------------------
    ts_array = px["timestamp"].to_numpy(dtype="datetime64[ns]")
    buy_x, buy_y, sell_x, sell_y = [], [], [], []
    for o in orders or []:  # gestisce anche None
        if o.timestamp is None:
            continue
        if not (start_ts <= o.timestamp <= end_ts):
            continue

        idx = _nearest_plot_idx(ts_array, np.datetime64(o.timestamp))
        if idx is None:
            continue

        t = px.loc[idx, "plot_idx"]  # ora usiamo plot_idx
        p = float(o.price)

        if o.side.upper() == "BUY":
            buy_x.append(t)
            buy_y.append(p)
        else:
            sell_x.append(t)
            sell_y.append(p)

    # ------------------------------------------------------------------
    # 4. Crea figura e assi
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # --- Pannello Prezzo ---
    axes[0].plot(px["plot_idx"], px["close"], label="Price", color="black")
    if buy_x:
        axes[0].scatter(buy_x, buy_y, color="green", marker="^", s=80, label="BUY")
    if sell_x:
        axes[0].scatter(sell_x, sell_y, color="red", marker="v", s=80, label="SELL")

    axes[0].set_title(f"Price with Orders | {start_date} → {end_date}")
    axes[0].set_ylabel("Price")
    axes[0].legend(loc="best")

    # --- Pannello Equity ---
    axes[1].plot(eq["plot_idx"], eq["equity"], label="Equity", color="blue")
    axes[1].set_title("Equity Curve (intraday, trading hours only)")
    axes[1].set_ylabel("Portfolio Value (USD)")
    axes[1].yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes[1].legend(loc="best")

    # Y dinamico con margine 5%
    ymin, ymax = eq["equity"].min(), eq["equity"].max()
    margin = (ymax - ymin) * 0.05 if ymax > ymin else 1
    axes[1].set_ylim(ymin - margin, ymax + margin)

    # ------------------------------------------------------------------
    # 5. Etichette asse X (date+ora inizio giornata)
    # ------------------------------------------------------------------
    px["date"] = px["timestamp"].dt.date
    day_starts = px.groupby("date", as_index=False).first()[["plot_idx", "timestamp"]]

    tick_positions = day_starts["plot_idx"].to_numpy()
    tick_labels = day_starts["timestamp"].dt.strftime("%m-%d %H:%M").tolist()

    axes[1].set_xticks(tick_positions)
    axes[1].set_xticklabels(tick_labels, rotation=0)

    # Linee verticali separatrici tra giorni
    if len(tick_positions) > 1:
        for x in tick_positions[1:]:
            for ax in axes:
                ax.axvline(x, color="gray", alpha=0.25, linewidth=1)

    # Bande alternate (giorni dispari)
    day_edges = list(tick_positions) + [px["plot_idx"].iloc[-1]]
    for i in range(len(day_edges) - 1):
        if i % 2 == 1:
            for ax in axes:
                ax.axvspan(day_edges[i], day_edges[i + 1], color="lightgray", alpha=0.08)

    plt.tight_layout()
    plt.show()
