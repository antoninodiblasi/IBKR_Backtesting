# engine/execution.py

class ExecutionHandler:
    """
    Gestore di esecuzione ordini nel backtest.
    Simula il comportamento del mercato (fill, slippage, commissioni) e aggiorna il portafoglio.
    """

    def __init__(self, portfolio, slippage=0.0, commission=0.0):
        """
        Parameters
        ----------
        portfolio : Portfolio
            Oggetto Portfolio che mantiene cash, posizioni e storico.
        slippage : float
            Percentuale di slippage (es. 0.001 = 0.1%) applicata al prezzo di esecuzione.
        commission : float
            Commissione fissa per ogni trade (in unità monetaria, non %).
        """
        self.portfolio = portfolio
        self.slippage = slippage
        self.commission = commission

    def execute_order(self, symbol, order, bar):
        """
        Simula l'esecuzione di un ordine in base ai dati della barra.

        Parameters
        ----------
        symbol : str
            Nome/ticker del sottostante.
        order : Order
            Oggetto ordine con attributi: side (BUY/SELL), qty, price, order_type.
        bar : pandas.NamedTuple
            Barra del mercato con campi tipici: timestamp, open, high, low, close, volume.

        Returns
        -------
        filled : bool
            True se l'ordine è stato eseguito, False altrimenti.
        exec_price : float or None
            Prezzo a cui è stato eseguito l'ordine, None se non eseguito.
        """
        exec_price = None
        filled = False

        if order.order_type == "MARKET":
            # MARKET order → eseguito sempre al close della barra ± slippage
            if order.side == "BUY":
                exec_price = bar.close * (1 + self.slippage)
            else:  # SELL
                exec_price = bar.close * (1 - self.slippage)
            filled = True

        elif order.order_type == "LIMIT":
            # LIMIT order → eseguito solo se i prezzi della barra toccano il livello limite
            if order.side == "BUY" and bar.low <= order.price:
                exec_price = order.price
                filled = True
            elif order.side == "SELL" and bar.high >= order.price:
                exec_price = order.price
                filled = True

        # Se l’ordine è stato eseguito aggiorniamo il portafoglio
        if filled:
            self.portfolio.update_position(
                symbol, order.qty, exec_price, order.side, timestamp=bar.timestamp
            )

            # Commissione fissa per trade (sottratta dal cash disponibile)
            if self.commission > 0:
                self.portfolio.cash -= self.commission

        return filled, exec_price
