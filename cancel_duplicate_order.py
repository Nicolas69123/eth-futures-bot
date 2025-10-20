#!/usr/bin/env python3
"""Cancel duplicate LIMIT BUY order"""
import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BITGET_API_KEY')
api_secret = os.getenv('BITGET_SECRET')
api_password = os.getenv('BITGET_PASSPHRASE')

print(f"API Key: {'✅' if api_key else '❌'}")
print(f"Secret: {'✅' if api_secret else '❌'}")
print(f"Password: {'✅' if api_password else '❌'}")

exchange = ccxt.bitget({
    'apiKey': api_key,
    'secret': api_secret,
    'password': api_password,
    'options': {'defaultType': 'swap'},
    'headers': {'PAPTRADING': '1'},
    'enableRateLimit': True
})

pair = 'DOGE/USDT:USDT'
order_id = '1364159526252740609'  # Ordre LIMIT BUY 498 @ 0.19967 (duplicate)

print(f"\n🗑️  Annulation ordre LIMIT BUY en double...")
print(f"   Order ID: {order_id}")
print(f"   Amount: 498 contrats @ 0.19967")

try:
    result = exchange.cancel_order(order_id, pair)
    print(f"\n✅ Ordre annulé avec succès!")
    print(f"   Résultat: {result}")
except Exception as e:
    print(f"\n❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
