"""
ETH/USDT Futures - Prix en temps réel via WebSocket MEXC
Affiche le prix du perpetual ETH_USDT toutes les secondes
"""

import websocket
import json
import time
from datetime import datetime
import sys

class ETHFuturesMonitor:
    def __init__(self):
        """
        Initialise le moniteur ETH Futures
        """
        self.ws_url = "wss://contract.mexc.com/edge"
        self.ws = None
        self.last_price = None
        self.last_data = {}
        self.ping_interval = 30  # Ping toutes les 30 secondes
        self.last_ping_time = time.time()

    def on_message(self, ws, message):
        """
        Callback appelé à chaque message reçu
        """
        try:
            data = json.loads(message)

            # Réponse au ping
            if data.get('channel') == 'pong':
                return

            # Données ticker
            if data.get('channel') == 'push.ticker':
                ticker_data = data.get('data', {})

                # Sauvegarder les données
                self.last_data = ticker_data
                self.last_price = ticker_data.get('lastPrice', 0)

                # Afficher les données
                self.display_ticker(ticker_data)

        except json.JSONDecodeError:
            print(f"❌ Erreur JSON: {message}")
        except Exception as e:
            print(f"❌ Erreur: {e}")

    def on_error(self, ws, error):
        """
        Callback appelé en cas d'erreur
        """
        print(f"❌ Erreur WebSocket: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """
        Callback appelé à la fermeture
        """
        print("\n🔌 Connexion fermée")

    def on_open(self, ws):
        """
        Callback appelé à l'ouverture de la connexion
        """
        print("✅ Connecté au WebSocket MEXC Futures")
        print("📡 Souscription à ETH_USDT perpetual...\n")

        # Souscrire au ticker ETH_USDT
        subscribe_msg = {
            "method": "sub.ticker",
            "param": {
                "symbol": "ETH_USDT"
            }
        }

        ws.send(json.dumps(subscribe_msg))

    def send_ping(self, ws):
        """
        Envoie un ping pour maintenir la connexion
        """
        current_time = time.time()
        if current_time - self.last_ping_time >= self.ping_interval:
            ping_msg = {"method": "ping"}
            ws.send(json.dumps(ping_msg))
            self.last_ping_time = current_time

    def display_ticker(self, data):
        """
        Affiche les données du ticker de manière formatée

        Args:
            data: Données du ticker
        """
        # Effacer l'écran
        print("\033[2J\033[H", end="")

        # Header
        print("=" * 80)
        print("🔥 ETH/USDT PERPETUAL FUTURES - MEXC")
        print("=" * 80)
        print(f"⏰ Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Prix principal
        last_price = data.get('lastPrice', 0)
        rise_fall_rate = data.get('riseFallRate', 0) * 100  # Convertir en %
        rise_fall_value = data.get('riseFallValue', 0)

        # Indicateur de tendance
        if rise_fall_rate >= 0:
            trend = "🟢"
            sign = "+"
        else:
            trend = "🔴"
            sign = ""

        print(f"\n{trend} PRIX: ${last_price:,.2f}")
        print(f"   Variation: {sign}{rise_fall_value:+,.2f} ({sign}{rise_fall_rate:.2f}%)")

        # Spread
        ask1 = data.get('ask1', 0)
        bid1 = data.get('bid1', 0)
        spread = ask1 - bid1

        print(f"\n📊 SPREAD")
        print(f"   Ask: ${ask1:,.2f}")
        print(f"   Bid: ${bid1:,.2f}")
        print(f"   Spread: ${spread:.2f}")

        # Prix 24h
        high_24 = data.get('high24Price', 0)
        low_24 = data.get('lower24Price', 0)

        print(f"\n📈 24H")
        print(f"   High: ${high_24:,.2f}")
        print(f"   Low:  ${low_24:,.2f}")
        print(f"   Range: ${high_24 - low_24:,.2f}")

        # Volume
        volume_24 = data.get('volume24', 0)
        hold_vol = data.get('holdVol', 0)

        print(f"\n💰 VOLUME")
        print(f"   24h: ${volume_24:,.0f}")
        print(f"   Open Interest: {hold_vol:,.0f}")

        # Prix index et fair price
        index_price = data.get('indexPrice', 0)
        fair_price = data.get('fairPrice', 0)
        funding_rate = data.get('fundingRate', 0) * 100  # En %

        print(f"\n🔍 DONNÉES AVANCÉES")
        print(f"   Index Price: ${index_price:,.2f}")
        print(f"   Fair Price:  ${fair_price:,.2f}")
        print(f"   Funding Rate: {funding_rate:.4f}%")

        print("\n" + "=" * 80)
        print("💡 Appuyez sur Ctrl+C pour arrêter")
        print("=" * 80)

    def run(self):
        """
        Lance la connexion WebSocket
        """
        print("=" * 80)
        print("🚀 DÉMARRAGE DU MONITEUR ETH FUTURES")
        print("=" * 80)
        print(f"📡 Connexion à: {self.ws_url}")
        print("🎯 Paire: ETH_USDT Perpetual")
        print("⏱️  Rafraîchissement: Temps réel (push serveur)\n")

        # Configuration WebSocket
        websocket.enableTrace(False)

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        # Lancer la connexion avec auto-ping
        try:
            self.ws.run_forever(ping_interval=self.ping_interval, ping_timeout=10)
        except KeyboardInterrupt:
            print("\n\n✋ Arrêt demandé par l'utilisateur")
            self.ws.close()
            sys.exit(0)


def main():
    """
    Fonction principale
    """
    monitor = ETHFuturesMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
