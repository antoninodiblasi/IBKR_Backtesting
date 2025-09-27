# utils/data_handler.py
import pandas as pd

def prepare_dataframe(df):
    """
    Adatta un DataFrame scaricato da IBKR (via ib_insync) al formato
    richiesto dal BacktestEngine.

    Parametri
    ---------
    df : pandas.DataFrame
        DataFrame originario di IBKR con colonne tipiche:
        ['date', 'open', 'high', 'low', 'close', 'volume'].

    Ritorna
    -------
    pandas.DataFrame
        DataFrame con colonne standardizzate:
        ['timestamp','open','high','low','close','volume'],
        ordinato temporalmente e con timestamp in formato datetime.
    """
    # Rinominiamo la colonna 'date' in 'timestamp'
    # (le altre colonne hanno già i nomi che ci servono)
    df = df.rename(columns={
        "date": "timestamp",
        "open": "open",    # ridondante ma lascia esplicito il mapping
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume"
    })

    # Conversione esplicita a datetime (IBKR può restituire stringhe)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Ordiniamo per timestamp per sicurezza (anche se IBKR di solito fornisce già ordinato)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Ritorniamo solo le colonne richieste dal framework
    return df[["timestamp", "open", "high", "low", "close", "volume"]]
