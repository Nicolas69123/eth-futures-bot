#!/usr/bin/env python3
"""
Script de test pour vérifier les détails d'ordre Bitget
Teste si presetStopSurplusPrice est bien retourné dans order details
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
print("TEST BITGET ORDER DETAILS")
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

    if not active_positions:
        print("   ⚠️ Aucune position active - impossible de tester order details")
        print("   💡 Lance le bot d'abord pour créer des positions avec TP/SL")
        exit(0)

    # 2. Récupérer les ordres plan (TP/SL) pour une position
    test_symbol = active_positions[0]['symbol']
    print(f"\n🔍 Test avec la paire: {test_symbol}")

    print("\n📋 Récupération des ordres plan (TP/SL)...")

    # Utiliser l'API directe Bitget pour récupérer les ordres plan
    import time
    import hmac
    import hashlib
    import requests

    api_key = os.getenv('BITGET_API_KEY')
    secret = os.getenv('BITGET_SECRET')
    passphrase = os.getenv('BITGET_PASSPHRASE')

    # Endpoint pour ordres plan pending
    timestamp = str(int(time.time() * 1000))
    method = 'GET'
    request_path = '/api/v2/mix/order/orders-plan-pending?productType=USDT-FUTURES'

    # Signature (timestamp + method + path + body)
    message = timestamp + method + request_path
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = __import__('base64').b64encode(signature).decode()

    headers = {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': signature_b64,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': passphrase,
        'Content-Type': 'application/json',
        'locale': 'en-US',
        'PAPTRADING': '1'  # MODE SIMULATION
    }

    url = f'https://api.bitget.com{request_path}'

    print(f"   DEBUG - URL: {url}")
    print(f"   DEBUG - Headers: {headers}")
    print(f"   DEBUG - Signature message: {message}")

    response = requests.get(url, headers=headers)
    data = response.json()

    print(f"   Status: {data.get('code')} - {data.get('msg')}")
    if data.get('code') != '00000':
        print(f"   Full response: {json.dumps(data, indent=2)}")

    if data.get('code') == '00000':
        orders = data.get('data', {}).get('entrustedList', [])
        print(f"   Ordres plan trouvés: {len(orders)}")

        if orders:
            # Prendre le premier ordre TP
            test_order = orders[0]
            order_id = test_order.get('orderId')

            print(f"\n🎯 Test order detail pour ordre: {order_id}")
            print(f"   Plan Type: {test_order.get('planType')}")
            print(f"   Trigger Price: {test_order.get('triggerPrice')}")
            print(f"   Size: {test_order.get('size')}")

            # 3. Récupérer les détails complets de cet ordre
            print(f"\n📝 Récupération ORDER DETAILS via API...")

            symbol_param = test_symbol.replace('/USDT:USDT', 'USDT').replace('/', '').upper()
            request_path_detail = f'/api/v2/mix/order/detail?symbol={symbol_param}&orderId={order_id}'

            timestamp_detail = str(int(time.time() * 1000))
            message_detail = timestamp_detail + 'GET' + request_path_detail
            signature_detail = hmac.new(
                secret.encode('utf-8'),
                message_detail.encode('utf-8'),
                hashlib.sha256
            ).digest()
            signature_b64_detail = __import__('base64').b64encode(signature_detail).decode()

            headers_detail = {
                'ACCESS-KEY': api_key,
                'ACCESS-SIGN': signature_b64_detail,
                'ACCESS-TIMESTAMP': timestamp_detail,
                'ACCESS-PASSPHRASE': passphrase,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'  # MODE SIMULATION
            }

            url_detail = f'https://api.bitget.com{request_path_detail}'
            response_detail = requests.get(url_detail, headers=headers_detail)
            data_detail = response_detail.json()

            print(f"\n✅ Réponse ORDER DETAILS:")
            print(json.dumps(data_detail, indent=2))

            # Vérifier si presetStopSurplusPrice existe
            if data_detail.get('code') == '00000':
                order_data = data_detail.get('data', {})
                preset_tp = order_data.get('presetStopSurplusPrice')
                preset_sl = order_data.get('presetStopLossPrice')

                print(f"\n{'='*80}")
                print(f"🎯 RÉSULTAT DU TEST:")
                print(f"{'='*80}")

                if preset_tp:
                    print(f"✅ presetStopSurplusPrice TROUVÉ: {preset_tp}")
                    print(f"   presetStopSurplusExecutePrice: {order_data.get('presetStopSurplusExecutePrice')}")
                else:
                    print(f"❌ presetStopSurplusPrice NON TROUVÉ")

                if preset_sl:
                    print(f"✅ presetStopLossPrice TROUVÉ: {preset_sl}")
                else:
                    print(f"❌ presetStopLossPrice NON TROUVÉ")

                print(f"\n💡 Cette méthode est {'FIABLE ✅' if preset_tp or preset_sl else 'NON FIABLE ❌'} pour détecter TP/SL")
            else:
                print(f"❌ Erreur API: {data_detail.get('msg')}")
        else:
            print("   ⚠️ Aucun ordre plan trouvé - impossible de tester order details")
    else:
        print(f"   ❌ Erreur: {data.get('msg')}")

except Exception as e:
    print(f"\n❌ Erreur: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}")
print("FIN DU TEST")
print(f"{'='*80}")
