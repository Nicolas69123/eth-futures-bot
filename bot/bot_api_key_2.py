#!/usr/bin/env python3
"""
🤖 Bot Multi-Paires API Key 2 - PEPE + ETH

Lance 2 instances du bot V4 en parallèle avec API Key 2.
Chaque instance surveille sa paire indépendamment.

Paires:
- PEPE/USDT:USDT
- ETH/USDT:USDT
"""

import subprocess
import sys
import time
import signal

# Configuration paires pour API Key 2 (PRODUCTION: PEPE seul)
PAIRS = [
    'PEPE/USDT:USDT',
]

API_KEY_ID = 2

print("=" * 80)
print(f"🤖 BOT API KEY {API_KEY_ID} - {len(PAIRS)} PAIRES")
print("=" * 80)
print()
print("Paires:")
for p in PAIRS:
    pair_name = p.split('/')[0]
    print(f"  • {pair_name}")
print()
print("⚠️  Chaque paire a son propre bot en parallèle")
print("⚠️  Appuyez sur Ctrl+C pour arrêter tous les bots")
print("=" * 80)
print()

# Store processes
processes = []

# Handle Ctrl+C
def signal_handler(sig, frame):
    print("\n\n⏹️  ARRÊT DE TOUS LES BOTS API KEY 2...")
    for p in processes:
        print(f"   🛑 Arrêt {p['pair']}...")
        p['process'].terminate()

    # Wait
    time.sleep(2)

    # Force kill if needed
    for p in processes:
        if p['process'].poll() is None:
            print(f"   ⚠️  Force kill {p['pair']}")
            p['process'].kill()

    print("\n✅ Tous les bots arrêtés")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Launch instances
for idx, pair in enumerate(PAIRS):
    pair_short = pair.split('/')[0]

    print(f"🔄 Lancement bot {pair_short}...")

    # Launch process
    process = subprocess.Popen(
        [sys.executable, 'bot/bitget_hedge_fibonacci_v4_multipairs.py',
         '--pair', pair,
         '--api-key-id', str(API_KEY_ID)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    processes.append({
        'pair': pair_short,
        'process': process,
        'pid': process.pid
    })

    print(f"   ✅ PID {process.pid} - {pair_short}")

    # Wait 12s between launches (avoid rate limits during initial setup)
    if idx < len(PAIRS) - 1:
        print(f"   ⏳ Attente 12s avant lancement suivant...")
        time.sleep(12)

print()
print("=" * 80)
print("✅ TOUS LES BOTS LANCÉS")
print("=" * 80)
print()

for p in processes:
    print(f"   • {p['pair']:<8} - PID {p['pid']}")

print()
print("=" * 80)
print("📊 MONITORING (Logs en temps réel)")
print("=" * 80)
print()

# Monitor outputs
try:
    while True:
        for p in processes:
            # Check if process crashed
            if p['process'].poll() is not None:
                print(f"\n⚠️  {p['pair']} (PID {p['pid']}) s'est arrêté!")
                print(f"    Code retour: {p['process'].returncode}")

            # Read output
            while True:
                line = p['process'].stdout.readline()
                if not line:
                    break
                print(line.rstrip())

        time.sleep(0.1)

except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)
