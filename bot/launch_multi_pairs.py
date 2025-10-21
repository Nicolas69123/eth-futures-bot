#!/usr/bin/env python3
"""
🚀 Launcher Multi-Paires - Lance 6 instances du bot

Lance 6 instances du bot simultanément, une par paire.
"""

import subprocess
import time
import sys

# Paires à trader - 2 paires avec 2 clés API (1 par clé)
# API Key 1: DOGE
# API Key 2: ETH
PAIRS = [
    {'pair': 'DOGE/USDT:USDT', 'api_key_id': 1},
    {'pair': 'ETH/USDT:USDT', 'api_key_id': 2},
]

print("="*80)
print(f"🚀 LANCEMENT MULTI-PAIRES - {len(PAIRS)} INSTANCES (2 API Keys)")
print("="*80)
print(f"\nPaires: {', '.join([p['pair'].split('/')[0] for p in PAIRS])}")
print(f"API Key 1: {', '.join([p['pair'].split('/')[0] for p in PAIRS if p['api_key_id'] == 1])}")
print(f"API Key 2: {', '.join([p['pair'].split('/')[0] for p in PAIRS if p['api_key_id'] == 2])}\n")

# Store processes
processes = []

# Launch each instance
for p in PAIRS:
    pair = p['pair']
    api_key_id = p['api_key_id']
    pair_short = pair.split('/')[0]
    print(f"🔄 Lancement bot {pair_short} (API Key {api_key_id})...")

    # Launch in background
    process = subprocess.Popen(
        [sys.executable, 'bot/bitget_hedge_multi_instance.py', '--pair', pair, '--api-key-id', str(api_key_id)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    processes.append({
        'pair': pair_short,
        'process': process,
        'pid': process.pid
    })

    print(f"   ✅ PID {process.pid} - {pair_short} (API Key {api_key_id})")
    time.sleep(10)  # 10s entre chaque lancement (évite rate limits)

print("\n" + "="*80)
print("✅ TOUTES LES INSTANCES LANCÉES")
print("="*80)
print(f"\nTotal: {len(processes)} instances en cours\n")

for p in processes:
    print(f"   • {p['pair']:<8} - PID {p['pid']}")

print("\n" + "="*80)
print("📊 MONITORING")
print("="*80)
print("Appuyez sur Ctrl+C pour arrêter toutes les instances\n")

try:
    # Monitor processes
    while True:
        time.sleep(5)

        # Check if any process died
        for p in processes:
            if p['process'].poll() is not None:
                print(f"⚠️  {p['pair']} (PID {p['pid']}) s'est arrêté!")
                # Could restart it here if needed

except KeyboardInterrupt:
    print("\n\n⏹️  ARRÊT DE TOUTES LES INSTANCES...")

    for p in processes:
        print(f"   🛑 Arrêt {p['pair']} (PID {p['pid']})...")
        p['process'].terminate()

    # Wait for all to terminate
    time.sleep(3)

    # Force kill if still running
    for p in processes:
        if p['process'].poll() is None:
            print(f"   ⚠️  Force kill {p['pair']}")
            p['process'].kill()

    print("\n✅ Toutes les instances arrêtées")
