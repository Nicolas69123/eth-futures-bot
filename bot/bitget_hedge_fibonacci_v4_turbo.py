#!/usr/bin/env python3
"""
Bitget Hedge Fibonacci Bot V4.1 TURBO - Ultra rapide (3 secondes max)
Stratégie de hedge avec niveaux Fibonacci et doublement automatique
"""

import ccxt
import os
import sys
import time
import logging
import argparse
from dotenv import load_dotenv
from datetime import datetime
import traceback

# Configuration du logging avec détails complets
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

class BitgetHedgeFibonacciBot:
    def __init__(self, pair='DOGE/USDT:USDT', api_key_id=1):
        """
        Initialise le bot de trading

        Args:
            pair: Paire de trading (ex: 'DOGE/USDT:USDT', 'ETH/USDT:USDT')
            api_key_id: ID de la clé API à utiliser (1 ou 2)
        """
        # Paramètres de trading
        self.PAIR = pair
        self.API_KEY_ID = api_key_id
        self.TP_PERCENT = 0.1  # TP fixe à 0.1%
        self.FIBO_LEVELS = [0.1, 0.2, 0.4, 0.8, 1.6]  # Niveaux Fibonacci en %
        self.INITIAL_MARGIN = 0.15  # Marge initiale en USD par position (augmentée pour garantir > 5 USDT)
        self.LEVERAGE = 50

        # Logging pour debug
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Nom du fichier log avec la paire et timestamp
        pair_name = pair.split('/')[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{log_dir}/v4_turbo_{pair_name}_{timestamp}.log"

        # Configurer file handler pour logs détaillés
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S'))
        logger.addHandler(file_handler)

        # Header avec infos du bot
        logger.info("=" * 80)
        logger.info(f"📝 LOGS TURBO: {log_file}")
        logger.info("=" * 80)

        # Initialiser l'exchange
        self.exchange = self.init_exchange()

        # État des positions
        self.tracked_positions = {
            'long': {'entry': 0, 'size': 0},
            'short': {'entry': 0, 'size': 0}
        }

        # Tracking des ordres
        self.tp_orders = {
            'long': None,
            'short': None
        }

        self.fibo_orders = {
            'long': None,
            'short': None
        }

        # Tracking niveaux Fibonacci
        self.fibo_level = {
            'long': 0,
            'short': 0
        }

        # Valeurs précédentes pour détection
        self.previous_long_size = 0
        self.previous_short_size = 0

    def init_exchange(self):
        """Initialise la connexion à l'exchange Bitget"""
        logger.info("=" * 80)
        logger.info(f" BOT V4.1 TURBO - {self.PAIR.split('/')[0]} ")
        logger.info("=" * 80)

        # Sélection des credentials selon l'API key ID
        if self.API_KEY_ID == 1:
            api_key = os.getenv('BITGET_API_KEY')
            secret = os.getenv('BITGET_SECRET')
            passphrase = os.getenv('BITGET_PASSPHRASE')
            logger.info("✅ API Key 1 loaded")
        else:
            api_key = os.getenv('BITGET_API_KEY_2')
            secret = os.getenv('BITGET_SECRET_2')
            passphrase = os.getenv('BITGET_PASSPHRASE_2')
            logger.info("✅ API Key 2 loaded")

        logger.info(f"Paire: {self.PAIR}")
        logger.info(f"TP: {self.TP_PERCENT}%")
        logger.info(f"Fibo levels: {self.FIBO_LEVELS}")
        logger.info(f"Marge: ${self.INITIAL_MARGIN}")
        logger.info(f"Leverage: {self.LEVERAGE}x")
        logger.info("=" * 80)

        return ccxt.bitget({
            'apiKey': api_key,
            'secret': secret,
            'password': passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultMarginMode': 'cross'
            },
            'headers': {'PAPTRADING': '1'}  # Paper trading
        })

    def cancel_all_limit_orders(self):
        """Cancel ALL LIMIT orders for this pair"""
        try:
            open_orders = self.exchange.fetch_open_orders(self.PAIR)
            cancelled_count = 0

            for order in open_orders:
                try:
                    self.exchange.cancel_order(order['id'], self.PAIR)
                    logger.debug(f"   ✅ Ordre LIMIT annulé: {order['id'][:16]}...")
                    cancelled_count += 1
                    time.sleep(0.05)  # TURBO: 50ms entre annulations
                except Exception as e:
                    if '40768' not in str(e) and '40721' not in str(e):
                        logger.warning(f"   ⚠️ Erreur annulation ordre {order['id'][:16]}: {str(e)[:50]}")

            if cancelled_count > 0:
                logger.debug(f"   🧹 {cancelled_count} ordres LIMIT annulés")

            return cancelled_count

        except Exception as e:
            logger.error(f"Erreur cancel_all_limit_orders: {e}")
            return 0

    def full_cleanup_orders(self):
        """
        Cleanup COMPLET de tous les ordres LIMIT
        Utilise cancel_all_limit_orders pour tout nettoyer
        """
        try:
            logger.info("🧹 Cleanup complet des ordres...")

            # Annuler TOUS les ordres LIMIT
            cancelled = self.cancel_all_limit_orders()

            # Reset tracking
            self.fibo_orders = {'long': None, 'short': None}

            logger.info(f"   ✅ Total {cancelled} ordres nettoyés")

        except Exception as e:
            logger.error(f"Erreur full_cleanup_orders: {e}")

    def cleanup_all(self):
        """Nettoie toutes les positions et ordres du compte"""
        logger.info("=" * 80)
        logger.info(" CLEANUP INITIAL ")
        logger.info("=" * 80)

        logger.info("🧹 Cleanup avec vérification...")

        # Boucle de cleanup jusqu'à ce que tout soit clean
        max_attempts = 3
        for attempt in range(max_attempts):
            if attempt > 0:
                logger.info(f"\n🔄 Tentative {attempt+1}/{max_attempts}...")

            # 1. Annuler tous les ordres LIMIT
            try:
                open_orders = self.exchange.fetch_open_orders(self.PAIR)
                if open_orders:
                    logger.info(f"  📝 {len(open_orders)} ordres LIMIT à annuler...")
                    for order in open_orders:
                        try:
                            self.exchange.cancel_order(order['id'], self.PAIR)
                            time.sleep(0.05)  # TURBO: 50ms
                        except:
                            pass
            except:
                pass

            # 2. Fermer toutes les positions avec flash close
            try:
                positions = self.exchange.fetch_positions([self.PAIR])
                positions_to_close = []

                for pos in positions:
                    if pos.get('contracts') and float(pos.get('contracts', 0)) > 0:
                        positions_to_close.append(pos)

                if positions_to_close:
                    symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')

                    for pos in positions_to_close:
                        side = pos.get('side', '').lower()
                        size = float(pos.get('contracts', 0))

                        if size < 1:
                            continue

                        logger.info(f"  🔴 Flash closing {side.upper()}: {size:.0f} contrats")

                        try:
                            result = self.exchange.private_mix_post_v2_mix_order_close_positions({
                                'symbol': symbol_bitget,
                                'productType': 'USDT-FUTURES',
                                'holdSide': side
                            })

                            if result.get('code') == '00000':
                                time.sleep(0.5)  # TURBO: 500ms après flash close
                        except Exception as e:
                            if '22002' not in str(e):
                                logger.debug(f"    Flash close error: {str(e)[:50]}")

                    if positions_to_close:
                        logger.info(f"  ⚡ {len(positions_to_close)} positions flash closed")
            except:
                pass

            # 3. Vérifier si tout est clean
            time.sleep(1)  # TURBO: 1s pour propagation

            try:
                final_orders = self.exchange.fetch_open_orders(self.PAIR)
                final_positions = self.exchange.fetch_positions([self.PAIR])

                orders_count = len(final_orders)
                positions_count = sum(1 for p in final_positions
                                    if p.get('contracts') and float(p.get('contracts', 0)) > 0)

                if orders_count == 0 and positions_count == 0:
                    logger.info("✅ Cleanup VÉRIFIÉ - Compte clean!")
                    break
                else:
                    if attempt < max_attempts - 1:
                        logger.warning(f"⚠️  Il reste: {orders_count} ordres, {positions_count} positions")
                    else:
                        logger.error(f"❌ Cleanup incomplet après {max_attempts} tentatives")
            except:
                pass

    def get_real_positions(self):
        """Récupère les vraies positions depuis l'API"""
        try:
            positions = self.exchange.fetch_positions([self.PAIR])

            real_pos = {
                'long': None,
                'short': None
            }

            for pos in positions:
                if pos['contracts'] and pos['contracts'] > 0:
                    side = pos['side'].lower()

                    entry_price = None
                    if pos['info'].get('openPriceAvg'):
                        entry_price = float(pos['info']['openPriceAvg'])
                    elif pos.get('entryPrice'):
                        entry_price = float(pos['entryPrice'])
                    elif pos['info'].get('markPrice'):
                        entry_price = float(pos['info']['markPrice'])

                    real_pos[side] = {
                        'size': float(pos['contracts']),
                        'entry': entry_price,
                        'pnl': float(pos.get('unrealizedPnl', 0)),
                        'margin': float(pos.get('initialMargin', 0)),
                        'leverage': float(pos.get('leverage', 0))
                    }

            return real_pos
        except:
            return {'long': None, 'short': None}

    def open_initial_hedge(self):
        """Ouvre le hedge initial avec gestion des erreurs"""
        logger.info("=" * 80)
        logger.info(" OUVERTURE HEDGE INITIAL ")
        logger.info("=" * 80)

        try:
            # Récupérer le prix actuel
            ticker = self.exchange.fetch_ticker(self.PAIR)
            current_price = float(ticker['last'])
            logger.info(f"Prix actuel: ${current_price:.5f}")

            # Calculer la taille
            notional = (self.INITIAL_MARGIN * self.LEVERAGE) / current_price
            size = round(notional * current_price)

            logger.info(f"Size calculée: {size} contrats (${self.INITIAL_MARGIN * self.LEVERAGE:.1f} notional)")

            # 1. Ouvrir LONG
            logger.info("\n[1/6] Ouverture LONG MARKET...")
            long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='buy',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            logger.info(f"   ✅ LONG ouvert: {long_order['id']}")

            # 2. Ouvrir SHORT
            logger.info("\n[2/6] Ouverture SHORT MARKET...")
            short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='sell',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            logger.info(f"   ✅ SHORT ouvert: {short_order['id']}")

            # 3. Attendre et récupérer les vraies positions
            logger.info("\n⏳ Attente 1s puis récupération positions...")  # TURBO: 1s au lieu de 5s
            time.sleep(1)

            real_pos = self.get_real_positions()

            if real_pos['long'] and real_pos['short']:
                self.tracked_positions['long'] = {
                    'entry': real_pos['long']['entry'],
                    'size': real_pos['long']['size']
                }
                self.tracked_positions['short'] = {
                    'entry': real_pos['short']['entry'],
                    'size': real_pos['short']['size']
                }

                logger.info("   ✅ Position tracking mis à jour")
                logger.info(f"      LONG: Entry=${real_pos['long']['entry']:.5f}, Size={real_pos['long']['size']:.2f}")
                logger.info(f"      SHORT: Entry=${real_pos['short']['entry']:.5f}, Size={real_pos['short']['size']:.2f}")
            else:
                logger.error("❌ Impossible de récupérer les positions!")
                return False

            # 4. Placer TP LONG
            logger.info("\n[3/6] Placement TP LONG...")
            tp_long_price = self.tracked_positions['long']['entry'] * (1 + self.TP_PERCENT/100)
            logger.info(f"   Calcul TP: Entry=${self.tracked_positions['long']['entry']:.5f} * (1 + {self.TP_PERCENT}%) = ${tp_long_price:.5f}")

            if self.place_tp_order('long', real_pos['long']['size'], tp_long_price):
                logger.info(f"   ✅ TP LONG placé @ ${tp_long_price:.5f}")

            # 5. Placer TP SHORT
            logger.info("\n[4/6] Placement TP SHORT...")
            tp_short_price = self.tracked_positions['short']['entry'] * (1 - self.TP_PERCENT/100)
            logger.info(f"   Calcul TP: Entry=${self.tracked_positions['short']['entry']:.5f} * (1 - {self.TP_PERCENT}%) = ${tp_short_price:.5f}")

            if self.place_tp_order('short', real_pos['short']['size'], tp_short_price):
                logger.info(f"   ✅ TP SHORT placé @ ${tp_short_price:.5f}")

            # 6. Placer ordre LIMIT BUY (Fibo Long)
            logger.info("\n[5/6] Placement LIMIT BUY (Fibo Long - double marge)...")
            fibo_long_price = self.tracked_positions['long']['entry'] * (1 - self.FIBO_LEVELS[0]/100)
            logger.info(f"   Calcul: Entry=${self.tracked_positions['long']['entry']:.5f} * (1 - {self.FIBO_LEVELS[0]}%) = ${fibo_long_price:.5f}")

            fibo_long_price = round(fibo_long_price, 5)
            long_order_limit = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='buy',
                amount=real_pos['long']['size'],
                price=fibo_long_price,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.fibo_orders['long'] = long_order_limit['id']
            logger.info(f"   ✅ LIMIT BUY: {long_order_limit['id']}")
            logger.info(f"      - Price: ${fibo_long_price:.5f}")
            logger.info(f"      - Size: {real_pos['long']['size']:.2f}")

            # 7. Placer ordre LIMIT SELL (Fibo Short)
            logger.info("\n[6/6] Placement LIMIT SELL (Fibo Short - double marge)...")
            fibo_short_price = self.tracked_positions['short']['entry'] * (1 + self.FIBO_LEVELS[0]/100)
            logger.info(f"   Calcul: Entry=${self.tracked_positions['short']['entry']:.5f} * (1 + {self.FIBO_LEVELS[0]}%) = ${fibo_short_price:.5f}")

            fibo_short_price = round(fibo_short_price, 5)
            short_order_limit = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='sell',
                amount=real_pos['short']['size'],
                price=fibo_short_price,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.fibo_orders['short'] = short_order_limit['id']
            logger.info(f"   ✅ LIMIT SELL: {short_order_limit['id']}")
            logger.info(f"      - Price: ${fibo_short_price:.5f}")
            logger.info(f"      - Size: {real_pos['short']['size']:.2f}")

            logger.info("=" * 80)
            logger.info(" HEDGE INITIAL OUVERT ")
            logger.info("=" * 80)
            logger.info(f"Positions: LONG {real_pos['long']['size']:.0f} + SHORT {real_pos['short']['size']:.0f}")
            logger.info(f"Ordres TP: 2")
            logger.info(f"Ordres LIMIT Fibo: 2 (doublent la marge)")
            logger.info(f"Total: 2 positions + 4 ordres")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur ouverture hedge: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def place_tp_order(self, side, size, trigger_price):
        """Place un ordre TP pour une position"""
        try:
            symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')

            # Arrondir le prix selon la valeur
            if trigger_price >= 100:
                trigger_price_rounded = round(trigger_price, 2)
            elif trigger_price >= 1:
                trigger_price_rounded = round(trigger_price, 4)
            else:
                trigger_price_rounded = round(trigger_price, 5)

            # Côté opposé pour fermer
            close_side = 'sell' if side == 'long' else 'buy'

            response = self.exchange.private_mix_post_v2_mix_order_place_tpsl_order({
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'marginMode': 'crossed',
                'marginCoin': 'USDT',
                'holdSide': side,
                'triggerPrice': str(trigger_price_rounded),
                'triggerType': 'mark_price',
                'size': str(int(size)),
                'side': close_side,
                'orderType': 'market',
                'planType': 'profit_plan'
            })

            if response.get('code') == '00000' and response.get('data'):
                order_id = response['data'].get('orderId')
                self.tp_orders[side] = order_id
                logger.info(f"   ✅ TP/SL PLACÉ!")
                logger.info(f"      - Order ID: {order_id}")
                logger.info(f"      - Side: {side.upper()}")
                logger.info(f"      - Trigger Price: ${trigger_price_rounded}")
                logger.info(f"      - Size: {int(size)} contrats")
                return True

        except Exception as e:
            logger.error(f"❌ Erreur placement TP {side}: {e}")

        return False

    def handle_tp_long(self):
        """Gère la réouverture après TP Long"""
        logger.info("=" * 80)
        logger.info(" HANDLER TP LONG ")
        logger.info("=" * 80)
        logger.info("🔄 Réouverture hedge après TP LONG...")

        # Cleanup complet des ordres
        self.full_cleanup_orders()

        # Réouvrir le hedge complet
        time.sleep(0.5)  # TURBO: 500ms avant réouverture
        self.open_initial_hedge()

    def handle_tp_short(self):
        """Gère la réouverture après TP Short"""
        logger.info("=" * 80)
        logger.info(" HANDLER TP SHORT ")
        logger.info("=" * 80)
        logger.info("🔄 Réouverture hedge après TP SHORT...")

        # Cleanup complet des ordres
        self.full_cleanup_orders()

        # Réouvrir le hedge complet
        time.sleep(0.5)  # TURBO: 500ms avant réouverture
        self.open_initial_hedge()

    def handle_fibo_long(self, new_size):
        """Gère le doublement Fibo Long"""
        logger.info("=" * 80)
        logger.info(" HANDLER FIBO LONG ")
        logger.info("=" * 80)

        # Incrémenter le niveau Fibo
        self.fibo_level['long'] += 1
        current_level = self.fibo_level['long']

        logger.info(f"📈 Traitement Fibo LONG (niveau {current_level})...")

        # Mettre à jour le TP avec nouvelle taille
        new_tp_price = self.tracked_positions['long']['entry'] * (1 + self.TP_PERCENT/100)
        logger.info(f"   🎯 Nouveau TP LONG: ${new_tp_price:.5f}")
        self.place_tp_order('long', new_size, new_tp_price)

        # Si on n'a pas atteint le dernier niveau, placer nouvel ordre Fibo
        if current_level < len(self.FIBO_LEVELS):
            next_fibo_price = self.tracked_positions['long']['entry'] * (1 - self.FIBO_LEVELS[current_level]/100)
            logger.info(f"   📊 Nouveau LIMIT BUY @ ${next_fibo_price:.5f} (Niveau {current_level + 1})")

            next_fibo_price = round(next_fibo_price, 5)

            try:
                order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='buy',
                    amount=new_size,
                    price=next_fibo_price,
                    params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                self.fibo_orders['long'] = order['id']
            except Exception as e:
                logger.error(f"❌ Erreur placement Fibo Long niveau {current_level + 1}: {e}")

    def handle_fibo_short(self, new_size):
        """Gère le doublement Fibo Short"""
        logger.info("=" * 80)
        logger.info(" HANDLER FIBO SHORT ")
        logger.info("=" * 80)

        # Incrémenter le niveau Fibo
        self.fibo_level['short'] += 1
        current_level = self.fibo_level['short']

        logger.info(f"📉 Traitement Fibo SHORT (niveau {current_level})...")

        # Mettre à jour le TP avec nouvelle taille
        new_tp_price = self.tracked_positions['short']['entry'] * (1 - self.TP_PERCENT/100)
        logger.info(f"   🎯 Nouveau TP SHORT: ${new_tp_price:.5f}")
        self.place_tp_order('short', new_size, new_tp_price)

        # Si on n'a pas atteint le dernier niveau, placer nouvel ordre Fibo
        if current_level < len(self.FIBO_LEVELS):
            next_fibo_price = self.tracked_positions['short']['entry'] * (1 + self.FIBO_LEVELS[current_level]/100)
            logger.info(f"   📊 Nouveau LIMIT SELL @ ${next_fibo_price:.5f} (Niveau {current_level + 1})")

            next_fibo_price = round(next_fibo_price, 5)

            try:
                order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='sell',
                    amount=new_size,
                    price=next_fibo_price,
                    params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                self.fibo_orders['short'] = order['id']
            except Exception as e:
                logger.error(f"❌ Erreur placement Fibo Short niveau {current_level + 1}: {e}")

    def display_state(self, label=""):
        """Affiche l'état actuel du compte avec détails complets"""
        if label:
            logger.info("=" * 80)
            logger.info(f" {label} ")
            logger.info("=" * 80)

        try:
            # Prix actuel
            ticker = self.exchange.fetch_ticker(self.PAIR)
            current_price = float(ticker['last'])
            logger.info(f"📊 PRIX MARCHÉ ACTUEL: ${current_price:.5f}")

            # Positions
            real_pos = self.get_real_positions()

            if real_pos['long']:
                logger.info(f"  🟢 LONG POSITION:")
                logger.info(f"     - Size: {real_pos['long']['size']:.2f} contrats")
                logger.info(f"     - Entry Price: ${real_pos['long']['entry']:.5f}")
                logger.info(f"     - PnL: ${real_pos['long']['pnl']:.2f}")
                logger.info(f"     - Leverage: {real_pos['long']['leverage']:.1f}x")
            else:
                logger.info(f"  ⚪ LONG: Fermée")

            if real_pos['short']:
                logger.info(f"  🔴 SHORT POSITION:")
                logger.info(f"     - Size: {real_pos['short']['size']:.2f} contrats")
                logger.info(f"     - Entry Price: ${real_pos['short']['entry']:.5f}")
                logger.info(f"     - PnL: ${real_pos['short']['pnl']:.2f}")
                logger.info(f"     - Leverage: {real_pos['short']['leverage']:.1f}x")
            else:
                logger.info(f"  ⚪ SHORT: Fermée")

            # Ordres ouverts
            open_orders = self.exchange.fetch_open_orders(self.PAIR)
            logger.info(f"  📋 ORDRES OUVERTS: {len(open_orders)}")

            if open_orders:
                for order in open_orders[:5]:
                    logger.info(f"     - {order['side'].upper()} {order['amount']:.2f} @ ${order['price']:.5f} [{order['id'][:16]}...] ({order['status']})")

            # Ordres TP/SL trackés
            logger.info(f"  🎯 ORDRES TP/SL TRACKÉS:")
            logger.info(f"     - TP Long ID: {self.tp_orders['long']}")
            logger.info(f"     - TP Short ID: {self.tp_orders['short']}")

            # Ordres LIMIT Fibo trackés
            logger.info(f"  🔄 ORDRES LIMIT FIBO TRACKÉS:")
            logger.info(f"     - Double Long ID: {self.fibo_orders['long']}")
            logger.info(f"     - Double Short ID: {self.fibo_orders['short']}")

        except Exception as e:
            logger.error(f"Erreur affichage état: {e}")

    def check_orders_status(self):
        """Vérifie l'état des ordres et positions"""
        try:
            # Récupérer les vraies positions
            real_pos = self.get_real_positions()

            # Initialiser les valeurs previous si c'est la première fois
            if self.previous_long_size == 0 and real_pos['long']:
                self.previous_long_size = real_pos['long']['size']
            if self.previous_short_size == 0 and real_pos['short']:
                self.previous_short_size = real_pos['short']['size']

            # Détection TP LONG
            if self.tracked_positions['long']['size'] > 0 and not real_pos['long']:
                logger.info("🎯 TP LONG HIT! Position fermée")
                self.display_state("TP LONG HIT")
                self.tracked_positions['long'] = {'entry': 0, 'size': 0}
                self.fibo_level['long'] = 0
                self.previous_long_size = 0
                self.handle_tp_long()
                return

            # Détection TP SHORT
            if self.tracked_positions['short']['size'] > 0 and not real_pos['short']:
                logger.info("🎯 TP SHORT HIT! Position fermée")
                self.display_state("TP SHORT HIT")
                self.tracked_positions['short'] = {'entry': 0, 'size': 0}
                self.fibo_level['short'] = 0
                self.previous_short_size = 0
                self.handle_tp_short()
                return

            # Détection FIBO LONG
            if real_pos['long'] and self.previous_long_size > 0:
                if real_pos['long']['size'] > self.previous_long_size * 1.5:
                    logger.info(f"📈 FIBO LONG HIT! Size: {self.previous_long_size} → {real_pos['long']['size']}")
                    self.display_state(f"FIBO LONG HIT - LEVEL {self.fibo_level['long'] + 1}")
                    self.previous_long_size = real_pos['long']['size']
                    self.tracked_positions['long']['size'] = real_pos['long']['size']
                    self.handle_fibo_long(real_pos['long']['size'])
                    return

            # Détection FIBO SHORT
            if real_pos['short'] and self.previous_short_size > 0:
                if real_pos['short']['size'] > self.previous_short_size * 1.5:
                    logger.info(f"📉 FIBO SHORT HIT! Size: {self.previous_short_size} → {real_pos['short']['size']}")
                    self.display_state(f"FIBO SHORT HIT - LEVEL {self.fibo_level['short'] + 1}")
                    self.previous_short_size = real_pos['short']['size']
                    self.tracked_positions['short']['size'] = real_pos['short']['size']
                    self.handle_fibo_short(real_pos['short']['size'])
                    return

        except Exception as e:
            logger.error(f"❌ Erreur check_orders_status: {e}")

    def run(self):
        """Boucle principale du bot"""
        try:
            # Cleanup initial
            self.cleanup_all()

            # Afficher état après cleanup
            self.display_state("POST-CLEANUP STATE")

            # Ouvrir le hedge initial
            if not self.open_initial_hedge():
                logger.error("❌ Échec ouverture hedge")
                return

            # Afficher état après ouverture
            self.display_state("POST-HEDGE OPENING")

            logger.info("=" * 80)
            logger.info(" MONITORING PRINCIPAL ")
            logger.info("=" * 80)

            # Boucle de monitoring
            iteration = 0
            last_snapshot = time.time()

            while True:
                try:
                    # Check toutes les 0.25 secondes (TURBO: 4 checks/seconde)
                    self.check_orders_status()

                    # Snapshot périodique toutes les 60 secondes
                    if time.time() - last_snapshot > 60:
                        iteration += 60
                        self.display_state(f"PERIODIC SNAPSHOT #{iteration}")
                        last_snapshot = time.time()

                    time.sleep(0.25)  # TURBO: 250ms entre checks

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Erreur dans la boucle: {e}")
                    time.sleep(1)

        except KeyboardInterrupt:
            logger.info("\n⚠️ Arrêt demandé par l'utilisateur")
            logger.info("🧹 Nettoyage en cours...")
            self.cleanup_all()
            logger.info("✅ Bot arrêté proprement")

def main():
    parser = argparse.ArgumentParser(description='Bitget Hedge Fibonacci Bot V4.1 TURBO')
    parser.add_argument('--pair', type=str, default='DOGE/USDT:USDT',
                      help='Paire de trading (ex: DOGE/USDT:USDT, ETH/USDT:USDT)')
    parser.add_argument('--api-key-id', type=int, choices=[1, 2], default=1,
                      help='ID de la clé API à utiliser (1 ou 2)')

    args = parser.parse_args()

    bot = BitgetHedgeFibonacciBot(pair=args.pair, api_key_id=args.api_key_id)
    bot.run()

if __name__ == "__main__":
    main()