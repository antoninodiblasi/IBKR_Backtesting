# engine/order.py
from __future__ import annotations
import datetime as dt


class Order:
    """
    Rappresenta un ordine generato dalla strategia.

    Caratteristiche:
    - Supporta MARKET e LIMIT.
    - Compatibile con multi-asset: il campo `symbol` è sempre obbligatorio.
    - Validazioni basilari su side, qty e order_type.
    - Timestamp può essere assegnato dalla strategia o dal motore in fase di fill.
    """

    def __init__(
        self,
        symbol: str,
        side: str,
        qty: int | float,
        price: float | None = None,
        timestamp: dt.datetime | None = None,
        order_type: str = "MARKET",
    ) -> None:
        # ---------------- VALIDAZIONI ----------------
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'.")

        order_type = order_type.upper()
        if order_type not in ("MARKET", "LIMIT"):
            raise ValueError(f"Invalid order_type: {order_type}. Must be 'MARKET' or 'LIMIT'.")

        if qty <= 0:
            raise ValueError("Order qty must be positive.")

        if order_type == "LIMIT" and price is None:
            raise ValueError("Limit orders must include a price.")

        # ---------------- ASSEGNAZIONE ----------------
        self.symbol: str = symbol            # ticker TWS / asset identifier
        self.side: str = side                # BUY o SELL
        self.qty: int | float = qty          # quantità > 0
        self.price: float | None = price     # solo per LIMIT
        self.timestamp: dt.datetime | None = timestamp  # settato dal motore se mancante
        self.order_type: str = order_type    # MARKET o LIMIT

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------
    def is_market(self) -> bool:
        """True se ordine di tipo MARKET."""
        return self.order_type == "MARKET"

    def is_limit(self) -> bool:
        """True se ordine di tipo LIMIT."""
        return self.order_type == "LIMIT"

    # -------------------------------------------------------------------------
    # Rappresentazione leggibile
    # -------------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Order("
            f"symbol={self.symbol}, side={self.side}, qty={self.qty}, "
            f"type={self.order_type}, price={self.price}, "
            f"time={self.timestamp})"
        )
