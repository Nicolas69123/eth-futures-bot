#!/usr/bin/env python3
"""
Test script pour debugger GET plan orders endpoint
Essaie différentes combinaisons de paramètres
"""

import requests
import json
import time
import hmac
import base64
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BITGET_API_KEY')
SECRET_KEY = os.getenv('BITGET_SECRET_KEY')
PASSPHRASE = os.getenv('BITGET_PASSPHRASE')

def sign_request(timestamp, method, request_path, body=''):
    """Sign request for Bitget API"""
    message = timestamp + method + request_path + body
    signature = base64.b64encode(
        hmac.new(SECRET_KEY.encode(), message.encode(), 'sha256').digest()
    ).decode()
    return signature

def test_get_endpoint(endpoint, params, description):
    """Test une requête GET avec des paramètres spécifiques"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST: {description}")
    print(f"Endpoint: {endpoint}")
    print(f"Params: {json.dumps(params, indent=2)}")

    timestamp = str(int(time.time() * 1000))

    # Build query string
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    request_path = f"{endpoint}?{query_string}"

    signature = sign_request(timestamp, 'GET', request_path, '')

    headers = {
        'ACCESS-KEY': API_KEY,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json',
        'locale': 'en-US',
        'PAPTRADING': '1'
    }

    url = f"https://api.bitget.com{request_path}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data.get('code') == '00000':
            print(f"✅ SUCCESS! Réponse: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ ERREUR {data.get('code')}: {data.get('msg')}")
            print(f"   Réponse complète: {json.dumps(data, indent=2)}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

print("🔍 DEBUGGING GET PLAN ORDERS ENDPOINT")

# Test 1: Try /api/mix/v1/order/orders-plan-pending with minimal params
test_get_endpoint(
    '/api/mix/v1/order/orders-plan-pending',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'umcbl'
    },
    "v1 - Minimal (symbol + productType)"
)

# Test 2: Try with marginCoin
test_get_endpoint(
    '/api/mix/v1/order/orders-plan-pending',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'umcbl',
        'marginCoin': 'USDT'
    },
    "v1 - Avec marginCoin"
)

# Test 3: Try v2 endpoint
test_get_endpoint(
    '/api/v2/mix/order/orders-plan-pending',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'umcbl'
    },
    "v2 - Minimal"
)

# Test 4: Try v2 with USDT-FUTURES productType
test_get_endpoint(
    '/api/v2/mix/order/orders-plan-pending',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'USDT-FUTURES'
    },
    "v2 - Avec productType=USDT-FUTURES"
)

# Test 5: Try fetch_orders endpoint instead
test_get_endpoint(
    '/api/mix/v1/order/openOrders',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'umcbl'
    },
    "v1 - openOrders (pas plan orders)"
)

# Test 6: Try orders endpoint
test_get_endpoint(
    '/api/mix/v1/order/orders',
    {
        'symbol': 'DOGEUSDT',
        'productType': 'umcbl',
        'limit': '100'
    },
    "v1 - orders list"
)

# Test 7: Try without symbol (get all plan orders)
test_get_endpoint(
    '/api/mix/v1/order/orders-plan-pending',
    {
        'productType': 'umcbl'
    },
    "v1 - Sans symbol (tous les ordres plan)"
)

print("\n" + "="*80)
print("✅ Tests terminés!")
