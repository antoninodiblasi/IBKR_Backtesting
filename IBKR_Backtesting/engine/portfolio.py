import datetime as dt
from typing import Dict, List, Tuple


class Portfolio:
    """
    Portafoglio multi-asset per backtest.

    Traccia:
    - cash (liquidità)
    - posizioni per simbolo (qty, avg price)
    - PnL realizzato cumulato per simbolo
    - storico dei fill
    - snapshot equity con dettaglio per-asset (per visualizzazioni/tabelle)
    """

    def __init__(self, cash: float = 0.0, base_currency: str = "USD"):
        self.cash = float(cash)
        self.base_currency = base_currency

        # Posizioni correnti
        self.positions: Dict[str, int] = {}        # symbol -> qty
        self.avg_price: Dict[str, float] = {}      # symbol -> prezzo medio

        # PnL realizzato cumulato per simbolo
        self.realized_pnl: Dict[str, float] = {}   # symbol -> pnl cumulato

        # Storico fill (per audit/plot)
        self.history: List[Dict] = []

    # -------------------------------------------------------------------------
    # LETTURE BASE
    # -------------------------------------------------------------------------
    def get_position(self, symbol: str) -> int:
        return int(self.positions.get(symbol, 0))

    def mark_to_market(self, prices: Dict[str, float]) -> float:
        """
        Equity = cash + ∑ qty*px correnti (solo simboli presenti).
        """
        equity = float(self.cash)
        for sym, qty in self.positions.items():
            px = prices.get(sym)
            if px is not None:
                equity += float(qty) * float(px)
        return equity

    # -------------------------------------------------------------------------
    # UPDATE STATO
    # -------------------------------------------------------------------------
    def apply_fill(self, symbol: str, side: str, qty: int, price: float, ts: dt.datetime):
        """
        Applica un'esecuzione (fill) e aggiorna posizioni, avg price, cash e realized PnL.
        """
        side = side.upper()
        qty = int(qty)
        price = float(price)
        signed_qty = qty if side == "BUY" else -qty

        prev_qty = int(self.positions.get(symbol, 0))
        prev_avg = float(self.avg_price.get(symbol, 0.0))
        new_qty = prev_qty + signed_qty

        # Cash: BUY riduce, SELL aumenta
        self.cash += -signed_qty * price

        # Prezzo medio
        if new_qty != 0:
            if prev_qty == 0:
                new_avg = price
            elif (prev_qty > 0 and signed_qty > 0) or (prev_qty < 0 and signed_qty < 0):
                # Aggiunta nella stessa direzione
                new_avg = (prev_avg * abs(prev_qty) + price * abs(signed_qty)) / abs(new_qty)
            else:
                # Riduzione: mantieni avg del residuo
                new_avg = prev_avg
            self.avg_price[symbol] = float(new_avg)
        else:
            # Posizione chiusa
            self.avg_price[symbol] = 0.0

        self.positions[symbol] = int(new_qty)

        # Realized PnL del trade (se sto chiudendo parte della posizione)
        realized_pnl = 0.0
        if prev_qty != 0 and ((prev_qty > 0 and signed_qty < 0) or (prev_qty < 0 and signed_qty > 0)):
            close_qty = min(abs(prev_qty), abs(signed_qty))
            realized_pnl = close_qty * (price - prev_avg) * (1 if prev_qty > 0 else -1)

        # Accumula per simbolo
        self.realized_pnl[symbol] = float(self.realized_pnl.get(symbol, 0.0) + realized_pnl)

        # Log storico
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
            "realized_pnl_cum": float(self.realized_pnl[symbol]),
        })

    # -------------------------------------------------------------------------
    # METRICHE PER VISUALIZZAZIONE
    # -------------------------------------------------------------------------
    def unrealized_pnl_by_symbol(self, prices: Dict[str, float]) -> Dict[str, float]:
        """
        PnL non realizzato per simbolo = qty * (px_mkt - avg_price).
        """
        out: Dict[str, float] = {}
        for sym, qty in self.positions.items():
            px = prices.get(sym)
            if px is None:
                continue
            out[sym] = float(qty) * (float(px) - float(self.avg_price.get(sym, 0.0)))
        return out

    def holdings_table(self, prices: Dict[str, float]) -> List[Dict]:
        """
        Tabella per-asset pronta per DataFrame/plot:
        - symbol, qty, avg_price, mkt_price, market_value, unrealized_pnl, realized_pnl_cum
        """
        rows: List[Dict] = []
        u_pnl = self.unrealized_pnl_by_symbol(prices)
        for sym in sorted(set(self.positions.keys()) | set(prices.keys())):
            qty = int(self.positions.get(sym, 0))
            avg = float(self.avg_price.get(sym, 0.0))
            px = float(prices.get(sym, avg or 0.0))
            mv = float(qty) * px
            rows.append({
                "symbol": sym,
                "qty": qty,
                "avg_price": avg,
                "mkt_price": px,
                "market_value": mv,
                "unrealized_pnl": float(u_pnl.get(sym, 0.0)),
                "realized_pnl_cum": float(self.realized_pnl.get(sym, 0.0)),
            })
        return rows

    def exposures(self, prices: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
        """
        Ritorna esposizione totale e per simbolo (qty*px).
        """
        per_sym: Dict[str, float] = {}
        total = 0.0
        for sym, qty in self.positions.items():
            px = prices.get(sym)
            if px is None:
                continue
            exp = float(qty) * float(px)
            per_sym[sym] = exp
            total += exp
        return float(total), {k: float(v) for k, v in per_sym.items()}

    def snapshot_equity(self, prices: Dict[str, float], ts: dt.datetime) -> Dict:
        """
        Snapshot completo per visualizzazioni multi-asset.
        """
        eq = self.mark_to_market(prices)
        unreal = self.unrealized_pnl_by_symbol(prices)
        total_exp, exp_by_sym = self.exposures(prices)

        return {
            "timestamp": ts,
            "equity": float(eq),
            "cash": float(self.cash),
            "positions": dict(self.positions),                   # qty per simbolo
            "avg_price": dict(self.avg_price),                   # avg per simbolo
            "realized_pnl_cum": dict(self.realized_pnl),         # pnl realizzato cumulato
            "unrealized_pnl": unreal,                            # pnl non realizzato per simbolo
            "exposure_total": float(total_exp),
            "exposure_by_symbol": exp_by_sym,
            "holdings_table": self.holdings_table(prices),       # righe pronte per DataFrame
        }

    def __repr__(self):
        return f"Portfolio(cash={self.cash:.2f}, positions={self.positions})"
