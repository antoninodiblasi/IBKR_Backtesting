# engine/execution.py
from __future__ import annotations

import pandas as pd
from typing import Any


class ExecutionHandler:
    """
    Gestore esecuzione ordini nel backtest.
    - Supporta MARKET e LIMIT
    - Usa bid/ask se disponibili, altrimenti fallback su close
    - Slippage, commissioni e impatto lineare
    - Multi-asset: symbol preso direttamente da order.symbol
    Nota:
    - Lo snapshot equity completo non viene più fatto qui, ma in BacktestEngine.
    """

    def __init__(self, portfolio, slippage: float = 0.0,
                 commission: float = 0.0, impact_lambda: float = 0.0) -> None:
        # Portafoglio condiviso
        self.portfolio = portfolio

        # Parametri di esecuzione (dovrebbero arrivare da strategy.get_config)
        self.slippage = float(slippage)
        self.commission = float(commission)
        self.impact_lambda = float(impact_lambda)

    # -----------------------------------------------------------------
    # HELPER: estrazione book
    # -----------------------------------------------------------------
    @staticmethod
    def _extract_book(bar: Any) -> tuple[float, float, float, float]:
        """
        Ritorna best bid/ask e size.
        Se non disponibili → fallback su close con size enorme.
        """
        bid = getattr(bar, "bid", None)
        ask = getattr(bar, "ask", None)
        bid_sz = getattr(bar, "bid_size", None)
        ask_sz = getattr(bar, "ask_size", None)

        if bid is None or ask is None:
            close_px = float(getattr(bar, "close", 0.0))
            bid = ask = close_px
            bid_sz = ask_sz = float(getattr(bar, "volume", 0.0) or 1e9)

        return float(bid), float(ask), float(bid_sz), float(ask_sz)

    # -----------------------------------------------------------------
    # ESECUZIONE ORDINI
    # -----------------------------------------------------------------
    def execute_order(self, order, bar: Any) -> tuple[bool, float | None]:
        """
        Simula l’esecuzione di un ordine su una singola barra.
        Restituisce (filled, exec_price).

        Parametri
        ---------
        order : Order
            L'ordine da eseguire (symbol, side, qty, order_type, price opzionale).
        bar : Any
            Barra dati (deve avere almeno: timestamp, close, bid, ask, bid_size, ask_size).

        Ritorna
        -------
        (filled: bool, exec_price: float | None)
        """
        # Estrai bid/ask dal bar (o fallback su close)
        bid, ask, bid_sz, ask_sz = self._extract_book(bar)
        if pd.isna(bid) or pd.isna(ask):
            px = float(getattr(bar, "close", 0.0))
            bid = ask = px
            bid_sz = ask_sz = 1e9  # praticamente liquidità infinita

        side = order.side.upper()
        otype = order.order_type.upper()
        qty = int(order.qty)
        qty_f = float(qty)

        exec_price = None
        filled = False

        # ==============================================================
        # MARKET ORDERS
        # ==============================================================
        if otype == "MARKET":
            # Se l'ordine ha già un prezzo imposto → usalo
            if order.price is not None:
                exec_price = float(order.price)
                filled = True
            else:
                # Altrimenti calcola dal book
                if side == "BUY":
                    base_px = ask * (1 + self.slippage)
                    overflow = max(0.0, qty_f - ask_sz)
                    impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                    exec_price = base_px * (1 + impact)
                    filled = True
                elif side == "SELL":
                    base_px = bid * (1 - self.slippage)
                    overflow = max(0.0, qty_f - bid_sz)
                    impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                    exec_price = base_px * (1 - impact)
                    filled = True

        # ==============================================================
        # LIMIT ORDERS
        # ==============================================================
        elif otype == "LIMIT":
            lim = float(order.price)
            if side == "BUY" and lim >= bid:
                base_px = min(lim, ask)
                overflow = max(0.0, qty_f - ask_sz)
                impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                exec_price = base_px * (1 + self.slippage) * (1 + impact)
                filled = True
            elif side == "SELL" and lim <= ask:
                base_px = max(lim, bid)
                overflow = max(0.0, qty_f - bid_sz)
                impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                exec_price = base_px * (1 - self.slippage) * (1 - impact)
                filled = True

        # ==============================================================
        # APPLY FILL
        # ==============================================================
        if filled and exec_price is not None:
            exec_price = float(exec_price)
            symbol = getattr(order, "symbol")

            # Aggiorna portafoglio
            self.portfolio.apply_fill(
                symbol=symbol,
                side=side,
                qty=qty,
                price=exec_price,
                ts=order.timestamp or bar.timestamp,
            )

            # Commissione fissa per trade
            if self.commission > 0.0:
                self.portfolio.cash -= self.commission

            # Log di debug
            pos = self.portfolio.get_position(symbol)
            avg_px = self.portfolio.get_avg_price(symbol)
            print(f"[FILL] {order.timestamp or bar.timestamp} | {side} {qty} {symbol} @ {exec_price:.4f} ({otype})")
            print(f"       Book: BID {bid:.4f} x {bid_sz:.0f} | ASK {ask:.4f} x {ask_sz:.0f}")
            print(f"       Position: {pos} @ AvgPx={avg_px:.4f} | Cash={self.portfolio.cash:.2f}")

        return filled, exec_price
