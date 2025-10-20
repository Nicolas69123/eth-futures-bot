#!/usr/bin/env python3
"""
🧪 Bitget Hedge Fibonacci Bot V3 - TEST LOCAL SIMPLIFIÉ

Stratégie: Hedge permanent avec TP/Fibo à 0.1%
- TP: 0.1% (au lieu de 1%)
- Fibo niveau 1: 0.1% (au lieu de 1%)
- Tests locaux uniquement
- Pas de Telegram
- Logs debug détaillés
"""

import ccxt
import time
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_v3_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()


class Position:
    """Track position state for a trading pair"""
    def __init__(self, pair):
        self.pair = pair
        self.long_open = False
        self.short_open = False
        self.entry_price_long = 0
        self.entry_price_short = 0
        self.long_fib_level = 0
        self.short_fib_level = 0

        # Track sizes for Fibo detection
        self.long_size_previous = 0
        self.short_size_previous = 0

        # Order IDs
        self.orders = {
            'tp_long': None,
            'tp_short': None,
            'double_long': None,  # LIMIT BUY pour doubler LONG
            'double_short': None  # LIMIT SELL pour doubler SHORT
        }

        # Fibonacci levels (%)
        self.fib_levels = [0.1, 0.2, 0.4, 0.7, 1.2, 2.0, 3.5]  # 0.1%, 0.2%, 0.4%...


