class Portfolio:
    """
    Rappresenta il portafoglio durante il backtest.

    Tiene traccia di:
    - liquidità disponibile (cash)
    - posizioni aperte per simbolo (quantità e prezzo medio di carico)
    - storico dettagliato delle operazioni eseguite
    - equity mark-to-market tramite snapshot
    """

    def __init__(self, cash: float = 0.0, base_currency: str = "USD"):
        """
        Parameters
        ----------
        cash : float
            Capitale iniziale disponibile.
        base_currency : str
            Valuta di riferimento del portafoglio (default: "USD").
        """
        self.cash = float(cash)
        self.base_currency = base_currency

        # Dizionario delle posizioni correnti
        # symbol -> qty netta
        self.positions: dict[str, int] = {}

        # Prezzo medio di carico per ogni simbolo
        # symbol -> avg price
        self.avg_price: dict[str, float] = {}

        # Storico di tutte le operazioni (ogni fill applicato)
        self.history: list[dict] = []

    # -------------------------------------------------------------------------
    # METODI PUBBLICI
    # -------------------------------------------------------------------------

    def get_position(self, symbol: str) -> int:
        """
        Restituisce la quantità netta detenuta su un simbolo.
        """
        return int(self.positions.get(symbol, 0))

    def mark_to_market(self, prices: dict[str, float]) -> float:
        """
        Calcola l'equity mark-to-market = cash + valore posizioni aperte.

        Parameters
        ----------
        prices : dict
            Mappa {symbol: price} con i prezzi correnti.

        Returns
        -------
        float
            Equity corrente mark-to-market.
        """
        equity = self.cash
        for sym, qty in self.positions.items():
            px = prices.get(sym)
            if px is not None:
                equity += qty * px
        return equity

    def apply_fill(self, symbol: str, side: str, qty: int, price: float, ts):
        """
        Aggiorna lo stato del portafoglio in seguito a un'esecuzione (fill).

        Parameters
        ----------
        symbol : str
            Nome/ticker del titolo.
        side : str
            Direzione: "BUY" o "SELL".
        qty : int
            Quantità eseguita.
        price : float
            Prezzo di esecuzione.
        ts : datetime
            Timestamp del fill.
        """
        # Normalizziamo il lato
        side = side.upper()
        signed_qty = qty if side == "BUY" else -qty

        # Recupero posizione precedente e prezzo medio
        prev_qty = self.positions.get(symbol, 0)
        prev_avg = self.avg_price.get(symbol, 0.0)

        # Nuova quantità netta dopo l'operazione
        new_qty = prev_qty + signed_qty

        # ------------------- Aggiornamento cash -------------------
        # BUY: cash diminuisce
        # SELL: cash aumenta
        trade_cash = -signed_qty * price
        self.cash += trade_cash

        # ------------------- Prezzo medio -------------------------
        if new_qty != 0:
            if prev_qty == 0:
                # Apertura di una nuova posizione
                new_avg = price
            elif (prev_qty > 0 and signed_qty > 0) or (prev_qty < 0 and signed_qty < 0):
                # Aumento della posizione esistente (stesso segno)
                new_avg = (prev_avg * abs(prev_qty) + price * abs(signed_qty)) / abs(new_qty)
            else:
                # Riduzione della posizione: mantieni lo stesso avg
                new_avg = prev_avg
            self.avg_price[symbol] = new_avg
        else:
            # Posizione chiusa → reset prezzo medio
            self.avg_price[symbol] = 0.0

        # Aggiorno la posizione netta
        self.positions[symbol] = new_qty

        # ------------------- Realized PnL -------------------------
        realized_pnl = 0.0
        if prev_qty != 0 and ((prev_qty > 0 and signed_qty < 0) or (prev_qty < 0 and signed_qty > 0)):
            # Sto chiudendo (parzialmente o totalmente) una posizione
            close_qty = min(abs(prev_qty), abs(signed_qty))
            # PnL = quantità chiusa * differenza prezzo * direzione
            realized_pnl = close_qty * (price - prev_avg) * (1 if prev_qty > 0 else -1)

        # ------------------- Storico ------------------------------
        self.history.append({
            "timestamp": ts,
            "symbol": symbol,
            "side": side,
            "qty": int(qty),
            "price": float(price),
            "cash": float(self.cash),
            "position": int(new_qty),
            "avg_price": float(self.avg_price[symbol]),
            "realized_pnl": float(realized_pnl),
        })

    def snapshot_equity(self, prices: dict[str, float], ts):
        """
        Restituisce uno snapshot dello stato del portafoglio.

        Parameters
        ----------
        prices : dict
            Prezzi correnti {symbol: price}.
        ts : datetime
            Momento dello snapshot.

        Returns
        -------
        dict
            Con:
            - timestamp
            - equity (cash + valore posizioni)
            - cash
            - positions (copia)
        """
        eq = self.mark_to_market(prices)
        return {
            "timestamp": ts,
            "equity": eq,
            "cash": self.cash,
            "positions": dict(self.positions),  # copia
        }

    def __repr__(self):
        """
        Rappresentazione leggibile del portafoglio.
        Mostra cash e posizioni correnti.
        """
        return f"Portfolio(cash={self.cash:.2f}, positions={self.positions})"
