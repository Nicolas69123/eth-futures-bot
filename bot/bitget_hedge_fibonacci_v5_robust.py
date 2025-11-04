#!/usr/bin/env python3
"""
🤖 Bitget Hedge Fibonacci Bot V5 - ROBUSTESSE MAXIMALE

Améliorations V5:
✅ Vérification APRÈS chaque action (ordres, positions)
✅ Calcul prix basé sur MARCHÉ ACTUEL (pas entry ancien)
✅ Retry intelligent avec ajustement prix
✅ Self-healing agressif (check 5s)
✅ Détection ordres "stale" (trop loin du prix)
✅ État machine clair (IDLE/OPENING/MONITORING/TP_HIT/REOPENING)
✅ Logs ultra-détaillés pour debug

Stratégie:
- TP: 0.8% (plus facile à atteindre)
- Fibo niveau 1: 0.5% (moins fréquent, plus sûr)
- Max 3 doublements (évite explosion marge)
- Stop auto si PnL < -$100
- Marge initiale: 5 USDT
- Leverage: 50x

Usage:
    python bitget_hedge_fibonacci_v5_robust.py --pair DOGE/USDT:USDT
"""

import ccxt
import time
import os
import argparse
import requests
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class BotState(Enum):
    """Bot state machine"""
    IDLE = "idle"
    OPENING = "opening"
    MONITORING = "monitoring"
    TP_HIT = "tp_hit"
    REOPENING = "reopening"
    ERROR = "error"


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

        # Order IDs with timestamps
        self.orders = {
            'tp_long': {'id': None, 'placed_at': 0},
            'tp_short': {'id': None, 'placed_at': 0},
            'fibo_long': {'id': None, 'placed_at': 0, 'price': 0},
            'fibo_short': {'id': None, 'placed_at': 0, 'price': 0}
        }


