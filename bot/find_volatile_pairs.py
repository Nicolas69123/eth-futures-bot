#!/usr/bin/env python3
"""
Script pour trouver les paires avec le plus de fluctuation
"""

import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

# Setup Bitget
exchange = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_SECRET'),
    'password': os.getenv('BITGET_PASSPHRASE'),
    'options': {
        'defaultType': 'swap',
    },
    'headers': {'PAPTRADING': '1'},
})

print("🔍 Recherche des paires les plus volatiles...")
print("="*80)

# Récupérer tous les tickers futures USDT
tickers = exchange.fetch_tickers()

# Filtrer pour USDT futures uniquement
usdt_futures = []
for symbol, ticker in tickers.items():
    if ':USDT' in symbol and ticker.get('percentage') is not None:
        # Calculer la volatilité (% de changement + volume)
        change_pct = abs(ticker['percentage'])  # % change 24h
        volume_usd = ticker.get('quoteVolume', 0)  # Volume en USD

        # Score = changement % * log(volume) pour favoriser les paires liquides ET volatiles
        import math
        if volume_usd > 1000000:  # Minimum 1M$ volume
            volatility_score = change_pct * math.log10(volume_usd)
        else:
            volatility_score = 0

        usdt_futures.append({
            'symbol': symbol,
            'change_pct': change_pct,
            'volume_usd': volume_usd,
            'volatility_score': volatility_score,
            'price': ticker['last']
        })

# Trier par score de volatilité
usdt_futures.sort(key=lambda x: x['volatility_score'], reverse=True)

# Afficher top 20
print("\n📊 TOP 20 PAIRES LES PLUS VOLATILES (24h)")
print("="*80)
print(f"{'Rang':<5} {'Paire':<20} {'Change 24h':<12} {'Volume (M$)':<15} {'Score':<10}")
print("-"*80)

for i, pair in enumerate(usdt_futures[:20], 1):
    symbol_short = pair['symbol'].replace('/USDT:USDT', '')
    print(f"{i:<5} {symbol_short:<20} {pair['change_pct']:>10.2f}%  ${pair['volume_usd']/1e6:>12.1f}M  {pair['volatility_score']:>8.1f}")

print("\n" + "="*80)
print("🎯 TOP 6 RECOMMANDÉES POUR LE BOT:")
print("="*80)

top_6 = usdt_futures[:6]
for i, pair in enumerate(top_6, 1):
    print(f"{i}. {pair['symbol']}")

print("\n📋 Liste Python pour le bot:")
print("PAIRS = [")
for pair in top_6:
    print(f"    '{pair['symbol']}',")
print("]")
