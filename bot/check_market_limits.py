#!/usr/bin/env python3
"""Check market limits and minimum sizes for each pair"""
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

pairs = ['DOGE/USDT:USDT', 'PEPE/USDT:USDT', 'SHIB/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'AVAX/USDT:USDT']

print("📊 LIMITES MARCHÉS BITGET")
print("="*80)

markets = exchange.load_markets()

for pair in pairs:
    if pair in markets:
        market = markets[pair]

        pair_short = pair.split('/')[0]

        # Get current price
        ticker = exchange.fetch_ticker(pair)
        current_price = ticker['last']

        # Limits
        min_amount = market['limits']['amount']['min']
        min_cost = market['limits']['cost']['min']

        # Calculate min margin needed
        if min_amount:
            min_margin_from_amount = (min_amount * current_price) / 50  # With 50x leverage
        else:
            min_margin_from_amount = 0

        if min_cost:
            min_margin_from_cost = min_cost / 50  # With 50x leverage
        else:
            min_margin_from_cost = 0

        min_margin = max(min_margin_from_amount, min_margin_from_cost)

        print(f"\n{pair_short}:")
        print(f"  Prix actuel: ${current_price:.5f}")
        print(f"  Min amount: {min_amount} contrats")
        print(f"  Min cost: ${min_cost} notional")
        print(f"  → Marge min avec 50x: ${min_margin:.2f}")
        print(f"  → Recommandé: ${min_margin * 2:.2f} (2x sécurité)")

    else:
        print(f"\n{pair}: ❌ Non disponible")

print("\n" + "="*80)
print("💡 RECOMMANDATIONS:")
print("="*80)
print("Pour trading avec 50x leverage:")
print("  - DOGE: Utiliser $5 minimum ✅")
print("  - ETH: Utiliser $50-100 minimum")
print("  - Autres: Vérifier ci-dessus")