class BitgetHedgeBotV3:
    """Simplified bot for local testing with 0.1% TP/Fibo levels"""

    def __init__(self):
        logger.info("="*80)
        logger.info("🧪 BITGET HEDGE BOT V3 - TEST LOCAL (TP/Fibo 0.1%)")
        logger.info("="*80)

        # API credentials
        self.api_key = os.getenv('BITGET_API_KEY')
        self.api_secret = os.getenv('BITGET_SECRET')
        self.api_password = os.getenv('BITGET_PASSPHRASE')

        if not all([self.api_key, self.api_secret, self.api_password]):
            raise ValueError("Missing API credentials in .env")

        logger.info(f"✅ API credentials loaded")

        # Exchange setup
        self.exchange = ccxt.bitget({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'password': self.api_password,
            'options': {
                'defaultType': 'swap',
                'defaultMarginMode': 'cross',
            },
            'headers': {'PAPTRADING': '1'},
            'enableRateLimit': True
        })

        # Parameters
        self.PAIR = 'DOGE/USDT:USDT'
        self.INITIAL_MARGIN = 1  # $1 par position
        self.LEVERAGE = 50

        # TP and Fibo levels
        self.TP_PERCENT = 0.1  # 0.1% TP
        self.FIBO_LEVELS = [0.1, 0.2, 0.4, 0.7, 1.2]  # First level: 0.1%

        # Position tracking
        self.position = Position(self.PAIR)

        logger.info(f"Paire: {self.PAIR}")
        logger.info(f"TP: {self.TP_PERCENT}%")
        logger.info(f"Fibo levels: {self.FIBO_LEVELS}")
        logger.info(f"Initial margin: ${self.INITIAL_MARGIN}")
        logger.info(f"Leverage: {self.LEVERAGE}x")

    def cleanup_all(self):
        """Clean all positions and orders with retry loop"""
        logger.info("\n" + "="*80)
        logger.info("🧹 CLEANUP AGRESSIF - FERMETURE DE TOUT")
        logger.info("="*80)

        max_retries = 5

        for attempt in range(max_retries):
            logger.info(f"\n🔄 Tentative {attempt + 1}/{max_retries}...")

            all_clean = True

            try:
                # 1. Close all positions with MARKET orders
                positions = self.exchange.fetch_positions(symbols=[self.PAIR])
                for pos in positions:
                    size = float(pos.get('contracts', 0))
                    if size > 0:
                        all_clean = False
                        side = pos.get('side', '').lower()
                        logger.info(f"   🔴 Fermeture {side.upper()}: {size} contrats")

                        # Close with MARKET order (more reliable than Flash Close)
                        market_side = 'sell' if side == 'long' else 'buy'
                        try:
                            close_order = self.exchange.create_order(
                                symbol=self.PAIR,
                                type='market',
                                side=market_side,
                                amount=size,
                                params={'tradeSide': 'close', 'holdSide': side}
                            )
                            logger.info(f"      ✅ Ordre fermeture MARKET: {close_order['id']}")
                        except Exception as e:
                            logger.error(f"      ❌ Erreur fermeture: {e}")

                        time.sleep(2)

                        # Verify closed
                        verify = self.exchange.fetch_positions(symbols=[self.PAIR])
                        for vpos in verify:
                            if vpos.get('side', '').lower() == side:
                                remaining = float(vpos.get('contracts', 0))
                                if remaining > 0:
                                    logger.warning(f"   ⚠️ {side.upper()}: {remaining} reste encore")
                                    all_clean = False
                                else:
                                    logger.info(f"   ✅ {side.upper()} fermé!")

                # 2. Cancel all orders
                open_orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                if open_orders:
                    all_clean = False
                    logger.info(f"\n   🗑️  Annulation de {len(open_orders)} ordres...")
                    for order in open_orders:
                        try:
                            logger.info(f"      - {order['type']} {order['side']}: {order['id'][:12]}...")
                            self.exchange.cancel_order(order['id'], self.PAIR)
                            time.sleep(0.3)
                        except Exception as e:
                            logger.warning(f"      ⚠️ Erreur annulation: {e}")

                # Check if everything is clean
                if all_clean:
                    logger.info("\n✅ CLEANUP COMPLET - Tout est fermé!")
                    logger.info("="*80 + "\n")
                    return True

                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Erreur cleanup tentative {attempt + 1}: {e}")

        logger.warning("\n⚠️ CLEANUP INCOMPLET après 5 tentatives")
        logger.info("="*80 + "\n")
        return False

    def flash_close_position(self, side):
        """Close position using flash close API"""
        try:
            result = self.exchange.private_mix_post_v2_mix_order_close_positions({
                'symbol': self.PAIR.replace('/USDT:USDT', 'USDT'),
                'productType': 'USDT-FUTURES',
                'holdSide': side
            })

            if result.get('code') == '00000':
                logger.info(f"   ✅ Flash Close {side} réussi")
                return True
            else:
                logger.error(f"   ❌ Flash Close {side} échec: {result}")
                return False

        except Exception as e:
            logger.error(f"   ❌ Erreur Flash Close: {e}")
            return False

    def get_price(self):
        """Get current market price"""
        ticker = self.exchange.fetch_ticker(self.PAIR)
        return float(ticker['last'])

    def get_real_positions(self):
        """Get actual positions from API"""
        positions = self.exchange.fetch_positions(symbols=[self.PAIR])

        result = {'long': None, 'short': None}

        for pos in positions:
            size = float(pos.get('contracts', 0))
            if size > 0:
                side = pos.get('side', '').lower()
                result[side] = {
                    'size': size,
                    'entry_price': float(pos.get('entryPrice', 0)),
                    'margin': float(pos.get('initialMargin', 0)),
                    'pnl': float(pos.get('unrealizedPnl', 0))
                }

        return result

    def place_tpsl_order(self, trigger_price, hold_side, size, plan_type='profit_plan'):
        """Place TP/SL order using Bitget API"""

        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')

        # Convert plan_type to Bitget format
        bitget_plan_type = 'pos_profit' if plan_type == 'profit_plan' else 'pos_loss'

        # Round trigger price
        trigger_price_rounded = round(trigger_price, 5)

        body = {
            'marginCoin': 'USDT',
            'productType': 'USDT-FUTURES',
            'symbol': symbol_bitget,
            'planType': bitget_plan_type,
            'triggerPrice': str(trigger_price_rounded),
            'triggerType': 'mark_price',
            'executePrice': '0',
            'holdSide': hold_side,
            'size': str(int(size))
        }

        logger.info(f"   📤 Place TP/SL {plan_type}: {body}")

        try:
            result = self.exchange.private_mix_post_v2_mix_order_place_tpsl_order(body)

            if result.get('code') == '00000':
                order_id = result['data']['orderId']
                logger.info(f"   ✅ TP/SL placé: {order_id}")
                return {'id': order_id}
            else:
                logger.error(f"   ❌ TP/SL échec: {result}")
                return None

        except Exception as e:
            logger.error(f"   ❌ Erreur place TP/SL: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def open_initial_hedge(self):
        """
        Open initial hedge: LONG + SHORT + 4 orders

        Orders created:
        1. LONG market
        2. SHORT market
        3. TP LONG (0.1%)
        4. TP SHORT (0.1%)
        5. LIMIT BUY (doubler LONG si prix -0.1%)
        6. LIMIT SELL (doubler SHORT si prix +0.1%)
        """
        logger.info("\n" + "="*80)
        logger.info("🚀 OUVERTURE HEDGE INITIAL")
        logger.info("="*80)

        try:
            current_price = self.get_price()
            logger.info(f"Prix actuel: ${current_price:.5f}")

            # Calculate sizes
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size = notional / current_price
            logger.info(f"Size calculée: {size:.1f} contrats (${notional} notional)")

            # 1. Open LONG market
            logger.info("\n[1/6] Ouverture LONG MARKET...")
            long_order = self.exchange.create_order(
                symbol=self.PAIR, type='market', side='buy', amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            logger.info(f"   ✅ LONG ouvert: {long_order['id']}")

            # 2. Open SHORT market
            logger.info("\n[2/6] Ouverture SHORT MARKET...")
            short_order = self.exchange.create_order(
                symbol=self.PAIR, type='market', side='sell', amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            logger.info(f"   ✅ SHORT ouvert: {short_order['id']}")

            # Wait and get real positions
            logger.info("\n⏳ Attente 5s puis récupération positions...")
            time.sleep(5)
            real_pos = self.get_real_positions()

            if not real_pos['long'] or not real_pos['short']:
                logger.error("❌ Impossible de récupérer positions!")
                return False

            entry_long = real_pos['long']['entry_price']
            entry_short = real_pos['short']['entry_price']
            size_long = real_pos['long']['size']
            size_short = real_pos['short']['size']

            logger.info(f"\n✅ Positions confirmées:")
            logger.info(f"   LONG:  {size_long:.0f} @ ${entry_long:.5f}")
            logger.info(f"   SHORT: {size_short:.0f} @ ${entry_short:.5f}")

            # Update position state
            self.position.long_open = True
            self.position.short_open = True
            self.position.entry_price_long = entry_long
            self.position.entry_price_short = entry_short
            self.position.long_size_previous = size_long
            self.position.short_size_previous = size_short

            # Calculate TP and Fibo prices
            tp_long_price = entry_long * (1 + self.TP_PERCENT / 100)
            tp_short_price = entry_short * (1 - self.TP_PERCENT / 100)
            fibo_long_price = entry_long * (1 - self.FIBO_LEVELS[0] / 100)
            fibo_short_price = entry_short * (1 + self.FIBO_LEVELS[0] / 100)

            logger.info(f"\n📊 Prix calculés:")
            logger.info(f"   TP Long:   ${tp_long_price:.5f} (+{self.TP_PERCENT}%)")
            logger.info(f"   TP Short:  ${tp_short_price:.5f} (-{self.TP_PERCENT}%)")
            logger.info(f"   Fibo Long: ${fibo_long_price:.5f} (-{self.FIBO_LEVELS[0]}%)")
            logger.info(f"   Fibo Short: ${fibo_short_price:.5f} (+{self.FIBO_LEVELS[0]}%)")

            # 3. Place TP LONG
            logger.info("\n[3/6] Placement TP LONG...")
            time.sleep(2)
            tp_long = self.place_tpsl_order(
                trigger_price=tp_long_price,
                hold_side='long',
                size=size_long,
                plan_type='profit_plan'
            )
            if tp_long and tp_long.get('id'):
                self.position.orders['tp_long'] = tp_long['id']
                logger.info(f"   ✅ TP Long: {tp_long['id']}")

            # 4. Place TP SHORT
            logger.info("\n[4/6] Placement TP SHORT...")
            time.sleep(2)
            tp_short = self.place_tpsl_order(
                trigger_price=tp_short_price,
                hold_side='short',
                size=size_short,
                plan_type='profit_plan'
            )
            if tp_short and tp_short.get('id'):
                self.position.orders['tp_short'] = tp_short['id']
                logger.info(f"   ✅ TP Short: {tp_short['id']}")

            # 5. Place LIMIT BUY (doubler LONG si prix baisse)
            logger.info("\n[5/6] Placement LIMIT BUY (Fibo Long)...")
            time.sleep(1)
            fibo_long = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='buy', amount=size_long * 2,
                price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.position.orders['double_long'] = fibo_long['id']
            logger.info(f"   ✅ LIMIT BUY: {fibo_long['id']} - {size_long * 2:.0f} @ ${fibo_long_price:.5f}")

            # 6. Place LIMIT SELL (doubler SHORT si prix monte)
            logger.info("\n[6/6] Placement LIMIT SELL (Fibo Short)...")
            time.sleep(1)
            fibo_short = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='sell', amount=size_short * 2,
                price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.position.orders['double_short'] = fibo_short['id']
            logger.info(f"   ✅ LIMIT SELL: {fibo_short['id']} - {size_short * 2:.0f} @ ${fibo_short_price:.5f}")

            logger.info("\n" + "="*80)
            logger.info("✅ HEDGE INITIAL COMPLET!")
            logger.info("="*80)
            logger.info(f"📊 Résumé:")
            logger.info(f"   Positions: LONG {size_long:.0f} + SHORT {size_short:.0f}")
            logger.info(f"   Ordres TP: 2")
            logger.info(f"   Ordres LIMIT: 2")
            logger.info(f"   Total: 2 positions + 4 ordres")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur ouverture hedge: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def detect_tp_long_executed(self, real_pos):
        """Detect if TP LONG was executed (position disappeared)"""
        return self.position.long_open and not real_pos.get('long')

    def detect_tp_short_executed(self, real_pos):
        """Detect if TP SHORT was executed (position disappeared)"""
        return self.position.short_open and not real_pos.get('short')

    def detect_fibo_long_executed(self, real_pos):
        """Detect if LIMIT LONG was executed (size doubled)"""
        if not real_pos.get('long'):
            return False

        current_size = real_pos['long']['size']
        previous_size = self.position.long_size_previous

        # Size increased significantly = Fibo executed
        if previous_size > 0 and current_size >= previous_size * 1.8:
            logger.info(f"🔍 Fibo Long détecté: {previous_size:.0f} → {current_size:.0f}")
            return True

        return False

    def detect_fibo_short_executed(self, real_pos):
        """Detect if LIMIT SHORT was executed (size doubled)"""
        if not real_pos.get('short'):
            return False

        current_size = real_pos['short']['size']
        previous_size = self.position.short_size_previous

        # Size increased significantly = Fibo executed
        if previous_size > 0 and current_size >= previous_size * 1.8:
            logger.info(f"🔍 Fibo Short détecté: {previous_size:.0f} → {current_size:.0f}")
            return True

        return False

    def handle_tp_long_executed(self):
        """
        TP LONG executed → Reopen LONG + create new orders
        """
        logger.info("\n" + "🔔"*40)
        logger.info("🔔 TP LONG EXÉCUTÉ - HANDLER START")
        logger.info("🔔"*40)

        try:
            # 1. Cancel LIMIT LONG (ignore errors)
            logger.info("\n[1/4] Annulation LIMIT LONG...")
            if self.position.orders.get('double_long'):
                try:
                    self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
                    logger.info("   ✅ LIMIT LONG annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ LIMIT LONG déjà annulé: {e}")
                self.position.orders['double_long'] = None

            # 2. Reopen LONG market
            logger.info("\n[2/4] Réouverture LONG MARKET...")
            current_price = self.get_price()
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size = notional / current_price

            logger.info(f"   Prix: ${current_price:.5f}")
            logger.info(f"   Size: {size:.1f} contrats")

            long_order = self.exchange.create_order(
                symbol=self.PAIR, type='market', side='buy', amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            logger.info(f"   ✅ LONG réouvert: {long_order['id']}")

            # Get real position
            time.sleep(2)
            real_pos = self.get_real_positions()

            if not real_pos.get('long'):
                logger.error("   ❌ Long pas trouvé après réouverture!")
                return

            entry_long = real_pos['long']['entry_price']
            size_long = real_pos['long']['size']

            logger.info(f"   Position confirmée: {size_long:.0f} @ ${entry_long:.5f}")

            # Update state
            self.position.entry_price_long = entry_long
            self.position.long_open = True
            self.position.long_fib_level = 0
            self.position.long_size_previous = size_long

            # 3. Place NEW TP LONG
            logger.info(f"\n[3/4] Placement NOUVEAU TP LONG ({self.TP_PERCENT}%)...")
            time.sleep(1)
            tp_long_price = entry_long * (1 + self.TP_PERCENT / 100)

            tp_order = self.place_tpsl_order(
                trigger_price=tp_long_price,
                hold_side='long',
                size=size_long
            )
            if tp_order and tp_order.get('id'):
                self.position.orders['tp_long'] = tp_order['id']
                logger.info(f"   ✅ Nouveau TP Long @ ${tp_long_price:.5f}")

            # 4. Place NEW LIMIT LONG (Fibo level 0)
            logger.info(f"\n[4/4] Placement NOUVEAU LIMIT LONG (Fibo {self.FIBO_LEVELS[0]}%)...")
            time.sleep(1)
            fibo_long_price = entry_long * (1 - self.FIBO_LEVELS[0] / 100)

            fibo_order = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='buy', amount=size_long * 2,
                price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.position.orders['double_long'] = fibo_order['id']
            logger.info(f"   ✅ LIMIT BUY @ ${fibo_long_price:.5f}")

            logger.info("\n✅ TP LONG HANDLER TERMINÉ\n")

        except Exception as e:
            logger.error(f"❌ Erreur handle_tp_long: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_tp_short_executed(self):
        """
        TP SHORT executed → Reopen SHORT + create new orders
        """
        logger.info("\n" + "🔔"*40)
        logger.info("🔔 TP SHORT EXÉCUTÉ - HANDLER START")
        logger.info("🔔"*40)

        try:
            # 1. Cancel LIMIT SHORT (ignore errors)
            logger.info("\n[1/4] Annulation LIMIT SHORT...")
            if self.position.orders.get('double_short'):
                try:
                    self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
                    logger.info("   ✅ LIMIT SHORT annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ LIMIT SHORT déjà annulé: {e}")
                self.position.orders['double_short'] = None

            # 2. Reopen SHORT market
            logger.info("\n[2/4] Réouverture SHORT MARKET...")
            current_price = self.get_price()
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size = notional / current_price

            logger.info(f"   Prix: ${current_price:.5f}")
            logger.info(f"   Size: {size:.1f} contrats")

            short_order = self.exchange.create_order(
                symbol=self.PAIR, type='market', side='sell', amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            logger.info(f"   ✅ SHORT réouvert: {short_order['id']}")

            # Get real position
            time.sleep(2)
            real_pos = self.get_real_positions()

            if not real_pos.get('short'):
                logger.error("   ❌ Short pas trouvé après réouverture!")
                return

            entry_short = real_pos['short']['entry_price']
            size_short = real_pos['short']['size']

            logger.info(f"   Position confirmée: {size_short:.0f} @ ${entry_short:.5f}")

            # Update state
            self.position.entry_price_short = entry_short
            self.position.short_open = True
            self.position.short_fib_level = 0
            self.position.short_size_previous = size_short

            # 3. Place NEW TP SHORT
            logger.info(f"\n[3/4] Placement NOUVEAU TP SHORT ({self.TP_PERCENT}%)...")
            time.sleep(1)
            tp_short_price = entry_short * (1 - self.TP_PERCENT / 100)

            tp_order = self.place_tpsl_order(
                trigger_price=tp_short_price,
                hold_side='short',
                size=size_short
            )
            if tp_order and tp_order.get('id'):
                self.position.orders['tp_short'] = tp_order['id']
                logger.info(f"   ✅ Nouveau TP Short @ ${tp_short_price:.5f}")

            # 4. Place NEW LIMIT SHORT (Fibo level 0)
            logger.info(f"\n[4/4] Placement NOUVEAU LIMIT SHORT (Fibo {self.FIBO_LEVELS[0]}%)...")
            time.sleep(1)
            fibo_short_price = entry_short * (1 + self.FIBO_LEVELS[0] / 100)

            fibo_order = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='sell', amount=size_short * 2,
                price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.position.orders['double_short'] = fibo_order['id']
            logger.info(f"   ✅ LIMIT SELL @ ${fibo_short_price:.5f}")

            logger.info("\n✅ TP SHORT HANDLER TERMINÉ\n")

        except Exception as e:
            logger.error(f"❌ Erreur handle_tp_short: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_fibo_long_executed(self):
        """
        LIMIT LONG executed (size doubled) → Update TP + new LIMIT at next Fibo level
        """
        logger.info("\n" + "⚡"*40)
        logger.info("⚡ FIBO LONG EXÉCUTÉ - HANDLER START")
        logger.info("⚡"*40)

        try:
            # 1. Cancel old orders (ignore errors if already gone)
            logger.info("\n[1/3] Annulation anciens ordres LONG...")
            if self.position.orders.get('tp_long'):
                try:
                    self.exchange.cancel_order(self.position.orders['tp_long'], self.PAIR)
                    logger.info("   ✅ TP Long annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ TP Long déjà annulé ou inexistant: {e}")
                self.position.orders['tp_long'] = None

            if self.position.orders.get('double_long'):
                try:
                    self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
                    logger.info("   ✅ LIMIT Long annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ LIMIT Long déjà annulé ou inexistant: {e}")
                self.position.orders['double_long'] = None

            # Get current position
            time.sleep(1)
            real_pos = self.get_real_positions()

            if not real_pos.get('long'):
                logger.error("   ❌ Long pas trouvé!")
                return

            entry_long_avg = real_pos['long']['entry_price']
            size_long_total = real_pos['long']['size']

            logger.info(f"   Position LONG doublée: {size_long_total:.0f} @ ${entry_long_avg:.5f} (prix moyen)")

            # 2. Increase Fib level
            self.position.long_fib_level += 1
            self.position.entry_price_long = entry_long_avg
            self.position.long_size_previous = size_long_total

            logger.info(f"   Fib level: {self.position.long_fib_level}")

            # 3. Place NEW TP LONG (at average price)
            logger.info(f"\n[2/3] Placement NOUVEAU TP LONG ({self.TP_PERCENT}% du prix moyen)...")
            time.sleep(1)
            tp_long_price = entry_long_avg * (1 + self.TP_PERCENT / 100)

            tp_order = self.place_tpsl_order(
                trigger_price=tp_long_price,
                hold_side='long',
                size=size_long_total
            )
            if tp_order and tp_order.get('id'):
                self.position.orders['tp_long'] = tp_order['id']
                logger.info(f"   ✅ Nouveau TP Long @ ${tp_long_price:.5f}")

            # 4. Place NEW LIMIT LONG (next Fibo level)
            next_level = self.position.long_fib_level + 1
            if next_level < len(self.FIBO_LEVELS):
                logger.info(f"\n[3/3] Placement NOUVEAU LIMIT LONG (Fibo level {next_level}: {self.FIBO_LEVELS[next_level]}%)...")
                time.sleep(1)
                fibo_long_price = entry_long_avg * (1 - self.FIBO_LEVELS[next_level] / 100)

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR, type='limit', side='buy', amount=size_long_total * 2,
                    price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                self.position.orders['double_long'] = fibo_order['id']
                logger.info(f"   ✅ LIMIT BUY @ ${fibo_long_price:.5f}")
            else:
                logger.warning("   ⚠️ Niveau Fibo max atteint, pas de nouveau LIMIT")

            logger.info("\n✅ FIBO LONG HANDLER TERMINÉ\n")

        except Exception as e:
            logger.error(f"❌ Erreur handle_fibo_long: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_fibo_short_executed(self):
        """
        LIMIT SHORT executed (size doubled) → Update TP + new LIMIT at next Fibo level
        """
        logger.info("\n" + "⚡"*40)
        logger.info("⚡ FIBO SHORT EXÉCUTÉ - HANDLER START")
        logger.info("⚡"*40)

        try:
            # 1. Cancel old orders (ignore errors if already gone)
            logger.info("\n[1/3] Annulation anciens ordres SHORT...")
            if self.position.orders.get('tp_short'):
                try:
                    self.exchange.cancel_order(self.position.orders['tp_short'], self.PAIR)
                    logger.info("   ✅ TP Short annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ TP Short déjà annulé ou inexistant: {e}")
                self.position.orders['tp_short'] = None

            if self.position.orders.get('double_short'):
                try:
                    self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
                    logger.info("   ✅ LIMIT Short annulé")
                except Exception as e:
                    logger.warning(f"   ⚠️ LIMIT Short déjà annulé ou inexistant: {e}")
                self.position.orders['double_short'] = None

            # Get current position
            time.sleep(1)
            real_pos = self.get_real_positions()

            if not real_pos.get('short'):
                logger.error("   ❌ Short pas trouvé!")
                return

            entry_short_avg = real_pos['short']['entry_price']
            size_short_total = real_pos['short']['size']

            logger.info(f"   Position SHORT doublée: {size_short_total:.0f} @ ${entry_short_avg:.5f} (prix moyen)")

            # 2. Increase Fib level
            self.position.short_fib_level += 1
            self.position.entry_price_short = entry_short_avg
            self.position.short_size_previous = size_short_total

            logger.info(f"   Fib level: {self.position.short_fib_level}")

            # 3. Place NEW TP SHORT (at average price)
            logger.info(f"\n[2/3] Placement NOUVEAU TP SHORT ({self.TP_PERCENT}% du prix moyen)...")
            time.sleep(1)
            tp_short_price = entry_short_avg * (1 - self.TP_PERCENT / 100)

            tp_order = self.place_tpsl_order(
                trigger_price=tp_short_price,
                hold_side='short',
                size=size_short_total
            )
            if tp_order and tp_order.get('id'):
                self.position.orders['tp_short'] = tp_order['id']
                logger.info(f"   ✅ Nouveau TP Short @ ${tp_short_price:.5f}")

            # 4. Place NEW LIMIT SHORT (next Fibo level)
            next_level = self.position.short_fib_level + 1
            if next_level < len(self.FIBO_LEVELS):
                logger.info(f"\n[3/3] Placement NOUVEAU LIMIT SHORT (Fibo level {next_level}: {self.FIBO_LEVELS[next_level]}%)...")
                time.sleep(1)
                fibo_short_price = entry_short_avg * (1 + self.FIBO_LEVELS[next_level] / 100)

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR, type='limit', side='sell', amount=size_short_total * 2,
                    price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                self.position.orders['double_short'] = fibo_order['id']
                logger.info(f"   ✅ LIMIT SELL @ ${fibo_short_price:.5f}")
            else:
                logger.warning("   ⚠️ Niveau Fibo max atteint, pas de nouveau LIMIT")

            logger.info("\n✅ FIBO SHORT HANDLER TERMINÉ\n")

        except Exception as e:
            logger.error(f"❌ Erreur handle_fibo_short: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def check_events(self):
        """Check for TP/Fibo execution events"""

        try:
            real_pos = self.get_real_positions()

            # Event 1: TP LONG executed
            if self.detect_tp_long_executed(real_pos):
                logger.info("🔥 DÉTECTION: TP LONG EXÉCUTÉ!")
                self.handle_tp_long_executed()
                return True

            # Event 2: TP SHORT executed
            if self.detect_tp_short_executed(real_pos):
                logger.info("🔥 DÉTECTION: TP SHORT EXÉCUTÉ!")
                self.handle_tp_short_executed()
                return True

            # Event 3: Fibo LONG executed
            if self.detect_fibo_long_executed(real_pos):
                logger.info("🔥 DÉTECTION: FIBO LONG EXÉCUTÉ!")
                self.handle_fibo_long_executed()
                return True

            # Event 4: Fibo SHORT executed
            if self.detect_fibo_short_executed(real_pos):
                logger.info("🔥 DÉTECTION: FIBO SHORT EXÉCUTÉ!")
                self.handle_fibo_short_executed()
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Erreur check_events: {e}")
            return False

    def run(self):
        """Main loop"""
        logger.info("\n🎬 DÉMARRAGE BOT V3...\n")

        # Cleanup with verification
        cleanup_ok = self.cleanup_all()
        if not cleanup_ok:
            logger.error("❌ CLEANUP ÉCHOUÉ - BOT ARRÊTÉ POUR SÉCURITÉ")
            logger.error("   Vérifiez manuellement sur Bitget et fermez les positions restantes")
            return

        time.sleep(3)

        # Open initial hedge
        if not self.open_initial_hedge():
            logger.error("❌ Échec ouverture hedge initial!")
            return

        logger.info("\n" + "="*80)
        logger.info("🔄 BOUCLE DE MONITORING DÉMARRÉE")
        logger.info("="*80)
        logger.info("Checking for events every 2 seconds...")
        logger.info("Press Ctrl+C to stop\n")

        iteration = 0

        try:
            while True:
                iteration += 1

                # Check for events
                event_detected = self.check_events()

                if event_detected:
                    logger.info("⏸️  Événement traité, pause 5s...")
                    time.sleep(5)

                # Log every 10 iterations
                if iteration % 10 == 0:
                    real_pos = self.get_real_positions()
                    long_size = real_pos['long']['size'] if real_pos.get('long') else 0
                    short_size = real_pos['short']['size'] if real_pos.get('short') else 0
                    price = self.get_price()

                    logger.info(f"[{iteration}] 💚 LONG: {long_size:.0f} | ❤️ SHORT: {short_size:.0f} | 💰 Prix: ${price:.5f}")

                time.sleep(2)

        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Arrêt demandé par utilisateur")
            logger.info("Bot arrêté proprement.")


if __name__ == "__main__":
    try:
        bot = BitgetHedgeBotV3()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
