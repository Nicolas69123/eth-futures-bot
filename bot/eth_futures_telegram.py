"""
ETH/USDT Futures Trading Bot avec Alertes Telegram
Analyse le prix en temps réel et envoie des alertes sur Telegram
"""

import websocket
import json
import time
import requests
import os
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
from pathlib import Path

# Charger le fichier .env depuis la racine du projet
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class ETHFuturesBot:
    def __init__(self):
        """Initialisation du bot"""

        # Configuration Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Configuration WebSocket
        self.ws_url = "wss://contract.mexc.com/edge"
        self.ws = None

        # Historique des prix (pour analyse)
        self.price_history = deque(maxlen=900)  # 15 minutes à 1 prix/seconde
        self.price_1min = deque(maxlen=60)      # 1 minute

        # Dernier prix
        self.current_price = None
        self.last_alert_time = {}  # Éviter spam alertes

        # Configuration alertes
        self.CRASH_THRESHOLD = -2.0  # -2% = crash
        self.CRASH_TIMEFRAME = 900    # 15 minutes en secondes
        self.VARIATION_THRESHOLD = 0.5  # 0.5% en 1 minute
        self.ALERT_COOLDOWN = 300     # 5 minutes entre alertes similaires

        # Stats
        self.start_time = datetime.now()
        self.alerts_sent = 0

    def send_telegram(self, message):
        """
        Envoie un message sur Telegram

        Args:
            message: Message à envoyer
        """
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  Token ou Chat ID manquant")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"

        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.alerts_sent += 1
                print(f"✅ Message Telegram envoyé ({self.alerts_sent} alertes)")
                return True
            else:
                print(f"❌ Erreur Telegram: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erreur envoi Telegram: {e}")
            return False

    def can_send_alert(self, alert_type):
        """
        Vérifie si on peut envoyer une alerte (cooldown)

        Args:
            alert_type: Type d'alerte (crash, variation, opportunity)

        Returns:
            bool: True si on peut envoyer
        """
        now = time.time()
        last_time = self.last_alert_time.get(alert_type, 0)

        if now - last_time >= self.ALERT_COOLDOWN:
            self.last_alert_time[alert_type] = now
            return True
        return False

    def check_crash(self):
        """
        Détecte un crash (-2% en moins de 15 minutes)

        Returns:
            dict or None: Infos du crash si détecté
        """
        if len(self.price_history) < 2:
            return None

        current = self.current_price

        # Vérifier sur différentes périodes (30s, 1min, 5min, 15min)
        timeframes = [
            (30, "30 secondes"),
            (60, "1 minute"),
            (300, "5 minutes"),
            (900, "15 minutes")
        ]

        for seconds, label in timeframes:
            if len(self.price_history) >= seconds:
                old_price = list(self.price_history)[-seconds]
                change_pct = ((current - old_price) / old_price) * 100

                if change_pct <= self.CRASH_THRESHOLD:
                    return {
                        'timeframe': label,
                        'old_price': old_price,
                        'new_price': current,
                        'change_pct': change_pct,
                        'change_value': current - old_price
                    }

        return None

    def check_high_variation(self):
        """
        Détecte variation importante sur 1 minute (> 0.5%)

        Returns:
            dict or None: Infos de la variation si détectée
        """
        if len(self.price_1min) < 60:
            return None

        current = self.current_price
        price_1min_ago = self.price_1min[0]

        change_pct = abs(((current - price_1min_ago) / price_1min_ago) * 100)

        if change_pct >= self.VARIATION_THRESHOLD:
            return {
                'old_price': price_1min_ago,
                'new_price': current,
                'change_pct': change_pct if current >= price_1min_ago else -change_pct,
                'change_value': current - price_1min_ago
            }

        return None

    def check_trading_opportunity(self):
        """
        Détecte opportunité de trading (selon stratégie)
        Basé sur stratégie crash buying : crash suivi d'un rebond

        Returns:
            dict or None: Infos de l'opportunité si détectée
        """
        if len(self.price_history) < 300:  # Au moins 5 minutes d'historique
            return None

        current = self.current_price
        prices = list(self.price_history)

        # Détecter pattern : chute rapide puis stabilisation/rebond
        # 1. Y a-t-il eu une chute de -1.5% dans les 5 dernières minutes ?
        price_5min_ago = prices[-300]
        drop_pct = ((current - price_5min_ago) / price_5min_ago) * 100

        if drop_pct < -1.5:  # Il y a eu une chute
            # 2. Y a-t-il un rebond dans les dernières 30 secondes ?
            if len(prices) >= 30:
                price_30s_ago = prices[-30]
                recent_change = ((current - price_30s_ago) / price_30s_ago) * 100

                if recent_change > 0.2:  # Rebond de +0.2%
                    return {
                        'type': 'REBOND après CHUTE',
                        'drop_pct': drop_pct,
                        'rebond_pct': recent_change,
                        'current_price': current,
                        'low_price': min(prices[-300:])
                    }

        return None

    def analyze_and_alert(self):
        """
        Analyse le prix et envoie des alertes si nécessaire
        """
        if not self.current_price:
            return

        # 1. Vérifier CRASH
        crash = self.check_crash()
        if crash and self.can_send_alert('crash'):
            message = f"""
🔴 <b>ALERTE CRASH DÉTECTÉ !</b>

📉 ETH/USDT a chuté de <b>{crash['change_pct']:.2f}%</b> en {crash['timeframe']}

💰 Prix actuel: <b>${crash['new_price']:,.2f}</b>
📊 Prix avant: ${crash['old_price']:,.2f}
📉 Perte: ${crash['change_value']:,.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(message)

        # 2. Vérifier VARIATION IMPORTANTE
        variation = self.check_high_variation()
        if variation and self.can_send_alert('variation'):
            trend = "📈" if variation['change_pct'] > 0 else "📉"
            action = "HAUSSE" if variation['change_pct'] > 0 else "BAISSE"

            message = f"""
{trend} <b>VARIATION IMPORTANTE !</b>