class BitgetHedgeBotV5:
    """Ultra-robust single-pair bot with verification at every step"""

    def __init__(self, pair, api_key_id=1):
        self.pair_name = pair.split('/')[0]
        self.state = BotState.IDLE

        print("=" * 80)
        print(f"🤖 BOT V5 ROBUST - {self.pair_name} (API Key {api_key_id})")
        print("=" * 80)

        # Load API credentials
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

        print(f"✅ API Key {api_key_id} loaded")

        # Telegram credentials
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if self.telegram_token and self.telegram_chat_id:
            print(f"✅ Telegram configuré")
        else:
            print(f"⚠️  Telegram non configuré")

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
        self.INITIAL_MARGIN = 5  # $5 per position
        self.LEVERAGE = 50

        # PRODUCTION PARAMETERS (plus conservateurs)
        self.TP_PERCENT = 0.8  # 0.8% TP (plus facile à atteindre)
        self.FIBO_LEVELS = [0.5, 1.0, 1.5]  # Max 3 doublements
        self.MAX_FIBO_LEVEL = len(self.FIBO_LEVELS) - 1

        # Safety limits
        self.MAX_LOSS = -100  # Stop si < -$100
        self.STALE_ORDER_THRESHOLD = 60  # Ordre "stale" après 60s sans exec

        # Position tracking
        self.position = Position(self.PAIR)

        # Handler lock
        self.handler_running = False

        print(f"Paire: {self.PAIR}")
        print(f"TP: {self.TP_PERCENT}%")
        print(f"Fibo levels: {self.FIBO_LEVELS}")
        print(f"Max doublements: {self.MAX_FIBO_LEVEL}")
        print(f"Marge: ${self.INITIAL_MARGIN}")
        print(f"Leverage: {self.LEVERAGE}x")
        print(f"Max Loss: ${self.MAX_LOSS}")
        print("=" * 80)

    def log(self, message, level="INFO"):
        """Enhanced logging with state"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        state_emoji = {
            BotState.IDLE: "⚪",
            BotState.OPENING: "🟡",
            BotState.MONITORING: "🟢",
            BotState.TP_HIT: "🔵",
            BotState.REOPENING: "🟠",
            BotState.ERROR: "🔴"
        }
        emoji = state_emoji.get(self.state, "⚪")
        print(f"[{timestamp}] {emoji} [{self.pair_name}] {message}")

    def send_telegram(self, message):
        """Send Telegram notification"""
        if not self.telegram_token or not self.telegram_chat_id:
            return False

        full_message = f"[{self.pair_name}] {message}"
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": full_message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except:
            return False

    def get_price(self):
        """Get current market price"""
        ticker = self.exchange.fetch_ticker(self.PAIR)
        return float(ticker['last'])

    def round_price(self, price):
        """Round price based on current price level"""
        if price >= 100:
            return round(price, 2)  # ETH, SOL
        elif price >= 1:
            return round(price, 4)
        elif price >= 0.0001:
            return round(price, 5)  # DOGE
        elif price >= 0.00001:
            return round(price, 8)  # SHIB
        else:
            return round(price, 8)  # PEPE

    def calculate_size(self, price):
        """Calculate size based on price level"""
        notional = self.INITIAL_MARGIN * self.LEVERAGE
        size = notional / price

        if price < 1:
            return int(size)  # DOGE, PEPE → integers
        else:
            size = round(size, 2)  # ETH, SOL → 2 decimals
            return max(size, 0.01)  # Bitget minimum

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
                    'pnl': float(pos.get('unrealizedPnl', 0)),
                    'leverage': float(pos.get('leverage', 0))
                }

        return result

    def verify_position_exists(self, side, expected_size=None, max_retries=5):
        """
        CRITICAL: Verify position exists after opening
        Returns: position data or None
        """
        for attempt in range(max_retries):
            time.sleep(1 + attempt)  # Progressive wait

            real_pos = self.get_real_positions()
            pos = real_pos.get(side)

            if pos:
                if expected_size:
                    actual_size = pos['size']
                    # Allow 1% tolerance
                    if abs(actual_size - expected_size) / expected_size < 0.01:
                        self.log(f"   ✅ Position {side.upper()} VERIFIED: {actual_size:.2f} @ ${pos['entry_price']:.5f}")
                        return pos
                    else:
                        self.log(f"   ⚠️  Size mismatch: expected {expected_size}, got {actual_size}")
                else:
                    self.log(f"   ✅ Position {side.upper()} exists: {pos['size']:.2f}")
                    return pos

            if attempt < max_retries - 1:
                self.log(f"   🔄 Tentative {attempt + 1}/{max_retries}: Position {side} pas encore visible...")

        self.log(f"   ❌ Position {side.upper()} NOT FOUND après {max_retries} tentatives!")
        return None

    def verify_order_exists(self, order_id, order_type="LIMIT", max_retries=3):
        """
        CRITICAL: Verify order exists after placement
        Returns: True if exists, False otherwise
        """
        for attempt in range(max_retries):
            time.sleep(0.5)

            try:
                orders = self.exchange.fetch_open_orders(self.PAIR)
                if any(o['id'] == order_id for o in orders):
                    self.log(f"   ✅ Ordre {order_type} VERIFIED: {order_id[:12]}...")
                    return True
            except:
                pass

            if attempt < max_retries - 1:
                self.log(f"   🔄 Vérification ordre {order_type} tentative {attempt + 2}...")

        self.log(f"   ❌ Ordre {order_type} {order_id[:12]}... NOT FOUND!")
        return False

    def place_tpsl_order_verified(self, trigger_price, hold_side, size, plan_type='profit_plan'):
        """
        Place TP/SL with VERIFICATION
        Returns: order_id or None
        """
        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')
        bitget_plan_type = 'pos_profit' if plan_type == 'profit_plan' else 'pos_loss'

        max_retries = 5

        for attempt in range(max_retries):
            # Adjust price based on retry
            if attempt > 0:
                adjustment = 0.001 * attempt  # 0.1% per retry
                if hold_side == 'long':
                    current_price = trigger_price * (1 + adjustment)
                else:
                    current_price = trigger_price * (1 - adjustment)
                self.log(f"      Retry {attempt + 1}: Prix ajusté → ${current_price:.5f}")
            else:
                current_price = trigger_price

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
                result = self.exchange.private_mix_post_v2_mix_order_place_tpsl_order(body)

                if result.get('code') == '00000':
                    order_id = result['data']['orderId']
                    self.log(f"   ✅ TP/SL placé: {order_id}")

                    # VERIFICATION: Check via API
                    time.sleep(1)
                    if self.verify_tpsl_order_exists(hold_side, bitget_plan_type):
                        return order_id
                    else:
                        self.log(f"   ⚠️  TP/SL placé mais non trouvé, retry...")
                        continue
                else:
                    self.log(f"   ⚠️  Tentative {attempt + 1}: {result.get('msg')}")
                    time.sleep(0.5)
                    continue

            except Exception as e:
                error_msg = str(e)
                self.log(f"   ⚠️  Tentative {attempt + 1} erreur: {e}")
                time.sleep(0.5)
                continue

        self.log(f"   ❌ ÉCHEC placement TP après {max_retries} tentatives!")
        return None

    def verify_tpsl_order_exists(self, hold_side, plan_type):
        """Verify TP/SL order exists via Bitget API"""
        try:
            symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')
            result = self.exchange.private_mix_get_v2_mix_order_orders_plan_pending({
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'planType': plan_type
            })

            if result.get('code') == '00000':
                orders = result.get('data', {}).get('entrustedList', [])
                for order in orders:
                    if order.get('holdSide') == hold_side:
                        return True
            return False
        except:
            return False

    def place_limit_order_verified(self, side, price, size, max_retries=3):
        """
        Place LIMIT order with VERIFICATION
        Returns: order_id or None
        """
        for attempt in range(max_retries):
            try:
                order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side=side,
                    amount=size,
                    price=price,
                    params={'tradeSide': 'open', 'holdSide': 'long' if side == 'buy' else 'short'}
                )

                order_id = order['id']
                self.log(f"   📤 LIMIT {side.upper()} placé: {order_id[:12]}...")

                # VERIFICATION
                if self.verify_order_exists(order_id, f"LIMIT {side.upper()}"):
                    return order_id
                else:
                    self.log(f"   ⚠️  Ordre placé mais non trouvé, retry...")
                    continue

            except Exception as e:
                self.log(f"   ❌ Erreur placement LIMIT: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return None

        return None

    def flash_close_position(self, side):
        """
        FLASH CLOSE: Force close position using Bitget special endpoint
        More reliable than regular market orders
        """
        symbol_bitget = self.PAIR.replace('/USDT:USDT', 'USDT')

        try:
            result = self.exchange.private_mix_post_v2_mix_order_close_positions({
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'holdSide': side
            })

            if result.get('code') == '00000':
                self.log(f"     ⚡ Flash close {side.upper()} SUCCESS")
                return True
            else:
                error_msg = result.get('msg', 'Unknown error')
                if '22002' in str(result):
                    self.log(f"     ⚠️  Position {side} déjà fermée (22002)")
                    return True  # Already closed = success
                else:
                    self.log(f"     ❌ Flash close {side} failed: {error_msg}")
                    return False

        except Exception as e:
            error_str = str(e)
            if '22002' in error_str:
                self.log(f"     ⚠️  Position {side} déjà fermée (22002)")
                return True
            else:
                self.log(f"     ❌ Exception flash close {side}: {e}")
                return False

    def cleanup_all(self):
        """Clean all positions and orders - WITH FLASH CLOSE"""
        self.log("🧹 Cleanup avec FLASH CLOSE...")

        max_retries = 3

        for attempt in range(max_retries):
            if attempt > 0:
                self.log(f"🔄 Tentative {attempt + 1}/{max_retries}...")

            try:
                # 1. Cancel all LIMIT orders
                orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                if orders:
                    self.log(f"  📝 {len(orders)} ordres LIMIT à annuler...")
                    for order in orders:
                        self.exchange.cancel_order(order['id'], self.PAIR)
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
                        self.log(f"  🔴 Flash closing {side.upper()}: {size:.0f} contrats")

                        if self.flash_close_position(side):
                            closed_count += 1

                        time.sleep(1)

                if closed_count > 0:
                    self.log(f"  ⚡ {closed_count} positions flash closed")

                # 4. VERIFICATION FINALE
                time.sleep(2)
                final_orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                final_positions = self.exchange.fetch_positions(symbols=[self.PAIR])
                final_pos_count = sum(1 for p in final_positions if float(p.get('contracts', 0)) > 0)

                if len(final_orders) == 0 and final_pos_count == 0:
                    self.log("✅ Cleanup VÉRIFIÉ - Compte clean!")
                    return True
                else:
                    self.log(f"⚠️  Il reste: {len(final_orders)} ordres, {final_pos_count} positions")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue

            except Exception as e:
                self.log(f"❌ Erreur cleanup: {e}")
                if attempt == max_retries - 1:
                    return False

        self.log("⚠️ Cleanup incomplet après 3 tentatives")
        return False

    def cancel_all_tpsl_orders(self):
        """Cancel ALL TP/SL orders for this pair"""
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
            self.log(f"  🗑️  {cancelled_count} ordres TP/SL annulés")

        return cancelled_count

    def open_initial_hedge(self):
        """
        Open initial hedge with VERIFICATION at every step
        Returns: True if success, False otherwise
        """
        self.state = BotState.OPENING
        self.log("🚀 Ouverture Hedge Initial avec vérifications...")

        try:
            current_price = self.get_price()
            self.log(f"Prix actuel: ${current_price:.5f}")

            size = self.calculate_size(current_price)
            self.log(f"Size calculée: {size} contrats")

            # ============================================================
            # STEP 1/6: Open LONG MARKET
            # ============================================================
            self.log("\n[1/6] Ouverture LONG MARKET...")
            long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='buy',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.log(f"   📤 LONG ordre envoyé: {long_order['id']}")

            # VERIFY LONG position
            long_pos = self.verify_position_exists('long', expected_size=size)
            if not long_pos:
                self.log("❌ LONG position pas trouvée - ARRÊT")
                return False

            self.position.long_open = True
            self.position.entry_price_long = long_pos['entry_price']
            self.position.long_size_previous = long_pos['size']

            time.sleep(2)

            # ============================================================
            # STEP 2/6: Open SHORT MARKET
            # ============================================================
            self.log("\n[2/6] Ouverture SHORT MARKET...")
            short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='sell',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.log(f"   📤 SHORT ordre envoyé: {short_order['id']}")

            # VERIFY SHORT position
            short_pos = self.verify_position_exists('short', expected_size=size)
            if not short_pos:
                self.log("❌ SHORT position pas trouvée - ARRÊT")
                return False

            self.position.short_open = True
            self.position.entry_price_short = short_pos['entry_price']
            self.position.short_size_previous = short_pos['size']

            time.sleep(2)

            # ============================================================
            # STEP 3/6: Place TP LONG
            # ============================================================
            self.log("\n[3/6] Placement TP LONG...")
            tp_long_price = self.position.entry_price_long * (1 + self.TP_PERCENT / 100)
            self.log(f"   🎯 TP LONG: ${tp_long_price:.5f} (+{self.TP_PERCENT}%)")

            tp_long_id = self.place_tpsl_order_verified(
                trigger_price=tp_long_price,
                hold_side='long',
                size=long_pos['size'],
                plan_type='profit_plan'
            )

            if tp_long_id:
                self.position.orders['tp_long'] = {'id': tp_long_id, 'placed_at': time.time()}
            else:
                self.log("⚠️  TP LONG pas placé, continuons quand même...")

            time.sleep(1)

            # ============================================================
            # STEP 4/6: Place TP SHORT
            # ============================================================
            self.log("\n[4/6] Placement TP SHORT...")
            tp_short_price = self.position.entry_price_short * (1 - self.TP_PERCENT / 100)
            self.log(f"   🎯 TP SHORT: ${tp_short_price:.5f} (-{self.TP_PERCENT}%)")

            tp_short_id = self.place_tpsl_order_verified(
                trigger_price=tp_short_price,
                hold_side='short',
                size=short_pos['size'],
                plan_type='profit_plan'
            )

            if tp_short_id:
                self.position.orders['tp_short'] = {'id': tp_short_id, 'placed_at': time.time()}
            else:
                self.log("⚠️  TP SHORT pas placé, continuons quand même...")

            time.sleep(1)

            # ============================================================
            # STEP 5/6: Place LIMIT BUY (Fibo LONG)
            # ============================================================
            self.log("\n[5/6] Placement LIMIT BUY (Fibo Long)...")

            # CRITICAL: Use CURRENT market price, not entry!
            current_market_price = self.get_price()
            fibo_long_price = current_market_price * (1 - self.FIBO_LEVELS[0] / 100)
            fibo_long_price = self.round_price(fibo_long_price)

            self.log(f"   📊 Marché: ${current_market_price:.5f} → Fibo: ${fibo_long_price:.5f} (-{self.FIBO_LEVELS[0]}%)")

            fibo_long_id = self.place_limit_order_verified(
                side='buy',
                price=fibo_long_price,
                size=long_pos['size']
            )

            if fibo_long_id:
                self.position.orders['fibo_long'] = {
                    'id': fibo_long_id,
                    'placed_at': time.time(),
                    'price': fibo_long_price
                }
            else:
                self.log("⚠️  LIMIT BUY pas placé, continuons quand même...")

            time.sleep(1)

            # ============================================================
            # STEP 6/6: Place LIMIT SELL (Fibo SHORT)
            # ============================================================
            self.log("\n[6/6] Placement LIMIT SELL (Fibo Short)...")

            # CRITICAL: Use CURRENT market price, not entry!
            current_market_price = self.get_price()
            fibo_short_price = current_market_price * (1 + self.FIBO_LEVELS[0] / 100)
            fibo_short_price = self.round_price(fibo_short_price)

            self.log(f"   📊 Marché: ${current_market_price:.5f} → Fibo: ${fibo_short_price:.5f} (+{self.FIBO_LEVELS[0]}%)")

            fibo_short_id = self.place_limit_order_verified(
                side='sell',
                price=fibo_short_price,
                size=short_pos['size']
            )

            if fibo_short_id:
                self.position.orders['fibo_short'] = {
                    'id': fibo_short_id,
                    'placed_at': time.time(),
                    'price': fibo_short_price
                }
            else:
                self.log("⚠️  LIMIT SELL pas placé, continuons quand même...")

            # ============================================================
            # SUMMARY
            # ============================================================
            self.log("\n" + "=" * 80)
            self.log("✅ HEDGE INITIAL COMPLET (avec vérifications)!")
            self.log("=" * 80)
            self.log(f"Positions: LONG {long_pos['size']:.2f} + SHORT {short_pos['size']:.2f}")
            self.log(f"TP: {self.TP_PERCENT}% | Fibo: {self.FIBO_LEVELS[0]}%")
            self.log("=" * 80)

            self.send_telegram(
                f"✅ <b>HEDGE OUVERT</b>\n"
                f"📊 LONG {long_pos['size']:.0f} + SHORT {short_pos['size']:.0f}\n"
                f"🎯 TP: {self.TP_PERCENT}% | Fibo: {self.FIBO_LEVELS[0]}%"
            )

            self.state = BotState.MONITORING
            return True

        except Exception as e:
            self.log(f"❌ Erreur ouverture hedge: {e}")
            import traceback
            traceback.print_exc()
            self.state = BotState.ERROR
            return False

    def check_and_replace_stale_orders(self):
        """
        Check if LIMIT orders are "stale" (too far from current price)
        Replace them if needed
        """
        if self.handler_running:
            return

        try:
            current_price = self.get_price()
            current_time = time.time()

            # Check Fibo LONG order
            fibo_long = self.position.orders.get('fibo_long', {})
            if fibo_long.get('id'):
                age = current_time - fibo_long.get('placed_at', 0)
                order_price = fibo_long.get('price', 0)

                if age > self.STALE_ORDER_THRESHOLD and order_price > 0:
                    distance_pct = abs(current_price - order_price) / current_price * 100

                    # If order is >2% away from current price, it's stale
                    if distance_pct > 2.0:
                        self.log(f"🔄 Ordre LONG stale ({distance_pct:.1f}% du prix), replacement...")
                        self.replace_fibo_order('long')

            # Check Fibo SHORT order
            fibo_short = self.position.orders.get('fibo_short', {})
            if fibo_short.get('id'):
                age = current_time - fibo_short.get('placed_at', 0)
                order_price = fibo_short.get('price', 0)

                if age > self.STALE_ORDER_THRESHOLD and order_price > 0:
                    distance_pct = abs(current_price - order_price) / current_price * 100

                    if distance_pct > 2.0:
                        self.log(f"🔄 Ordre SHORT stale ({distance_pct:.1f}% du prix), replacement...")
                        self.replace_fibo_order('short')

        except Exception as e:
            self.log(f"❌ Erreur check stale orders: {e}")

    def replace_fibo_order(self, side):
        """Replace single Fibo order (long or short)"""
        try:
            real_pos = self.get_real_positions()

            if side == 'long':
                if not real_pos.get('long'):
                    return

                # Cancel old order
                old_id = self.position.orders['fibo_long'].get('id')
                if old_id:
                    try:
                        self.exchange.cancel_order(old_id, self.PAIR)
                        time.sleep(0.5)
                    except:
                        pass

                # Place new order based on CURRENT market price
                current_price = self.get_price()
                fibo_level = self.FIBO_LEVELS[min(self.position.long_fib_level, self.MAX_FIBO_LEVEL)]
                fibo_price = current_price * (1 - fibo_level / 100)
                fibo_price = self.round_price(fibo_price)

                new_id = self.place_limit_order_verified(
                    side='buy',
                    price=fibo_price,
                    size=real_pos['long']['size']
                )

                if new_id:
                    self.position.orders['fibo_long'] = {
                        'id': new_id,
                        'placed_at': time.time(),
                        'price': fibo_price
                    }
                    self.log(f"  ✅ LIMIT BUY replacé @ ${fibo_price:.5f}")

            elif side == 'short':
                if not real_pos.get('short'):
                    return

                # Cancel old order
                old_id = self.position.orders['fibo_short'].get('id')
                if old_id:
                    try:
                        self.exchange.cancel_order(old_id, self.PAIR)
                        time.sleep(0.5)
                    except:
                        pass

                # Place new order based on CURRENT market price
                current_price = self.get_price()
                fibo_level = self.FIBO_LEVELS[min(self.position.short_fib_level, self.MAX_FIBO_LEVEL)]
                fibo_price = current_price * (1 + fibo_level / 100)
                fibo_price = self.round_price(fibo_price)

                new_id = self.place_limit_order_verified(
                    side='sell',
                    price=fibo_price,
                    size=real_pos['short']['size']
                )

                if new_id:
                    self.position.orders['fibo_short'] = {
                        'id': new_id,
                        'placed_at': time.time(),
                        'price': fibo_price
                    }
                    self.log(f"  ✅ LIMIT SELL replacé @ ${fibo_price:.5f}")

        except Exception as e:
            self.log(f"❌ Erreur replace fibo order: {e}")

    def check_positions(self):
        """
        Check for events (TP hit, Fibo hit)
        Returns: event type or None
        """
        try:
            real_pos = self.get_real_positions()

            # Detect TP hit (position disappeared)
            if self.position.long_open and not real_pos.get('long'):
                self.log("🎯 TP LONG HIT! Position fermée")
                self.position.long_open = False
                self.send_telegram("🎯 <b>TP LONG TOUCHÉ!</b>\n💰 Position fermée avec profit")
                return 'tp_long'

            if self.position.short_open and not real_pos.get('short'):
                self.log("🎯 TP SHORT HIT! Position fermée")
                self.position.short_open = False
                self.send_telegram("🎯 <b>TP SHORT TOUCHÉ!</b>\n💰 Position fermée avec profit")
                return 'tp_short'

            # Detect Fibo hit (position size increased significantly)
            if real_pos.get('long'):
                current_size = real_pos['long']['size']
                if current_size > self.position.long_size_previous * 1.5:
                    self.log(f"📈 FIBO LONG HIT! Size: {self.position.long_size_previous:.0f} → {current_size:.0f}")
                    self.send_telegram(f"📈 <b>FIBO LONG TOUCHÉ!</b>\n📊 Niveau {self.position.long_fib_level + 1}")
                    self.position.long_size_previous = current_size
                    self.position.long_fib_level += 1
                    return 'fibo_long'

            if real_pos.get('short'):
                current_size = real_pos['short']['size']
                if current_size > self.position.short_size_previous * 1.5:
                    self.log(f"📉 FIBO SHORT HIT! Size: {self.position.short_size_previous:.0f} → {current_size:.0f}")
                    self.send_telegram(f"📉 <b>FIBO SHORT TOUCHÉ!</b>\n📊 Niveau {self.position.short_fib_level + 1}")
                    self.position.short_size_previous = current_size
                    self.position.short_fib_level += 1
                    return 'fibo_short'

            return None

        except Exception as e:
            self.log(f"❌ Erreur check_positions: {e}")
            return None

    def handle_tp_hit(self, side):
        """
        Handle TP hit - Full cleanup and reopen hedge
        side: 'long' or 'short'
        """
        self.state = BotState.REOPENING
        self.log(f"🔄 Réouverture hedge après TP {side.upper()}...")

        # Full cleanup
        self.cleanup_all()
        time.sleep(2)

        # Reopen hedge
        success = self.open_initial_hedge()

        if not success:
            self.log("❌ Échec réouverture hedge!")
            self.send_telegram("❌ <b>ERREUR RÉOUVERTURE</b>")
            self.state = BotState.ERROR

        return success

    def handle_fibo_hit(self, side):
        """
        Handle Fibo hit - Update TP and place new LIMIT order
        side: 'long' or 'short'
        """
        self.log(f"📊 Traitement Fibo {side.upper()}...")

        try:
            real_pos = self.get_real_positions()
            pos = real_pos.get(side)

            if not pos:
                self.log(f"❌ Position {side} pas trouvée!")
                return False

            current_size = pos['size']
            current_entry = pos['entry_price']

            # 1. Cancel old TP/SL
            tp_key = f'tp_{side}'
            old_tp_id = self.position.orders[tp_key].get('id')
            if old_tp_id:
                try:
                    self.cancel_all_tpsl_orders()
                    time.sleep(0.5)
                except:
                    pass

            # 2. Place new TP based on current entry price
            if side == 'long':
                tp_price = current_entry * (1 + self.TP_PERCENT / 100)
            else:
                tp_price = current_entry * (1 - self.TP_PERCENT / 100)

            self.log(f"   🎯 Nouveau TP {side.upper()}: ${tp_price:.5f}")

            tp_id = self.place_tpsl_order_verified(
                trigger_price=tp_price,
                hold_side=side,
                size=current_size,
                plan_type='profit_plan'
            )

            if tp_id:
                self.position.orders[tp_key] = {'id': tp_id, 'placed_at': time.time()}

            # 3. Cancel old LIMIT order
            fibo_key = f'fibo_{side}'
            old_fibo_id = self.position.orders[fibo_key].get('id')
            if old_fibo_id:
                try:
                    self.exchange.cancel_order(old_fibo_id, self.PAIR)
                    time.sleep(0.5)
                except:
                    pass

            # 4. Place new LIMIT order (next Fibo level)
            fib_level_idx = self.position.long_fib_level if side == 'long' else self.position.short_fib_level

            if fib_level_idx <= self.MAX_FIBO_LEVEL:
                # Use CURRENT market price, not entry!
                current_market_price = self.get_price()
                fibo_level = self.FIBO_LEVELS[fib_level_idx]

                if side == 'long':
                    fibo_price = current_market_price * (1 - fibo_level / 100)
                    order_side = 'buy'
                else:
                    fibo_price = current_market_price * (1 + fibo_level / 100)
                    order_side = 'sell'

                fibo_price = self.round_price(fibo_price)

                self.log(f"   📊 Nouveau LIMIT {order_side.upper()} @ ${fibo_price:.5f} (Niveau {fib_level_idx + 1})")

                fibo_id = self.place_limit_order_verified(
                    side=order_side,
                    price=fibo_price,
                    size=current_size
                )

                if fibo_id:
                    self.position.orders[fibo_key] = {
                        'id': fibo_id,
                        'placed_at': time.time(),
                        'price': fibo_price
                    }
            else:
                self.log(f"   ⚠️  Max Fibo level atteint ({self.MAX_FIBO_LEVEL}), pas de nouvel ordre")

            return True

        except Exception as e:
            self.log(f"❌ Erreur handle_fibo_{side}: {e}")
            return False

    def check_safety_limits(self):
        """Check if we hit safety limits (max loss)"""
        try:
            real_pos = self.get_real_positions()

            if real_pos['long'] or real_pos['short']:
                long_pnl = real_pos['long']['pnl'] if real_pos['long'] else 0
                short_pnl = real_pos['short']['pnl'] if real_pos['short'] else 0
                total_pnl = long_pnl + short_pnl

                if total_pnl < self.MAX_LOSS:
                    self.log(f"🚨 SAFETY LIMIT HIT! PnL: ${total_pnl:.2f} < ${self.MAX_LOSS}")
                    self.send_telegram(f"🚨 <b>STOP LOSS AUTO!</b>\nPnL: ${total_pnl:.2f}")
                    return True

            return False

        except:
            return False

    def run(self):
        """Main loop with enhanced monitoring"""
        try:
            # Initial cleanup
            self.log("🧹 Cleanup initial obligatoire...")
            if not self.cleanup_all():
                self.log("❌ CLEANUP ÉCHEC - ARRÊT")
                return

            time.sleep(2)

            # Open hedge
            if not self.open_initial_hedge():
                self.log("❌ Échec ouverture hedge")
                return

            # Notification
            self.send_telegram("🤖 <b>BOT V5 DÉMARRÉ</b>\n✅ Monitoring ultra-robuste actif")

            self.log("\n🔄 BOUCLE DE MONITORING - 1 check/seconde")
            self.log("=" * 80)

            iteration = 0
            last_pnl_report = time.time()

            while True:
                iteration += 1

                # Safety check every 10 seconds
                if iteration % 10 == 0:
                    if self.check_safety_limits():
                        self.log("🛑 ARRÊT BOT - Safety limit atteint")
                        self.cleanup_all()
                        break

                # Check for stale orders every 30 seconds
                if iteration % 30 == 0:
                    self.check_and_replace_stale_orders()

                # Check for events
                event = self.check_positions()

                if event and not self.handler_running:
                    self.handler_running = True

                    if event in ['tp_long', 'tp_short']:
                        side = event.split('_')[1]
                        self.handle_tp_hit(side)
                    elif event in ['fibo_long', 'fibo_short']:
                        side = event.split('_')[1]
                        self.handle_fibo_hit(side)

                    self.handler_running = False

                # PnL report every 60 seconds
                if time.time() - last_pnl_report > 60:
                    real_pos = self.get_real_positions()
                    if real_pos['long'] or real_pos['short']:
                        long_pnl = real_pos['long']['pnl'] if real_pos['long'] else 0
                        short_pnl = real_pos['short']['pnl'] if real_pos['short'] else 0
                        total_pnl = long_pnl + short_pnl
                        self.log(f"💰 PnL: ${total_pnl:.2f} (L: ${long_pnl:.2f} | S: ${short_pnl:.2f})")
                    last_pnl_report = time.time()

                time.sleep(1)

        except KeyboardInterrupt:
            self.log("\n⏹️  Arrêt demandé")
            self.cleanup_all()
        except Exception as e:
            self.log(f"❌ Erreur fatale: {e}")
            import traceback
            traceback.print_exc()
            self.state = BotState.ERROR


def main():
    parser = argparse.ArgumentParser(description='Bitget Hedge Bot V5 - Ultra Robust')
    parser.add_argument('--pair', required=True, help='Paire à trader (ex: DOGE/USDT:USDT)')
    parser.add_argument('--api-key-id', type=int, default=1, choices=[1, 2],
                        help='API Key ID (1 ou 2)')

    args = parser.parse_args()

    bot = BitgetHedgeBotV5(pair=args.pair, api_key_id=args.api_key_id)
    bot.run()


if __name__ == '__main__':
    main()
