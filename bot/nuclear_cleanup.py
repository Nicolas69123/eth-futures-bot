#!/usr/bin/env python3
"""NUCLEAR CLEANUP - Cancel ALL TP/SL orders then close ALL positions"""

import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

def cancel_all_tpsl(exchange, pair_symbol):
    """Cancel ALL TP/SL plan orders for a pair"""
    symbol_bitget = pair_symbol.replace('/USDT:USDT', 'USDT')
    cancelled = 0

    for plan_type in ['pos_profit', 'pos_loss']:
        try:
            result = exchange.private_mix_get_v2_mix_order_orders_plan_pending({
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'planType': plan_type
            })

            if result.get('code') == '00000':
                orders = result.get('data', {}).get('entrustedList', [])
                for order in orders:
                    try:
                        exchange.private_mix_post_v2_mix_order_cancel_plan_order({
                            'orderId': order['orderId'],
                            'symbol': symbol_bitget,
                            'productType': 'USDT-FUTURES',
                            'marginCoin': 'USDT'
                        })
                        cancelled += 1
                        time.sleep(0.2)
                    except:
                        pass
        except:
            pass

    return cancelled

# Load both API keys
exchange1 = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

exchange2 = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY_2'),
    'secret': os.getenv('BITGET_SECRET_2'),
    'password': os.getenv('BITGET_PASSPHRASE_2'),
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

print("☢️  NUCLEAR CLEANUP - Cancel ALL TP/SL + Close ALL positions")
print("=" * 80)

for idx, exchange in enumerate([exchange1, exchange2], 1):
    print(f"\n🔑 API Key {idx}")
    print("-" * 80)

    try:
        # Step 1: Cancel ALL LIMIT orders
        print("  🗑️  Annulation ordres LIMIT...")
        markets = exchange.load_markets()
        limit_cancelled = 0

        for symbol in markets:
            if 'USDT:USDT' in symbol:
                try:
                    orders = exchange.fetch_open_orders(symbol)
                    for order in orders:
                        try:
                            exchange.cancel_order(order['id'], symbol)
                            limit_cancelled += 1
                            time.sleep(0.2)
                        except:
                            pass
                except:
                    pass

        print(f"     ✅ {limit_cancelled} ordres LIMIT annulés")

        # Step 2: Cancel ALL TP/SL orders for each pair
        print("  🗑️  Annulation ordres TP/SL...")
        tpsl_cancelled = 0

        for pair in ['DOGE/USDT:USDT', 'PEPE/USDT:USDT', 'SOL/USDT:USDT',
                     'AVAX/USDT:USDT', 'ETH/USDT:USDT', 'SHIB/USDT:USDT']:
            cancelled = cancel_all_tpsl(exchange, pair)
            tpsl_cancelled += cancelled
            time.sleep(0.5)

        print(f"     ✅ {tpsl_cancelled} ordres TP/SL annulés")

        time.sleep(2)  # Wait for cancellations to process

        # Step 3: Close ALL positions with REDUCE_ONLY
        print("  🔴 Fermeture positions...")
        positions = exchange.fetch_positions()
        closed_count = 0

        for pos in positions:
            size = float(pos.get('contracts', 0))
            if size > 0:
                symbol = pos['symbol']
                side = pos.get('side', '').lower()

                print(f"     {symbol} {side.upper()}: {size:.0f} contrats")

                try:
                    market_side = 'sell' if side == 'long' else 'buy'

                    # Try with reduceOnly flag
                    exchange.create_order(
                        symbol=symbol,
                        type='market',
                        side=market_side,
                        amount=size,
                        params={
                            'tradeSide': 'close',
                            'holdSide': side,
                            'reduceOnly': True
                        }
                    )
                    print(f"        ✅ Fermé")
                    closed_count += 1
                    time.sleep(1)

                except Exception as e:
                    error = str(e)
                    if '22002' in error:
                        print(f"        ⚠️  Déjà fermé (22002)")
                    elif '43001' in error:
                        # Position locked, try without params
                        try:
                            exchange.create_market_order(
                                symbol=symbol,
                                side=market_side,
                                amount=size
                            )
                            print(f"        ✅ Fermé (méthode alternative)")
                            closed_count += 1
                        except Exception as e2:
                            print(f"        ❌ Échec définitif: {e2}")
                    else:
                        print(f"        ❌ Erreur: {e}")

        if closed_count == 0:
            print("     ✅ Aucune position ouverte")
        else:
            print(f"     ✅ {closed_count} positions fermées")

    except Exception as e:
        print(f"  ❌ Erreur API Key {idx}: {e}")

print("\n" + "=" * 80)
print("☢️  CLEANUP NUCLÉAIRE TERMINÉ")
print("\nVérifiez avec check_positions.py que tout est clean!")
