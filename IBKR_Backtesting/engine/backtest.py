from IBKR_Backtesting.engine.execution import ExecutionHandler
from IBKR_Backtesting.engine.portfolio import Portfolio
import pandas as pd

class BacktestEngine:
    """
    Motore di backtesting.
    Si occupa di:
    - orchestrare il loop principale sul dataset
    - richiamare la strategia per generare ordini
    - simulare l'esecuzione tramite l'ExecutionHandler
    - aggiornare il portafoglio e costruire l'equity curve
    - calcolare metriche di performance
    """

    def __init__(self, strategy, data, symbol, initial_cash, slippage=0.0, commission=0.0):
        """
        Parameters
        ----------
        strategy : object
            Strategia che implementa il metodo on_bar(bar).
        data : pandas.DataFrame
            Serie storica del sottostante, con colonne ['timestamp','open','high','low','close','volume'].
        symbol : str
            Ticker/identificativo del sottostante.
        initial_cash : float
            Capitale iniziale per il portafoglio.
        slippage : float, optional
            Percentuale di slippage da applicare sul prezzo di esecuzione (default=0.0).
        commission : float, optional
            Commissione fissa per trade (default=0.0).
        """
        self.strategy = strategy
        self.data = data
        self.symbol = symbol
        self.portfolio = Portfolio(cash=initial_cash)
        # Gestore esecuzione: simula market/limit order con slippage/commissioni
        self.execution = ExecutionHandler(self.portfolio, slippage, commission)
        self.filled_orders = []   # lista ordini effettivamente eseguiti
        self.equity_curve = []    # lista snapshot equity (uno per ogni barra)

    def run(self):
        """
        Esegue il loop principale del backtest.
        Per ogni barra:
        - genera eventuali ordini dalla strategia
        - li esegue tramite ExecutionHandler
        - aggiorna equity curve con snapshot mark-to-market
        """
        # snapshot iniziale: equity = solo cash, nessuna posizione
        first_bar = self.data.iloc[0]
        snapshot = self.portfolio.snapshot_equity(
            {self.symbol: first_bar.close}, first_bar.timestamp
        )
        self.equity_curve.append(snapshot)

        # loop su tutte le barre del dataset
        for bar in self.data.itertuples(index=False):
            # strategia produce ordini
            orders = self.strategy.on_bar(bar)
            if orders:
                for order in orders:
                    filled, exec_price = self.execution.execute_order(self.symbol, order, bar)
                    if filled:
                        # aggiorniamo l'ordine con info effettive
                        order.timestamp = bar.timestamp
                        order.price = exec_price
                        self.filled_orders.append(order)

            # snapshot equity: cash + valore mark-to-market posizioni
            snapshot = self.portfolio.snapshot_equity(
                {self.symbol: bar.close}, bar.timestamp
            )
            self.equity_curve.append(snapshot)

    def report(self, initial_cash):
        """
        Costruisce DataFrame equity e calcola metriche di performance.

        Returns
        -------
        equity_df : pandas.DataFrame
            Serie temporale di equity mark-to-market.
        metrics : dict
            Dizionario con metriche: Total Return, Volatility, Sharpe, Max Drawdown.
        filled_orders : list
            Lista ordini eseguiti con timestamp e prezzo.
        """
        equity_df = pd.DataFrame(self.equity_curve).set_index("timestamp")

        # calcolo metriche base di performance
        returns = equity_df["equity"].pct_change().fillna(0)
        total_return = (equity_df["equity"].iloc[-1] / initial_cash - 1) * 100
        volatility = returns.std() * (252 ** 0.5) * 100  # annualizzata
        sharpe = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() != 0 else 0
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        max_drawdown = drawdown.min() * 100

        metrics = {
            "Total Return %": round(total_return, 3),
            "Volatility %": round(volatility, 3),
            "Sharpe Ratio": round(sharpe, 3),
            "Max Drawdown %": round(max_drawdown, 3)
        }

        return equity_df, metrics, self.filled_orders
