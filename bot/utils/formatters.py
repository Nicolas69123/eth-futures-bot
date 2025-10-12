"""
Fonctions de formatage pour l'affichage
"""


def format_price(price, pair):
    """Formate le prix selon la paire (ex: PEPE/SHIB ont besoin de plus de décimales)"""
    if price == 0:
        return "$0.00000"

    # Paires à petits prix (memecoins)
    if any(coin in pair for coin in ['PEPE', 'SHIB', 'FLOKI', 'BONK']):
        if price < 0.0001:
            return f"${price:.8f}"
        elif price < 0.01:
            return f"${price:.6f}"

    return f"${price:.5f}"


def round_price(price, pair):
    """Arrondit le prix selon les règles Bitget (max décimales)"""
    # PEPE/SHIB/FLOKI/BONK : 8 décimales max
    if any(coin in pair for coin in ['PEPE', 'SHIB', 'FLOKI', 'BONK']):
        return round(price, 8)

    # DOGE et autres : 5 décimales max
    return round(price, 5)
