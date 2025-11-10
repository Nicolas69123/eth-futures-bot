#!/usr/bin/env python3
"""
Check current account state - positions and orders
"""

import ccxt
import os
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

# Initialize exchange
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'defaultMarginMode': 'cross'
    },
    'headers': {'PAPTRADING': '1'}  # Paper trading
})

print("="*80)
print(f"📊 ÉTAT ACTUEL DU COMPTE - {datetime.now().strftime('%H:%M:%S')}")
print("="*80)

# Check positions
positions_by_symbol = {}
total_positions = 0

try:
    positions = exchange.fetch_positions()

    print("\n🔷 POSITIONS OUVERTES:")
    print("-"*80)

    if not positions:
        print("Aucune position ouverte")
    else:
        total_positions = 0
        positions_by_symbol = {}

        for pos in positions:
            if pos['contracts'] and pos['contracts'] > 0:
                symbol = pos['symbol']
                side = pos['side']

                if symbol not in positions_by_symbol:
                    positions_by_symbol[symbol] = {'long': None, 'short': None}

                positions_by_symbol[symbol][side] = pos
                total_positions += 1

                print(f"\n📍 {symbol} - {side.upper()}")
                print(f"   • Taille: {pos['contracts']} contrats")
                print(f"   • Prix d'entrée: ${pos['info'].get('openPriceAvg', 'N/A')}")
                print(f"   • PnL: ${pos['unrealizedPnl']:.2f}")
                print(f"   • Marge: ${pos['initialMargin']:.2f}" if pos['initialMargin'] else "   • Marge: N/A")

        print(f"\n📊 TOTAL: {total_positions} positions ouvertes")

        # Check for hedge pairs
        for symbol, sides in positions_by_symbol.items():
            if sides['long'] and sides['short']:
                print(f"\n✅ Hedge complet sur {symbol}")
            elif sides['long']:
                print(f"\n⚠️ Seulement LONG sur {symbol}")
            elif sides['short']:
                print(f"\n⚠️ Seulement SHORT sur {symbol}")

except Exception as e:
    print(f"❌ Erreur récupération positions: {e}")

# Check open orders
print("\n\n🔷 ORDRES OUVERTS:")
print("-"*80)

open_orders = []

try:
    # Check regular orders
    open_orders = exchange.fetch_open_orders()

    if open_orders:
        print(f"\n📋 ORDRES LIMIT ({len(open_orders)} ordres):")
        for order in open_orders:
            print(f"   • {order['side'].upper()} {order['amount']} @ ${order['price']} [{order['symbol']}]")
            print(f"     Status: {order['status']} | ID: {order['id'][:16]}...")

    # Check TP/SL orders for each symbol
    symbols_to_check = ['DOGEUSDT', 'PEPEUSDT', 'SHIBUSDT']

    total_tpsl = 0

    for symbol_bitget in symbols_to_check:
        for plan_type in ['pos_profit', 'pos_loss']:
            try:
                result = exchange.private_mix_get_v2_mix_order_orders_plan_pending({
                    'symbol': symbol_bitget,
                    'productType': 'USDT-FUTURES',
                    'planType': plan_type
                })

                if result and result['data'] and result['data']['entrustedList']:
                    orders = result['data']['entrustedList']
                    total_tpsl += len(orders)

                    for order in orders:
                        order_type = "TP" if plan_type == 'pos_profit' else "SL"
                        side = order.get('holdSide', 'unknown').upper()
                        trigger_price = order.get('triggerPrice', 'N/A')
                        size = order.get('size', 'N/A')

                        print(f"\n   🎯 {order_type} {side} sur {symbol_bitget}")
                        print(f"      • Trigger: ${trigger_price}")
                        print(f"      • Taille: {size} contrats")
                        print(f"      • ID: {order.get('orderId', 'N/A')[:16]}...")

            except Exception as e:
                pass  # Ignore symbols without orders

    print(f"\n📊 RÉSUMÉ ORDRES:")
    print(f"   • Ordres LIMIT: {len(open_orders)}")
    print(f"   • Ordres TP/SL: {total_tpsl}")
    print(f"   • TOTAL: {len(open_orders) + total_tpsl} ordres")

except Exception as e:
    print(f"❌ Erreur récupération ordres: {e}")

print("\n" + "="*80)

# Check for anomalies
print("\n⚠️ ANALYSE DES ANOMALIES:")
print("-"*80)

anomalies = []

# Check for unbalanced hedges
for symbol, sides in positions_by_symbol.items():
    if sides['long'] and not sides['short']:
        anomalies.append(f"❌ LONG sans SHORT sur {symbol}")
    elif sides['short'] and not sides['long']:
        anomalies.append(f"❌ SHORT sans LONG sur {symbol}")
    elif sides['long'] and sides['short']:
        if abs(sides['long']['contracts'] - sides['short']['contracts']) > 10:
            anomalies.append(f"⚠️ Déséquilibre sur {symbol}: LONG={sides['long']['contracts']}, SHORT={sides['short']['contracts']}")

# Check for too many positions
if total_positions > 6:  # More than 3 pairs
    anomalies.append(f"⚠️ Trop de positions: {total_positions} (max attendu: 6)")

# Check for orphan orders
if len(open_orders) > total_positions * 2:
    anomalies.append(f"⚠️ Trop d'ordres par rapport aux positions: {len(open_orders)} ordres pour {total_positions} positions")

if anomalies:
    for anomaly in anomalies:
        print(anomaly)
else:
    print("✅ Aucune anomalie détectée")

print("\n" + "="*80)