#!/usr/bin/env python3
"""
Fibonacci Trading Bot - Architecture Orientée Objet
Version ultra-rapide et modulaire pour trading multi-paires
Adaptation automatique aux minimums de l'exchange
"""

import ccxt
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from enum import Enum

# Configuration
load_dotenv()

# ================================================================================
# DATA CLASSES & ENUMS
# ================================================================================

class PositionSide(Enum):
    LONG = "long"
    SHORT = "short"

class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"
    TAKE_PROFIT = "profit_plan"

@dataclass
class MarketInfo:
    """Informations complètes sur le marché et les limites"""
    symbol: str
    min_size: float
    min_notional: float  # Minimum margin en USDT
    max_leverage: int
    price_precision: int
    size_precision: int
    current_price: float
    contract_size: float  # Taille d'un contrat

    def get_minimum_margin(self, leverage: int) -> float:
        """Calcule la marge minimum nécessaire"""
        # La marge minimum est le minimum notional divisé par le leverage
        # Mais on doit respecter le minimum notional
        return max(self.min_notional / leverage, self.min_notional)

@dataclass
class PositionData:
    """Données d'une position"""
    side: PositionSide
    entry_price: float
    size: float
    margin: float
    order_id: Optional[str] = None
    is_open: bool = False

# ================================================================================
# CLASSES PRINCIPALES
# ================================================================================

class Position:
    """Gère une position (LONG ou SHORT)"""

    def __init__(self, exchange, symbol: str, side: PositionSide, margin: float, leverage: int):
        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.margin = margin
        self.leverage = leverage
        self.entry_price = None
        self.size = None
        self.order_id = None
        self.is_open = False

    def open(self, current_price: float) -> Dict:
        """Ouvre la position avec ordre MARKET"""
        try:
            # Calcul de la taille
            notional = self.margin * self.leverage
            self.size = int(notional / current_price)

            # Paramètres selon le side
            side_str = "buy" if self.side == PositionSide.LONG else "sell"

            logging.info(f"  📍 Ouverture {self.side.value.upper()} : {self.size} contrats @ ${current_price:.8f}")
            logging.info(f"     Margin: ${self.margin:.2f}, Leverage: {self.leverage}x, Notional: ${notional:.2f}")

            logging.debug(f"  DEBUG Position.open():")
            logging.debug(f"    - Symbol: {self.symbol}")
            logging.debug(f"    - Side: {side_str}")
            logging.debug(f"    - Size calculée: {self.size}")
            logging.debug(f"    - Prix: ${current_price}")
            logging.debug(f"    - Notional: ${notional}")

            # Ordre MARKET
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=side_str,
                amount=self.size,
                params={
                    'tdMode': 'cross',
                    'tradeSide': 'open'
                }
            )

            self.order_id = order['id']
            self.is_open = True
            self.entry_price = current_price  # On utilisera le prix réel après

            logging.debug(f"    - Order response: {order}")
            logging.info(f"    ✅ {self.side.value.upper()} ouvert: {self.order_id}")
            return order

        except Exception as e:
            logging.error(f"    ❌ Erreur ouverture {self.side.value}: {e}")
            logging.debug(f"    DEBUG Exception: {type(e).__name__}: {str(e)}")
            raise

    def update_from_exchange(self) -> bool:
        """Met à jour les données depuis l'exchange"""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if pos['side'] == self.side.value:
                    self.entry_price = pos['entryPrice'] or self.entry_price
                    self.size = pos['contracts'] or self.size
                    self.is_open = pos['contracts'] > 0
                    return True
            return False
        except Exception as e:
            logging.error(f"Erreur update position: {e}")
            return False

class LimitFibonacci:
    """Gère un ordre LIMIT Fibonacci"""

    def __init__(self, exchange, symbol: str, position: Position, fibo_level: float):
        self.exchange = exchange
        self.symbol = symbol
        self.position = position
        self.fibo_level = fibo_level
        self.order_id = None
        self.price = None
        self.size = None

    def place(self) -> Dict:
        """Place l'ordre LIMIT Fibonacci"""
        try:
            # Calcul du prix selon le niveau Fibonacci
            if self.position.side == PositionSide.LONG:
                # Pour un LONG, on achète plus bas (double down)
                self.price = self.position.entry_price * (1 - self.fibo_level)
                side = "buy"
            else:
                # Pour un SHORT, on vend plus haut (double down)
                self.price = self.position.entry_price * (1 + self.fibo_level)
                side = "sell"

            # Même taille que la position initiale (pour doubler)
            self.size = self.position.size

            # Arrondir le prix selon la précision
            if self.price < 0.001:
                self.price = round(self.price, 8)
            elif self.price < 1:
                self.price = round(self.price, 5)
            else:
                self.price = round(self.price, 2)

            logging.info(f"  📊 LIMIT {self.position.side.value} Fibo {self.fibo_level*100}%: {self.size} @ ${self.price:.8f}")

            order = self.exchange.create_limit_order(
                symbol=self.symbol,
                side=side,
                amount=self.size,
                price=self.price,
                params={
                    'tdMode': 'cross',
                    'tradeSide': 'open'
                }
            )

            self.order_id = order['id']
            logging.info(f"    ✅ LIMIT placé: {self.order_id}")
            return order

        except Exception as e:
            logging.error(f"    ❌ Erreur LIMIT Fibonacci: {e}")
            raise

