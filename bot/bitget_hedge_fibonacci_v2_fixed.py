#!/usr/bin/env python3
"""
🤖 Bitget Hedge Fibonacci Bot V2 Fixed - PRODUCTION

Stratégie: Hedge permanent avec TP/Fibo optimisés
- TP: 0.5%
- Fibo niveau 1: 0.3%
- Marge initiale: 5 USDT
- Notifications Telegram
- Handlers robustes avec try/except
- Retry automatique pour ordres TP
"""

import ccxt
import time
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'logs/bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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
        self.fib_levels = [0.3, 0.6, 1.0, 1.5, 2.0, 3.0, 5.0]  # 0.3%, 0.6%, 1.0%...


class BitgetHedgeBotV2Fixed:
    """Production bot with Telegram notifications and 0.5% TP"""

    def __init__(self):
        logger.info("="*80)
        logger.info("🤖 BITGET HEDGE BOT V2 FIXED - PRODUCTION (TP 0.5% | Fibo 0.3%)")
        logger.info("="*80)

        # API credentials
        self.api_key = os.getenv('BITGET_API_KEY')
        self.api_secret = os.getenv('BITGET_SECRET')
        self.api_password = os.getenv('BITGET_PASSPHRASE')

        # Telegram credentials
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if not all([self.api_key, self.api_secret, self.api_password]):
            raise ValueError("Missing API credentials in .env")

        logger.info(f"✅ API credentials loaded")
        if self.telegram_token and self.telegram_chat_id:
            logger.info(f"✅ Telegram configured")
        else:
            logger.warning(f"⚠️ Telegram not configured (will run without notifications)")

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
        self.INITIAL_MARGIN = 5  # $5 par position
        self.LEVERAGE = 50

        # TP and Fibo levels
        self.TP_PERCENT = 0.5  # 0.5% TP
        self.FIBO_LEVELS = [0.3, 0.6, 1.0, 1.5, 2.0]  # First level: 0.3%

        # Position tracking
        self.position = Position(self.PAIR)

        # Telegram updates tracking
        self.last_telegram_update_id = 0
        self.telegram_check_interval = 5  # Check toutes les 5 secondes
        self.last_telegram_check = 0

        logger.info(f"Paire: {self.PAIR}")
        logger.info(f"TP: {self.TP_PERCENT}%")
        logger.info(f"Fibo levels: {self.FIBO_LEVELS}")
        logger.info(f"Initial margin: ${self.INITIAL_MARGIN}")
        logger.info(f"Leverage: {self.LEVERAGE}x")

    def send_telegram(self, message):
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

    def send_detailed_position_update(self, pair):
        """
        Envoie des messages Telegram détaillés pour les positions
        """
        try:
            # Récupérer positions réelles depuis API
            real_pos = self.get_real_positions()
            if not real_pos:
                return

            # MESSAGE POUR POSITION LONG
            if real_pos.get('long'):
                long_data = real_pos['long']
                current_price = self.get_price()
                pnl_pct = ((current_price - long_data['entry_price']) / long_data['entry_price']) * 100

                message_long = [f"🟢 <b>POSITION LONG - {pair.split('/')[0]}</b>"]
                message_long.append("━━━━━━━━━━━━━━━━━━")
                message_long.append(f"📊 <b>Position Actuelle:</b>")
                message_long.append(f"• Contrats: {long_data['size']:.0f}")
                message_long.append(f"• Entrée: ${long_data['entry_price']:.5f}")
                message_long.append(f"• Prix actuel: ${current_price:.5f}")
                message_long.append(f"• PnL: {long_data['pnl']:.7f} USDT ({pnl_pct:.2f}%)")
                message_long.append(f"• Niveau Fib: {self.position.long_fib_level}")
                message_long.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                self.send_telegram("\n".join(message_long))

            # MESSAGE POUR POSITION SHORT
            if real_pos.get('short'):
                short_data = real_pos['short']
                current_price = self.get_price()
                pnl_pct = ((short_data['entry_price'] - current_price) / short_data['entry_price']) * 100

                message_short = [f"🔴 <b>POSITION SHORT - {pair.split('/')[0]}</b>"]
                message_short.append("━━━━━━━━━━━━━━━━━━")
                message_short.append(f"📊 <b>Position Actuelle:</b>")
                message_short.append(f"• Contrats: {short_data['size']:.0f}")
                message_short.append(f"• Entrée: ${short_data['entry_price']:.5f}")
                message_short.append(f"• Prix actuel: ${current_price:.5f}")
                message_short.append(f"• PnL: {short_data['pnl']:.7f} USDT ({pnl_pct:.2f}%)")
                message_short.append(f"• Niveau Fib: {self.position.short_fib_level}")
                message_short.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                self.send_telegram("\n".join(message_short))

        except Exception as e:
            logger.error(f"Erreur send_detailed_position_update: {e}")

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
        """
        Place TP/SL order with retry and price adjustment

        Retries up to 5 times if price is invalid
        Adjusts price by 0.05% each retry to ensure it's valid
        """

        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')
        bitget_plan_type = 'pos_profit' if plan_type == 'profit_plan' else 'pos_loss'

        max_retries = 5
        current_price = trigger_price

        for attempt in range(max_retries):
            # Adjust price based on retry attempt
            if attempt > 0:
                # For LONG TP: increase price (must be > mark price)
                # For SHORT TP: decrease price (must be < mark price)
                adjustment = 0.0005 * attempt  # 0.05% per retry
                if hold_side == 'long':
                    current_price = trigger_price * (1 + adjustment)
                else:  # short
                    current_price = trigger_price * (1 - adjustment)

                logger.info(f"      Retry {attempt + 1}: Ajustement prix → ${current_price:.5f}")

            trigger_price_rounded = round(current_price, 5)

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

            if attempt == 0:
                logger.info(f"   📤 Place TP/SL {plan_type}: prix ${trigger_price_rounded:.5f}")

            try:
                result = self.exchange.private_mix_post_v2_mix_order_place_tpsl_order(body)

                if result.get('code') == '00000':
                    order_id = result['data']['orderId']
                    logger.info(f"   ✅ TP/SL placé (tentative {attempt + 1}): {order_id}")
                    return {'id': order_id}
                else:
                    logger.warning(f"      ⚠️ Tentative {attempt + 1} échec: {result.get('msg')}")
                    time.sleep(0.5)
                    continue

            except Exception as e:
                error_msg = str(e)

                # Check if error is about price validation
                if '40915' in error_msg or 'price please' in error_msg.lower():
                    logger.warning(f"      ⚠️ Tentative {attempt + 1}: Prix invalide, ajustement...")
                    time.sleep(0.5)
                    continue
                else:
                    # Other error, retry anyway
                    logger.error(f"      ❌ Tentative {attempt + 1} erreur: {e}")
                    time.sleep(0.5)
                    continue

        # Failed after all retries
        logger.error(f"   ❌ ÉCHEC PLACEMENT TP après {max_retries} tentatives!")
        logger.error(f"   ⚠️ Position {hold_side.upper()} SANS TP - ATTENTION!")
        return None

    def open_initial_hedge(self):
        """
        Open initial hedge: LONG + SHORT + 4 orders (2 TP + 2 LIMIT Fibo)

        Orders created:
        1. LONG market
        2. SHORT market
        3. TP LONG
        4. TP SHORT
        5. LIMIT LONG (Fibo) - Double la marge LONG
        6. LIMIT SHORT (Fibo) - Double la marge SHORT
        """
        logger.info("\n" + "="*80)
        logger.info("🚀 OUVERTURE HEDGE INITIAL (2 TP + 2 LIMIT FIBO)")
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

            # 5. Place LIMIT BUY (double la marge LONG quand exécuté)
            logger.info("\n[5/6] Placement LIMIT BUY (Fibo Long - double marge)...")
            time.sleep(1)
            fibo_long = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='buy', amount=size_long,
                price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.position.orders['double_long'] = fibo_long['id']
            logger.info(f"   ✅ LIMIT BUY: {fibo_long['id']} - {size_long:.0f} @ ${fibo_long_price:.5f}")

            # 6. Place LIMIT SELL (double la marge SHORT quand exécuté)
            logger.info("\n[6/6] Placement LIMIT SELL (Fibo Short - double marge)...")
            time.sleep(1)
            fibo_short = self.exchange.create_order(
                symbol=self.PAIR, type='limit', side='sell', amount=size_short,
                price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.position.orders['double_short'] = fibo_short['id']
            logger.info(f"   ✅ LIMIT SELL: {fibo_short['id']} - {size_short:.0f} @ ${fibo_short_price:.5f}")

            logger.info("\n" + "="*80)
            logger.info("✅ HEDGE INITIAL COMPLET!")
            logger.info("="*80)
            logger.info(f"📊 Résumé:")
            logger.info(f"   Positions: LONG {size_long:.0f} + SHORT {size_short:.0f}")
            logger.info(f"   Ordres TP: 2")
            logger.info(f"   Ordres LIMIT Fibo: 2 (doublent la marge)")
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

        # Notification Telegram
        self.send_telegram(f"✅ <b>TP LONG TOUCHÉ - {self.PAIR.split('/')[0]}</b>\n\nRéouverture en cours...")

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

            # Notification finale avec détails
            self.send_detailed_position_update(self.PAIR)

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

        # Notification Telegram
        self.send_telegram(f"✅ <b>TP SHORT TOUCHÉ - {self.PAIR.split('/')[0]}</b>\n\nRéouverture en cours...")

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

            # Notification finale avec détails
            self.send_detailed_position_update(self.PAIR)

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

        # Notification Telegram
        self.send_telegram(f"📉 <b>FIBO LONG TOUCHÉ - {self.PAIR.split('/')[0]}</b>\n\nDoublement position...")

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
                    symbol=self.PAIR, type='limit', side='buy', amount=size_long_total,
                    price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                self.position.orders['double_long'] = fibo_order['id']
                logger.info(f"   ✅ LIMIT BUY @ ${fibo_long_price:.5f} (size: {size_long_total:.0f})")
            else:
                logger.warning("   ⚠️ Niveau Fibo max atteint, pas de nouveau LIMIT")

            logger.info("\n✅ FIBO LONG HANDLER TERMINÉ\n")

            # Notification finale avec détails
            self.send_detailed_position_update(self.PAIR)

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

        # Notification Telegram
        self.send_telegram(f"📈 <b>FIBO SHORT TOUCHÉ - {self.PAIR.split('/')[0]}</b>\n\nDoublement position...")

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
                    symbol=self.PAIR, type='limit', side='sell', amount=size_short_total,
                    price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                self.position.orders['double_short'] = fibo_order['id']
                logger.info(f"   ✅ LIMIT SELL @ ${fibo_short_price:.5f} (size: {size_short_total:.0f})")
            else:
                logger.warning("   ⚠️ Niveau Fibo max atteint, pas de nouveau LIMIT")

            logger.info("\n✅ FIBO SHORT HANDLER TERMINÉ\n")

            # Notification finale avec détails
            self.send_detailed_position_update(self.PAIR)

        except Exception as e:
            logger.error(f"❌ Erreur handle_fibo_short: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def get_telegram_updates(self):
        """Récupère les nouveaux messages Telegram (commandes)"""
        if not self.telegram_token:
            return []

        url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
        params = {'offset': self.last_telegram_update_id + 1, 'timeout': 0}

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    return data['result']
        except:
            pass

        return []

    def check_telegram_updates(self):
        """Check for new Telegram commands"""
        updates = self.get_telegram_updates()

        for update in updates:
            self.last_telegram_update_id = update['update_id']

            if 'message' in update and 'text' in update['message']:
                text = update['message']['text'].strip()

                if text.startswith('/'):
                    logger.info(f"📱 Commande Telegram reçue: {text}")
                    self.handle_telegram_command(text)

    def handle_telegram_command(self, command):
        """Traite les commandes Telegram"""
        try:
            # Séparer commande et arguments
            parts = command.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            if cmd == '/pnl':
                self.cmd_pnl()
            elif cmd == '/status':
                self.cmd_status()
            elif cmd == '/setmargin':
                self.cmd_setmargin(args)
            elif cmd == '/settp':
                self.cmd_settp(args)
            elif cmd == '/setfibo':
                self.cmd_setfibo(args)
            elif cmd == '/stop':
                self.cmd_stop(args)
            elif cmd == '/help':
                self.cmd_help()
            else:
                self.send_telegram(f"❌ Commande inconnue: {cmd}\nTapez /help pour voir les commandes disponibles")

        except Exception as e:
            logger.error(f"❌ Erreur traitement commande {command}: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def cmd_pnl(self):
        """Commande /pnl - Affiche P&L total"""
        try:
            real_pos = self.get_real_positions()
            current_price = self.get_price()

            # PnL non réalisé
            total_pnl = 0
            margin_used = 0

            if real_pos.get('long'):
                long_pnl = real_pos['long']['pnl']
                long_margin = real_pos['long']['margin']
                total_pnl += long_pnl
                margin_used += long_margin

            if real_pos.get('short'):
                short_pnl = real_pos['short']['pnl']
                short_margin = real_pos['short']['margin']
                total_pnl += short_pnl
                margin_used += short_margin

            message = f"""💰 <b>P&L - {self.PAIR.split('/')[0]}</b>

📊 <b>Positions:</b>"""

            if real_pos.get('long'):
                entry_long = real_pos['long']['entry_price']
                size_long = real_pos['long']['size']
                pnl_long = real_pos['long']['pnl']
                pnl_pct_long = ((current_price - entry_long) / entry_long) * 100
                message += f"""
🟢 LONG: {size_long:.0f} contrats
   Entrée: ${entry_long:.5f}
   PnL: {pnl_long:+.7f} USDT ({pnl_pct_long:+.2f}%)"""

            if real_pos.get('short'):
                entry_short = real_pos['short']['entry_price']
                size_short = real_pos['short']['size']
                pnl_short = real_pos['short']['pnl']
                pnl_pct_short = ((entry_short - current_price) / entry_short) * 100
                message += f"""
🔴 SHORT: {size_short:.0f} contrats
   Entrée: ${entry_short:.5f}
   PnL: {pnl_short:+.7f} USDT ({pnl_pct_short:+.2f}%)"""

            message += f"""

━━━━━━━━━━━━━━━━━
💎 <b>PnL Total: {total_pnl:+.7f} USDT</b>
💵 Marge utilisée: {margin_used:.7f} USDT
💰 Prix actuel: ${current_price:.5f}

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            self.send_telegram(message)

        except Exception as e:
            logger.error(f"Erreur /pnl: {e}")
            self.send_telegram(f"❌ Erreur /pnl: {e}")

    def cmd_status(self):
        """Commande /status - État du bot"""
        try:
            real_pos = self.get_real_positions()
            current_price = self.get_price()

            # Compter les ordres actifs
            open_orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
            tp_orders = [o for o in open_orders if 'profit' in o.get('info', {}).get('planType', '').lower()]
            limit_orders = [o for o in open_orders if o['type'] == 'limit']

            message = f"""🤖 <b>STATUS BOT - {self.PAIR.split('/')[0]}</b>

📊 <b>Positions:</b>"""

            if real_pos.get('long'):
                size_long = real_pos['long']['size']
                entry_long = real_pos['long']['entry_price']
                message += f"""
🟢 LONG: {size_long:.0f} @ ${entry_long:.5f}
   Niveau Fib: {self.position.long_fib_level}"""

            if real_pos.get('short'):
                size_short = real_pos['short']['size']
                entry_short = real_pos['short']['entry_price']
                message += f"""
🔴 SHORT: {size_short:.0f} @ ${entry_short:.5f}
   Niveau Fib: {self.position.short_fib_level}"""

            message += f"""

📋 <b>Ordres actifs:</b>
• TP orders: {len(tp_orders)}
• LIMIT orders: {len(limit_orders)}

⚙️ <b>Configuration:</b>
• TP: {self.TP_PERCENT}%
• Fibo levels: {self.FIBO_LEVELS}
• Marge initiale: ${self.INITIAL_MARGIN}
• Levier: {self.LEVERAGE}x

💰 Prix actuel: ${current_price:.5f}

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            self.send_telegram(message)

        except Exception as e:
            logger.error(f"Erreur /status: {e}")
            self.send_telegram(f"❌ Erreur /status: {e}")

    def cmd_setmargin(self, args):
        """Commande /setmargin <montant> - Change INITIAL_MARGIN"""
        try:
            if not args:
                self.send_telegram("❌ Usage: /setmargin <montant>\n\nExemple: /setmargin 2")
                return

            new_margin = float(args[0])

            if new_margin <= 0:
                self.send_telegram("❌ Le montant doit être > 0")
                return

            old_margin = self.INITIAL_MARGIN
            self.INITIAL_MARGIN = new_margin

            message = f"""✅ <b>MARGE MODIFIÉE</b>

Ancienne marge: ${old_margin}
Nouvelle marge: ${new_margin}

⚠️ La modification s'appliquera aux PROCHAINES positions ouvertes.
Les positions actuelles ne sont pas affectées.

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            self.send_telegram(message)
            logger.info(f"💰 INITIAL_MARGIN modifié: ${old_margin} → ${new_margin}")

        except ValueError:
            self.send_telegram("❌ Montant invalide. Utilisez un nombre (ex: 2)")
        except Exception as e:
            logger.error(f"Erreur /setmargin: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def cmd_settp(self, args):
        """Commande /settp <pourcent> - Change TP_PERCENT"""
        try:
            if not args:
                self.send_telegram("❌ Usage: /settp <pourcent>\n\nExemple: /settp 0.5")
                return

            new_tp = float(args[0])

            if new_tp < 0.1 or new_tp > 2.0:
                self.send_telegram("❌ TP doit être entre 0.1% et 2%")
                return

            old_tp = self.TP_PERCENT
            self.TP_PERCENT = new_tp

            message = f"""✅ <b>TP MODIFIÉ</b>

Ancien TP: {old_tp}%
Nouveau TP: {new_tp}%

⚠️ La modification s'appliquera aux PROCHAINS ordres TP.
Les ordres TP actuels ne sont pas modifiés.

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            self.send_telegram(message)
            logger.info(f"📊 TP_PERCENT modifié: {old_tp}% → {new_tp}%")

        except ValueError:
            self.send_telegram("❌ Valeur invalide. Utilisez un nombre décimal (ex: 0.5)")
        except Exception as e:
            logger.error(f"Erreur /settp: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def cmd_setfibo(self, args):
        """Commande /setfibo <niveaux> - Change FIBO_LEVELS"""
        try:
            if not args:
                self.send_telegram(f"❌ Usage: /setfibo <niveaux séparés par virgule>\n\nExemple: /setfibo 0.3,0.6,1.2\n\nNiveaux actuels: {self.FIBO_LEVELS}")
                return

            # Parse niveaux
            levels_str = args[0].replace(' ', '')
            new_levels = [float(x) for x in levels_str.split(',')]

            # Validation: niveaux croissants
            if new_levels != sorted(new_levels):
                self.send_telegram("❌ Les niveaux doivent être en ordre croissant")
                return

            if len(new_levels) < 2:
                self.send_telegram("❌ Il faut au moins 2 niveaux")
                return

            old_levels = self.FIBO_LEVELS
            self.FIBO_LEVELS = new_levels

            message = f"""✅ <b>NIVEAUX FIBO MODIFIÉS</b>

Anciens niveaux: {old_levels}
Nouveaux niveaux: {new_levels}

⚠️ La modification s'appliquera aux PROCHAINS ordres LIMIT.
Les ordres LIMIT actuels ne sont pas modifiés.

⏰ {datetime.now().strftime('%H:%M:%S')}"""

            self.send_telegram(message)
            logger.info(f"📐 FIBO_LEVELS modifié: {old_levels} → {new_levels}")

        except ValueError:
            self.send_telegram("❌ Format invalide. Utilisez des nombres séparés par virgule (ex: 0.3,0.6,1.2)")
        except Exception as e:
            logger.error(f"Erreur /setfibo: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def cmd_stop(self, args):
        """Commande /stop - Ferme TOUT et arrête le bot"""
        if not args or args[0].upper() != 'CONFIRM':
            message = """⚠️ <b>ARRÊT DU BOT</b>

Cette commande va:
1. Fermer TOUTES les positions
2. Annuler TOUS les ordres
3. Arrêter le bot

Pour confirmer, tapez:
/stop CONFIRM"""
            self.send_telegram(message)
            return

        try:
            self.send_telegram("🛑 <b>ARRÊT EN COURS...</b>\n\n1. Fermeture positions\n2. Annulation ordres\n3. Arrêt bot")
            logger.info("🛑 Arrêt demandé via /stop CONFIRM")

            # 1. CLEANUP complet (fermer positions + annuler ordres)
            logger.info("🧹 Cleanup avant arrêt...")
            self.cleanup_all()

            # 2. Message final
            self.send_telegram("✅ <b>BOT ARRÊTÉ</b>\n\nPositions fermées\nOrdres annulés\nBot arrêté")
            logger.info("✅ Cleanup terminé, arrêt bot")
            time.sleep(2)

            # 3. Arrêt
            import sys
            sys.exit(0)

        except Exception as e:
            logger.error(f"Erreur /stop: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def cmd_help(self):
        """Commande /help - Liste des commandes"""
        message = """🤖 <b>COMMANDES DISPONIBLES</b>

📊 <b>Informations:</b>
/pnl - P&L total et positions
/status - État du bot et ordres

⚙️ <b>Configuration:</b>
/setmargin &lt;montant&gt; - Changer marge initiale
/settp &lt;pourcent&gt; - Changer TP %
/setfibo &lt;niveaux&gt; - Changer niveaux Fibo

🛠️ <b>Contrôle:</b>
/stop - Arrêter le bot (demande confirmation)

❓ /help - Cette aide"""

        self.send_telegram(message)

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
        logger.info("\n🎬 DÉMARRAGE BOT V2 FIXED...\n")

        # Notification démarrage
        startup_msg = f"""🤖 <b>BOT V2 FIXED DÉMARRÉ</b>

📊 Config:
• Paire: {self.PAIR.split('/')[0]}
• TP: {self.TP_PERCENT}%
• Fibo: {self.FIBO_LEVELS[0]}%
• Levier: {self.LEVERAGE}x

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
        self.send_telegram(startup_msg)

        # CLEANUP AUTOMATIQUE OBLIGATOIRE AU DÉMARRAGE
        logger.info("\n🧹 CLEANUP AUTOMATIQUE AU DÉMARRAGE...")
        cleanup_ok = self.cleanup_all()
        if not cleanup_ok:
            logger.error("❌ CLEANUP ÉCHOUÉ - BOT ARRÊTÉ POUR SÉCURITÉ")
            logger.error("   Vérifiez manuellement sur Bitget et fermez les positions restantes")
            self.send_telegram("❌ <b>CLEANUP ÉCHOUÉ</b>\n\nBot arrêté. Vérifiez Bitget manuellement.")
            return

        time.sleep(3)

        # Open initial hedge
        if not self.open_initial_hedge():
            logger.error("❌ Échec ouverture hedge initial!")
            return

        logger.info("\n" + "="*80)
        logger.info("🔄 BOUCLE DE MONITORING DÉMARRÉE - 4 CHECKS/SECONDE")
        logger.info("="*80)
        logger.info("⚡ Checking for events every 0.25 seconds (4x/sec)")
        logger.info("Press Ctrl+C to stop\n")

        iteration = 0

        try:
            while True:
                iteration += 1

                # Check for events
                event_detected = self.check_events()

                if event_detected:
                    logger.info("⏸️  Événement traité, pause 3s...")
                    time.sleep(3)

                # Check Telegram commands every 5 seconds
                current_time = time.time()
                if current_time - self.last_telegram_check >= self.telegram_check_interval:
                    self.check_telegram_updates()
                    self.last_telegram_check = current_time

                # Log every 40 iterations (= every 10 seconds)
                if iteration % 40 == 0:
                    real_pos = self.get_real_positions()
                    long_size = real_pos['long']['size'] if real_pos.get('long') else 0
                    short_size = real_pos['short']['size'] if real_pos.get('short') else 0
                    price = self.get_price()

                    logger.info(f"[{iteration}] 💚 LONG: {long_size:.0f} | ❤️ SHORT: {short_size:.0f} | 💰 Prix: ${price:.5f}")

                time.sleep(0.25)  # 4 checks per second

        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Arrêt demandé par utilisateur")
            logger.info("🧹 CLEANUP AUTOMATIQUE AVANT ARRÊT...")
            self.send_telegram("⏹️ <b>Bot arrêté par utilisateur</b>\n\n🧹 Cleanup en cours...")
            cleanup_ok = self.cleanup_all()
            if cleanup_ok:
                logger.info("✅ Bot arrêté proprement - Compte nettoyé!")
                self.send_telegram("✅ <b>Bot arrêté proprement</b>\n\nCompte nettoyé (positions fermées + ordres annulés)")
            else:
                logger.warning("⚠️ Bot arrêté mais cleanup incomplet - Vérifiez Bitget!")
                self.send_telegram("⚠️ <b>Bot arrêté mais cleanup incomplet</b>\n\nVérifiez Bitget manuellement!")


if __name__ == "__main__":
    try:
        bot = BitgetHedgeBotV2Fixed()
        bot.run()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
