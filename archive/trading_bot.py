"""
Trading Bot - MEXC API
Détecte les paires à faible volatilité avec gros volume
Affiche les prix en temps réel
"""

import ccxt
import time
from datetime import datetime
import sys

class TradingBot:
    def __init__(self, api_key=None, api_secret=None):
        """
        Initialise la connexion à MEXC

        Args:
            api_key: Clé API MEXC (optionnel pour lecture seule)
            api_secret: Secret API MEXC (optionnel pour lecture seule)
        """
        self.exchange = ccxt.mexc({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # Trading spot
            }
        })

        self.top_pairs = []

    def calculate_volatility(self, ticker):
        """
        Calcule la volatilité d'une paire sur 24h
        Volatilité = (High - Low) / Low * 100

        Args:
            ticker: Données du ticker

        Returns:
            float: Volatilité en pourcentage
        """
        if ticker['high'] and ticker['low'] and ticker['low'] > 0:
            volatility = ((ticker['high'] - ticker['low']) / ticker['low']) * 100
            return volatility
        return None

    def get_low_volatility_high_volume_pairs(self, min_volume_usdt=100000, top_n=5):
        """
        Récupère les paires avec faible volatilité et gros volume

        Args:
            min_volume_usdt: Volume minimum en USDT (défaut 100k)
            top_n: Nombre de paires à retourner

        Returns:
            list: Liste des top paires
        """
        print("🔍 Récupération des données de marché MEXC...")

        try:
            # Récupérer tous les tickers
            tickers = self.exchange.fetch_tickers()

            # Filtrer les paires USDT avec volume suffisant
            valid_pairs = []

            for symbol, ticker in tickers.items():
                # Filtrer uniquement les paires /USDT
                if not symbol.endswith('/USDT'):
                    continue

                # Vérifier que les données sont complètes
                if not all([ticker.get('quoteVolume'), ticker.get('high'), ticker.get('low')]):
                    continue

                volume = ticker['quoteVolume']  # Volume en USDT

                # Filtrer par volume minimum
                if volume < min_volume_usdt:
                    continue

                # Calculer volatilité
                volatility = self.calculate_volatility(ticker)
                if volatility is None:
                    continue

                valid_pairs.append({
                    'symbol': symbol,
                    'price': ticker['last'],
                    'volume_usdt': volume,
                    'volatility': volatility,
                    'high_24h': ticker['high'],
                    'low_24h': ticker['low'],
                    'change_24h': ticker['percentage']
                })

            # Trier par volatilité croissante (faible volatilité d'abord)
            # puis par volume décroissant (gros volume d'abord)
            sorted_pairs = sorted(
                valid_pairs,
                key=lambda x: (x['volatility'], -x['volume_usdt'])
            )

            # Prendre les top N
            self.top_pairs = sorted_pairs[:top_n]

            return self.top_pairs

        except Exception as e:
            print(f"❌ Erreur lors de la récupération des données: {e}")
            return []

    def display_top_pairs(self):
        """
        Affiche les paires sélectionnées avec leurs statistiques
        """
        if not self.top_pairs:
            print("Aucune paire trouvée")
            return

        print("\n" + "="*80)
        print("📊 TOP 5 PAIRES - Faible Volatilité & Gros Volume")
        print("="*80)

        for i, pair in enumerate(self.top_pairs, 1):
            print(f"\n{i}. {pair['symbol']}")
            print(f"   💰 Prix actuel:      ${pair['price']:.4f}")
            print(f"   📊 Volume 24h:       ${pair['volume_usdt']:,.0f}")
            print(f"   📉 Volatilité 24h:   {pair['volatility']:.2f}%")
            print(f"   📈 Variation 24h:    {pair['change_24h']:.2f}%")
            print(f"   🔺 High 24h:         ${pair['high_24h']:.4f}")
            print(f"   🔻 Low 24h:          ${pair['low_24h']:.4f}")

        print("\n" + "="*80 + "\n")

    def display_realtime_prices(self, refresh_interval=5):
        """
        Affiche les prix en temps réel des paires sélectionnées

        Args:
            refresh_interval: Intervalle de rafraîchissement en secondes
        """
        if not self.top_pairs:
            print("❌ Aucune paire sélectionnée")
            return

        symbols = [pair['symbol'] for pair in self.top_pairs]

        print("🔄 Surveillance des prix en temps réel (Ctrl+C pour arrêter)...\n")

        try:
            while True:
                # Effacer l'écran (optionnel)
                print("\033[2J\033[H", end="")  # ANSI escape code pour clear

                print(f"⏰ Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*80)

                # Récupérer les prix actuels
                for symbol in symbols:
                    try:
                        ticker = self.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        change = ticker['percentage']

                        # Indicateur de tendance
                        trend = "🟢" if change >= 0 else "🔴"

                        print(f"{trend} {symbol:15} | Prix: ${price:>12.4f} | Variation: {change:>+7.2f}%")

                    except Exception as e:
                        print(f"⚠️  {symbol:15} | Erreur: {str(e)[:40]}")

                print("="*80)
                print(f"\n⏳ Prochain rafraîchissement dans {refresh_interval}s...")

                time.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n\n✋ Arrêt de la surveillance")
            sys.exit(0)


def main():
    """
    Fonction principale
    """
    print("="*80)
    print("🤖 TRADING BOT - MEXC")
    print("="*80)

    # TODO: Remplacer par vos clés API MEXC (optionnel pour lecture seule)
    API_KEY = None  # Mettre votre clé API ici
    API_SECRET = None  # Mettre votre secret ici

    # Initialiser le bot
    bot = TradingBot(api_key=API_KEY, api_secret=API_SECRET)

    # Paramètres
    MIN_VOLUME = 100000  # Volume minimum: 100k USDT
    TOP_N = 5  # Top 5 paires
    REFRESH_INTERVAL = 5  # Rafraîchir toutes les 5 secondes

    # 1. Récupérer les paires optimales
    pairs = bot.get_low_volatility_high_volume_pairs(
        min_volume_usdt=MIN_VOLUME,
        top_n=TOP_N
    )

    if not pairs:
        print("❌ Aucune paire trouvée avec les critères spécifiés")
        return

    # 2. Afficher les statistiques
    bot.display_top_pairs()

    # 3. Demander si on lance la surveillance temps réel
    try:
        response = input("▶️  Lancer la surveillance des prix en temps réel ? (o/n): ")
        if response.lower() in ['o', 'y', 'oui', 'yes']:
            bot.display_realtime_prices(refresh_interval=REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n👋 Au revoir!")


if __name__ == "__main__":
    main()
