#!/usr/bin/env python3
"""
🤖 Bitget Hedge Fibonacci Bot V4.1 - DEBUG COMPLET

Version V4 + LOGS DE DEBUG ULTRA-DÉTAILLÉS:
✅ État positions (LONG/SHORT/sizes/entry/PnL)
✅ Prix marché actuel
✅ Ordres LIMIT Fibo (prix, sizes)
✅ Ordres TP/SL (prix, IDs)
✅ API calls (requêtes + réponses)
✅ Logs dans fichier + stdout
✅ Snapshots réguliers de l'état

Stratégie:
- TP: 0.5%
- Fibo niveau 1: 0.3%
- Marge initiale: 5 USDT
- Leverage: 50x

Usage:
    python bitget_hedge_fibonacci_v4_debug.py --pair DOGE/USDT:USDT
    python bitget_hedge_fibonacci_v4_debug.py --pair PEPE/USDT:USDT --api-key-id 2
"""

import ccxt
import time
import os
import argparse
import logging
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class DebugLogger:
    """Logger personnalisé avec logs fichier + stdout"""

    def __init__(self, pair_name):
        self.pair_name = pair_name

        # Créer dossier logs s'il existe pas
        os.makedirs('logs', exist_ok=True)

        # Filename avec timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f'logs/v4_debug_{pair_name}_{timestamp}.log'

        # Logger Python
        self.logger = logging.getLogger(f'BOT_{pair_name}')
        self.logger.setLevel(logging.DEBUG)

        # Handler fichier
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)

        # Handler console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter détaillé
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Print path
        print(f"\n{'='*80}")
        print(f"📝 LOGS DEBUG: {self.log_file}")
        print(f"{'='*80}\n")

    def info(self, msg):
        self.logger.info(msg)

    def debug(self, msg):
        self.logger.debug(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def separator(self, title=""):
        msg = "=" * 80
        if title:
            msg = f"{'='*30} {title} {'='*30}"
        self.info(msg)


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
            'double_long': None,
            'double_short': None
        }


