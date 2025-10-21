#!/usr/bin/env python3
"""
🚀 Launcher Multi-Paires - Lance 6 instances du bot

Lance 6 instances du bot simultanément, une par paire.
"""

import subprocess
import time
import sys

# Paires à trader
PAIRS = [
    'DOGE/USDT:USDT',
    'PEPE/USDT:USDT',
    'SHIB/USDT:USDT',
    'ETH/USDT:USDT',
    'SOL/USDT:USDT',
    'AVAX/USDT:USDT',
]

print("="*80)
print("🚀 LANCEMENT MULTI-PAIRES - 6 INSTANCES")
print("="*80)
print(f"\nPaires: {', '.join([p.split('/')[0] for p in PAIRS])}\n")

# Store processes
processes = []

# Launch each instance
for pair in PAIRS:
    pair_short = pair.split('/')[0]
    print(f"🔄 Lancement bot {pair_short}...")

    # Launch in background
    process = subprocess.Popen(
        [sys.executable, 'bot/bitget_hedge_multi_instance.py', '--pair', pair],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    processes.append({
        'pair': pair_short,
        'process': process,
        'pid': process.pid
    })

    print(f"   ✅ PID {process.pid} - {pair_short}")
    time.sleep(1)  # Petit délai entre chaque lancement

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