{action} de <b>{abs(variation['change_pct']):.2f}%</b> en 1 minute

💰 Prix actuel: <b>${variation['new_price']:,.2f}</b>
📊 Prix il y a 1 min: ${variation['old_price']:,.2f}
{trend} Variation: ${variation['change_value']:+,.2f}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(message)

        # 3. Vérifier OPPORTUNITÉ DE TRADING
        opportunity = self.check_trading_opportunity()
        if opportunity and self.can_send_alert('opportunity'):
            message = f"""
💰 <b>OPPORTUNITÉ DE TRADING !</b>

🎯 Pattern détecté: <b>{opportunity['type']}</b>

📉 Chute initiale: {opportunity['drop_pct']:.2f}%
📈 Rebond récent: +{opportunity['rebond_pct']:.2f}%

💵 Prix actuel: <b>${opportunity['current_price']:,.2f}</b>
🔻 Plus bas récent: ${opportunity['low_price']:,.2f}

💡 Possibilité d'entrée pour stratégie grid trading

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(message)

    def on_message(self, ws, message):
        """Callback WebSocket - message reçu"""
        try:
            data = json.loads(message)

            # Ignorer pong
            if data.get('channel') == 'pong':
                return

            # Données ticker
            if data.get('channel') == 'push.ticker':
                ticker_data = data.get('data', {})
                price = ticker_data.get('lastPrice', 0)

                if price > 0:
                    self.current_price = price

                    # Ajouter aux historiques
                    self.price_history.append(price)
                    self.price_1min.append(price)

                    # Analyser et alerter
                    self.analyze_and_alert()

                    # Log console (silencieux)
                    if len(self.price_history) % 60 == 0:  # Toutes les minutes
                        print(f"📊 Prix: ${price:,.2f} | Historique: {len(self.price_history)}s | Alertes: {self.alerts_sent}")

        except Exception as e:
            print(f"❌ Erreur traitement message: {e}")

    def on_error(self, ws, error):
        """Callback WebSocket - erreur"""
        print(f"❌ Erreur WebSocket: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """Callback WebSocket - fermeture"""
        print("🔌 Connexion fermée, reconnexion dans 5s...")
        time.sleep(5)

    def on_open(self, ws):
        """Callback WebSocket - ouverture"""
        print("✅ Connecté au WebSocket MEXC Futures")

        # Envoyer message de démarrage
        startup_msg = f"""
🤖 <b>BOT ETH FUTURES DÉMARRÉ</b>

📡 Connexion: MEXC Futures
🎯 Paire: ETH/USDT Perpetual
⏱️  Analyse: Temps réel (1x/seconde)

🔔 <b>Alertes activées:</b>
🔴 Crash: -2% en 15 min
⚡ Variation: ±0.5% en 1 min
💰 Opportunité: Pattern trading

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_telegram(startup_msg)

        # Souscrire au ticker
        subscribe_msg = {
            "method": "sub.ticker",
            "param": {"symbol": "ETH_USDT"}
        }
        ws.send(json.dumps(subscribe_msg))
        print("📡 Souscription à ETH_USDT activée")

    def run(self):
        """Lance le bot"""
        print("=" * 80)
        print("🚀 ETH FUTURES TRADING BOT")
        print("=" * 80)
        print(f"📡 WebSocket: {self.ws_url}")
        print(f"💬 Telegram: {'✅ Configuré' if self.telegram_token else '❌ Non configuré'}")
        print("=" * 80)

        # Vérifier config
        if not self.telegram_token or not self.telegram_chat_id:
            print("\n⚠️  ATTENTION: Variables d'environnement manquantes!")
            print("Définir: TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID\n")

        # Configuration WebSocket
        websocket.enableTrace(False)

        while True:
            try:
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )

                # Lancer avec ping automatique
                self.ws.run_forever(ping_interval=30, ping_timeout=10)

            except KeyboardInterrupt:
                print("\n\n✋ Arrêt demandé")
                if self.telegram_token:
                    self.send_telegram("🛑 Bot arrêté manuellement")
                break
            except Exception as e:
                print(f"❌ Erreur: {e}")
                print("🔄 Reconnexion dans 5s...")
                time.sleep(5)


def main():
    """Point d'entrée"""
    bot = ETHFuturesBot()
    bot.run()


if __name__ == "__main__":
    main()