class BitgetHedgeBotV4Debug:
    """V4 with DEBUG logging"""

    def __init__(self, pair, api_key_id=1):
        self.pair_name = pair.split('/')[0]
        self.logger = DebugLogger(self.pair_name)

        self.logger.separator(f"BOT V4.1 DEBUG - {self.pair_name}")

        # Load API credentials based on api_key_id
        if api_key_id == 1:
            self.api_key = os.getenv('BITGET_API_KEY')
            self.api_secret = os.getenv('BITGET_SECRET')
            self.api_password = os.getenv('BITGET_PASSPHRASE')
        else:
            self.api_key = os.getenv('BITGET_API_KEY_2')
            self.api_secret = os.getenv('BITGET_SECRET_2')
            self.api_password = os.getenv('BITGET_PASSPHRASE_2')

        if not all([self.api_key, self.api_secret, self.api_password]):
            raise ValueError(f"Missing API credentials for key {api_key_id}")

        self.logger.info(f"✅ API Key {api_key_id} loaded")

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
        self.PAIR = pair
        self.INITIAL_MARGIN = 0.11  # $0.11 per position (assure > 5 USDT minimum Bitget)
        self.LEVERAGE = 50

        # TP and Fibo levels
        self.TP_PERCENT = 0.1  # 0.1% TP (même niveau que premier Fibo)
        self.FIBO_LEVELS = [0.1, 0.2, 0.4, 0.8, 1.6]  # Commence à 0.1%, progression x2

        # Position tracking
        self.position = Position(self.PAIR)

        self.logger.info(f"Paire: {self.PAIR}")
        self.logger.info(f"TP: {self.TP_PERCENT}%")
        self.logger.info(f"Fibo levels: {self.FIBO_LEVELS}")
        self.logger.info(f"Marge: ${self.INITIAL_MARGIN}")
        self.logger.info(f"Leverage: {self.LEVERAGE}x")
        self.logger.separator()

    def log_api_call(self, method, endpoint, params=None, response=None, error=None):
        """Log API calls for debugging"""
        self.logger.debug(f"API [{method}] {endpoint}")
        if params:
            self.logger.debug(f"  Params: {params}")
        if response:
            self.logger.debug(f"  Response: {response}")
        if error:
            self.logger.debug(f"  Error: {error}")

    def cancel_all_tpsl_orders(self):
        """Cancel ALL TP/SL plan orders"""
        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')
        cancelled_count = 0

        for plan_type in ['pos_profit', 'pos_loss']:
            try:
                result = self.exchange.private_mix_get_v2_mix_order_orders_plan_pending({
                    'symbol': symbol_bitget,
                    'productType': 'USDT-FUTURES',
                    'planType': plan_type
                })

                if result.get('code') == '00000':
                    orders = result.get('data', {}).get('entrustedList', [])
                    for order in orders:
                        try:
                            self.exchange.private_mix_post_v2_mix_order_cancel_plan_order({
                                'orderId': order['orderId'],
                                'symbol': symbol_bitget,
                                'productType': 'USDT-FUTURES',
                                'marginCoin': 'USDT'
                            })
                            cancelled_count += 1
                            time.sleep(0.3)
                        except:
                            pass
            except:
                pass

        if cancelled_count > 0:
            self.logger.info(f"  🗑️  {cancelled_count} ordres TP/SL annulés")

        return cancelled_count

    def flash_close_position(self, side):
        """FLASH CLOSE: Force close position using Bitget special endpoint"""
        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')

        try:
            result = self.exchange.private_mix_post_v2_mix_order_close_positions({
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'holdSide': side
            })

            if result.get('code') == '00000':
                self.logger.debug(f"     ⚡ Flash close {side.upper()} SUCCESS")
                return True
            else:
                error_msg = result.get('msg', 'Unknown error')
                if '22002' in str(result):
                    self.logger.debug(f"     ⚠️  Position {side} déjà fermée (22002)")
                    return True  # Already closed = success
                else:
                    self.logger.warning(f"     ❌ Flash close {side} failed: {error_msg}")
                    return False

        except Exception as e:
            error_str = str(e)
            if '22002' in error_str:
                self.logger.debug(f"     ⚠️  Position {side} déjà fermée (22002)")
                return True
            else:
                self.logger.warning(f"     ❌ Exception flash close {side}: {e}")
                return False

    def cancel_all_limit_orders(self):
        """Cancel ALL LIMIT orders for this pair"""
        try:
            open_orders = self.exchange.fetch_open_orders(self.PAIR)
            cancelled_count = 0

            for order in open_orders:
                try:
                    self.exchange.cancel_order(order['id'], self.PAIR)
                    self.logger.debug(f"   ✅ Ordre LIMIT annulé: {order['id'][:16]}...")
                    cancelled_count += 1
                    time.sleep(0.2)
                except Exception as e:
                    if '40768' not in str(e) and '40721' not in str(e):  # Ignore "order not exist"
                        self.logger.warning(f"   ⚠️ Erreur annulation ordre {order['id'][:16]}: {str(e)[:50]}")

            if cancelled_count > 0:
                self.logger.info(f"   🧹 {cancelled_count} ordres LIMIT annulés")

            return cancelled_count

        except Exception as e:
            self.logger.error(f"❌ Erreur cancel_all_limit_orders: {e}")
            return 0

    def full_cleanup_orders(self):
        """Complete cleanup of ALL orders (LIMIT + TP/SL)"""
        self.logger.info("🧹 Cleanup complet des ordres...")

        # Cancel LIMIT orders
        limit_cancelled = self.cancel_all_limit_orders()

        # Cancel TP/SL orders
        tpsl_cancelled = self.cancel_all_tpsl_orders()

        # Reset tracking
        self.position.orders = {
            'tp_long': None,
            'tp_short': None,
            'double_long': None,
            'double_short': None
        }

        total = limit_cancelled + tpsl_cancelled
        if total > 0:
            self.logger.info(f"   ✅ Total {total} ordres nettoyés")

        return total

    def verify_position_exists(self, side, expected_size=None, max_retries=5):
        """CRITICAL: Verify position exists after opening with retry"""
        for attempt in range(max_retries):
            time.sleep(1 + attempt)  # Progressive wait 1-5s

            real_pos = self.get_real_positions()
            pos = real_pos.get(side)

            if pos:
                if expected_size:
                    actual_size = pos['size']
                    # Allow 1% tolerance
                    if abs(actual_size - expected_size) / expected_size < 0.01:
                        self.logger.info(f"   ✅ Position {side.upper()} VERIFIED: {actual_size:.2f} @ ${pos['entry_price']:.8f}")
                        return pos
                    else:
                        self.logger.warning(f"   ⚠️  Size mismatch: expected {expected_size}, got {actual_size}")
                else:
                    self.logger.info(f"   ✅ Position {side.upper()} exists: {pos['size']:.2f}")
                    return pos

            if attempt < max_retries - 1:
                self.logger.info(f"   🔄 Tentative {attempt + 1}/{max_retries}: Position {side} pas encore visible...")

        self.logger.error(f"   ❌ Position {side.upper()} NOT FOUND après {max_retries} tentatives!")
        return None

    def snapshot_state(self, title="STATE SNAPSHOT"):
        """Log complete state of bot"""
        self.logger.separator(title)

        try:
            # Get current price
            ticker = self.exchange.fetch_ticker(self.PAIR)
            current_price = float(ticker['last'])
            self.logger.info(f"📊 PRIX MARCHÉ ACTUEL: ${current_price:.8f}")

            # Get positions
            real_pos = self.get_real_positions()

            if real_pos['long']:
                pos = real_pos['long']
                self.logger.info(f"  🟢 LONG POSITION:")
                self.logger.info(f"     - Size: {pos['size']:.2f} contrats")
                self.logger.info(f"     - Entry Price: ${pos['entry_price']:.8f}")
                self.logger.info(f"     - PnL: ${pos['pnl']:.2f}")
                self.logger.info(f"     - Leverage: {pos['leverage']}x")
            else:
                self.logger.info(f"  ⚪ LONG: Fermée")

            if real_pos['short']:
                pos = real_pos['short']
                self.logger.info(f"  🔴 SHORT POSITION:")
                self.logger.info(f"     - Size: {pos['size']:.2f} contrats")
                self.logger.info(f"     - Entry Price: ${pos['entry_price']:.8f}")
                self.logger.info(f"     - PnL: ${pos['pnl']:.2f}")
                self.logger.info(f"     - Leverage: {pos['leverage']}x")
            else:
                self.logger.info(f"  ⚪ SHORT: Fermée")

            # Get orders
            orders = self.exchange.fetch_open_orders(self.PAIR)
            self.logger.info(f"  📋 ORDRES OUVERTS: {len(orders)}")
            for order in orders:
                side = order.get('side', 'unknown')
                amount = order.get('amount', 0)
                price = order.get('price', 0)
                order_id = order.get('id', 'unknown')[:16]
                status = order.get('status', 'unknown')
                self.logger.info(f"     - {side.upper()} {amount:.2f} @ ${price:.8f} [{order_id}...] ({status})")

            # TP/SL orders from tracking
            self.logger.info(f"  🎯 ORDRES TP/SL TRACKÉS:")
            self.logger.info(f"     - TP Long ID: {self.position.orders['tp_long']}")
            self.logger.info(f"     - TP Short ID: {self.position.orders['tp_short']}")
            self.logger.info(f"  🔄 ORDRES LIMIT FIBO TRACKÉS:")
            self.logger.info(f"     - Double Long ID: {self.position.orders['double_long']}")
            self.logger.info(f"     - Double Short ID: {self.position.orders['double_short']}")

        except Exception as e:
            self.logger.error(f"Erreur snapshot: {e}")

    def cleanup_all(self):
        """Clean all positions and orders - WITH VERIFICATION"""
        self.logger.separator("CLEANUP INITIAL")
        self.logger.info("🧹 Cleanup avec vérification...")

        max_retries = 3

        for attempt in range(max_retries):
            if attempt > 0:
                self.logger.info(f"\n🔄 Tentative {attempt + 1}/{max_retries}...")

            try:
                # 1. Cancel all LIMIT orders
                orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                if orders:
                    self.logger.info(f"  📝 {len(orders)} ordres LIMIT à annuler...")
                    for order in orders:
                        try:
                            self.exchange.cancel_order(order['id'], self.PAIR)
                            self.logger.debug(f"    ✅ Ordre {order['id'][:16]}... annulé")
                        except Exception as e:
                            self.logger.warning(f"    ⚠️  Erreur annulation {order['id'][:16]}: {e}")
                        time.sleep(0.2)

                # 2. Cancel all TP/SL orders
                self.cancel_all_tpsl_orders()

                # 3. FLASH CLOSE all positions (more reliable than market orders)
                positions = self.exchange.fetch_positions(symbols=[self.PAIR])
                closed_count = 0
                for pos in positions:
                    size = float(pos.get('contracts', 0))
                    if size > 0:
                        side = pos.get('side', '').lower()
                        self.logger.info(f"  🔴 Flash closing {side.upper()}: {size:.0f} contrats")

                        if self.flash_close_position(side):
                            closed_count += 1

                        time.sleep(1)

                if closed_count > 0:
                    self.logger.info(f"  ⚡ {closed_count} positions flash closed")

                # 4. VERIFICATION FINALE
                time.sleep(2)
                final_orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                final_positions = self.exchange.fetch_positions(symbols=[self.PAIR])
                final_pos_count = sum(1 for p in final_positions if float(p.get('contracts', 0)) > 0)

                if len(final_orders) == 0 and final_pos_count == 0:
                    self.logger.info("✅ Cleanup VÉRIFIÉ - Compte clean!")
                    self.snapshot_state("POST-CLEANUP STATE")
                    return True
                else:
                    self.logger.warning(f"⚠️  Il reste: {len(final_orders)} ordres, {final_pos_count} positions")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue

            except Exception as e:
                self.logger.error(f"❌ Erreur cleanup: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                if attempt == max_retries - 1:
                    return False

        self.logger.warning("⚠️ Cleanup incomplet après 3 tentatives")
        return False

    def get_price(self):
        """Get current market price"""
        try:
            ticker = self.exchange.fetch_ticker(self.PAIR)
            price = float(ticker['last'])
            self.logger.debug(f"API [fetch_ticker] → ${price:.8f}")
            return price
        except Exception as e:
            self.logger.error(f"Erreur fetch_ticker: {e}")
            raise

    def get_real_positions(self):
        """Get actual positions from API"""
        try:
            positions = self.exchange.fetch_positions(symbols=[self.PAIR])

            result = {'long': None, 'short': None}

            for pos in positions:
                size = float(pos.get('contracts', 0))
                if size > 0:
                    side = pos.get('side', '').lower()
                    result[side] = {
                        'size': size,
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'pnl': float(pos.get('unrealizedPnl', 0)),
                        'leverage': float(pos.get('leverage', 0))
                    }
                    self.logger.debug(f"API [fetch_positions] {side}: size={size}, entry=${result[side]['entry_price']:.8f}, pnl=${result[side]['pnl']:.2f}")

            return result
        except Exception as e:
            self.logger.error(f"Erreur fetch_positions: {e}")
            raise

    def place_tpsl_order(self, trigger_price, hold_side, size, plan_type='profit_plan'):
        """Place TP/SL order using Bitget API (EXACTLY like V2_fixed)"""

        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')
        bitget_plan_type = 'pos_profit' if plan_type == 'profit_plan' else 'pos_loss'

        max_retries = 5
        current_price = trigger_price

        for attempt in range(max_retries):
            # Adjust price based on retry attempt
            if attempt > 0:
                adjustment = 0.0005 * attempt  # 0.05% per retry
                if hold_side == 'long':
                    current_price = trigger_price * (1 + adjustment)
                else:  # short
                    current_price = trigger_price * (1 - adjustment)
                self.logger.info(f"      Retry {attempt + 1}: Ajustement prix → ${current_price:.8f}")

            trigger_price_rounded = self.round_price(current_price)

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

            try:
                self.logger.debug(f"API [place_tpsl_order] Body: {body}")
                result = self.exchange.private_mix_post_v2_mix_order_place_tpsl_order(body)
                self.logger.debug(f"API Response: {result}")

                if result.get('code') == '00000':
                    order_id = result['data']['orderId']
                    self.logger.info(f"   ✅ TP/SL PLACÉ!")
                    self.logger.info(f"      - Order ID: {order_id}")
                    self.logger.info(f"      - Side: {hold_side.upper()}")
                    self.logger.info(f"      - Trigger Price: ${trigger_price_rounded:.8f}")
                    self.logger.info(f"      - Size: {int(size)} contrats")
                    return {'id': order_id}
                else:
                    self.logger.warning(f"      ⚠️ Tentative {attempt + 1} échec: {result.get('msg')}")
                    time.sleep(0.5)
                    continue

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"      ⚠️ Tentative {attempt + 1} erreur: {e}")
                time.sleep(0.5)
                continue

        # Failed after all retries
        self.logger.error(f"   ❌ ÉCHEC PLACEMENT TP après {max_retries} tentatives!")
        return None

    def open_initial_hedge(self):
        """Open initial hedge: 2 positions + 2 TP + 2 LIMIT Fibo"""
        self.logger.separator("OUVERTURE HEDGE INITIAL")

        try:
            current_price = self.get_price()
            self.logger.info(f"Prix actuel: ${current_price:.8f}")

            # Calculate size (adapt based on price level)
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size = notional / current_price

            # Low-price coins need integers, high-price coins need decimals
            if current_price < 1:
                size = int(size)  # DOGE, PEPE, SHIB → integers
            else:
                size = round(size, 2)  # ETH, SOL → 2 decimals (min 0.01)
                if size < 0.01:
                    size = 0.01  # Bitget minimum

            self.logger.info(f"Size calculée: {size} contrats (${notional} notional)")

            # 1. Open LONG MARKET
            self.logger.info("\n[1/6] Ouverture LONG MARKET...")
            self.logger.debug(f"API [create_order] LONG MARKET: {self.PAIR}, amount={size}")
            long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='buy',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.logger.info(f"   ✅ LONG ouvert: {long_order['id']}")
            self.logger.debug(f"   Détails: {long_order}")

            time.sleep(0.5)

            # 2. Open SHORT MARKET
            self.logger.info("\n[2/6] Ouverture SHORT MARKET...")
            self.logger.debug(f"API [create_order] SHORT MARKET: {self.PAIR}, amount={size}")
            short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='sell',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.logger.info(f"   ✅ SHORT ouvert: {short_order['id']}")
            self.logger.debug(f"   Détails: {short_order}")

            # Wait for positions to settle
            self.logger.info("\n⏳ Attente 5s puis récupération positions...")
            time.sleep(5)

            # Get real positions
            real_pos = self.get_real_positions()
            if not real_pos['long'] or not real_pos['short']:
                self.logger.error("❌ Positions pas trouvées après ouverture!")
                self.snapshot_state("POSITIONS MANQUANTES")
                return False

            # Update position tracking
            self.position.long_open = True
            self.position.short_open = True
            self.position.entry_price_long = real_pos['long']['entry_price']
            self.position.entry_price_short = real_pos['short']['entry_price']
            self.position.long_size_previous = real_pos['long']['size']
            self.position.short_size_previous = real_pos['short']['size']
            self.position.long_fib_level = 0
            self.position.short_fib_level = 0

            self.logger.info(f"   ✅ Position tracking mis à jour")
            self.logger.info(f"      LONG: Entry=${real_pos['long']['entry_price']:.8f}, Size={real_pos['long']['size']:.2f}")
            self.logger.info(f"      SHORT: Entry=${real_pos['short']['entry_price']:.8f}, Size={real_pos['short']['size']:.2f}")

            # 3. Place TP LONG (using Bitget TP/SL API)
            self.logger.info("\n[3/6] Placement TP LONG...")
            tp_long_price = self.position.entry_price_long * (1 + self.TP_PERCENT / 100)
            self.logger.info(f"   Calcul TP: Entry=${self.position.entry_price_long:.8f} * (1 + {self.TP_PERCENT}%) = ${tp_long_price:.8f}")
            time.sleep(2)
            tp_long = self.place_tpsl_order(
                trigger_price=tp_long_price,
                hold_side='long',
                size=real_pos['long']['size'],
                plan_type='profit_plan'
            )
            if tp_long and tp_long.get('id'):
                self.position.orders['tp_long'] = tp_long['id']

            # 4. Place TP SHORT (using Bitget TP/SL API)
            self.logger.info("\n[4/6] Placement TP SHORT...")
            tp_short_price = self.position.entry_price_short * (1 - self.TP_PERCENT / 100)
            self.logger.info(f"   Calcul TP: Entry=${self.position.entry_price_short:.8f} * (1 - {self.TP_PERCENT}%) = ${tp_short_price:.8f}")
            time.sleep(2)
            tp_short = self.place_tpsl_order(
                trigger_price=tp_short_price,
                hold_side='short',
                size=real_pos['short']['size'],
                plan_type='profit_plan'
            )
            if tp_short and tp_short.get('id'):
                self.position.orders['tp_short'] = tp_short['id']

            # 5. Place LIMIT BUY (Fibo Long)
            self.logger.info("\n[5/6] Placement LIMIT BUY (Fibo Long - double marge)...")
            fibo_long_price = self.position.entry_price_long * (1 - self.FIBO_LEVELS[0] / 100)
            fibo_long_price = self.round_price(fibo_long_price)
            self.logger.info(f"   Calcul: Entry=${self.position.entry_price_long:.8f} * (1 - {self.FIBO_LEVELS[0]}%) = ${fibo_long_price:.8f}")

            self.logger.debug(f"API [create_order] LIMIT BUY: price={fibo_long_price}, amount={real_pos['long']['size']}")
            fibo_long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='buy',
                amount=real_pos['long']['size'],  # SAME size (doubles when executed)
                price=self.format_price_for_api(fibo_long_price),
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.position.orders['double_long'] = fibo_long_order['id']
            self.logger.info(f"   ✅ LIMIT BUY: {fibo_long_order['id']}")
            self.logger.info(f"      - Price: ${fibo_long_price:.8f}")
            self.logger.info(f"      - Size: {real_pos['long']['size']:.2f}")

            time.sleep(0.5)

            # 6. Place LIMIT SELL (Fibo Short)
            self.logger.info("\n[6/6] Placement LIMIT SELL (Fibo Short - double marge)...")
            fibo_short_price = self.position.entry_price_short * (1 + self.FIBO_LEVELS[0] / 100)
            fibo_short_price = self.round_price(fibo_short_price)
            self.logger.info(f"   Calcul: Entry=${self.position.entry_price_short:.8f} * (1 + {self.FIBO_LEVELS[0]}%) = ${fibo_short_price:.8f}")

            self.logger.debug(f"API [create_order] LIMIT SELL: price={fibo_short_price}, amount={real_pos['short']['size']}")
            fibo_short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='sell',
                amount=real_pos['short']['size'],  # SAME size (doubles when executed)
                price=self.format_price_for_api(fibo_short_price),
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.position.orders['double_short'] = fibo_short_order['id']
            self.logger.info(f"   ✅ LIMIT SELL: {fibo_short_order['id']}")
            self.logger.info(f"      - Price: ${fibo_short_price:.8f}")
            self.logger.info(f"      - Size: {real_pos['short']['size']:.2f}")

            # Summary
            self.logger.separator("HEDGE INITIAL OUVERT")
            self.logger.info(f"Positions: LONG {real_pos['long']['size']:.0f} + SHORT {real_pos['short']['size']:.0f}")
            self.logger.info(f"Ordres TP: 2")
            self.logger.info(f"Ordres LIMIT Fibo: 2 (doublent la marge)")
            self.logger.info(f"Total: 2 positions + 4 ordres")

            self.snapshot_state("POST-HEDGE OPENING")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur ouverture hedge: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def round_price(self, price):
        """Round price based on current price level"""
        if price >= 100:
            return round(price, 2)  # ETH
        elif price >= 1:
            return round(price, 4)
        elif price >= 0.0001:
            return round(price, 5)  # DOGE
        elif price >= 0.00001:
            return round(price, 8)  # SHIB
        else:
            return round(price, 8)  # PEPE (very low price)

    def format_price_for_api(self, price):
        """Format price as string for API (avoids scientific notation for small prices)"""
        if price >= 100:
            decimal_places = 2
        elif price >= 1:
            decimal_places = 4
        elif price >= 0.0001:
            decimal_places = 5
        elif price >= 0.00001:
            decimal_places = 8
        else:
            decimal_places = 8

        # Return formatted string without scientific notation
        return f"{price:.{decimal_places}f}"

    def check_positions(self):
        """Check positions status - simple version"""
        try:
            real_pos = self.get_real_positions()

            # Detect TP hit (position disappeared)
            if self.position.long_open and not real_pos.get('long'):
                self.logger.info("🎯 TP LONG HIT! Position fermée")
                self.position.long_open = False
                self.snapshot_state("TP LONG HIT")
                return 'tp_long'

            if self.position.short_open and not real_pos.get('short'):
                self.logger.info("🎯 TP SHORT HIT! Position fermée")
                self.position.short_open = False
                self.snapshot_state("TP SHORT HIT")
                return 'tp_short'

            # Detect Fibo hit (position size doubled)
            if real_pos.get('long'):
                current_size = real_pos['long']['size']
                if current_size > self.position.long_size_previous * 1.5:
                    self.logger.info(f"📈 FIBO LONG HIT! Size: {self.position.long_size_previous} → {current_size}")
                    self.position.long_size_previous = current_size
                    self.position.long_fib_level += 1
                    self.snapshot_state(f"FIBO LONG HIT - LEVEL {self.position.long_fib_level}")
                    return 'fibo_long'

            if real_pos.get('short'):
                current_size = real_pos['short']['size']
                if current_size > self.position.short_size_previous * 1.5:
                    self.logger.info(f"📉 FIBO SHORT HIT! Size: {self.position.short_size_previous} → {current_size}")
                    self.position.short_size_previous = current_size
                    self.position.short_fib_level += 1
                    self.snapshot_state(f"FIBO SHORT HIT - LEVEL {self.position.short_fib_level}")
                    return 'fibo_short'

            return None

        except Exception as e:
            self.logger.error(f"❌ Erreur check_positions: {e}")
            return None

    def handle_tp_long(self):
        """Handle TP Long hit - Reopen hedge"""
        self.logger.separator("HANDLER TP LONG")
        self.logger.info("🔄 Réouverture hedge après TP LONG...")

        # Full cleanup of ALL orders
        self.full_cleanup_orders()

        time.sleep(2)

        # Reopen initial hedge
        return self.open_initial_hedge()

    def handle_tp_short(self):
        """Handle TP Short hit - Reopen hedge"""
        self.logger.separator("HANDLER TP SHORT")
        self.logger.info("🔄 Réouverture hedge après TP SHORT...")

        # Cancel remaining orders
        try:
            if self.position.orders['tp_long']:
                self.logger.debug(f"Annulation TP LONG: {self.position.orders['tp_long']}")
                self.exchange.cancel_order(self.position.orders['tp_long'], self.PAIR)
            if self.position.orders['double_long']:
                self.logger.debug(f"Annulation DOUBLE LONG: {self.position.orders['double_long']}")
                self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
            if self.position.orders['double_short']:
                self.logger.debug(f"Annulation DOUBLE SHORT: {self.position.orders['double_short']}")
                self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
        except Exception as e:
            self.logger.warning(f"⚠️  Erreur annulation ordres: {e}")

        time.sleep(2)

        # Reopen initial hedge
        return self.open_initial_hedge()

    def handle_fibo_long(self):
        """Handle Fibo Long hit - Update TP and place new LIMIT order"""
        self.logger.separator("HANDLER FIBO LONG")
        self.logger.info(f"📈 Traitement Fibo LONG (niveau {self.position.long_fib_level})...")

        try:
            real_pos = self.get_real_positions()
            pos = real_pos.get('long')

            if not pos:
                self.logger.error(f"❌ Position LONG pas trouvée!")
                return False

            current_size = pos['size']
            current_entry = pos['entry_price']

            # 1. Cancel old TP LONG
            tp_key = 'tp_long'
            old_tp_id = self.position.orders[tp_key]
            if old_tp_id:
                try:
                    self.logger.debug(f"Annulation TP LONG: {old_tp_id}")
                    self.cancel_all_tpsl_orders()
                    time.sleep(0.5)
                except:
                    pass

            # 2. Place new TP based on current entry price
            tp_price = current_entry * (1 + self.TP_PERCENT / 100)
            self.logger.info(f"   🎯 Nouveau TP LONG: ${tp_price:.8f}")

            tp_id = self.place_tpsl_order(
                trigger_price=tp_price,
                hold_side='long',
                size=current_size,
                plan_type='profit_plan'
            )

            if tp_id and tp_id.get('id'):
                self.position.orders[tp_key] = tp_id['id']

            # 3. Cancel old LIMIT order
            fibo_key = 'double_long'
            old_fibo_id = self.position.orders[fibo_key]
            if old_fibo_id:
                try:
                    self.exchange.cancel_order(old_fibo_id, self.PAIR)
                    time.sleep(0.5)
                except:
                    pass

            # 4. Place new LIMIT order (next Fibo level)
            fib_level_idx = self.position.long_fib_level

            if fib_level_idx < len(self.FIBO_LEVELS):
                # Use CURRENT market price, not entry!
                current_market_price = self.get_price()
                fibo_level = self.FIBO_LEVELS[fib_level_idx]

                fibo_price = current_market_price * (1 - fibo_level / 100)
                fibo_price = self.round_price(fibo_price)

                self.logger.info(f"   📊 Nouveau LIMIT BUY @ ${fibo_price:.8f} (Niveau {fib_level_idx + 1})")

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='buy',
                    amount=current_size,
                    price=self.format_price_for_api(fibo_price),
                    params={'tradeSide': 'open', 'holdSide': 'long'}
                )

                if fibo_order:
                    self.position.orders[fibo_key] = fibo_order['id']
            else:
                self.logger.warning(f"   ⚠️  Max Fibo level atteint ({len(self.FIBO_LEVELS)}), pas de nouvel ordre")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur handle_fibo_long: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def handle_fibo_short(self):
        """Handle Fibo Short hit - Update TP and place new LIMIT order"""
        self.logger.separator("HANDLER FIBO SHORT")
        self.logger.info(f"📉 Traitement Fibo SHORT (niveau {self.position.short_fib_level})...")

        try:
            real_pos = self.get_real_positions()
            pos = real_pos.get('short')

            if not pos:
                self.logger.error(f"❌ Position SHORT pas trouvée!")
                return False

            current_size = pos['size']
            current_entry = pos['entry_price']

            # 1. Cancel old TP SHORT
            tp_key = 'tp_short'
            old_tp_id = self.position.orders[tp_key]
            if old_tp_id:
                try:
                    self.logger.debug(f"Annulation TP SHORT: {old_tp_id}")
                    self.cancel_all_tpsl_orders()
                    time.sleep(0.5)
                except:
                    pass

            # 2. Place new TP based on current entry price
            tp_price = current_entry * (1 - self.TP_PERCENT / 100)
            self.logger.info(f"   🎯 Nouveau TP SHORT: ${tp_price:.8f}")

            tp_id = self.place_tpsl_order(
                trigger_price=tp_price,
                hold_side='short',
                size=current_size,
                plan_type='profit_plan'
            )

            if tp_id and tp_id.get('id'):
                self.position.orders[tp_key] = tp_id['id']

            # 3. Cancel old LIMIT order
            fibo_key = 'double_short'
            old_fibo_id = self.position.orders[fibo_key]
            if old_fibo_id:
                try:
                    self.exchange.cancel_order(old_fibo_id, self.PAIR)
                    time.sleep(0.5)
                except:
                    pass

            # 4. Place new LIMIT order (next Fibo level)
            fib_level_idx = self.position.short_fib_level

            if fib_level_idx < len(self.FIBO_LEVELS):
                # Use CURRENT market price, not entry!
                current_market_price = self.get_price()
                fibo_level = self.FIBO_LEVELS[fib_level_idx]

                fibo_price = current_market_price * (1 + fibo_level / 100)
                fibo_price = self.round_price(fibo_price)

                self.logger.info(f"   📊 Nouveau LIMIT SELL @ ${fibo_price:.8f} (Niveau {fib_level_idx + 1})")

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='sell',
                    amount=current_size,
                    price=self.format_price_for_api(fibo_price),
                    params={'tradeSide': 'open', 'holdSide': 'short'}
                )

                if fibo_order:
                    self.position.orders[fibo_key] = fibo_order['id']
            else:
                self.logger.warning(f"   ⚠️  Max Fibo level atteint ({len(self.FIBO_LEVELS)}), pas de nouvel ordre")

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur handle_fibo_short: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def run(self):
        """Main loop"""
        try:
            # Initial cleanup
            if not self.cleanup_all():
                self.logger.error("❌ CLEANUP ÉCHEC - ARRÊT")
                return

            time.sleep(2)

            # Open hedge
            if not self.open_initial_hedge():
                self.logger.error("❌ Échec ouverture hedge")
                return

            self.logger.separator("MONITORING PRINCIPAL")
            iteration = 0

            while True:
                iteration += 1

                # Regular state snapshot every 60 iterations (~60 seconds)
                if iteration % 60 == 0:
                    self.snapshot_state(f"PERIODIC SNAPSHOT #{iteration}")

                # Check for events
                event = self.check_positions()

                if event:
                    if event == 'tp_long':
                        self.handle_tp_long()
                    elif event == 'tp_short':
                        self.handle_tp_short()
                    elif event == 'fibo_long':
                        self.handle_fibo_long()
                    elif event == 'fibo_short':
                        self.handle_fibo_short()

                time.sleep(1)

        except KeyboardInterrupt:
            self.logger.separator("BOT ARRÊTÉ")
            self.logger.info("⏹️  Arrêt demandé")
            self.snapshot_state("FINAL STATE")
            self.cleanup_all()
        except Exception as e:
            self.logger.error(f"❌ Erreur fatale: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.snapshot_state("ERROR STATE")


def main():
    parser = argparse.ArgumentParser(description='Bitget Hedge Bot V4.1 - Debug')
    parser.add_argument('--pair', required=True, help='Paire à trader (ex: DOGE/USDT:USDT)')
    parser.add_argument('--api-key-id', type=int, default=1, choices=[1, 2],
                        help='API Key ID (1 ou 2)')

    args = parser.parse_args()

    bot = BitgetHedgeBotV4Debug(pair=args.pair, api_key_id=args.api_key_id)
    bot.run()


if __name__ == '__main__':
    main()
