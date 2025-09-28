# utils/ibkr_client.py

from ib_insync import IB, Stock, MarketOrder, util
import pandas as pd


class IBKRClient:
    """
    Wrapper semplice per interagire con IBKR via ib_insync.

    Funzionalità principali:
    - Connessione al TWS / Gateway
    - Download storico (barre OHLCV aggregate)
    - Download tick-by-tick BID/ASK
    - Invio ordini di test (MarketOrder)
    """

    def __init__(self, host: str, port: int, client_id: int):
        """
        Inizializza e connette il client a IBKR.

        Parameters
        ----------
        host : str
            Indirizzo del server TWS o Gateway (tipicamente "127.0.0.1").
        port : int
            Porta (7496 = live, 7497 = paper).
        client_id : int
            Identificativo univoco del client (evita conflitti multipli).
        """
        self.host = host
        self.port = port
        self.client_id = client_id

        self.ib = IB()
        # Connessione immediata al server
        self.ib.connect(host, port, clientId=client_id)

    # -------------------------------------------------------------------------
    # HISTORICAL BARS
    # -------------------------------------------------------------------------
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        end_datetime: str,
        duration: str,
        bar_size: str
    ) -> pd.DataFrame:
        """
        Scarica barre storiche OHLCV da IBKR.

        Parameters
        ----------
        symbol : str
            Ticker (es. "SPY").
        exchange : str
            Es. "SMART".
        currency : str
            Es. "USD".
        end_datetime : str
            Data/ora di fine (formato 'YYYYMMDD HH:MM:SS').
        duration : str
            Durata (es. "2 D").
        bar_size : str
            Dimensione barra (es. "1 min").

        Returns
        -------
        pd.DataFrame
            DataFrame con colonne: ['date','open','high','low','close','volume'].
        """
        contract = Stock(symbol, exchange, currency)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_datetime,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",   # usa i prezzi dei trade
            useRTH=True,           # solo orari regolari di mercato
            formatDate=1
        )
        return util.df(bars)

    # -------------------------------------------------------------------------
    # HISTORICAL BID/ASK TICKS
    # -------------------------------------------------------------------------
    def get_historical_bidask_ticks(
        self,
        symbol: str,
        exchange: str = "SMART",
        currency: str = "USD",
        start_dt: str = None,
        end_dt: str = None,
        useRth: bool = True,
        batch_size: int = 1000
    ) -> pd.DataFrame:
        """
        Scarica tick storici BID/ASK da IBKR.

        Parameters
        ----------
        symbol : str
            Ticker (es. "SPY").
        exchange : str
            Borsa (es. "SMART").
        currency : str
            Valuta (es. "USD").
        start_dt : str
            Data/ora di inizio (formato 'YYYYMMDD HH:MM:SS').
        end_dt : str
            Data/ora di fine (formato 'YYYYMMDD HH:MM:SS').
        useRth : bool
            Se True, considera solo Regular Trading Hours.
        batch_size : int
            Numero massimo di tick per chiamata (limite IBKR ≈ 1000).

        Returns
        -------
        pd.DataFrame
            Colonne: ['timestamp','bid','ask','bid_size','ask_size'].
        """
        contract = Stock(symbol, exchange, currency)

        ticks = self.ib.reqHistoricalTicks(
            contract,
            startDateTime=start_dt,
            endDateTime=end_dt,
            numberOfTicks=batch_size,
            whatToShow="BID_ASK",
            useRth=useRth
        )

        records = []
        for t in ticks:
            records.append({
                "timestamp": pd.to_datetime(t.time).tz_localize(None),
                "bid": t.priceBid,
                "ask": t.priceAsk,
                "bid_size": t.sizeBid,
                "ask_size": t.sizeAsk
            })
        return pd.DataFrame(records)

    # -------------------------------------------------------------------------
    # PLACE ORDER
    # -------------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        exchange: str = "SMART",
        currency: str = "USD"
    ):
        """
        Invia un MarketOrder a IBKR.

        ⚠ Nota: Usare SOLO con account Paper se non si desidera
        mandare ordini reali sul mercato.

        Parameters
        ----------
        symbol : str
            Ticker (es. "AAPL").
        side : str
            Direzione ordine: "BUY" o "SELL".
        qty : int
            Quantità da negoziare.
        exchange : str
            Es. "SMART".
        currency : str
            Es. "USD".

        Returns
        -------
        ib_insync.Trade
            Oggetto Trade con lo stato dell'ordine.
        """
        contract = Stock(symbol, exchange, currency)
        action = "BUY" if side.upper() == "BUY" else "SELL"
        order = MarketOrder(action, qty)
        trade = self.ib.placeOrder(contract, order)
        return trade
