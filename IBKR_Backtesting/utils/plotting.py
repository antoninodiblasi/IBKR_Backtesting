import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
from matplotlib import pyplot as plt


def _nearest_plot_idx(px_ts: np.ndarray, target_ts: np.datetime64) -> int | None:
    """
    Trova l'indice in px_ts (array ordinato di datetime64) più vicino a target_ts.
    Utile per piazzare marker ordini sul grafico anche se i timestamp
    non coincidono esattamente.
    """
    if len(px_ts) == 0:
        return None

    # Posizione di inserimento ordinata
    i = np.searchsorted(px_ts, target_ts)

    # Gestione bordi
    if i == 0:
        return 0
    if i >= len(px_ts):
        return len(px_ts) - 1

    # Confronto distanza con timestamp precedente e successivo
    prev_diff = abs(target_ts - px_ts[i - 1])
    next_diff = abs(px_ts[i] - target_ts)
    return i - 1 if prev_diff <= next_diff else i


def plot_backtest(price_df: pd.DataFrame,
                  equity_df: pd.DataFrame,
                  orders,
                  start_date: str,
                  end_date: str):
    """
    Visualizza i risultati del backtest in due pannelli:
    1) Prezzo con ordini BUY/SELL
    2) Equity curve intraday, riallineata ai timestamp del prezzo

    Funzionalità:
    - Asse x sintetico continuo (plot_idx) per evitare gap tra giorni
    - Tick x solo a inizio giornata, con separatori verticali
    - Bande alternate per distinguere i giorni
    - Ordini sovrapposti al grafico prezzo con marker
    """

    # ------------------------------------------------------------------
    # 1. Filtraggio dei dati nel range richiesto
    # ------------------------------------------------------------------
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    px = price_df[(price_df["timestamp"] >= start_ts) & (price_df["timestamp"] <= end_ts)].copy()
    eq = equity_df[(equity_df["timestamp"] >= start_ts) & (equity_df["timestamp"] <= end_ts)].copy()

    if px.empty or eq.empty:
        print("[WARN] Nessun dato valido per il plotting nel range selezionato.")
        return

    # ------------------------------------------------------------------
    # 2. Costruzione indice sintetico (plot_idx)
    # ------------------------------------------------------------------
    px = px.reset_index(drop=True)
    px["plot_idx"] = np.arange(len(px), dtype=int)

    # Mapping timestamp → indice (serve per riallineare equity e ordini)
    ts_to_idx = dict(zip(px["timestamp"], px["plot_idx"]))

    # ------------------------------------------------------------------
    # 3. Riallineamento dell’equity su stesso asse del prezzo
    # ------------------------------------------------------------------
    eq = eq.reset_index(drop=True)
    eq["plot_idx"] = eq["timestamp"].map(ts_to_idx)

    # Drop di eventuali snapshot equity con timestamp non presenti in px
    eq = eq.dropna(subset=["plot_idx"])

    # ------------------------------------------------------------------
    # 4. Calcolo dei marker di inizio giornata
    # ------------------------------------------------------------------
    px["date"] = px["timestamp"].dt.date

    # prendiamo la PRIMA barra di ogni giornata
    day_starts = px.groupby("date", as_index=False).first()[["date", "timestamp"]]

    # Tick positions = timestamp veri
    tick_locs = day_starts["timestamp"].to_numpy()
    tick_labels = day_starts["date"].astype(str).tolist()

    # ------------------------------------------------------------------
    # 5. Preparazione ordini
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

    import matplotlib.dates as mdates

    # ------------------------------------------------------------------
    # 6. Creazione figure e assi
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # ==============================
    # Pannello Prezzo
    # ==============================
    axes[0].plot(px["timestamp"], px["close"], label="Price", color="black")

    if buy_x:
        axes[0].scatter(
            [px.loc[i, "timestamp"] for i in buy_x],
            buy_y,
            color="green", marker="^", s=80, label="BUY"
        )
    if sell_x:
        axes[0].scatter(
            [px.loc[i, "timestamp"] for i in sell_x],
            sell_y,
            color="red", marker="v", s=80, label="SELL"
        )

    axes[0].set_title(f"Price with Orders | {start_date} → {end_date}")
    axes[0].set_ylabel("Price")
    axes[0].legend(loc="best")

    # ==============================
    # Pannello Equity
    # ==============================
    axes[1].plot(eq["timestamp"], eq["equity"], label="Equity", color="blue")
    axes[1].set_title("Equity Curve (intraday, aligned with price timestamps)")
    axes[1].set_ylabel("Portfolio Value (USD)")
    axes[1].yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes[1].legend(loc="best")

    # Dinamico: scala asse Y dell’equity con margine 5%
    if not eq.empty:
        ymin, ymax = eq["equity"].min(), eq["equity"].max()
        margin = (ymax - ymin) * 0.05 if ymax > ymin else 1
        axes[1].set_ylim(ymin - margin, ymax + margin)

    # ------------------------------------------------------------------
    # 7. Personalizzazioni asse X
    # ------------------------------------------------------------------
    # Tick agli inizi di giornata
    tick_locs = day_starts["timestamp"].to_numpy()
    tick_labels = day_starts["date"].astype(str).tolist()
    axes[1].set_xticks(tick_locs)
    axes[1].set_xticklabels(tick_labels, rotation=0)

    # Formattazione dinamica dell’asse tempo
    if (end_ts - start_ts).days < 5:
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    else:
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    # Linee verticali separatrici tra giorni
    for x in tick_locs[1:]:
        for ax in axes:
            ax.axvline(x, color="gray", alpha=0.25, linewidth=1)

    # Bande alternate per distinguere visivamente i giorni
    day_edges = list(tick_locs) + [px["timestamp"].iloc[-1]]
    for i in range(len(day_edges) - 1):
        if i % 2 == 1:  # evidenzia solo i giorni dispari
            for ax in axes:
                ax.axvspan(day_edges[i], day_edges[i + 1],
                           color="lightgray", alpha=0.08)

    plt.tight_layout()
    plt.show()
