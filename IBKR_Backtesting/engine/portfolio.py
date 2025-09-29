# engine/portfolio.py
import datetime as dt
from typing import Dict, List, Optional


class Portfolio:
    """
    Portafoglio multi-asset per backtest.

    Gestisce:
    - liquidità (cash)
    - posizioni per simbolo: qty, avg_price, realized_pnl
    - storico dei fill
    - snapshot di equity/esposizioni

    Logica:
    - BUY → qty aumenta, cash diminuisce
    - SELL → qty diminuisce, cash aumenta
    - PnL realizzato al momento della chiusura (parziale o totale)
    - Prezzo medio aggiornato solo quando si incrementa nella stessa direzione
    - Configurazioni (es. base_currency) arrivano dalla strategia via get_config()
    """

    def __init__(self, cash: float = 0.0, base_currency: str = "USD"):
        # Liquidità iniziale
        self.cash: float = float(cash)
        self.base_currency: str = base_currency

        # Stato posizioni: symbol -> {qty, avg_price, realized_pnl}
        self._positions: Dict[str, Dict[str, float]] = {}

        # Storico fill per audit/debug
        self.history: List[Dict] = []

    # ------------------------------------------------------------------
    # LETTURE BASE
    # ------------------------------------------------------------------
    def get_position(self, symbol: str) -> int:
        """Quantità netta attuale di un simbolo (0 se flat)."""
        return int(self._positions.get(symbol, {}).get("qty", 0))

    def get_avg_price(self, symbol: str) -> float:
        """Prezzo medio di carico di un simbolo (0 se flat)."""
        return float(self._positions.get(symbol, {}).get("avg_price", 0.0))

    def get_realized_pnl(self, symbol: str) -> float:
        """PnL realizzato cumulato di un simbolo."""
        return float(self._positions.get(symbol, {}).get("realized_pnl", 0.0))

    def mark_to_market(self, prices: Dict[str, float]) -> float:
        """
        Equity totale = cash + valore corrente delle posizioni mark-to-market.
        `prices` deve essere un dict {symbol: price}.
        """
        equity = self.cash
        for sym, pos in self._positions.items():
            qty = pos["qty"]
            px = prices.get(sym)
            if px is not None:
                equity += qty * px
        return float(equity)

    # ------------------------------------------------------------------
    # UPDATE: FILL
    # ------------------------------------------------------------------
    def apply_fill(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        ts: Optional[dt.datetime] = None,
    ) -> None:
        """
        Applica un'esecuzione aggiornando lo stato del portafoglio.

        Parametri:
        - symbol : asset scambiato
        - side   : "BUY" o "SELL"
        - qty    : quantità eseguita (>0)
        - price  : prezzo di esecuzione
        - ts     : timestamp del fill
        """
        side = side.upper()
        assert side in {"BUY", "SELL"}, f"Side non valido: {side}"

        qty = int(qty)
        price = float(price)
        signed_qty = qty if side == "BUY" else -qty

        # Stato precedente (se non esiste inizializza)
        pos = self._positions.get(symbol, {"qty": 0, "avg_price": 0.0, "realized_pnl": 0.0})
        prev_qty = pos["qty"]
        prev_avg = pos["avg_price"]
        realized_pnl = pos["realized_pnl"]

        # Nuova quantità netta
        new_qty = prev_qty + signed_qty

        # Cash: BUY riduce, SELL aumenta
        self.cash -= signed_qty * price

        # Prezzo medio e PnL realizzato
        if prev_qty == 0 or (prev_qty > 0 and signed_qty > 0) or (prev_qty < 0 and signed_qty < 0):
            # Apertura o incremento stessa direzione → aggiorno media
            new_avg = (prev_avg * abs(prev_qty) + price * abs(signed_qty)) / abs(new_qty)
        elif new_qty == 0:
            # Posizione chiusa totalmente
            realized_pnl += prev_qty * (price - prev_avg)
            new_avg = 0.0
        else:
            # Riduzione parziale
            closed_qty = abs(signed_qty)
            realized_pnl += closed_qty * (price - prev_avg) * (1 if prev_qty > 0 else -1)
            new_avg = prev_avg

        # Aggiorna stato
        self._positions[symbol] = {
            "qty": new_qty,
            "avg_price": new_avg,
            "realized_pnl": realized_pnl,
        }

        # Log storico
        self.history.append({
            "timestamp": ts,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "cash": self.cash,
            "position": new_qty,
            "avg_price": new_avg,
            "realized_pnl_cum": realized_pnl,
        })

    # ------------------------------------------------------------------
    # METRICHE
    # ------------------------------------------------------------------
    def unrealized_pnl(self, prices: Dict[str, float]) -> Dict[str, float]:
        """PnL non realizzato per ogni simbolo in base ai prezzi correnti."""
        out: Dict[str, float] = {}
        for sym, pos in self._positions.items():
            qty = pos["qty"]
            avg = pos["avg_price"]
            px = prices.get(sym)
            if px is not None:
                out[sym] = qty * (px - avg)
        return out

    def exposures(self, prices: Dict[str, float]) -> Dict[str, float]:
        """Esposizione (qty * price) per ogni simbolo."""
        out: Dict[str, float] = {}
        for sym, pos in self._positions.items():
            px = prices.get(sym)
            if px is not None:
                out[sym] = pos["qty"] * px
        return out

    def snapshot(self, prices: Dict[str, float], ts: dt.datetime) -> Dict:
        """Snapshot di equity/cash/posizioni al timestamp `ts`."""
        equity = self.mark_to_market(prices)
        return {
            "timestamp": ts,
            "equity": float(equity),
            "cash": float(self.cash),
            "positions": {s: dict(p) for s, p in self._positions.items()},
        }

    # ------------------------------------------------------------------
    # REPR
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        positions = {s: p["qty"] for s, p in self._positions.items()}
        return f"Portfolio(cash={self.cash:.2f}, positions={positions})"
