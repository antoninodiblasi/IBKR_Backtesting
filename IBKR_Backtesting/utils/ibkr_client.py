# utils/ibkr_client.py

from ib_insync import IB, Stock, MarketOrder, util
import pandas as pd


class IBKRClient:
    """
    Wrapper semplice per interagire con IBKR via ib_insync.

    Funzionalità principali:
    - Connessione a TWS / Gateway
    - Download storico barre OHLCV
    - Download tick-by-tick BID/ASK
    - Invio ordini Market di test

    Note multi-asset
    ----------------
    - I metodi accettano un singolo symbol.
    - In una strategia multi-asset si devono chiamare in loop
      per ciascun ticker definito in strategy.get_config()["symbols"].
    - Tutti i parametri operativi (exchange, currency, bar_size, duration, ecc.)
      vanno definiti nella strategia, non hard-coded qui.
    """

    def __init__(self, host: str, port: int, client_id: int):
        """
        Inizializza e connette il client a IBKR.

        I parametri host/port/client_id devono arrivare da strategy.get_config()
        in modo che siano modificabili per ogni strategia senza toccare il backend.
        """
        self.host = host
        self.port = port
        self.client_id = client_id

        self.ib = IB()
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
        bar_size: str,
        what_to_show: str = "TRADES",
        use_rth: bool = True
    ) -> pd.DataFrame:
        """
        Scarica barre storiche OHLCV da IBKR.

        Tutti i parametri (exchange, currency, bar_size, duration, use_rth, ecc.)
        vanno forniti dalla strategia tramite get_config().

        Returns
        -------
        pd.DataFrame con colonne:
        ['date','open','high','low','close','volume'].
        """
        contract = Stock(symbol, exchange, currency)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_datetime,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=use_rth,
            formatDate=1
        )
        return util.df(bars)

    # -------------------------------------------------------------------------
    # HISTORICAL BID/ASK TICKS
    # -------------------------------------------------------------------------
    def get_historical_bidask_ticks(
        self,
        symbol: str,
        exchange: str,
        currency: str,
        start_dt: str,
        end_dt: str,
        use_rth: bool,
        batch_size: int
    ) -> pd.DataFrame:
        """
        Scarica tick storici BID/ASK da IBKR.

        Anche qui i parametri (exchange, currency, date range, use_rth, batch_size)
        devono arrivare dalla strategia.

        Returns
        -------
        pd.DataFrame con colonne:
        ['timestamp','bid','ask','bid_size','ask_size'].
        """
        contract = Stock(symbol, exchange, currency)
        ticks = self.ib.reqHistoricalTicks(
            contract,
            startDateTime=start_dt,
            endDateTime=end_dt,
            numberOfTicks=batch_size,
            whatToShow="BID_ASK",
            useRth=use_rth
        )

        records = [
            {
                "timestamp": pd.to_datetime(t.time).tz_localize(None),
                "bid": t.priceBid,
                "ask": t.priceAsk,
                "bid_size": t.sizeBid,
                "ask_size": t.sizeAsk
            }
            for t in ticks
        ]
        return pd.DataFrame(records)

    # -------------------------------------------------------------------------
    # PLACE ORDER
    # -------------------------------------------------------------------------
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: int,
        exchange: str,
        currency: str
    ):
        """
        Invia un MarketOrder a IBKR.

        ⚠ Usare SOLO con account Paper per non inviare ordini reali.

        Anche exchange/currency vanno presi da strategy.get_config().
        """
        contract = Stock(symbol, exchange, currency)
        action = "BUY" if side.upper() == "BUY" else "SELL"
        order = MarketOrder(action, qty)
        trade = self.ib.placeOrder(contract, order)
        return trade
