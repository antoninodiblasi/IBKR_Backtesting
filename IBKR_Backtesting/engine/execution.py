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
    - Multi-asset: simbolo preso direttamente da order.symbol
    """

    def __init__(self, portfolio, slippage: float = 0.0, commission: float = 0.0,
                 impact_lambda: float = 0.0) -> None:
        self.portfolio = portfolio
        self.slippage = float(slippage)
        self.commission = float(commission)
        self.impact_lambda = float(impact_lambda)

    # -------------------------------------------------------------------------
    # HELPER: estrazione book
    # -------------------------------------------------------------------------
    @staticmethod
    def _extract_book(bar: Any) -> tuple[float, float, float, float]:
        """
        Ritorna best bid/ask e relative size.
        Se mancanti → fallback su close con size grandi.
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

    # -------------------------------------------------------------------------
    # ESECUZIONE ORDINI
    # -------------------------------------------------------------------------
    def execute_order(self, order, bar: Any) -> tuple[bool, float | None]:
        """
        Simula esecuzione ordine in base al book della barra.
        Restituisce (filled, exec_price).
        """
        bid, ask, bid_sz, ask_sz = self._extract_book(bar)

        # fallback se valori NaN
        if pd.isna(bid) or pd.isna(ask):
            px = float(getattr(bar, "close", 0.0))
            bid = ask = px
            bid_sz = ask_sz = 1e9

        exec_price: float | None = None
        filled = False

        side = order.side.upper()
        otype = order.order_type.upper()

        qty_int = int(order.qty)
        qty_f = float(qty_int)

        # ------------------------- MARKET -------------------------
        if otype == "MARKET":
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

        # ------------------------- LIMIT -------------------------
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

        # ------------------------- FILL -------------------------
        if filled and exec_price is not None:
            exec_price = float(exec_price)
            symbol = getattr(order, "symbol")

            # Aggiorna portafoglio
            self.portfolio.apply_fill(
                symbol=symbol,
                side=side,
                qty=qty_int,
                price=exec_price,
                ts=bar.timestamp
            )

            # Commissione
            if self.commission > 0.0:
                self.portfolio.cash -= self.commission

            # Snapshot equity immediato con il prezzo corrente
            mkt_price = float(getattr(bar, "close", exec_price))
            equity_snapshot = self.portfolio.snapshot({symbol: mkt_price}, bar.timestamp)

            # ------------------------- LOG -------------------------
            pos = self.portfolio.get_position(symbol)
            avg_px = self.portfolio.get_avg_price(symbol)

            print("\n" + "-" * 78)
            print(f"[FILL] {bar.timestamp} | {side} {qty_int} {symbol} | {otype}")
            print(f"       Exec Price : {exec_price:.4f}")
            print(f"       Book       : BID {bid:.4f} x {bid_sz:.0f} | ASK {ask:.4f} x {ask_sz:.0f}")
            print(f"       Bar        : O={float(bar.open):.4f} H={float(bar.high):.4f} "
                  f"L={float(bar.low):.4f} C={float(bar.close):.4f} Vol={float(bar.volume)}")
            print(f"       Position   : {pos} @ AvgPx={avg_px:.4f}")
            print(f"       Cash       : {self.portfolio.cash:.2f}")
            print(f"       Equity     : {equity_snapshot['equity']:.2f}")
            print("-" * 78)

        return filled, exec_price
