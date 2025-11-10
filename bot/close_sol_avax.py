#!/usr/bin/env python3
"""Close SOL and AVAX positions"""
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY_2'),  # These were on API Key 2
    'secret': os.getenv('BITGET_SECRET_2'),
    'password': os.getenv('BITGET_PASSPHRASE_2'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
})

print("🧹 Fermeture SOL et AVAX...")

for pair in ['SOL/USDT:USDT', 'AVAX/USDT:USDT']:
    print(f"\n📊 {pair}...")
    positions = exchange.fetch_positions(symbols=[pair])

    for pos in positions:
        size = float(pos.get('contracts', 0))
        if size > 0:
            side = pos['side']
            market_side = 'sell' if side == 'long' else 'buy'

            print(f"   🔴 Fermeture {side.upper()}: {size} contrats")

            try:
                order = exchange.create_order(
                    symbol=pair,
                    type='market',
                    side=market_side,
                    amount=size,
                    params={'tradeSide': 'close', 'holdSide': side}
                )
                print(f"   ✅ Fermé: {order['id']}")
            except Exception as e:
                if '"code":"22002"' in str(e):
                    print(f"   ✅ Déjà fermé (22002)")
                else:
                    print(f"   ❌ Erreur: {e}")

print("\n✅ SOL et AVAX fermés!")
