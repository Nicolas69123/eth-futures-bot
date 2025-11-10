#!/usr/bin/env python3
"""
Script de test pour V4.1 corrigée
Lance le bot pendant 2 minutes puis l'arrête proprement
"""

import subprocess
import time
import signal
import sys

def main():
    print("🚀 Lancement du test V4.1 pendant 2 minutes...")

    # Lancer le bot
    process = subprocess.Popen(
        ['python', 'bot/bitget_hedge_fibonacci_v4_debug.py', '--pair', 'DOGE/USDT:USDT'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    start_time = time.time()
    duration = 120  # 2 minutes

    try:
        # Afficher les logs en temps réel pendant 2 minutes
        while time.time() - start_time < duration:
            if process.poll() is not None:
                # Le processus s'est terminé
                print("❌ Le bot s'est arrêté prématurément!")
                break

            # Lire une ligne de sortie
            line = process.stdout.readline()
            if line:
                print(line.rstrip())

    except KeyboardInterrupt:
        print("\n⚠️ Test interrompu par l'utilisateur")

    finally:
        # Arrêter le bot proprement
        print("\n⏹️ Arrêt du bot...")
        process.terminate()
        time.sleep(2)
        if process.poll() is None:
            process.kill()

        print("✅ Test terminé!")

if __name__ == "__main__":
    main()