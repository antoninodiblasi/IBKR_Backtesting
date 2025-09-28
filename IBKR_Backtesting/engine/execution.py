# engine/execution.py
import pandas as pd


class ExecutionHandler:
    """
    Gestore di esecuzione ordini nel backtest.
    - Simula fill MARKET e LIMIT
    - Usa bid/ask reali se disponibili, altrimenti close
    - Applica slippage e commissioni
    - Aggiorna il portafoglio
    """

    def __init__(self, portfolio, slippage: float = 0.0, commission: float = 0.0,
                 impact_lambda: float = 0.0):
        """
        Parameters
        ----------
        portfolio : Portfolio
            Oggetto Portfolio.
        slippage : float
            Slippage percentuale (es. 0.001 = 0.1%).
        commission : float
            Commissione fissa per trade.
        impact_lambda : float
            Coefficiente di impatto lineare se qty > size disponibile.
        """
        self.portfolio = portfolio
        self.slippage = float(slippage)
        self.commission = float(commission)
        self.impact_lambda = float(impact_lambda)

    # -------------------------------------------------------------------------
    # HELPER: book dal bar
    # -------------------------------------------------------------------------
    def _extract_book(self, bar):
        """
        Ritorna best bid/ask e size dal bar, se disponibili.
        Se mancano, fallback su close con size grande.
        """
        bid = getattr(bar, "bid", None)
        ask = getattr(bar, "ask", None)
        bid_sz = getattr(bar, "bid_size", None)
        ask_sz = getattr(bar, "ask_size", None)

        if bid is None or ask is None:
            # fallback: usa close come mid → bid=ask=close
            bid = ask = float(bar.close)
            bid_sz = ask_sz = float(getattr(bar, "volume", 0.0) or 1e6)

        return float(bid), float(ask), float(bid_sz), float(ask_sz)

    # -------------------------------------------------------------------------
    # ESECUZIONE ORDINI
    # -------------------------------------------------------------------------
    def execute_order(self, symbol: str, order, bar):
        """
        Simula l'esecuzione di un ordine in base ai dati della barra e (se presenti) del book.
        - MARKET → esecuzione sempre al best bid/ask ± slippage e impatto di mercato.
        - LIMIT  → esecuzione solo se livello limite è compatibile con il book.
        """

        # Estraggo book dal bar o fallback a prezzi OHLC
        bid, ask, bid_sz, ask_sz = self._extract_book(bar)
        if pd.isna(bid) or pd.isna(ask):
            bid = ask = float(getattr(bar, "close", 0.0))
            bid_sz = ask_sz = float("inf")

        exec_price = None
        filled = False

        side = order.side.upper()
        otype = order.order_type.upper()
        qty = int(order.qty)

        # ------------------------- MARKET -------------------------
        if otype == "MARKET":
            if side == "BUY":
                base_px = ask * (1 + self.slippage)
                overflow = max(0, qty - ask_sz)
                impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                exec_price = base_px * (1 + impact)
                filled = True
            else:  # SELL
                base_px = bid * (1 - self.slippage)
                overflow = max(0, qty - bid_sz)
                impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                exec_price = base_px * (1 - impact)
                filled = True

        # ------------------------- LIMIT -------------------------
        elif otype == "LIMIT":
            lim = float(order.price)

            if side == "BUY" and lim >= bid:
                base_px = min(lim, ask)  # non pagare oltre ask
                overflow = max(0, qty - ask_sz)
                impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                exec_price = base_px * (1 + self.slippage) * (1 + impact)
                filled = True

            elif side == "SELL" and lim <= ask:
                base_px = max(lim, bid)  # non vendere sotto bid
                overflow = max(0, qty - bid_sz)
                impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                exec_price = base_px * (1 - self.slippage) * (1 - impact)
                filled = True

        # ------------------------- FILL -------------------------
        if filled and exec_price is not None:
            exec_price = float(exec_price)

            # aggiorna portafoglio
            self.portfolio.apply_fill(
                symbol=symbol,
                side=side,
                qty=qty,
                price=exec_price,
                ts=bar.timestamp
            )

            # applica commissione
            if self.commission > 0:
                self.portfolio.cash -= self.commission

            # snapshot equity
            equity_snapshot = self.portfolio.snapshot_equity(
                {symbol: float(getattr(bar, "close", exec_price))}, bar.timestamp
            )

            # ------------------------- LOG -------------------------
            pos = self.portfolio.get_position(symbol)
            avg_px = getattr(self.portfolio, "avg_price", {}).get(symbol, 0.0)

            print("\n" + "-" * 78)
            print(f"[FILL] {bar.timestamp} | {side} {qty} {symbol} | {otype}")
            print(f"       Exec Price : {exec_price:.4f}")
            print(f"       Book       : BID {bid:.4f} x {bid_sz:.0f} | ASK {ask:.4f} x {ask_sz:.0f}")
            print(f"       Bar        : O={bar.open:.4f} H={bar.high:.4f} "
                  f"L={bar.low:.4f} C={bar.close:.4f} Vol={bar.volume}")
            print(f"       Position   : {pos} @ AvgPx={avg_px:.4f}")
            print(f"       Cash       : {self.portfolio.cash:.2f}")
            print(f"       Equity     : {equity_snapshot['equity']:.2f}")
            print("-" * 78)

        return filled, exec_price
