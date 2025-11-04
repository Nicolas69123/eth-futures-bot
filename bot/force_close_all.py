#!/usr/bin/env python3
"""Force close ALL positions on Bitget (emergency cleanup)"""

import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Load API 1
exchange1 = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

# Load API 2
exchange2 = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY_2'),
    'secret': os.getenv('BITGET_SECRET_2'),
    'password': os.getenv('BITGET_PASSPHRASE_2'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

print("🧹 FORCE CLOSE ALL POSITIONS")
print("=" * 80)

for idx, exchange in enumerate([exchange1, exchange2], 1):
    print(f"\n🔑 API Key {idx}")
    print("-" * 80)

    try:
        # Cancel ALL orders first
        markets = exchange.load_markets()
        for symbol in markets:
            if 'USDT:USDT' in symbol:
                try:
                    orders = exchange.fetch_open_orders(symbol)
                    if orders:
                        print(f"  📝 {symbol}: {len(orders)} ordres à annuler...")
                        for order in orders:
                            try:
                                exchange.cancel_order(order['id'], symbol)
                                time.sleep(0.2)
                            except:
                                pass
                except:
                    pass

        # Close ALL positions
        positions = exchange.fetch_positions()

        closed_count = 0
        for pos in positions:
            size = float(pos.get('contracts', 0))
            if size > 0:
                symbol = pos['symbol']
                side = pos.get('side', '').lower()

                print(f"  🔴 Fermeture {symbol} {side.upper()}: {size:.2f} contrats")

                try:
                    market_side = 'sell' if side == 'long' else 'buy'
                    exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=market_side,
                        amount=size,
                        params={'tradeSide': 'close', 'holdSide': side}
                    )
                    print(f"     ✅ Fermé")
                    closed_count += 1
                    time.sleep(1)
                except Exception as e:
                    print(f"     ❌ Erreur: {e}")

        if closed_count == 0:
            print("  ✅ Aucune position ouverte")
        else:
            print(f"  ✅ {closed_count} positions fermées")

    except Exception as e:
        print(f"  ❌ Erreur API Key {idx}: {e}")

print("\n" + "=" * 80)
print("✅ CLEANUP TERMINÉ")
