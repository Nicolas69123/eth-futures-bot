"""
Grille Fibonacci pour la stratégie de martingale
"""


class FibonacciGrid:
    """Gère la grille Fibonacci de doublement"""

    # Niveaux en % - Ajustables selon la volatilité
    # Pour test rapide: 0.2%, 0.2%, 0.4%, 0.6%, 1.0%, 1.6%, 2.6%, 4.2%, 6.8%, 11.0%
    # Pour production: 1%, 1%, 2%, 3%, 5%, 8%, 13%, 21%, 34%, 55%
    LEVELS = [0.2, 0.2, 0.4, 0.6, 1.0, 1.6, 2.6, 4.2, 6.8, 11.0]

    @staticmethod
    def get_trigger_percent(level):
        """
        Retourne le pourcentage de trigger pour un niveau donné

        Args:
            level: Niveau actuel (0, 1, 2, ...)

        Returns:
            float: Pourcentage cumulé (ex: niveau 2 = 0.2 + 0.2 + 0.4 = 0.8%)
        """
        if level >= len(FibonacciGrid.LEVELS):
            return None

        return sum(FibonacciGrid.LEVELS[:level + 1])

    @staticmethod
    def get_next_level_percent(level):
        """Retourne le pourcentage du prochain niveau"""
        if level >= len(FibonacciGrid.LEVELS):
            return None

        return FibonacciGrid.LEVELS[level]

    @staticmethod
    def calculate_tp_price(entry_price, direction, level=0):
        """
        Calcule le prix de TP pour un niveau donné

        Args:
            entry_price: Prix d'entrée de la position
            direction: 'long' ou 'short'
            level: Niveau Fibonacci (0 par défaut)

        Returns:
            float: Prix du TP
        """
        trigger_pct = FibonacciGrid.get_trigger_percent(level)
        if trigger_pct is None:
            return None

        if direction == 'long':
            return entry_price * (1 + trigger_pct / 100)
        elif direction == 'short':
            return entry_price * (1 - trigger_pct / 100)

        return None

    @staticmethod
    def calculate_double_price(entry_price, direction, level):
        """
        Calcule le prix de doublement pour un niveau donné

        Args:
            entry_price: Prix d'entrée initial
            direction: 'long' ou 'short' (qu'est-ce qu'on double)
            level: Niveau Fibonacci suivant

        Returns:
            float: Prix de déclenchement du doublement
        """
        trigger_pct = FibonacciGrid.get_trigger_percent(level)
        if trigger_pct is None:
            return None

        # Pour doubler un Long, le prix doit descendre
        if direction == 'long':
            return entry_price * (1 - trigger_pct / 100)
        # Pour doubler un Short, le prix doit monter
        elif direction == 'short':
            return entry_price * (1 + trigger_pct / 100)

        return None
