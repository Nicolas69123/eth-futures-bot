"""
Gestion des positions hedge avec grille Fibonacci
"""


class HedgePosition:
    """Gère une position hedge avec ordres limites"""

    def __init__(self, pair, initial_margin, entry_price_long, entry_price_short):
        self.pair = pair
        self.initial_margin = initial_margin
        self.entry_price_long = entry_price_long
        self.entry_price_short = entry_price_short

        # État positions
        self.long_open = True
        self.short_open = True

        # Grille Fibonacci (en % - 0.2% pour marché volatil)
        self.fib_levels = [0.2, 0.2, 0.4, 0.6, 1.0, 1.6, 2.6, 4.2, 6.8, 11.0]
        self.current_level = 0

        # IDs des ordres actifs
        self.orders = {
            'tp_long': None,      # Take profit long
            'tp_short': None,     # Take profit short
            'double_short': None, # Doubler short
            'double_long': None   # Doubler long
        }

        # Stats
        self.profit_realized = 0
        self.adjustments_count = 0

    def get_next_trigger_pct(self):
        """Retourne le prochain niveau Fibonacci en %"""
        if self.current_level >= len(self.fib_levels):
            return None

        return sum(self.fib_levels[:self.current_level + 1])
