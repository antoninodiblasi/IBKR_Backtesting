# utils/performance.py

import pandas as pd
import numpy as np
from datetime import time as dtime


def compute_performance(
    portfolio_history: list[dict],
    initial_cash: float,
    trading_days: int = 252
):
    """
    Calcola metriche di performance a partire dallo storico del portafoglio.

    Parametri
    ---------
    portfolio_history : list[dict]
        Lista di fill / snapshot dal Portfolio.
        Multi-asset: ciascun elemento può contenere campi 'symbol' diversi.
        L'analisi è fatta sul portafoglio aggregato.
    initial_cash : float
        Capitale iniziale.
    trading_days : int, default 252
        Giorni di trading usati per annualizzare volatilità e Sharpe.
        ➜ Deve arrivare da strategy.get_config().

    Ritorna
    -------
    df : pd.DataFrame
        Serie temporale equity con colonna returns.
    metrics : dict
        Metriche aggregate (Total Return %, Volatility %, Sharpe Ratio, Max DD %).
    """
    if not portfolio_history:
        return pd.DataFrame(), {}

    df = pd.DataFrame(portfolio_history).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    if "equity" not in df.columns:
        df["equity"] = df["cash"]

    df["equity"] = df["equity"].astype(float)
    df["returns"] = df["equity"].pct_change(fill_method=None).fillna(0.0)

    # -------------------------
    # Metriche aggregate
    # -------------------------
    total_return = (df["equity"].iloc[-1] / initial_cash - 1.0) * 100.0
    vol = df["returns"].std() * np.sqrt(trading_days) if len(df) > 1 else 0.0
    sharpe = (df["returns"].mean() / df["returns"].std()) * np.sqrt(trading_days) \
        if df["returns"].std() > 0 else 0.0

    cumulative = (1.0 + df["returns"]).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min() * 100.0

    metrics = {
        "Total Return %": round(total_return, 3),
        "Volatility %": round(vol * 100, 3),
        "Sharpe Ratio": round(sharpe, 3),
        "Max Drawdown %": round(max_drawdown, 3),
    }

    return df, metrics


def aggregate_daily_equity(
    equity_df: pd.DataFrame,
    m2m_time: dtime
) -> pd.DataFrame:
    """
    Restituisce l'equity giornaliera con M2M a un orario fisso.

    Parametri
    ---------
    equity_df : pd.DataFrame
        Serie intraday dell'equity del portafoglio.
    m2m_time : datetime.time
        Orario target per M2M giornaliero.
        ➜ Deve arrivare da strategy.get_config().

    Ritorna
    -------
    daily : pd.DataFrame
        Serie giornaliera con equity al M2M e rendimento giornaliero.
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
            "equity": float(row["equity"])
        })

    daily = df.groupby("date", as_index=False).apply(pick_m2m, include_groups=False)
    daily = daily.sort_values("timestamp").reset_index(drop=True)

    daily["equity"] = pd.to_numeric(daily["equity"], errors="coerce")
    daily["ret"] = daily["equity"].pct_change().fillna(0.0)

    return daily
