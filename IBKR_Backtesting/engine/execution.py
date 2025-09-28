# engine/execution.py
from __future__ import annotations

import pandas as pd
from typing import Any


class ExecutionHandler:
    """
    Gestore di esecuzione ordini nel backtest.
    - Supporto MARKET e LIMIT
    - Usa bid/ask se disponibili, altrimenti fallback su close
    - Slippage, commissioni e impatto lineare
    - Multi-asset: il simbolo si legge da order.symbol
    """

    def __init__(self, portfolio, slippage: float = 0.0, commission: float = 0.0,
                 impact_lambda: float = 0.0) -> None:
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
    @staticmethod
    def _extract_book(bar: Any) -> tuple[float, float, float, float]:
        """
        Ritorna best bid/ask e relative size. Se mancano, fallback su close e size grandi.
        """
        bid = getattr(bar, "bid", None)
        ask = getattr(bar, "ask", None)
        bid_sz = getattr(bar, "bid_size", None)
        ask_sz = getattr(bar, "ask_size", None)

        if bid is None or ask is None:
            # Fallback: usa close come proxy per mid → bid=ask=close
            close_px = float(getattr(bar, "close", 0.0))
            bid = ask = close_px
            # Size grandi per evitare overflow artificiale
            bid_sz = ask_sz = float(getattr(bar, "volume", 0.0) or 1e9)

        return float(bid), float(ask), float(bid_sz), float(ask_sz)

    # -------------------------------------------------------------------------
    # ESECUZIONE ORDINI (multi-asset)
    # -------------------------------------------------------------------------
    def execute_order(self, order, bar: Any) -> tuple[bool, float | None]:
        """
        Simula l'esecuzione di un ordine in base alla barra corrente.
        - MARKET → esecuzione al best con slippage e impatto.
        - LIMIT  → esecuzione solo se compatibile con il book.
        Ritorna (filled, exec_price).
        """

        # Estrazione book o fallback
        bid, ask, bid_sz, ask_sz = self._extract_book(bar)
        if pd.isna(bid) or pd.isna(ask):
            px = float(getattr(bar, "close", 0.0))
            bid = ask = px
            bid_sz = ask_sz = 1e9  # size molto grandi per evitare overflow

        exec_price: float | None = None
        filled = False

        side = order.side.upper()
        otype = order.order_type.upper()

        # qty come int per il portafoglio, ma float per confronti con size float
        qty_int = int(order.qty)
        qty_f = float(qty_int)

        # ------------------------- MARKET -------------------------
        if otype == "MARKET":
            if side == "BUY":
                base_px = ask * (1.0 + self.slippage)
                overflow = max(0.0, qty_f - ask_sz)  # 0.0 evita warning int/float
                impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                exec_price = base_px * (1.0 + impact)
                filled = True
            else:  # SELL
                base_px = bid * (1.0 - self.slippage)
                overflow = max(0.0, qty_f - bid_sz)
                impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                exec_price = base_px * (1.0 - impact)
                filled = True

        # ------------------------- LIMIT -------------------------
        elif otype == "LIMIT":
            lim = float(order.price)

            if side == "BUY" and lim >= bid:
                # Non pagare oltre ask
                base_px = min(lim, ask)
                overflow = max(0.0, qty_f - ask_sz)
                impact = self.impact_lambda * (overflow / max(ask_sz, 1.0))
                exec_price = base_px * (1.0 + self.slippage) * (1.0 + impact)
                filled = True

            elif side == "SELL" and lim <= ask:
                # Non vendere sotto bid
                base_px = max(lim, bid)
                overflow = max(0.0, qty_f - bid_sz)
                impact = self.impact_lambda * (overflow / max(bid_sz, 1.0))
                exec_price = base_px * (1.0 - self.slippage) * (1.0 - impact)
                filled = True

        # ------------------------- FILL -------------------------
        if filled and exec_price is not None:
            exec_price = float(exec_price)
            symbol = getattr(order, "symbol")  # multi-asset: simbolo dall'ordine

            # Aggiorna portafoglio
            self.portfolio.apply_fill(
                symbol=symbol,
                side=side,
                qty=qty_int,
                price=exec_price,
                ts=bar.timestamp
            )

            # Commissione fissa
            if self.commission > 0.0:
                self.portfolio.cash -= self.commission

            # Snapshot equity con prezzo di close come proxy
            m2m_px = float(getattr(bar, "close", exec_price))
            equity_snapshot = self.portfolio.snapshot_equity({symbol: m2m_px}, bar.timestamp)

            # ------------------------- LOG -------------------------
            pos = self.portfolio.get_position(symbol)
            avg_px = getattr(self.portfolio, "avg_price", {}).get(symbol, 0.0)

            print("\n" + "-" * 78)
            print(f"[FILL] {bar.timestamp} | {side} {qty_int} {symbol} | {otype}")
            print(f"       Exec Price : {exec_price:.4f}")
            print(f"       Book       : BID {bid:.4f} x {bid_sz:.0f} | ASK {ask:.4f} x {ask_sz:.0f}")
            print(f"       Bar        : O={float(bar.open):.4f} H={float(bar.high):.4f} "
                  f"L={float(bar.low):.4f} C={float(bar.close):.4f} Vol={float(bar.volume)}")
            print(f"       Position   : {pos} @ AvgPx={float(avg_px):.4f}")
            print(f"       Cash       : {float(self.portfolio.cash):.2f}")
            print(f"       Equity     : {float(equity_snapshot['equity']):.2f}")
            print("-" * 78)

        return filled, exec_price
