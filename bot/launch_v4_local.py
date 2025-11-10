#!/usr/bin/env python3
"""
🚀 Launcher V4 - Test Local 2 Paires

Lance 2 instances du bot V4 en parallèle pour tests locaux.
Affiche les logs des 2 paires dans le shell.

Usage:
    python launch_v4_local.py
"""

import subprocess
import sys
import time
import os
import signal

# Configuration 2 paires (DOGE + PEPE)
PAIRS = [
    {'pair': 'DOGE/USDT:USDT', 'api_key_id': 1},
    {'pair': 'PEPE/USDT:USDT', 'api_key_id': 2},
]

print("=" * 80)
print(f"🚀 LAUNCHER V4 - TEST LOCAL - {len(PAIRS)} PAIRES")
print("=" * 80)
print()
print(f"Paires:")
for p in PAIRS:
    pair_name = p['pair'].split('/')[0]
    print(f"  • {pair_name:<8} (API Key {p['api_key_id']})")
print()
print("⚠️  Mode TEST LOCAL - Logs dans le shell")
print("⚠️  Appuyez sur Ctrl+C pour arrêter toutes les instances")
print("=" * 80)
print()

# Store processes
processes = []

# Handle Ctrl+C
def signal_handler(sig, frame):
    print("\n\n⏹️  ARRÊT DE TOUTES LES INSTANCES...")
    for p in processes:
        print(f"   🛑 Arrêt {p['pair']}...")
        p['process'].terminate()

    # Wait a bit
    time.sleep(2)

    # Force kill if still running
    for p in processes:
        if p['process'].poll() is None:
            print(f"   ⚠️  Force kill {p['pair']}")
            p['process'].kill()

    print("\n✅ Toutes les instances arrêtées")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Launch instances
for p in PAIRS:
    pair = p['pair']
    api_key_id = p['api_key_id']
    pair_short = pair.split('/')[0]

    print(f"🔄 Lancement bot {pair_short} (API Key {api_key_id})...")

    # Launch process
    process = subprocess.Popen(
        [sys.executable, 'bot/bitget_hedge_fibonacci_v4_debug.py',
         '--pair', pair,
         '--api-key-id', str(api_key_id)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stderr with stdout
        text=True,
        bufsize=1,  # Line buffered
        universal_newlines=True
    )

    processes.append({
        'pair': pair_short,
        'process': process,
        'pid': process.pid
    })

    print(f"   ✅ PID {process.pid} - {pair_short}")

    # Wait between launches to avoid rate limits (10s for 2 pairs)
    if len(processes) < len(PAIRS):
        print(f"   ⏳ Attente 10s avant lancement suivant...")
        time.sleep(10)

print()
print("=" * 80)
print("✅ TOUTES LES INSTANCES LANCÉES")
print("=" * 80)
print()

for p in processes:
    print(f"   • {p['pair']:<8} - PID {p['pid']}")

print()
print("=" * 80)
print("📊 MONITORING LOGS (Temps réel)")
print("=" * 80)
print()

# Monitor outputs in real-time
try:
    while True:
        for p in processes:
            # Check if process is still running
            if p['process'].poll() is not None:
                print(f"\n⚠️  {p['pair']} (PID {p['pid']}) s'est arrêté!")
                print(f"    Code de retour: {p['process'].returncode}")
                # Could restart here if needed

            # Read output line by line (non-blocking)
            while True:
                line = p['process'].stdout.readline()
                if not line:
                    break
                print(line.rstrip())  # Print without extra newline

        time.sleep(0.1)  # Small delay to avoid busy loop

except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)
