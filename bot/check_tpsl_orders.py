#!/usr/bin/env python3
"""Check all TP/SL plan orders on Bitget"""
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

print("📊 ORDRES TP/SL (PLAN ORDERS) SUR BITGET")
print("="*80)

# Fetch plan orders for each pair
pairs = ['PEPE/USDT:USDT', 'ETH/USDT:USDT']

total_plans = 0
for pair in pairs:
    symbol_bitget = pair.replace('/USDT:USDT', 'USDT')

    try:
        result = exchange.private_mix_get_v2_mix_order_orders_plan_pending({
            'symbol': symbol_bitget,
            'productType': 'USDT-FUTURES',
            'planType': 'pos_profit'  # TP orders
        })

        if result.get('code') == '00000':
            orders = result.get('data', {}).get('entrustedList', [])
            total_plans += len(orders)

            pair_short = pair.split('/')[0]
            print(f"\n{pair_short} TP orders: {len(orders)}")
            for order in orders:
                print(f"  - {order.get('holdSide')} TP @ ${order.get('triggerPrice')}")
        else:
            print(f"Erreur {pair}: {result}")

    except Exception as e:
        print(f"Erreur {pair}: {e}")

print("\n" + "="*80)
print(f"Total TP/SL orders: {total_plans}")
