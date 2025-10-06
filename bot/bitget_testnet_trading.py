"""
Bitget Testnet Trading Bot - Stratégie Crash Buying + Grid Trading
Analyse ETH/USDT en temps réel et exécute automatiquement la stratégie
"""

import ccxt
import time
import os
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
from pathlib import Path
import requests

# Charger le fichier .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class BitgetTestnetBot:
    def __init__(self):
        """Initialisation du bot"""

        # Configuration Bitget API
        self.api_key = os.getenv('BITGET_API_KEY')
        self.api_secret = os.getenv('BITGET_SECRET')
        self.api_password = os.getenv('BITGET_PASSPHRASE')

        # Configuration Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Initialiser l'exchange Bitget avec header PAPTRADING
        self.exchange = ccxt.bitget({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'password': self.api_password,
            'options': {
                'defaultType': 'swap',  # Futures perpetual
            },
            'headers': {
                'PAPTRADING': '1'  # Header obligatoire pour demo trading
            },
            'enableRateLimit': True
        })

        # Note: Utilise des clés API DEMO créées depuis le mode Demo Trading de Bitget
        # IMPORTANT: Bug connu ccxt+Bitget demo - si erreur persiste, utiliser Binance testnet

        # Configuration trading
        self.symbol = 'ETH/USDT:USDT'  # ETH perpetual futures
        self.current_price = None
        self.price_history = deque(maxlen=900)  # 15 minutes

        # Paramètres stratégie
        self.CRASH_THRESHOLD = -2.0  # -2% = crash
        self.CRASH_TIMEFRAME = 900    # 15 minutes
        self.GRID_SPACING = 1.0       # Espacement grille : 1%
        self.GRID_LEVELS = 5          # Nombre de niveaux
        self.ORDER_SIZE = 0.01        # Taille de chaque ordre (ETH)

        # État du bot
        self.crash_detected = False
        self.grid_active = False
        self.grid_orders = []
        self.entry_price = None

        # Stats
        self.total_orders = 0
        self.total_profit = 0

    def send_telegram(self, message):
        """Envoie un message Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  Telegram non configuré")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Erreur Telegram: {e}")
            return False

    def get_balance(self):
        """Récupère le solde du compte"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['free'] if 'USDT' in balance else 0
            return usdt_balance
        except Exception as e:
            print(f"❌ Erreur récupération balance: {e}")
            return 0

    def get_current_price(self):
        """Récupère le prix actuel ETH"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return ticker['last']
        except Exception as e:
            print(f"❌ Erreur prix: {e}")
            return None

    def detect_crash(self):
        """
        Détecte un crash (-2% en moins de 15 min)

        Returns:
            dict or None: Infos du crash si détecté
        """
        if len(self.price_history) < 60:  # Au moins 1 minute d'historique
            return None

        current = self.current_price

        # Vérifier sur différentes périodes
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
                        'change_pct': change_pct
                    }

        return None

    def place_market_order(self, side, amount):
        """
        Place un ordre au marché

        Args:
            side: 'buy' ou 'sell'
            amount: Quantité en ETH

        Returns:
            dict: Ordre créé ou None
        """
        try:
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side=side,
                amount=amount
            )

            self.total_orders += 1
            print(f"✅ Ordre {side} exécuté: {amount} ETH @ ${self.current_price:,.2f}")

            return order

        except Exception as e:
            print(f"❌ Erreur ordre: {e}")
            return None

    def place_limit_order(self, side, amount, price):
        """
        Place un ordre limite

        Args:
            side: 'buy' ou 'sell'
            amount: Quantité en ETH
            price: Prix limite

        Returns:
            dict: Ordre créé ou None
        """
        try:
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='limit',
                side=side,
                amount=amount,
                price=price
            )

            print(f"📝 Ordre limite {side} placé: {amount} ETH @ ${price:,.2f}")

            return order

        except Exception as e:
            print(f"❌ Erreur ordre limite: {e}")
            return None

    def execute_crash_strategy(self, crash_info):
        """
        Exécute la stratégie quand un crash est détecté

        Args:
            crash_info: Informations du crash
        """
        if self.crash_detected or self.grid_active:
            return  # Déjà en position

        print("\n" + "="*80)
        print("🔴 CRASH DÉTECTÉ - EXÉCUTION STRATÉGIE")
        print("="*80)

        # 1. Acheter au marché (première entrée)
        order = self.place_market_order('buy', self.ORDER_SIZE)

        if order:
            self.crash_detected = True
            self.entry_price = self.current_price
            self.grid_active = True

            # 2. Placer les ordres de la grille (achats échelonnés)
            self.setup_grid_orders()

            # 3. Notifier sur Telegram
            message = f"""
🔴 <b>CRASH DÉTECTÉ - STRATÉGIE ACTIVÉE</b>

📉 Chute: <b>{crash_info['change_pct']:.2f}%</b> en {crash_info['timeframe']}
💰 Prix entrée: <b>${self.entry_price:,.2f}</b>

