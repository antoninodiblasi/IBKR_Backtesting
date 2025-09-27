# utils/performance.py
import pandas as pd
import numpy as np

def compute_performance(portfolio_history, initial_cash):
    """
    Calcola le metriche di performance a partire dallo storico del portafoglio.

    Parameters
    ----------
    portfolio_history : list
        Lista di operazioni / snapshot registrate dal Portfolio.
        Ogni elemento deve contenere:
        ["symbol", "side", "qty", "price", "cash", "timestamp"]
    initial_cash : float
        Capitale iniziale (baseline per il calcolo del rendimento).

    Returns
    -------
    df : pandas.DataFrame
        DataFrame con lo storico del portafoglio e colonne aggiuntive:
        - equity  : valore del portafoglio (in questo caso = cash, quindi semplificato)
        - returns : rendimento percentuale bar-to-bar
    metrics : dict
        Dizionario con metriche aggregate:
        - Total Return %  : rendimento cumulato
        - Volatility %    : deviazione standard annualizzata dei rendimenti
        - Sharpe Ratio    : rapporto rischio/rendimento (ann.)
        - Max Drawdown %  : drawdown massimo cumulativo
    """
    # Convertiamo lo storico in DataFrame con colonne ben definite
    df = pd.DataFrame(
        portfolio_history,
        columns=["symbol", "side", "qty", "price", "cash", "timestamp"]
    )

    # NB: qui equity = cash → non considera posizioni mark-to-market.
    # Nel nuovo motore con snapshot_equity usiamo un approccio più realistico.
    df["equity"] = df["cash"]

    # Rendimenti percentuali bar-to-bar
    df["returns"] = df["equity"].pct_change().fillna(0)

    # Rendimento totale
    total_return = (df["equity"].iloc[-1] / initial_cash - 1) * 100

    # Volatilità annualizzata (252 giorni di trading come convenzione)
    volatility = df["returns"].std() * np.sqrt(252)

    # Sharpe ratio annualizzato (risk-free = 0)
    sharpe = (
        df["returns"].mean() / df["returns"].std() * np.sqrt(252)
        if df["returns"].std() != 0 else 0
    )

    # Calcolo drawdown massimo
    cumulative = (1 + df["returns"]).cumprod()
    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    max_drawdown = drawdown.min() * 100

    # Pacchetto finale di metriche
    metrics = {
        "Total Return %": round(total_return, 3),
        "Volatility %": round(volatility * 100, 3),  # % annualizzata
        "Sharpe Ratio": round(sharpe, 3),
        "Max Drawdown %": round(max_drawdown, 3)
    }

    return df, metrics
