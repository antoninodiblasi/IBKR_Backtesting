# engine/strategy.py

class Strategy:
    """
    Classe base astratta per tutte le strategie.

    Ogni strategia deve implementare:
    - on_bar: logica operativa a ogni nuova barra.
    - get_config: ritorna parametri di configurazione (simboli, date, cash, esecuzione...).

    Multi-asset:
    - Il parametro `data` passato a on_bar può essere:
        • una singola barra (NamedTuple/dict) in caso di strategia single-asset
        • un dict {symbol: bar} in caso di strategia multi-asset
    """

    def on_bar(self, data):
        """
        Definisce la logica della strategia da applicare a ogni barra.

        Parameters
        ----------
        data : object
            - Single asset: NamedTuple o dict-like con i campi
              {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
            - Multi asset: dict {symbol: bar} con la stessa struttura di cui sopra.

        Returns
        -------
        list[Order]
            Lista di oggetti Order da eseguire. Può essere vuota.

        Note
        ----
        - Deve essere implementato nelle sottoclassi.
        - Ogni strategia definisce le proprie regole di entrata/uscita.
        """
        raise NotImplementedError("Devi implementare on_bar nella tua strategia")

    def get_config(self) -> dict:
        """
        Restituisce la configurazione necessaria al backtest.

        Deve essere implementato nelle sottoclassi per includere:
        - symbols / symbol
        - date range (start_date, end_date)
        - initial_cash, base_currency
        - execution params (slippage, commission, impact_lambda)
        - bar_size, exchange, currency
        """
        raise NotImplementedError("Devi implementare get_config nella tua strategia")
