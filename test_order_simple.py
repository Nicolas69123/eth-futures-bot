#!/usr/bin/env python3
"""
Script de test simple pour vérifier order details avec CCXT
"""

import ccxt
import os
from dotenv import load_dotenv
import json

# Charger .env
load_dotenv()

# Init Bitget exchange (PAPER TRADING MODE - simulation !)
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {
        'defaultType': 'swap',
        'defaultMarginMode': 'cross',
    },
    'headers': {'PAPTRADING': '1'},  # MODE SIMULATION !
    'enableRateLimit': True
})

print("=" * 80)
print("TEST BITGET ORDER DETAILS (CCXT)")
print("=" * 80)

try:
    # 1. Récupérer les positions actuelles
    print("\n📊 Récupération des positions...")
    positions = exchange.fetch_positions()

    active_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]

    print(f"   Positions actives: {len(active_positions)}")

    for pos in active_positions:
        symbol = pos['symbol']
        side = pos['side']
        size = pos['contracts']
        print(f"   - {symbol} {side.upper()}: {size} contrats")
        print(f"     Entry: {pos['entryPrice']}")
        print(f"     P&L: {pos.get('unrealizedPnl', 0)}")

    if not active_positions:
        print("   ⚠️ Aucune position active")
        exit(0)

    # 2. Récupérer TOUS les ordres ouverts (incluant TP/SL)
    test_symbol = active_positions[0]['symbol']
    print(f"\n🔍 Test avec la paire: {test_symbol}")

    print("\n📋 Récupération des ordres ouverts...")
    open_orders = exchange.fetch_open_orders(test_symbol)

    print(f"   Ordres trouvés: {len(open_orders)}")

    for order in open_orders:
        print(f"\n   Ordre ID: {order['id']}")
        print(f"   Type: {order['type']} | Side: {order['side']} | Status: {order['status']}")
        print(f"   Price: {order.get('price', 'N/A')} | Amount: {order['amount']}")

        # Afficher les infos brutes pour voir tous les champs
        print(f"\n   🔍 INFOS BRUTES (order['info']):")
        order_info = order.get('info', {})
        print(json.dumps(order_info, indent=4))

        # Chercher les champs preset
        preset_tp = order_info.get('presetStopSurplusPrice')
        preset_sl = order_info.get('presetStopLossPrice')

        print(f"\n   {'='*70}")
        print(f"   🎯 RÉSULTAT POUR CET ORDRE:")
        print(f"   {'='*70}")

        if preset_tp:
            print(f"   ✅ presetStopSurplusPrice TROUVÉ: {preset_tp}")
            print(f"      Exec price: {order_info.get('presetStopSurplusExecutePrice')}")
        else:
            print(f"   ❌ presetStopSurplusPrice NON TROUVÉ")

        if preset_sl:
            print(f"   ✅ presetStopLossPrice TROUVÉ: {preset_sl}")
        else:
            print(f"   ❌ presetStopLossPrice NON TROUVÉ")

    if not open_orders:
        print("   ⚠️ Aucun ordre ouvert")

except Exception as e:
    print(f"\n❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}")
print("FIN DU TEST")
print(f"{'='*80}")
