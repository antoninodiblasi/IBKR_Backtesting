import numpy as np
import pandas as pd
import matplotlib.ticker as mticker
from matplotlib import pyplot as plt


def _nearest_plot_idx(px_ts: np.ndarray, target_ts: np.datetime64) -> int | None:
    """
    Trova l'indice di px_ts (array ordinato di datetime64) più vicino a target_ts.
    Utile per associare marker ordini al punto giusto sul grafico.
    """
    if len(px_ts) == 0:
        return None

    i = np.searchsorted(px_ts, target_ts)
    if i == 0:
        return 0
    if i >= len(px_ts):
        return len(px_ts) - 1

    prev_diff = abs(target_ts - px_ts[i - 1])
    next_diff = abs(px_ts[i] - target_ts)
    return i - 1 if prev_diff <= next_diff else i


def plot_backtest(
    price_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    orders,
    start_date: str,
    end_date: str,
    *,
    trading_start: int = 9,
    trading_end: int = 17,
    plot_orders: bool = True,
) -> None:
    """
    Visualizza i risultati del backtest in due pannelli:
    1. Prezzo con marker BUY/SELL (se attivi).
    2. Equity curve.

    Parametri
    ---------
    price_df : pd.DataFrame
        Dati OHLCV per un singolo asset, con colonna 'timestamp'.
    equity_df : pd.DataFrame
        Serie equity con colonne ['timestamp','equity'].
    orders : list[Order] o None
        Lista di ordini (con attributi timestamp, price, side).
    start_date, end_date : str
        Range temporale (YYYY-MM-DD).
    trading_start : int
        Ora inizio trading (solo per intraday).
    trading_end : int
        Ora fine trading (solo per intraday).
    plot_orders : bool
        Se False, non disegna marker BUY/SELL.
    """
    # -------------------------------
    # 1. Filtra range temporale
    # -------------------------------
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)

    px = price_df[(price_df["timestamp"] >= start_ts) & (price_df["timestamp"] <= end_ts)].copy()
    eq = equity_df[(equity_df["timestamp"] >= start_ts) & (equity_df["timestamp"] <= end_ts)].copy()

    if px.empty or eq.empty:
        print("[WARN] Nessun dato valido per il plotting nel range selezionato.")
        return

    # -------------------------------
    # 2. Costruisci indice continuo
    # -------------------------------
    px = px.reset_index(drop=True)

    # Se i dati sono DAILY → non filtriamo sugli orari
    is_daily = (px["timestamp"].dt.normalize() == px["timestamp"]).all()

    if is_daily:
        px["plot_idx"] = range(len(px))
    else:
        plot_idx = []
        counter = 0
        for t in px["timestamp"]:
            if trading_start <= t.hour < trading_end:
                plot_idx.append(counter)
                counter += 1
            else:
                plot_idx.append(None)
        px["plot_idx"] = plot_idx
        px = px.dropna(subset=["plot_idx"])
        if px.empty:
            print("[WARN] Nessun dato valido dentro trading hours.")
            return
        px["plot_idx"] = px["plot_idx"].astype(int)

    # Riallinea equity sugli stessi indici
    eq = eq.merge(px[["timestamp", "plot_idx"]], on="timestamp", how="inner")
    if eq.empty:
        print("[WARN] Nessuna equity allineata disponibile per plotting.")
        return

    # -------------------------------
    # 3. Marker BUY/SELL
    # -------------------------------
    buy_x, buy_y, sell_x, sell_y = [], [], [], []
    if plot_orders and orders:
        ts_array = px["timestamp"].to_numpy(dtype="datetime64[ns]")
        for o in orders:
            if not hasattr(o, "timestamp") or o.timestamp is None:
                continue
            if not (start_ts <= o.timestamp <= end_ts):
                continue

            idx = _nearest_plot_idx(ts_array, np.datetime64(o.timestamp))
            if idx is None:
                continue

            t = px.loc[idx, "plot_idx"]
            p = float(o.price) if o.price is not None else None
            if p is None:
                continue

            if o.side.upper() == "BUY":
                buy_x.append(t)
                buy_y.append(p)
            elif o.side.upper() == "SELL":
                sell_x.append(t)
                sell_y.append(p)

    # -------------------------------
    # 4. Plot
    # -------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Prezzo
    axes[0].plot(px["plot_idx"], px["close"], label="Price", color="black")
    if plot_orders and buy_x:
        axes[0].scatter(buy_x, buy_y, color="green", marker="^", s=80, label="BUY")
    if plot_orders and sell_x:
        axes[0].scatter(sell_x, sell_y, color="red", marker="v", s=80, label="SELL")
    axes[0].set_title(f"Price | {start_date} → {end_date}")
    axes[0].set_ylabel("Price")
    axes[0].legend(loc="best")

    # Equity
    axes[1].plot(eq["plot_idx"], eq["equity"], label="Equity", color="blue")
    axes[1].set_title("Equity Curve")
    axes[1].set_ylabel("Portfolio Value")
    axes[1].yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes[1].legend(loc="best")

    if not eq["equity"].dropna().empty:
        ymin, ymax = eq["equity"].min(), eq["equity"].max()
        margin = (ymax - ymin) * 0.05 if ymax > ymin else 1
        axes[1].set_ylim(ymin - margin, ymax + margin)

    # -------------------------------
    # 5. Etichette X
    # -------------------------------
    px["date"] = px["timestamp"].dt.date
    day_starts = px.groupby("date", as_index=False).first()[["plot_idx", "timestamp"]]
    tick_positions = day_starts["plot_idx"].to_numpy()
    tick_labels = day_starts["timestamp"].dt.strftime("%Y-%m-%d").tolist() if is_daily \
                  else day_starts["timestamp"].dt.strftime("%m-%d %H:%M").tolist()

    if len(tick_positions) > 0:
        axes[1].set_xticks(tick_positions)
        axes[1].set_xticklabels(tick_labels, rotation=0)

    # Linee verticali + bande alternate
    if len(tick_positions) > 1:
        for x in tick_positions[1:]:
            for ax in axes:
                ax.axvline(x, color="gray", alpha=0.25, linewidth=1)

        day_edges = list(tick_positions) + [px["plot_idx"].iloc[-1]]
        for i in range(len(day_edges) - 1):
            if i % 2 == 1:
                for ax in axes:
                    ax.axvspan(day_edges[i], day_edges[i + 1],
                               color="lightgray", alpha=0.08)

    plt.tight_layout()
    plt.show()
