# engine/order.py

class Order:
    """
    Rappresenta un ordine generato dalla strategia.
    Supporta sia MARKET che LIMIT orders, con informazioni base per il backtest.
    """

    def __init__(self, side, qty, price=None, timestamp=None, order_type="MARKET"):
        """
        Parameters
        ----------
        side : str
            Direzione dell'ordine: "BUY" o "SELL".
        qty : int or float
            Quantità (numero di azioni, contratti, ecc.).
        price : float, optional
            Prezzo limite dell'ordine. Usato solo se order_type="LIMIT".
        timestamp : datetime, optional
            Momento in cui l'ordine viene generato (utile per logging e plotting).
        order_type : str
            Tipo di ordine: "MARKET" o "LIMIT".
            - MARKET: eseguito al prezzo della barra (con slippage).
            - LIMIT: eseguito solo se il mercato tocca il prezzo specificato.
        """
        self.side = side                  # "BUY" o "SELL"
        self.qty = qty                    # quantità
        self.price = price                # usato solo per LIMIT order
        self.timestamp = timestamp        # assegnato quando la strategia lo genera
        self.order_type = order_type      # default = "MARKET"

    def __repr__(self):
        """
        Rappresentazione testuale utile per debug e logging.
        """
        return (
            f"Order(type={self.order_type}, side={self.side}, "
            f"qty={self.qty}, price={self.price}, time={self.timestamp})"
        )