class OrderTakeProfit:
    """Gère un ordre Take Profit"""

    def __init__(self, exchange, symbol: str, position: Position, tp_percent: float):
        self.exchange = exchange
        self.symbol = symbol
        self.position = position
        self.tp_percent = tp_percent
        self.order_id = None
        self.trigger_price = None

    def place(self) -> Dict:
        """Place l'ordre Take Profit"""
        try:
            # Calcul du prix TP
            if self.position.side == PositionSide.LONG:
                self.trigger_price = self.position.entry_price * (1 + self.tp_percent)
            else:
                self.trigger_price = self.position.entry_price * (1 - self.tp_percent)

            # Arrondir selon la précision
            if self.trigger_price < 0.001:
                self.trigger_price = round(self.trigger_price, 8)
            elif self.trigger_price < 1:
                self.trigger_price = round(self.trigger_price, 5)
            else:
                self.trigger_price = round(self.trigger_price, 2)

            logging.info(f"  🎯 TP {self.position.side.value}: {self.position.size} @ ${self.trigger_price:.8f}")

            # Utiliser l'endpoint TP/SL de Bitget
            params = {
                'symbol': self.symbol.replace('/', '').replace(':USDT', ''),
                'marginCoin': 'USDT',
                'productType': 'USDT-FUTURES',  # AJOUT du productType manquant
                'planType': 'profit_plan',
                'triggerPrice': str(self.trigger_price),
                'triggerType': 'mark_price',
                'size': str(int(self.position.size)),
                'side': 'buy' if self.position.side == PositionSide.SHORT else 'sell',
                'tradeSide': 'close',
                'orderType': 'market',
                'holdSide': self.position.side.value
            }

            logging.debug(f"  DEBUG TP params: {params}")

            response = self.exchange.privateMixPostV2MixOrderPlaceTpslOrder(params)

            if response and 'data' in response:
                self.order_id = response['data']['orderId']
                logging.info(f"    ✅ TP placé: {self.order_id}")
                return response['data']
            else:
                raise Exception(f"Réponse TP invalide: {response}")

        except Exception as e:
            logging.error(f"    ❌ Erreur TP: {e}")
            raise

# ================================================================================
# BOT PRINCIPAL
# ================================================================================

