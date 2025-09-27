# utils/ibkr_client.py
from ib_insync import *

class IBKRClient:
    """
    Wrapper minimale per interagire con IBKR via ib_insync.
    Gestisce:
    - connessione al TWS / Gateway
    - download storico (historical data)
    - invio ordini di test (solo MarketOrder in questa versione)
    """

    def __init__(self, host, port, client_id):
        """
        Parameters
        ----------
        host : str
            Indirizzo del server TWS o Gateway (tipicamente "127.0.0.1").
        port : int
            Porta di connessione (7496 = live, 7497 = paper).
        client_id : int
            Identificativo univoco per la sessione (evita conflitti se ci sono più client).
        """
        self.ib = IB()
        # Connessione immediata al server
        self.ib.connect(host, port, clientId=client_id)

    def get_historical_data(self, symbol, exchange, currency, end_datetime, duration, bar_size):
        """
        Scarica dati storici da IBKR per un certo strumento.

        Args:
            symbol (str): ticker (es. "SPY")
            exchange (str): es. "SMART"
            currency (str): es. "USD"
            end_datetime (str): data/ora di fine (formato 'YYYYMMDD HH:MM:SS')
            duration (str): durata (es. '2 D')
            bar_size (str): dimensione barre (es. '1 min')
        """
        contract = Stock(symbol, exchange, currency)
        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime=end_datetime,  # <<< adesso obbligatorio
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        return util.df(bars)
    def place_order(self, symbol, side, qty, exchange, currency):
        """
        Invia un ordine al server IBKR (default = MarketOrder).
        ⚠ Usare solo con account Paper se non si vuole mandare ordini reali.

        Parameters
        ----------
        symbol : str
            Ticker (es. "AAPL").
        side : str
            Direzione: "BUY" o "SELL".
        qty : int or float
            Quantità da comprare/vendere.
        exchange : str
            Borsa (es. "SMART").
        currency : str
            Valuta (es. "USD").

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
