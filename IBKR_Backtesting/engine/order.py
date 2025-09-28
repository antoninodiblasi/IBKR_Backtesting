# engine/order.py
from __future__ import annotations
import datetime as dt


class Order:
    """
    Rappresenta un ordine generato dalla strategia.

    Caratteristiche:
    - Supporta MARKET e LIMIT
    - Compatibile con multi-asset (campo symbol obbligatorio)
    - Validazioni basilari (side, qty, order_type)
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
        # Validazioni minime
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

        # Assegnazione
        self.symbol: str = symbol
        self.side: str = side
        self.qty: int | float = qty
        self.price: float | None = price
        self.timestamp: dt.datetime | None = timestamp
        self.order_type: str = order_type

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------
    def is_market(self) -> bool:
        return self.order_type == "MARKET"

    def is_limit(self) -> bool:
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