✅ Position ouverte: {self.ORDER_SIZE} ETH
📊 Grille activée: {self.GRID_LEVELS} niveaux

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(message)

    def setup_grid_orders(self):
        """
        Configure les ordres de grille (achats échelonnés)
        """
        print("\n📊 Configuration de la grille de trading...")

        # Placer des ordres limites tous les -1% en dessous
        for i in range(1, self.GRID_LEVELS + 1):
            # Prix de chaque niveau (-1%, -2%, -3%, etc.)
            level_price = self.entry_price * (1 - (i * self.GRID_SPACING / 100))

            # Placer ordre limite d'achat
            order = self.place_limit_order('buy', self.ORDER_SIZE, level_price)

            if order:
                self.grid_orders.append({
                    'level': i,
                    'price': level_price,
                    'order': order,
                    'filled': False
                })

        print(f"✅ Grille configurée: {len(self.grid_orders)} ordres placés")

    def check_grid_orders(self):
        """
        Vérifie si les ordres de la grille sont exécutés
        """
        if not self.grid_active:
            return

        for grid_order in self.grid_orders:
            if grid_order['filled']:
                continue

            # Vérifier si le prix a atteint ce niveau
            if self.current_price <= grid_order['price']:
                print(f"✅ Niveau {grid_order['level']} atteint: ${grid_order['price']:,.2f}")
                grid_order['filled'] = True

                # Notifier
                message = f"""
📊 <b>GRILLE - Niveau {grid_order['level']} atteint</b>

💰 Prix: ${grid_order['price']:,.2f}
📉 Baisse totale: {((grid_order['price'] - self.entry_price) / self.entry_price * 100):.2f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)

    def check_take_profit(self):
        """
        Vérifie si on doit prendre les profits
        """
        if not self.grid_active or not self.entry_price:
            return

        # Take profit à +2% du prix d'entrée moyen
        profit_target = self.entry_price * 1.02

        if self.current_price >= profit_target:
            print("\n💰 TAKE PROFIT ATTEINT - FERMETURE POSITIONS")

            # Annuler tous les ordres en attente
            self.cancel_all_orders()

            # Vendre toutes les positions
            # (Dans un vrai bot, calculer la quantité totale possédée)
            total_position = self.ORDER_SIZE  # Simplifié
            self.place_market_order('sell', total_position)

            # Réinitialiser
            profit_pct = ((self.current_price - self.entry_price) / self.entry_price) * 100

            message = f"""
💰 <b>TAKE PROFIT EXÉCUTÉ</b>

📈 Profit: <b>+{profit_pct:.2f}%</b>
💵 Prix sortie: ${self.current_price:,.2f}
📊 Prix entrée: ${self.entry_price:,.2f}

✅ Positions fermées

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(message)

            self.reset_strategy()

    def cancel_all_orders(self):
        """Annule tous les ordres en attente"""
        try:
            self.exchange.cancel_all_orders(self.symbol)
            print("🗑️  Tous les ordres annulés")
        except Exception as e:
            print(f"❌ Erreur annulation: {e}")

    def reset_strategy(self):
        """Réinitialise l'état de la stratégie"""
        self.crash_detected = False
        self.grid_active = False
        self.grid_orders = []
        self.entry_price = None
        print("🔄 Stratégie réinitialisée - En attente du prochain crash")

    def run(self):
        """Boucle principale du bot"""
        print("="*80)
        print("🚀 BITGET TESTNET TRADING BOT - STRATÉGIE CRASH BUYING")
        print("="*80)
        print(f"💬 Telegram: {'✅' if self.telegram_token else '❌'}")
        print(f"🔑 API Bitget: {'✅' if self.api_key else '❌'}")
        print("="*80)

        # Vérifier configuration
        if not self.api_key or not self.api_secret or not self.api_password:
            print("\n❌ ERREUR: Clés API Bitget manquantes!")
            print("Définir dans .env:")
            print("  BITGET_API_KEY=...")
            print("  BITGET_SECRET=...")
            print("  BITGET_PASSPHRASE=...")
            return

        try:
            # Charger les marchés
            print("\n📡 Connexion à Bitget Testnet...")
            self.exchange.load_markets()

            # Vérifier balance
            balance = self.get_balance()
            print(f"💰 Balance USDT: ${balance:,.2f}")

            # Message de démarrage
            startup_msg = f"""
🤖 <b>BOT BITGET TESTNET DÉMARRÉ</b>

🎯 Paire: ETH/USDT Perpetual
💰 Balance: ${balance:,.2f} USDT
⏱️  Mode: DÉMO (fonds virtuels)

📊 <b>Stratégie:</b>
🔴 Détection crash: -2% en 15 min
📈 Grid trading: {self.GRID_LEVELS} niveaux
💵 Taille ordre: {self.ORDER_SIZE} ETH
🎯 Take profit: +2%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(startup_msg)

            print("\n✅ Bot démarré - Surveillance active...")
            print("🔍 En attente d'un crash pour entrer en position...\n")

            # Boucle principale
            iteration = 0
            while True:
                try:
                    # Récupérer prix actuel
                    price = self.get_current_price()

                    if price:
                        self.current_price = price
                        self.price_history.append(price)

                        # 1. Vérifier si crash détecté
                        crash = self.detect_crash()
                        if crash and not self.crash_detected:
                            self.execute_crash_strategy(crash)

                        # 2. Vérifier ordres de grille
                        self.check_grid_orders()

                        # 3. Vérifier take profit
                        self.check_take_profit()

                        # Log toutes les 60 secondes
                        if iteration % 60 == 0:
                            status = "📊 GRILLE ACTIVE" if self.grid_active else "🔍 EN ATTENTE"
                            print(f"{status} | Prix: ${price:,.2f} | Historique: {len(self.price_history)}s | Ordres: {self.total_orders}")

                    iteration += 1
                    time.sleep(1)  # Analyser toutes les secondes

                except KeyboardInterrupt:
                    print("\n\n✋ Arrêt demandé...")
                    self.send_telegram("🛑 Bot arrêté manuellement")
                    break
                except Exception as e:
                    print(f"❌ Erreur: {e}")
                    time.sleep(5)

        except Exception as e:
            print(f"\n❌ Erreur fatale: {e}")
            self.send_telegram(f"❌ Bot arrêté - Erreur: {str(e)}")


def main():
    """Point d'entrée"""
    bot = BitgetTestnetBot()
    bot.run()


if __name__ == "__main__":
    main()
