import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
from matplotlib import pyplot as plt


def _nearest_plot_idx(px_ts: np.ndarray, target_ts: np.datetime64) -> int | None:
    """
    Trova l'indice del timestamp di px_ts più vicino a target_ts.
    Serve per associare un ordine al punto corretto della curva prezzo,
    anche se i timestamp non coincidono esattamente.
    """
    if len(px_ts) == 0:
        return None

    # posizione in cui "inserire" target_ts mantenendo ordine
    i = np.searchsorted(px_ts, target_ts)

    # caso bordo sinistro
    if i == 0:
        return 0
    # caso bordo destro
    if i >= len(px_ts):
        return len(px_ts) - 1

    # confronto con il timestamp precedente e successivo
    prev_diff = abs(target_ts - px_ts[i - 1])
    next_diff = abs(px_ts[i] - target_ts)
    return i - 1 if prev_diff <= next_diff else i


def plot_backtest(price_df: pd.DataFrame,
                  equity_df: pd.DataFrame,
                  orders,
                  start_date: str,
                  end_date: str):
    """
    Plotta i risultati del backtest in due pannelli:
    1. Prezzo con segnali BUY/SELL
    2. Equity curve intraday (allineata ai timestamp del prezzo)

    Features:
    - indice sintetico continuo (plot_idx) per evitare gap tra giorni
    - asse x con tick solo a inizio giornata
    - linee verticali per separare i giorni
    - bande alternate per distinguere visivamente i giorni
    """

    # ------------------------------------------------------------------
    # 1. Selezione dati nel range richiesto
    # ------------------------------------------------------------------
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    px = price_df[(price_df["timestamp"] >= start_ts) & (price_df["timestamp"] <= end_ts)].copy()
    eq = equity_df[(equity_df["timestamp"] >= start_ts) & (equity_df["timestamp"] <= end_ts)].copy()

    # ------------------------------------------------------------------
    # 2. Costruzione indice sintetico per il prezzo
    # ------------------------------------------------------------------
    px = px.reset_index(drop=True)
    px["plot_idx"] = np.arange(len(px), dtype=int)

    # creo una mappa timestamp → indice per riallineare l’equity
    ts_to_idx = dict(zip(px["timestamp"], px["plot_idx"]))

    # ------------------------------------------------------------------
    # 3. Allineamento dell’equity agli stessi indici del prezzo
    # ------------------------------------------------------------------
    eq = eq.reset_index(drop=True)
    eq["plot_idx"] = eq["timestamp"].map(ts_to_idx)

    # NB: se qualche timestamp di equity non esiste in px,
    # eq["plot_idx"] diventa NaN. Conviene droppare eventuali righe mancanti.
    eq = eq.dropna(subset=["plot_idx"])

    # ------------------------------------------------------------------
    # 4. Calcolo dei marker di inizio giornata
    # ------------------------------------------------------------------
    px["date"] = px["timestamp"].dt.date
    day_starts = px.groupby("date", as_index=False).first()[["date", "plot_idx"]]

    tick_locs = day_starts["plot_idx"].to_numpy()         # posizione dei tick
    tick_labels = day_starts["date"].astype(str).tolist() # etichette (YYYY-MM-DD)

    # ------------------------------------------------------------------
    # 5. Preparazione ordini (BUY/SELL)
    # ------------------------------------------------------------------
    ts_array = px["timestamp"].to_numpy(dtype="datetime64[ns]")

    buy_x, buy_y, sell_x, sell_y = [], [], [], []
    for o in orders:
        if o.timestamp is None:
            continue
        if not (start_ts <= o.timestamp <= end_ts):
            continue

        idx = _nearest_plot_idx(ts_array, np.datetime64(o.timestamp))
        if idx is None:
            continue

        x = int(px.loc[idx, "plot_idx"])
        y = float(o.price)

        if o.side.upper() == "BUY":
            buy_x.append(x)
            buy_y.append(y)
        else:
            sell_x.append(x)
            sell_y.append(y)

    # ------------------------------------------------------------------
    # 6. Plotting
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
    axes[1].set_title("Equity Curve (intraday, aligned with price timestamps)")
    axes[1].set_ylabel("Portfolio Value (USD)")
    axes[1].yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes[1].legend(loc="best")

    # ------------------------------------------------------------------
    # 7. Personalizzazioni asse X
    # ------------------------------------------------------------------
    for ax in axes:
        # Tick solo agli inizi di giornata
        ax.set_xticks(tick_locs, tick_labels, rotation=0)

        # Linee verticali per separare i giorni
        for x in tick_locs[1:]:
            ax.axvline(x, color="gray", alpha=0.25, linewidth=1)

    # Bande alternate per distinguere i giorni
    day_edges = list(tick_locs) + [px["plot_idx"].iloc[-1] + 1]
    for i in range(len(day_edges) - 1):
        if i % 2 == 1:  # ogni giorno dispari
            for ax in axes:
                ax.axvspan(day_edges[i], day_edges[i + 1],
                           color="lightgray", alpha=0.08)

    plt.tight_layout()
    plt.show()
