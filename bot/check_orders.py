#!/usr/bin/env python3
"""Check all open orders on Bitget"""
import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
})

print("📊 ORDRES OUVERTS SUR BITGET")
print("="*80)

orders = exchange.fetch_open_orders()

print(f"\nTotal: {len(orders)} ordres ouverts\n")

# Group by pair
from collections import defaultdict
by_pair = defaultdict(list)

for order in orders:
    symbol = order['symbol']
    by_pair[symbol].append(order)

for pair, pair_orders in sorted(by_pair.items()):
    pair_short = pair.split('/')[0]
    print(f"\n{pair_short}:")
    print("-" * 40)
    for i, order in enumerate(pair_orders, 1):
        print(f"  {i}. {order['type'].upper():<10} {order['side']:<5} @ ${float(order.get('price', 0)):.5f}")

print("\n" + "="*80)
print(f"Total ordres: {len(orders)}")
