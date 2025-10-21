#!/usr/bin/env python3
"""Check all open positions on Bitget"""
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

print("📊 POSITIONS OUVERTES SUR BITGET")
print("="*80)

positions = exchange.fetch_positions()
open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]

print(f"\nTotal: {len(open_positions)} positions ouvertes\n")

for i, pos in enumerate(open_positions, 1):
    symbol = pos['symbol']
    side = pos['side']
    size = float(pos['contracts'])
    entry = float(pos.get('entryPrice', 0))
    margin = float(pos.get('initialMargin', 0))
    pnl = float(pos.get('unrealizedPnl', 0))

    print(f"{i}. {symbol:<20} {side.upper():<6} {size:>12.2f} @ ${entry:.5f}  Marge: ${margin:.2f}  PnL: ${pnl:.2f}")

print("\n" + "="*80)
print(f"Total positions: {len(open_positions)}")
