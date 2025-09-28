# utils/data_handler.py
import pandas as pd


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte un DataFrame IBKR (via ib_insync) nel formato richiesto dal BacktestEngine.

    Parametri
    ---------
    df : pd.DataFrame
        Dati storici originari IBKR (tipici campi: ['date','open','high','low','close','volume']).

    Ritorna
    -------
    pd.DataFrame
        DataFrame con colonne standardizzate:
        ['timestamp','open','high','low','close','volume'],
        ordinato cronologicamente e con timestamp tz-naive.
    """
    if df.empty:
        return pd.DataFrame(columns=["timestamp","open","high","low","close","volume"])

    # Mapping esplicito (IBKR usa 'date')
    rename_map = {
        "date": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    }
    df = df.rename(columns=rename_map)

    # Parsing datetime e rimozione timezone per coerenza
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["timestamp"] = df["timestamp"].dt.tz_localize(None)

    # Ordina e reset index
    df = df.sort_values("timestamp").reset_index(drop=True)

    return df[["timestamp","open","high","low","close","volume"]]


def merge_bidask_to_bars(bars_df: pd.DataFrame, ticks_df: pd.DataFrame,
                         on_col: str = "timestamp",
                         direction: str = "backward",
                         tolerance: str = "5min") -> pd.DataFrame:
    """
    Allinea i tick BID/ASK a ciascuna barra (es. 1m OHLCV) usando merge_asof.

    Parameters
    ----------
    bars_df : pd.DataFrame
        DataFrame con barre OHLCV (output di prepare_dataframe).
    ticks_df : pd.DataFrame
        DataFrame con tick bid/ask scaricati da IBKR (colonne:
        ['timestamp','bid','ask','bid_size','ask_size']).
    on_col : str
        Colonna di merge (default 'timestamp').
    direction : str
        'backward' = ultimo tick <= timestamp della barra.
    tolerance : str
        Finestra massima per associare un tick (es. "5min").

    Returns
    -------
    pd.DataFrame
        DataFrame OHLCV con colonne aggiuntive bid/ask/bid_size/ask_size + mid.
    """
    if bars_df.empty:
        return bars_df
    if ticks_df.empty:
        out = bars_df.copy()
        for c in ["bid","ask","bid_size","ask_size","mid"]:
            out[c] = pd.NA
        return out

    bars = bars_df.copy()
    ticks = ticks_df.copy()

    # Normalizza timestamp
    bars[on_col] = pd.to_datetime(bars[on_col])
    ticks[on_col] = pd.to_datetime(ticks[on_col])
    bars = bars.sort_values(on_col)
    ticks = ticks.sort_values(on_col)

    # Merge asof: abbina ultimo tick disponibile a ogni barra
    merged = pd.merge_asof(
        left=bars,
        right=ticks[["timestamp","bid","ask","bid_size","ask_size"]],
        on=on_col,
        direction=direction,
        tolerance=pd.Timedelta(tolerance)
    )

    # Aggiungi mid
    merged["mid"] = merged[["bid","ask"]].mean(axis=1)

    return merged
