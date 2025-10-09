"""
Script pour nettoyer toutes les positions et ordres avant de relancer le bot
"""
import ccxt
import os
from dotenv import load_dotenv
from pathlib import Path

# Charger .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Initialiser exchange
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

print("🧹 Nettoyage des positions et ordres...")

# Paires à nettoyer
pairs = ['DOGE/USDT:USDT', 'PEPE/USDT:USDT', 'SHIB/USDT:USDT', 'BONK/USDT:USDT', 'FLOKI/USDT:USDT']

for pair in pairs:
    print(f"\n{'='*60}")
    print(f"🔍 {pair}")
    print(f"{'='*60}")

    # 1. Annuler tous les ordres ouverts
    try:
        open_orders = exchange.fetch_open_orders(pair)
        if open_orders:
            print(f"📝 {len(open_orders)} ordres ouverts trouvés")
            for order in open_orders:
                try:
                    exchange.cancel_order(order['id'], pair)
                    print(f"   ✅ Ordre {order['id'][:8]}... annulé")
                except Exception as e:
                    print(f"   ⚠️ Erreur annulation: {e}")
        else:
            print("✅ Aucun ordre ouvert")
    except Exception as e:
        print(f"⚠️ Erreur récupération ordres: {e}")

    # 2. Fermer toutes les positions
    try:
        positions = exchange.fetch_positions([pair])
        for pos in positions:
            size = float(pos.get('contracts', 0))
            if size > 0:
                side = pos.get('side', '').lower()
                print(f"📊 Position {side.upper()} trouvée: {size}")

                try:
                    # Fermer la position (en mode hedge: long=buy, short=sell pour fermer!)
                    close_side = 'buy' if side == 'long' else 'sell'
                    exchange.create_order(
                        pair, 'market', close_side, size,
                        params={'tradeSide': 'close', 'holdSide': side}
                    )
                    print(f"   ✅ Position {side.upper()} fermée")
                except Exception as e:
                    print(f"   ⚠️ Erreur fermeture: {e}")

        # Vérifier qu'il ne reste rien
        positions_after = exchange.fetch_positions([pair])
        still_open = sum(1 for p in positions_after if float(p.get('contracts', 0)) > 0)
        if still_open == 0:
            print("✅ Toutes les positions fermées")
        else:
            print(f"⚠️ {still_open} positions encore ouvertes")

    except Exception as e:
        print(f"⚠️ Erreur récupération positions: {e}")

print(f"\n{'='*60}")
print("✅ Nettoyage terminé !")
print(f"{'='*60}")
