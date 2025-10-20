#!/usr/bin/env python3
"""Force clean TOUTES les positions et ordres sur DOGE"""
import ccxt
import os
from dotenv import load_dotenv
import time

load_dotenv()

exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

pair = 'DOGE/USDT:USDT'
symbol_bitget = 'DOGEUSDT'

print("="*80)
print("🧹 FORCE CLEAN - FERMETURE DE TOUT SUR DOGE")
print("="*80)

# Close ALL positions (retry 3 times)
for attempt in range(3):
    print(f"\n🔄 Tentative {attempt + 1}/3...")

    positions = exchange.fetch_positions(symbols=[pair])
    positions_found = False

    for pos in positions:
        size = float(pos.get('contracts', 0))
        if size > 0:
            positions_found = True
            side = pos.get('side', '').lower()
            print(f"   🔴 Position {side.upper()}: {size} contrats")

            # Flash Close
            try:
                result = exchange.private_mix_post_v2_mix_order_close_positions({
                    'symbol': symbol_bitget,
                    'productType': 'USDT-FUTURES',
                    'holdSide': side
                })

                if result.get('code') == '00000':
                    print(f"   ✅ Flash Close {side} réussi")
                else:
                    print(f"   ❌ Flash Close {side} échec: {result.get('msg')}")

                time.sleep(2)

            except Exception as e:
                print(f"   ❌ Erreur: {e}")

    if not positions_found:
        print("   ✅ Aucune position trouvée!")
        break

    time.sleep(2)

# Cancel ALL orders
print("\n🗑️  Annulation ordres...")
try:
    open_orders = exchange.fetch_open_orders(symbol=pair)
    print(f"   Ordres trouvés: {len(open_orders)}")

    for order in open_orders:
        print(f"   - {order['type']} {order['side']}: {order['id'][:12]}...")
        try:
            exchange.cancel_order(order['id'], pair)
            print(f"     ✅ Annulé")
        except Exception as e:
            print(f"     ❌ Erreur: {e}")
        time.sleep(0.5)

except Exception as e:
    print(f"   ❌ Erreur fetch orders: {e}")

print("\n" + "="*80)
print("✅ FORCE CLEAN TERMINÉ!")
print("="*80)