class FibonacciBot:
    """Bot de trading Fibonacci multi-paires"""

    def __init__(self):
        # Configuration de base
        self.PAIRS = [
            {'symbol': 'DOGE/USDT:USDT', 'api_key_id': 1},
            {'symbol': 'PEPE/USDT:USDT', 'api_key_id': 2}
        ]

        self.TP_PERCENT = 0.005  # 0.5%
        self.FIBO_LEVELS = [0.005, 0.01, 0.02, 0.04, 0.08]  # 0.5%, 1%, 2%, 4%, 8%
        self.DEFAULT_LEVERAGE = 50  # Leverage par défaut
        self.MONITORING_DELAY = 0.25  # 250ms (TURBO)

        # Stockage des objets
        self.positions = {}  # {pair: {long: Position, short: Position}}
        self.limit_orders = {}  # {pair: [LimitFibonacci, ...]}
        self.tp_orders = {}  # {pair: [OrderTakeProfit, ...]}
        self.market_info = {}  # {pair: MarketInfo}

        # Exchanges (un par clé API)
        self.exchanges = {}

        # Mapping symbol → api_key_id pour le monitoring
        self.pair_to_api = {p['symbol']: p['api_key_id'] for p in self.PAIRS}

        # Telegram credentials
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Logging
        self.setup_logging()

    def setup_logging(self):
        """Configure le système de logging avec DEBUG"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Deux fichiers : un pour INFO, un pour DEBUG
        log_file = f"logs/fibonacci_{timestamp}.log"
        debug_file = f"logs/fibonacci_debug_{timestamp}.log"

        os.makedirs("logs", exist_ok=True)

        # Configuration du logger racine
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)  # Capturer TOUT

        # Formatter avec plus de détails
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        # Handler pour fichier DEBUG (TOUT)
        debug_handler = logging.FileHandler(debug_file)
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(formatter)

        # Handler pour fichier INFO (normal)
        info_handler = logging.FileHandler(log_file)
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)

        # Handler pour console (INFO seulement pour lisibilité)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # Ajouter tous les handlers
        logger.addHandler(debug_handler)
        logger.addHandler(info_handler)
        logger.addHandler(console_handler)

        logging.info("="*80)
        logging.info("🚀 FIBONACCI BOT - ADAPTIVE MARGIN EDITION [DEBUG MODE]")
        logging.info("="*80)
        logging.info(f"📁 Logs INFO: {log_file}")
        logging.info(f"🔍 Logs DEBUG: {debug_file}")
        logging.debug("DEBUG MODE ACTIVÉ - Logs détaillés dans le fichier debug")

    def send_telegram(self, message: str):
        """Envoie message Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
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
        except:
            return False

    def connect_exchange(self, api_key_id: int):
        """Connexion à l'exchange avec la clé API spécifiée"""
        if api_key_id in self.exchanges:
            return self.exchanges[api_key_id]

        try:
            if api_key_id == 1:
                api_key = os.getenv('BITGET_API_KEY')
                api_secret = os.getenv('BITGET_SECRET')
                passphrase = os.getenv('BITGET_PASSPHRASE')
            else:
                api_key = os.getenv(f'BITGET_API_KEY_{api_key_id}')
                api_secret = os.getenv(f'BITGET_SECRET_{api_key_id}')
                passphrase = os.getenv(f'BITGET_PASSPHRASE_{api_key_id}')

            exchange = ccxt.bitget({
                'apiKey': api_key,
                'secret': api_secret,
                'password': passphrase,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',
                    'createMarketBuyOrderRequiresPrice': False
                }
            })

            # Mode sandbox pour tests
            exchange.set_sandbox_mode(True)

            self.exchanges[api_key_id] = exchange
            logging.info(f"✅ API Key {api_key_id} connectée")
            return exchange

        except Exception as e:
            logging.error(f"❌ Erreur connexion API Key {api_key_id}: {e}")
            raise

    def get_complete_market_info(self, exchange, symbol: str) -> MarketInfo:
        """Récupère TOUTES les informations complètes du marché"""
        try:
            logging.info(f"\n📊 Récupération complète des infos pour {symbol}...")

            # Ticker pour le prix actuel
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']

            # Marchés pour TOUTES les limites
            markets = exchange.load_markets()
            market = exchange.market(symbol)

            # Extraction des limites importantes
            min_size = market.get('limits', {}).get('amount', {}).get('min', 1)
            min_notional = market.get('limits', {}).get('cost', {}).get('min', 5.0)
            max_leverage = market.get('limits', {}).get('leverage', {}).get('max', 50)

            # Précisions
            price_precision = market.get('precision', {}).get('price', 8)
            size_precision = market.get('precision', {}).get('amount', 0)

            # Taille du contrat
            contract_size = market.get('contractSize', 1)

            # Si certaines infos ne sont pas disponibles, essayer l'API directe
            try:
                # Endpoint Bitget pour les infos détaillées
                api_symbol = symbol.replace('/', '').replace(':USDT', '')
                response = exchange.publicMixGetV2MixMarketContracts({
                    'productType': 'USDT-FUTURES',
                    'symbol': api_symbol
                })

                if response and 'data' in response and len(response['data']) > 0:
                    contract_data = response['data'][0]
                    min_notional = float(contract_data.get('minTradeUSDT', min_notional))
                    max_leverage = int(contract_data.get('maxLever', max_leverage))
                    contract_size = float(contract_data.get('multiplier', contract_size))
            except:
                pass  # Utiliser les valeurs par défaut

            info = MarketInfo(
                symbol=symbol,
                min_size=min_size,
                min_notional=min_notional,
                max_leverage=max_leverage,
                price_precision=price_precision,
                size_precision=size_precision,
                current_price=current_price,
                contract_size=contract_size
            )

            logging.info(f"  ✅ Prix actuel: ${current_price:.8f}")
            logging.info(f"  ✅ Min notional (margin): ${min_notional}")
            logging.info(f"  ✅ Max leverage: {max_leverage}x")
            logging.info(f"  ✅ Min size: {min_size} contrats")
            logging.info(f"  ✅ Contract size: {contract_size}")
            logging.info(f"  ✅ Précisions: prix={price_precision}, size={size_precision}")

            return info

        except Exception as e:
            logging.error(f"❌ Erreur récupération market info complète: {e}")
            # Valeurs par défaut en cas d'erreur
            return MarketInfo(
                symbol=symbol,
                min_size=1,
                min_notional=5.0,
                max_leverage=50,
                price_precision=8,
                size_precision=0,
                current_price=current_price if 'current_price' in locals() else 0,
                contract_size=1
            )

    def complete_cleanup(self):
        """Nettoie COMPLÈTEMENT toutes les positions et TOUS les ordres"""
        logging.info("="*80)
        logging.info("🧹 CLEANUP COMPLET (Positions + Ordres Limit + TP/SL)")
        logging.info("="*80)

        for pair_config in self.PAIRS:
            symbol = pair_config['symbol']
            exchange = self.exchanges[pair_config['api_key_id']]

            logging.info(f"\n📍 Cleanup complet pour {symbol}...")

            try:
                # Phase 1: Flash close toutes les positions
                logging.info("  [1/3] Flash close des positions...")
                positions = exchange.fetch_positions([symbol])
                positions_closed = 0

                for pos in positions:
                    if pos['contracts'] and pos['contracts'] > 0:
                        side = pos['side']
                        size = pos['contracts']
                        logging.info(f"    🔴 Flash closing {side.upper()}: {size} contrats")

                        # Flash close avec productType
                        params = {
                            'symbol': symbol.replace('/', '').replace(':USDT', ''),
                            'marginCoin': 'USDT',
                            'productType': 'USDT-FUTURES',
                            'holdSide': side
                        }

                        try:
                            exchange.privateMixPostV2MixOrderClosePositions(params)
                            positions_closed += 1
                            time.sleep(0.5)
                        except Exception as e:
                            logging.warning(f"    ⚠️ Erreur flash close: {e}")

                if positions_closed > 0:
                    logging.info(f"    ✅ {positions_closed} positions fermées")
                else:
                    logging.info(f"    ✅ Pas de positions à fermer")

                # Phase 2: Annuler tous les ordres limit normaux
                logging.info("  [2/3] Annulation des ordres LIMIT...")
                try:
                    # Récupérer et annuler les ordres ouverts
                    open_orders = exchange.fetch_open_orders(symbol)
                    if open_orders:
                        for order in open_orders:
                            exchange.cancel_order(order['id'], symbol)
                            logging.info(f"    ❌ Annulé ordre {order['id']}")
                        logging.info(f"    ✅ {len(open_orders)} ordres LIMIT annulés")
                    else:
                        logging.info(f"    ✅ Pas d'ordres LIMIT à annuler")
                except Exception as e:
                    logging.info(f"    ⚠️ Pas d'ordres LIMIT ou erreur: {e}")

                # Phase 3: Annuler tous les ordres TP/SL (plan orders)
                logging.info("  [3/3] Annulation des ordres TP/SL...")
                try:
                    # Endpoint spécifique pour les plan orders
                    api_symbol = symbol.replace('/', '').replace(':USDT', '')

                    # Récupérer les plan orders
                    response = exchange.privateMixGetV2MixOrderOrdersPlanPending({
                        'symbol': api_symbol,
                        'productType': 'USDT-FUTURES'
                    })

                    if response and 'data' in response and response['data'].get('entrustedList'):
                        plan_orders = response['data']['entrustedList']
                        for order in plan_orders:
                            try:
                                # Annuler le plan order
                                cancel_params = {
                                    'symbol': api_symbol,
                                    'marginCoin': 'USDT',
                                    'productType': 'USDT-FUTURES',
                                    'orderId': order['orderId']
                                }
                                exchange.privateMixPostV2MixOrderCancelPlanOrder(cancel_params)
                                logging.info(f"    ❌ Annulé TP/SL {order['orderId']}")
                            except Exception as e:
                                logging.warning(f"    ⚠️ Erreur annulation TP/SL: {e}")

                        logging.info(f"    ✅ {len(plan_orders)} ordres TP/SL annulés")
                    else:
                        logging.info(f"    ✅ Pas d'ordres TP/SL à annuler")

                except Exception as e:
                    logging.info(f"    ⚠️ Pas d'ordres TP/SL ou erreur: {e}")

                logging.info(f"  ✅ {symbol} complètement nettoyé!")

            except Exception as e:
                logging.error(f"  ❌ Erreur cleanup complet {symbol}: {e}")

        logging.info("\n✅ CLEANUP COMPLET TERMINÉ")
        time.sleep(2)  # Attendre que tout soit bien appliqué

    def calculate_adaptive_margin(self, market_info: MarketInfo) -> float:
        """Calcule la marge adaptée selon les minimums de l'exchange"""
        # Le minimum notional est en fait le minimum de MARGE * LEVERAGE requis
        # Donc si min_notional = 5, c'est 5 USDT de valeur minimale
        # Avec leverage 50x, on a besoin de min_notional / leverage de marge
        # MAIS certains exchanges ont un minimum de MARGE directement

        # Pour Bitget, le minimum est de 5 USDT de VALEUR NOTIONALE
        # Donc avec leverage 50x : 5 / 50 = 0.1 USDT de marge minimum
        # MAIS si l'API refuse, c'est que le minimum est sur la MARGE elle-même !

        # On va utiliser le minimum notional comme MARGE minimum pour être sûr
        min_margin = market_info.min_notional  # Utiliser directement le min comme MARGE

        # Arrondir à 2 décimales
        min_margin = round(min_margin, 2)

        notional_value = min_margin * self.DEFAULT_LEVERAGE
        logging.info(f"  💰 Marge calculée: ${min_margin} (notional: ${notional_value}, leverage: {self.DEFAULT_LEVERAGE}x)")

        return min_margin

    def open_positions_sequence(self):
        """Ouvre toutes les positions dans l'ordre avec marges adaptatives"""
        logging.info("="*80)
        logging.info("📈 OUVERTURE DES POSITIONS AVEC MARGES ADAPTATIVES")
        logging.info("="*80)

        # Phase 1: Récupérer TOUTES les informations de marché
        logging.info("\n[Phase 1] Récupération COMPLÈTE des informations de marché...")
        margin_per_pair = {}

        for pair_config in self.PAIRS:
            symbol = pair_config['symbol']
            exchange = self.exchanges[pair_config['api_key_id']]

            # Récupérer TOUTES les infos
            self.market_info[symbol] = self.get_complete_market_info(exchange, symbol)

            # Calculer la marge adaptée
            margin = self.calculate_adaptive_margin(self.market_info[symbol])
            margin_per_pair[symbol] = margin

            # Ajuster le leverage si nécessaire
            if self.DEFAULT_LEVERAGE > self.market_info[symbol].max_leverage:
                logging.warning(f"  ⚠️ Leverage ajusté: {self.DEFAULT_LEVERAGE}x → {self.market_info[symbol].max_leverage}x (max)")

        # Phase 2: Ouvrir les positions hedge avec marges adaptées
        logging.info("\n[Phase 2] Ouverture des positions hedge avec marges adaptatives...")
        for pair_config in self.PAIRS:
            symbol = pair_config['symbol']
            exchange = self.exchanges[pair_config['api_key_id']]
            market_info = self.market_info[symbol]
            margin = margin_per_pair[symbol]

            # Utiliser le leverage max si notre défaut est trop élevé
            leverage = min(self.DEFAULT_LEVERAGE, market_info.max_leverage)

            logging.info(f"\n🎯 Ouverture hedge {symbol}:")
            logging.info(f"   💰 Marge utilisée: ${margin} (minimum requis)")
            logging.info(f"   📊 Leverage: {leverage}x")

            # Créer les objets Position avec la marge adaptée
            long_position = Position(exchange, symbol, PositionSide.LONG, margin, leverage)
            short_position = Position(exchange, symbol, PositionSide.SHORT, margin, leverage)

            # Ouvrir les positions
            long_position.open(market_info.current_price)
            time.sleep(0.5)  # Court délai entre ordres
            short_position.open(market_info.current_price)

            # Stocker
            self.positions[symbol] = {
                'long': long_position,
                'short': short_position
            }

        # Phase 3: Attendre et récupérer les vraies données
        logging.info("\n[Phase 3] Récupération des données réelles...")
        time.sleep(2)  # Attendre que les positions s'établissent

        for symbol, positions_dict in self.positions.items():
            positions_dict['long'].update_from_exchange()
            positions_dict['short'].update_from_exchange()
            logging.info(f"  ✅ {symbol}:")
            logging.info(f"     LONG: {positions_dict['long'].size} contrats @ ${positions_dict['long'].entry_price:.8f}")
            logging.info(f"     SHORT: {positions_dict['short'].size} contrats @ ${positions_dict['short'].entry_price:.8f}")

        # Phase 4: Placer les ordres Limit Fibonacci
        logging.info("\n[Phase 4] Placement des ordres LIMIT Fibonacci...")
        for symbol, positions_dict in self.positions.items():
            exchange = positions_dict['long'].exchange
            self.limit_orders[symbol] = []

            logging.info(f"\n📊 Ordres LIMIT pour {symbol}:")

            # Limite pour LONG (achat plus bas)
            fibo_long = LimitFibonacci(exchange, symbol, positions_dict['long'], self.FIBO_LEVELS[0])
            fibo_long.place()
            self.limit_orders[symbol].append(fibo_long)

            time.sleep(0.25)

            # Limite pour SHORT (vente plus haut)
            fibo_short = LimitFibonacci(exchange, symbol, positions_dict['short'], self.FIBO_LEVELS[0])
            fibo_short.place()
            self.limit_orders[symbol].append(fibo_short)

        # Phase 5: Placer les ordres Take Profit
        logging.info("\n[Phase 5] Placement des ordres Take Profit...")
        for symbol, positions_dict in self.positions.items():
            exchange = positions_dict['long'].exchange
            self.tp_orders[symbol] = []

            logging.info(f"\n🎯 Ordres TP pour {symbol}:")

            # TP pour LONG
            tp_long = OrderTakeProfit(exchange, symbol, positions_dict['long'], self.TP_PERCENT)
            tp_long.place()
            self.tp_orders[symbol].append(tp_long)

            time.sleep(0.25)

            # TP pour SHORT
            tp_short = OrderTakeProfit(exchange, symbol, positions_dict['short'], self.TP_PERCENT)
            tp_short.place()
            self.tp_orders[symbol].append(tp_short)

        logging.info("\n" + "="*80)
        logging.info("✅ TOUTES LES POSITIONS ET ORDRES SONT EN PLACE!")
        logging.info("="*80)
        self.display_summary()

    def display_summary(self):
        """Affiche un résumé de l'état actuel avec les marges"""
        logging.info("\n📊 RÉSUMÉ COMPLET:")

        total_positions = 0
        total_limits = 0
        total_tps = 0
        total_margin = 0

        for symbol in self.positions:
            positions = self.positions[symbol]
            limits = self.limit_orders.get(symbol, [])
            tps = self.tp_orders.get(symbol, [])

            pos_count = sum(1 for p in positions.values() if p.is_open)
            limit_count = len(limits)
            tp_count = len(tps)
            margin_used = sum(p.margin for p in positions.values() if p.is_open)

            total_positions += pos_count
            total_limits += limit_count
            total_tps += tp_count
            total_margin += margin_used

            logging.info(f"  {symbol}:")
            logging.info(f"    - Positions: {pos_count} (margin: ${margin_used:.2f})")
            logging.info(f"    - Ordres LIMIT: {limit_count}")
            logging.info(f"    - Ordres TP: {tp_count}")

        logging.info(f"\n  TOTAL:")
        logging.info(f"    - {total_positions} positions")
        logging.info(f"    - {total_limits} ordres LIMIT")
        logging.info(f"    - {total_tps} ordres TP")
        logging.info(f"    - Marge totale: ${total_margin:.2f}")
        logging.info(f"    - Éléments actifs: {total_positions + total_limits + total_tps}")

    def monitoring_loop(self):
        """
        Boucle de monitoring ROBUSTE par vérification de cohérence

        Principe:
        - Interroge API toutes les secondes
        - Compare avec état attendu (expected_state)
        - Détecte événements par analyse:
          * Position doublée = Fibonacci exécuté
          * Position disparue = TP exécuté
        - Réagit immédiatement pour maintenir cohérence
        """
        logging.info("\n" + "="*80)
        logging.info("🔄 DÉMARRAGE DU MONITORING ROBUSTE (1 seconde)")
        logging.info("="*80)
        logging.info("")
        logging.info("📋 Système de détection:")
        logging.info("   ✅ Position doublée → Fibonacci exécuté → Replacer nouveau Fibo")
        logging.info("   ✅ Position disparue → TP exécuté → Rouvrir position + TP + Fibo")
        logging.info("")

        # État attendu initial (après ouverture)
        expected_state = {}
        for symbol in self.positions:
            expected_state[symbol] = {
                'long': {
                    'size': self.positions[symbol]['long'].size,
                    'entry_price': self.positions[symbol]['long'].entry_price,
                    'has_tp': True,
                    'has_fibo': True
                },
                'short': {
                    'size': self.positions[symbol]['short'].size,
                    'entry_price': self.positions[symbol]['short'].entry_price,
                    'has_tp': True,
                    'has_fibo': True
                }
            }

        iteration = 0

        while True:
            try:
                iteration += 1
                start_time = time.time()

                # ===== INTERROGER L'API =====
                for symbol in self.positions:
                    exchange = self.exchanges[self.pair_to_api[symbol]]

                    # Fetch positions réelles
                    real_positions = exchange.fetch_positions([symbol])

                    # Créer dict par side
                    current_state = {'long': None, 'short': None}
                    for pos in real_positions:
                        if pos['contracts'] and pos['contracts'] > 0:
                            side = pos['side']
                            current_state[side] = {
                                'size': pos['contracts'],
                                'entry': pos['entryPrice']
                            }

                    # Fetch ordres LIMIT (Fibonacci)
                    limit_orders = exchange.fetch_open_orders(symbol)
                    fibo_orders = {'long': None, 'short': None}
                    for order in limit_orders:
                        if order['type'] == 'limit':
                            # BUY = Fibonacci LONG, SELL = Fibonacci SHORT
                            if order['side'] == 'buy':
                                fibo_orders['long'] = order
                            elif order['side'] == 'sell':
                                fibo_orders['short'] = order

                    # ===== ANALYSE ET DÉTECTION =====

                    for side in ['long', 'short']:
                        expected = expected_state[symbol][side]
                        current = current_state[side]

                        # CAS 1: Position disparue → TP EXÉCUTÉ
                        if current is None and expected['size'] > 0:
                            logging.info(f"")
                            logging.info(f"🎯 TP EXÉCUTÉ DÉTECTÉ: {symbol} {side.upper()} disparue!")
                            logging.info(f"   Taille attendue: {expected['size']:.0f} → Actuelle: 0")
                            logging.info(f"   ➡️  ACTION: Rouvrir position + TP + Fibonacci")

                            # Message Telegram
                            self.send_telegram(f"🎯 <b>TP EXÉCUTÉ</b>\n{symbol} {side.upper()}\nTaille: {expected['size']:.0f} contrats fermés")

                            # Rouvrir position
                            position_obj = self.positions[symbol][side]
                            current_price = exchange.fetch_ticker(symbol)['last']
                            result = position_obj.open(current_price)
                            logging.info(f"   ✅ Position {side.upper()} rouverte: {position_obj.size:.0f} contrats @ ${current_price:.8f}")

                            # Replacer TP
                            tp_obj = OrderTakeProfit(exchange, symbol, position_obj, self.TP_PERCENT)
                            tp_obj.place()
                            logging.info(f"   ✅ TP replacé")

                            # Replacer Fibonacci
                            fibo_obj = LimitFibonacci(exchange, symbol, position_obj, self.FIBO_LEVELS[0])
                            fibo_obj.place()
                            logging.info(f"   ✅ Fibonacci replacé")

                            # Message Telegram confirmation
                            self.send_telegram(f"✅ Position {side.upper()} rouverte\n{position_obj.size:.0f} @ ${current_price:.8f}\nTP + Fibo replacés")

                            # Mettre à jour état attendu
                            expected_state[symbol][side] = {
                                'size': position_obj.size,
                                'entry_price': position_obj.entry_price,
                                'has_tp': True,
                                'has_fibo': True
                            }

                        # CAS 2: Position doublée → FIBONACCI EXÉCUTÉ
                        elif current and current['size'] >= expected['size'] * 1.8:  # Tolérance 10%
                            logging.info(f"")
                            logging.info(f"🎯 FIBONACCI EXÉCUTÉ DÉTECTÉ: {symbol} {side.upper()} doublé!")
                            logging.info(f"   Taille: {expected['size']:.0f} → {current['size']:.0f}")
                            logging.info(f"   Prix moyen: ${expected.get('entry_price', 0):.8f} → ${current['entry']:.8f}")
                            logging.info(f"   ➡️  ACTION: Replacer TP + Fibonacci (anciens TP auto-annulés par Bitget)")

                            # Message Telegram
                            self.send_telegram(f"📊 <b>FIBONACCI EXÉCUTÉ</b>\n{symbol} {side.upper()}\nTaille: {expected['size']:.0f} → {current['size']:.0f}\nPrix moyen: ${current['entry']:.5f}")

                            # Mettre à jour position avec NOUVEAU prix moyen d'achat
                            position_obj = self.positions[symbol][side]
                            position_obj.size = current['size']
                            position_obj.entry_price = current['entry']

                            # RETRY LOOP: Placer nouveau TP jusqu'à confirmation
                            # Note: Attendre que position soit settled (erreur 43023 sinon)
                            tp_placed = False
                            for attempt in range(15):  # Max 15 tentatives
                                try:
                                    # Attendre progressivement plus longtemps
                                    wait_time = 2 + (attempt * 0.5)  # 2s, 2.5s, 3s, 3.5s...
                                    if attempt > 0:
                                        time.sleep(wait_time)

                                    tp_obj = OrderTakeProfit(exchange, symbol, position_obj, self.TP_PERCENT)
                                    tp_obj.place()

                                    # Vérifier que le TP est bien placé
                                    time.sleep(1)
                                    tp_orders = exchange.fetch_open_orders(symbol, params={'trigger': True, 'planType': 'profit_loss'})
                                    for order in tp_orders:
                                        if abs(float(order.get('triggerPrice', 0)) - tp_obj.price) < 0.0001:
                                            logging.info(f"   ✅ Nouveau TP confirmé @ {tp_obj.price:.8f} après {attempt+1} tentatives")
                                            tp_placed = True
                                            break
                                    if tp_placed:
                                        break
                                except Exception as e:
                                    if attempt < 14:
                                        logging.debug(f"   ⚠️ Tentative {attempt+1}/15 TP échouée: {str(e)[:60]}")
                                    else:
                                        logging.warning(f"   ⚠️ TP non placé après 15 tentatives: {e}")

                            if not tp_placed:
                                logging.warning(f"   → L'ancien TP reste actif (erreur 43023 persistante)")

                            # RETRY LOOP: Replacer nouveau Fibonacci jusqu'à confirmation
                            current_market_price = exchange.fetch_ticker(symbol)['last']
                            fibo_placed = False
                            for attempt in range(10):
                                try:
                                    temp_entry = position_obj.entry_price
                                    position_obj.entry_price = current_market_price  # Temporaire
                                    fibo_obj = LimitFibonacci(exchange, symbol, position_obj, self.FIBO_LEVELS[0])
                                    fibo_obj.place()
                                    position_obj.entry_price = temp_entry  # Restaurer

                                    # Vérifier que le Fibonacci est bien placé
                                    time.sleep(0.5)
                                    limit_orders = exchange.fetch_open_orders(symbol)
                                    for order in limit_orders:
                                        if order['type'] == 'limit' and abs(float(order.get('price', 0)) - fibo_obj.price) < 0.0001:
                                            logging.info(f"   ✅ Nouveau Fibonacci confirmé @ {fibo_obj.price:.8f} (prix actuel ${current_market_price:.8f} - 0.5%)")
                                            fibo_placed = True
                                            break
                                    if fibo_placed:
                                        break
                                except Exception as e:
                                    position_obj.entry_price = temp_entry  # Restaurer en cas d'erreur
                                    if attempt < 9:
                                        logging.debug(f"   ⚠️ Tentative {attempt+1}/10 Fibo échouée, retry...")
                                        time.sleep(0.5)
                                    else:
                                        logging.error(f"   ❌ Fibonacci non placé après 10 tentatives: {e}")

                            if not fibo_placed:
                                logging.error(f"   ❌ CRITIQUE: Fibonacci non placé!")

                            # Mettre à jour état attendu
                            expected_state[symbol][side]['size'] = current['size']
                            expected_state[symbol][side]['entry_price'] = current['entry']

                # Log toutes les 10 itérations (10 secondes)
                if iteration % 10 == 0:
                    logging.info(f"📡 Monitoring OK (it. {iteration})")

                # Dormir pour compléter 1 seconde
                elapsed = time.time() - start_time
                sleep_time = max(0, 1.0 - elapsed)
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                logging.info("\n⚠️ Arrêt demandé par l'utilisateur")
                break
            except Exception as e:
                logging.error(f"❌ Erreur monitoring: {e}")
                import traceback
                logging.error(traceback.format_exc())
                time.sleep(1)

    def run(self):
        """Lance le bot"""
        try:
            # Connexion aux exchanges
            logging.info("🔌 Connexion aux exchanges...")
            for pair_config in self.PAIRS:
                self.connect_exchange(pair_config['api_key_id'])

            # Message Telegram démarrage
            pairs_list = ", ".join([p['symbol'].split('/')[0] for p in self.PAIRS])
            self.send_telegram(f"🚀 <b>BOT DÉMARRÉ</b>\nFibonacci Bot OOP\nPaires: {pairs_list}\nTP: 0.5% | Fibo: 0.5%")

            # Cleanup COMPLET
            self.complete_cleanup()

            # Ouverture séquencée avec marges adaptatives
            self.open_positions_sequence()

            # Monitoring
            self.monitoring_loop()

        except KeyboardInterrupt:
            logging.info("\n⚠️ Arrêt du bot...")
        except Exception as e:
            logging.error(f"❌ Erreur fatale: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logging.info("👋 Bot arrêté")

# ================================================================================
# MAIN
# ================================================================================

if __name__ == "__main__":
    bot = FibonacciBot()
    bot.run()