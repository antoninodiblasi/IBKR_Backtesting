# utils/performance.py

import pandas as pd
import numpy as np
from datetime import time as dtime


def compute_performance(portfolio_history: list[dict], initial_cash: float):
    """
    Calcola le metriche di performance a partire dallo storico del portafoglio.

    Parameters
    ----------
    portfolio_history : list[dict]
        Lista di operazioni / snapshot registrate dal Portfolio.
        Ogni elemento deve contenere almeno:
        - symbol    : ticker
        - side      : BUY/SELL
        - qty       : quantità
        - price     : prezzo
        - cash      : cash dopo l'operazione
        - timestamp : datetime

        Opzionalmente può contenere:
        - position      : posizione netta dopo il fill
        - avg_price     : prezzo medio di carico
        - realized_pnl  : pnl realizzato
        - equity        : equity del portafoglio (se disponibile)

    initial_cash : float
        Capitale iniziale (baseline per i calcoli).

    Returns
    -------
    df : pd.DataFrame
        DataFrame dello storico con colonne aggiuntive:
        - equity  : valore del portafoglio
        - returns : rendimento percentuale bar-to-bar

    metrics : dict
        Dizionario con metriche aggregate:
        - Total Return %  : rendimento cumulato
        - Volatility %    : deviazione standard annualizzata dei rendimenti
        - Sharpe Ratio    : rapporto rischio/rendimento annualizzato
        - Max Drawdown %  : drawdown massimo
    """

    if not portfolio_history:
        return pd.DataFrame(), {}

    # Converti in DataFrame ordinato temporalmente
    df = pd.DataFrame(portfolio_history).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Se non esiste equity, fallback su cash
    if "equity" not in df.columns:
        df["equity"] = df["cash"]

    # Garantisce numerici (per evitare NaN in pct_change)
    df["equity"] = df["equity"].astype(float)

    # Calcolo rendimenti percentuali bar-to-bar
    df["returns"] = df["equity"].pct_change(fill_method=None).fillna(0.0)

    # -----------------------------
    # Metriche aggregate
    # -----------------------------

    # Rendimento totale (%)
    total_return = (df["equity"].iloc[-1] / initial_cash - 1.0) * 100.0

    # Volatilità annualizzata (252 giorni di trading)
    vol = df["returns"].std() * np.sqrt(252) if len(df) > 1 else 0.0

    # Sharpe ratio annualizzato (risk-free = 0)
    sharpe = (df["returns"].mean() / df["returns"].std()) * np.sqrt(252) \
        if df["returns"].std() > 0 else 0.0

    # Max Drawdown %
    cumulative = (1.0 + df["returns"]).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min() * 100.0

    metrics = {
        "Total Return %": round(total_return, 3),
        "Volatility %": round(vol * 100, 3),
        "Sharpe Ratio": round(sharpe, 3),
        "Max Drawdown %": round(max_drawdown, 3)
    }

    return df, metrics


def aggregate_daily_equity(equity_df: pd.DataFrame,
                           m2m_time: dtime = dtime(17, 15)) -> pd.DataFrame:
    """
    Restituisce l'equity giornaliera con mark-to-market (M2M) a un orario fisso.

    Parameters
    ----------
    equity_df : pd.DataFrame
        Serie intraday dell'equity, con almeno:
        - timestamp : datetime
        - equity    : valore del portafoglio
    m2m_time : datetime.time, default 17:15
        Orario target per il mark-to-market giornaliero.

    Returns
    -------
    daily : pd.DataFrame
        DataFrame con:
        - date      : giorno di riferimento
        - timestamp : timestamp scelto per il M2M
        - equity    : equity al M2M
        - ret       : rendimento giornaliero rispetto al giorno precedente
    """

    if equity_df.empty:
        return equity_df

    df = equity_df.reset_index(drop=True).copy()
    df["date"] = df["timestamp"].dt.date
    df["time"] = df["timestamp"].dt.time

    def pick_m2m(g):
        g_sorted = g.sort_values("timestamp")
        after = g_sorted[g_sorted["time"] >= m2m_time]
        row = after.iloc[0] if not after.empty else g_sorted.iloc[-1]
        return pd.Series({
            "timestamp": row["timestamp"],
            "equity": float(row["equity"])  # <<< forzo numerico
        })

    daily = df.groupby("date", as_index=False).apply(pick_m2m, include_groups=False)
    daily = daily.sort_values("timestamp").reset_index(drop=True)

    # conversione sicura
    daily["equity"] = pd.to_numeric(daily["equity"], errors="coerce")

    # rendimento giornaliero
    daily["ret"] = daily["equity"].pct_change().fillna(0.0)

    return daily
