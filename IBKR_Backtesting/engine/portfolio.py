# engine/portfolio.py

class Portfolio:
    """
    Rappresenta il portafoglio durante il backtest.
    Tiene traccia di:
    - cash disponibile
    - posizioni aperte (per simbolo)
    - storico delle operazioni eseguite
    - equity mark-to-market tramite snapshot
    """

    def __init__(self, cash):
        """
        Parameters
        ----------
        cash : float
            Capitale iniziale disponibile.
        """
        self.cash = cash
        self.positions = {}   # dict {symbol: qty} → quantità netta per ogni titolo
        self.history = []     # lista di dict → log delle operazioni eseguite

    def update_position(self, symbol, qty, price, side, timestamp=None):
        """
        Aggiorna il portafoglio in seguito a un'esecuzione d'ordine.

        Parameters
        ----------
        symbol : str
            Nome/ticker del titolo.
        qty : int or float
            Quantità eseguita.
        price : float
            Prezzo di esecuzione.
        side : str
            "BUY" o "SELL".
        timestamp : datetime, optional
            Momento dell'operazione.
        """
        if side == "BUY":
            # comprare riduce il cash ed aumenta la posizione netta
            self.cash -= qty * price
            self.positions[symbol] = self.positions.get(symbol, 0) + qty
        elif side == "SELL":
            # vendere aumenta il cash e riduce la posizione netta
            self.cash += qty * price
            self.positions[symbol] = self.positions.get(symbol, 0) - qty

        # registriamo l’operazione nello storico
        self.history.append({
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "cash": self.cash,
            "timestamp": timestamp
        })

    def snapshot_equity(self, prices, timestamp):
        """
        Calcola lo stato completo del portafoglio in un dato momento.

        Parameters
        ----------
        prices : dict
            Mappa {symbol: price} con i prezzi correnti.
        timestamp : datetime
            Momento dello snapshot.

        Returns
        -------
        dict
            Stato del portafoglio con:
            - timestamp
            - equity (cash + valore mark-to-market delle posizioni aperte)
            - cash
            - positions (copia del dict delle posizioni)
        """
        # equity = cash + somma di (qty * prezzo corrente) per ogni titolo
        portfolio_value = self.cash
        for symbol, qty in self.positions.items():
            if symbol in prices:
                portfolio_value += qty * prices[symbol]

        return {
            "timestamp": timestamp,
            "equity": portfolio_value,
            "cash": self.cash,
            "positions": dict(self.positions)  # copia per evitare mutazioni future
        }

    def __repr__(self):
        """
        Rappresentazione leggibile del portafoglio.
        Mostra cash e posizioni correnti.
        """
        return f"Portfolio(cash={self.cash}, positions={self.positions})"
