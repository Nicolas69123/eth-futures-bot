#!/usr/bin/env python3
"""
Test script pour debugger l'erreur 400172 de place-tpsl-order
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

def test_tpsl_order(endpoint, body, description):
    """Test une requête TP/SL avec un body spécifique"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST: {description}")
    print(f"Endpoint: {endpoint}")
    print(f"Body: {json.dumps(body, indent=2)}")

    timestamp = str(int(time.time() * 1000))
    body_json = json.dumps(body)
    signature = sign_request(timestamp, 'POST', endpoint, body_json)

    headers = {
        'ACCESS-KEY': API_KEY,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': PASSPHRASE,
        'Content-Type': 'application/json',
        'locale': 'en-US',
        'PAPTRADING': '1'
    }

    url = f"https://api.bitget.com{endpoint}"

    try:
        response = requests.post(url, headers=headers, data=body_json, timeout=10)
        data = response.json()

        if data.get('code') == '00000':
            print(f"✅ SUCCESS! Réponse: {data}")
            return True
        else:
            print(f"❌ ERREUR {data.get('code')}: {data.get('msg')}")
            print(f"   Réponse complète: {data}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

# Paramètres de base
symbol = "DOGEUSDT"
price = "0.2004"
size = "249.0"

print("🔍 DEBUGGING PLACE-TPSL-ORDER - Error 400172")
print(f"Symbol: {symbol}")
print(f"Price: {price}")
print(f"Size: {size}")

# Test 1: Endpoint v1 simple
test_tpsl_order(
    '/api/mix/v1/order/place-tpsl-order',
    {
        'symbol': symbol,
        'planType': 'profit_plan',
        'triggerPrice': price,
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': size,
        'executePrice': '0'
    },
    "v1 - Simple (current)"
)

# Test 2: Sans executePrice
test_tpsl_order(
    '/api/mix/v1/order/place-tpsl-order',
    {
        'symbol': symbol,
        'planType': 'profit_plan',
        'triggerPrice': price,
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': size
    },
    "v1 - Sans executePrice"
)

# Test 3: Avec marginCoin et productType
test_tpsl_order(
    '/api/mix/v1/order/place-tpsl-order',
    {
        'symbol': symbol,
        'marginCoin': 'USDT',
        'productType': 'umcbl',
        'planType': 'profit_plan',
        'triggerPrice': price,
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': size
    },
    "v1 - Avec marginCoin + productType"
)

# Test 4: Endpoint v2 format
test_tpsl_order(
    '/api/v2/mix/order/place-tpsl-order',
    {
        'symbol': symbol,
        'marginCoin': 'USDT',
        'productType': 'USDT-FUTURES',
        'planType': 'profit_plan',
        'triggerPrice': price,
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': size,
        'executePrice': '0'
    },
    "v2 - Original format"
)

# Test 5: Avec chainedOrder
test_tpsl_order(
    '/api/mix/v1/order/place-tpsl-order',
    {
        'symbol': symbol,
        'planType': 'profit_plan',
        'triggerPrice': price,
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': size,
        'executePrice': '0',
        'chainedOrder': 'false'
    },
    "v1 - Avec chainedOrder=false"
)

# Test 6: triggerPrice en float au lieu de string
test_tpsl_order(
    '/api/mix/v1/order/place-tpsl-order',
    {
        'symbol': symbol,
        'planType': 'profit_plan',
        'triggerPrice': float(price),
        'triggerType': 'mark_price',
        'holdSide': 'long',
        'size': float(size)
    },
    "v1 - Prices en float (pas string)"
)

print("\n" + "="*80)
print("✅ Tests terminés!")
