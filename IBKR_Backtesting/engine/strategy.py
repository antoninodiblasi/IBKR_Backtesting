# engine/strategy.py

class Strategy:
    """
    Classe base astratta per tutte le strategie.
    Ogni strategia deve implementare il metodo on_bar, che viene chiamato
    a ogni nuova barra del dataset durante il backtest.
    """

    def on_bar(self, data):
        """
        Definisce la logica della strategia da applicare a ogni barra.

        Parameters
        ----------
        data : object (tipicamente NamedTuple o dict-like)
            Contiene le informazioni della barra corrente.
            Es. {
                'timestamp': datetime,
                'open': float,
                'high': float,
                'low': float,
                'close': float,
                'volume': float
            }

        Returns
        -------
        list[Order]
            Una lista di oggetti Order da eseguire.
            Può essere vuota se la strategia decide di non operare in quella barra.

        Note
        ----
        - Deve essere implementato nelle sottoclassi.
        - Ogni strategia definisce le proprie regole di entrata/uscita.
        """
        raise NotImplementedError("Devi implementare on_bar nella tua strategia")
