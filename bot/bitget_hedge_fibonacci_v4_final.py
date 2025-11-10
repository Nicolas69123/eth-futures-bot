#!/usr/bin/env python3
"""
🤖 Bitget Hedge Fibonacci Bot V4 - MULTI-PAIRES LOCAL

Version simplifiée pour tests locaux:
- Basé sur V2_fixed (stratégie qui marche)
- SANS Telegram (juste logs shell)
- Support multi-instances (--pair argument)
- Logs clairs et simples

Stratégie:
- TP: 0.5%
- Fibo niveau 1: 0.3%
- Marge initiale: 5 USDT
- Leverage: 50x

Usage:
    python bitget_hedge_fibonacci_v4_multipairs.py --pair DOGE/USDT:USDT
    python bitget_hedge_fibonacci_v4_multipairs.py --pair PEPE/USDT:USDT --api-key-id 2
"""

import ccxt
import time
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

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
            'double_long': None,
            'double_short': None
        }


class BitgetHedgeBotV4:
    """Multi-pairs bot - Simple version for local testing"""

    def __init__(self, pair, api_key_id=1):
        self.pair_name = pair.split('/')[0]

        print("=" * 80)
        print(f"🤖 BOT V4 - {self.pair_name} (API Key {api_key_id})")
        print("=" * 80)

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

        print(f"✅ API Key {api_key_id} loaded")

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

        # TP and Fibo levels
        self.TP_PERCENT = 0.5  # 0.5% TP
        self.FIBO_LEVELS = [0.3, 0.6, 1.0, 1.5, 2.0]  # First: 0.3%

        # Position tracking
        self.position = Position(self.PAIR)

        print(f"Paire: {self.PAIR}")
        print(f"TP: {self.TP_PERCENT}%")
        print(f"Fibo levels: {self.FIBO_LEVELS}")
        print(f"Marge: ${self.INITIAL_MARGIN}")
        print(f"Leverage: {self.LEVERAGE}x")
        print("=" * 80)

    def log(self, message):
        """Simple logging with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] [{self.pair_name}] {message}")

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
            self.log(f"  🗑️  {cancelled_count} ordres TP/SL annulés")

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
                self.log(f"\n🔄 Tentative {attempt + 1}/{max_retries}...")

            try:
                # 1. Cancel all LIMIT orders
                orders = self.exchange.fetch_open_orders(symbol=self.PAIR)
                if orders:
                    self.log(f"  📝 {len(orders)} ordres LIMIT à annuler...")
                    for order in orders:
                        try:
                            self.exchange.cancel_order(order['id'], self.PAIR)
                            self.log(f"    ✅ Ordre {order['id'][:8]}... annulé")
                        except Exception as e:
                            self.log(f"    ⚠️  Erreur annulation {order['id'][:8]}: {e}")
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
                import traceback
                self.log(traceback.format_exc())
                if attempt == max_retries - 1:
                    return False

        self.log("⚠️ Cleanup incomplet après 3 tentatives")
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
                    'pnl': float(pos.get('unrealizedPnl', 0)),
                    'leverage': float(pos.get('leverage', 0))
                }

        return result

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
                self.log(f"      Retry {attempt + 1}: Ajustement prix → ${current_price:.5f}")

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
                    return {'id': order_id}
                else:
                    self.log(f"      ⚠️ Tentative {attempt + 1} échec: {result.get('msg')}")
                    time.sleep(0.5)
                    continue

            except Exception as e:
                error_msg = str(e)
                if '40915' in error_msg or 'price please' in error_msg.lower():
                    self.log(f"      ⚠️ Tentative {attempt + 1}: Prix invalide, ajustement...")
                    time.sleep(0.5)
                    continue
                else:
                    self.log(f"      ❌ Tentative {attempt + 1} erreur: {e}")
                    time.sleep(0.5)
                    continue

        # Failed after all retries
        self.log(f"   ❌ ÉCHEC PLACEMENT TP après {max_retries} tentatives!")
        return None

    def open_initial_hedge(self):
        """Open initial hedge: 2 positions + 2 TP + 2 LIMIT Fibo"""
        self.log("🚀 Ouverture Hedge Initial...")

        try:
            current_price = self.get_price()
            self.log(f"Prix actuel: ${current_price:.5f}")

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

            self.log(f"Size calculée: {size} contrats (${notional} notional)")

            # 1. Open LONG MARKET
            self.log("\n[1/6] Ouverture LONG MARKET...")
            long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='buy',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.log(f"   ✅ LONG ouvert: {long_order['id']}")

            time.sleep(0.5)

            # 2. Open SHORT MARKET
            self.log("\n[2/6] Ouverture SHORT MARKET...")
            short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='market',
                side='sell',
                amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.log(f"   ✅ SHORT ouvert: {short_order['id']}")

            # Wait for positions to settle
            self.log("\n⏳ Attente 5s puis récupération positions...")
            time.sleep(5)

            # Get real positions
            real_pos = self.get_real_positions()
            if not real_pos['long'] or not real_pos['short']:
                self.log("❌ Positions pas trouvées après ouverture!")
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

            # 3. Place TP LONG (using Bitget TP/SL API)
            self.log("\n[3/6] Placement TP LONG...")
            tp_long_price = self.position.entry_price_long * (1 + self.TP_PERCENT / 100)
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
            self.log("\n[4/6] Placement TP SHORT...")
            tp_short_price = self.position.entry_price_short * (1 - self.TP_PERCENT / 100)
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
            self.log("\n[5/6] Placement LIMIT BUY (Fibo Long - double marge)...")
            fibo_long_price = self.position.entry_price_long * (1 - self.FIBO_LEVELS[0] / 100)
            fibo_long_price = self.round_price(fibo_long_price)

            fibo_long_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='buy',
                amount=real_pos['long']['size'],  # SAME size (doubles when executed)
                price=fibo_long_price,
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            self.position.orders['double_long'] = fibo_long_order['id']
            self.log(f"   ✅ LIMIT BUY: {fibo_long_order['id'][:16]}... - {real_pos['long']['size']:.0f} @ ${fibo_long_price:.5f}")

            time.sleep(0.5)

            # 6. Place LIMIT SELL (Fibo Short)
            self.log("\n[6/6] Placement LIMIT SELL (Fibo Short - double marge)...")
            fibo_short_price = self.position.entry_price_short * (1 + self.FIBO_LEVELS[0] / 100)
            fibo_short_price = self.round_price(fibo_short_price)

            fibo_short_order = self.exchange.create_order(
                symbol=self.PAIR,
                type='limit',
                side='sell',
                amount=real_pos['short']['size'],  # SAME size (doubles when executed)
                price=fibo_short_price,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            self.position.orders['double_short'] = fibo_short_order['id']
            self.log(f"   ✅ LIMIT SELL: {fibo_short_order['id'][:16]}... - {real_pos['short']['size']:.0f} @ ${fibo_short_price:.5f}")

            # Summary
            self.log("\n" + "=" * 80)
            self.log("✅ HEDGE INITIAL COMPLET!")
            self.log("=" * 80)
            self.log(f"Positions: LONG {real_pos['long']['size']:.0f} + SHORT {real_pos['short']['size']:.0f}")
            self.log(f"Ordres TP: 2")
            self.log(f"Ordres LIMIT Fibo: 2 (doublent la marge)")
            self.log(f"Total: 2 positions + 4 ordres")
            self.log("=" * 80)

            return True

        except Exception as e:
            self.log(f"❌ Erreur ouverture hedge: {e}")
            import traceback
            traceback.print_exc()
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
            return round(price, 8)  # SHIB - NEEDS 8 decimals !
        else:
            return round(price, 8)  # PEPE (very low price)

    def check_positions(self):
        """Check positions status - simple version"""
        try:
            real_pos = self.get_real_positions()

            # Detect TP hit (position disappeared)
            if self.position.long_open and not real_pos.get('long'):
                self.log("🎯 TP LONG HIT! Position fermée")
                self.position.long_open = False
                return 'tp_long'

            if self.position.short_open and not real_pos.get('short'):
                self.log("🎯 TP SHORT HIT! Position fermée")
                self.position.short_open = False
                return 'tp_short'

            # Detect Fibo hit (position size doubled)
            if real_pos.get('long'):
                current_size = real_pos['long']['size']
                if current_size > self.position.long_size_previous * 1.5:
                    self.log(f"📈 FIBO LONG HIT! Size: {self.position.long_size_previous} → {current_size}")
                    self.position.long_size_previous = current_size
                    self.position.long_fib_level += 1
                    return 'fibo_long'

            if real_pos.get('short'):
                current_size = real_pos['short']['size']
                if current_size > self.position.short_size_previous * 1.5:
                    self.log(f"📉 FIBO SHORT HIT! Size: {self.position.short_size_previous} → {current_size}")
                    self.position.short_size_previous = current_size
                    self.position.short_fib_level += 1
                    return 'fibo_short'

            return None

        except Exception as e:
            self.log(f"❌ Erreur check_positions: {e}")
            return None

    def handle_tp_long(self):
        """Handle TP Long hit - Reopen hedge"""
        self.log("🔄 Réouverture hedge après TP LONG...")

        # Cancel remaining orders
        try:
            if self.position.orders['tp_short']:
                self.exchange.cancel_order(self.position.orders['tp_short'], self.PAIR)
            if self.position.orders['double_long']:
                self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
            if self.position.orders['double_short']:
                self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
        except:
            pass

        time.sleep(2)

        # Reopen initial hedge
        return self.open_initial_hedge()

    def handle_tp_short(self):
        """Handle TP Short hit - Reopen hedge"""
        self.log("🔄 Réouverture hedge après TP SHORT...")

        # Cancel remaining orders
        try:
            if self.position.orders['tp_long']:
                self.exchange.cancel_order(self.position.orders['tp_long'], self.PAIR)
            if self.position.orders['double_long']:
                self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
            if self.position.orders['double_short']:
                self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
        except:
            pass

        time.sleep(2)

        # Reopen initial hedge
        return self.open_initial_hedge()

    def handle_fibo_long(self):
        """Handle Fibo Long hit - Place new LIMIT + TP"""
        self.log("📊 Traitement Fibo LONG...")

        try:
            real_pos = self.get_real_positions()
            if not real_pos.get('long'):
                return False

            current_size = real_pos['long']['size']
            current_entry = real_pos['long']['entry_price']

            # Cancel old TP LONG
            if self.position.orders['tp_long']:
                try:
                    self.exchange.cancel_order(self.position.orders['tp_long'], self.PAIR)
                except:
                    pass

            # Place new TP LONG (using Bitget TP/SL API)
            tp_price = current_entry * (1 + self.TP_PERCENT / 100)
            time.sleep(1)
            tp_long = self.place_tpsl_order(
                trigger_price=tp_price,
                hold_side='long',
                size=current_size,
                plan_type='profit_plan'
            )
            if tp_long and tp_long.get('id'):
                self.position.orders['tp_long'] = tp_long['id']

            # Cancel old LIMIT BUY before placing new one
            if self.position.orders['double_long']:
                try:
                    self.exchange.cancel_order(self.position.orders['double_long'], self.PAIR)
                    self.log(f"  🗑️  Ancien LIMIT BUY annulé")
                except:
                    pass

            # Place new LIMIT BUY (next Fibo level)
            if self.position.long_fib_level < len(self.FIBO_LEVELS):
                fibo_price = current_entry * (1 - self.FIBO_LEVELS[self.position.long_fib_level] / 100)
                fibo_price = self.round_price(fibo_price)

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='buy',
                    amount=current_size,
                    price=fibo_price,
                    params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                self.position.orders['double_long'] = fibo_order['id']
                self.log(f"  ✅ Nouveau LIMIT BUY @ ${fibo_price:.5f}")

            return True

        except Exception as e:
            self.log(f"❌ Erreur handle_fibo_long: {e}")
            return False

    def handle_fibo_short(self):
        """Handle Fibo Short hit - Place new LIMIT + TP"""
        self.log("📊 Traitement Fibo SHORT...")

        try:
            real_pos = self.get_real_positions()
            if not real_pos.get('short'):
                return False

            current_size = real_pos['short']['size']
            current_entry = real_pos['short']['entry_price']

            # Cancel old TP SHORT
            if self.position.orders['tp_short']:
                try:
                    self.exchange.cancel_order(self.position.orders['tp_short'], self.PAIR)
                except:
                    pass

            # Place new TP SHORT (using Bitget TP/SL API)
            tp_price = current_entry * (1 - self.TP_PERCENT / 100)
            time.sleep(1)
            tp_short = self.place_tpsl_order(
                trigger_price=tp_price,
                hold_side='short',
                size=current_size,
                plan_type='profit_plan'
            )
            if tp_short and tp_short.get('id'):
                self.position.orders['tp_short'] = tp_short['id']

            # Cancel old LIMIT SELL before placing new one
            if self.position.orders['double_short']:
                try:
                    self.exchange.cancel_order(self.position.orders['double_short'], self.PAIR)
                    self.log(f"  🗑️  Ancien LIMIT SELL annulé")
                except:
                    pass

            # Place new LIMIT SELL (next Fibo level)
            if self.position.short_fib_level < len(self.FIBO_LEVELS):
                fibo_price = current_entry * (1 + self.FIBO_LEVELS[self.position.short_fib_level] / 100)
                fibo_price = self.round_price(fibo_price)

                fibo_order = self.exchange.create_order(
                    symbol=self.PAIR,
                    type='limit',
                    side='sell',
                    amount=current_size,
                    price=fibo_price,
                    params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                self.position.orders['double_short'] = fibo_order['id']
                self.log(f"  ✅ Nouveau LIMIT SELL @ ${fibo_price:.5f}")

            return True

        except Exception as e:
            self.log(f"❌ Erreur handle_fibo_short: {e}")
            return False

    def run(self):
        """Main loop"""
        try:
            # Cleanup OBLIGATOIRE
            cleanup_ok = self.cleanup_all()
            if not cleanup_ok:
                self.log("❌ CLEANUP ÉCHEC - ARRÊT SÉCURITÉ")
                self.log("⚠️  Compte pas clean, impossible d'ouvrir hedge!")
                return

            time.sleep(2)

            # Open initial hedge
            if not self.open_initial_hedge():
                self.log("❌ Échec ouverture hedge initial")
                return

            self.log("\n🔄 BOUCLE DE MONITORING - 1 check/seconde")
            self.log("=" * 80)

            # Main monitoring loop
            iteration = 0
            while True:
                iteration += 1

                # Check for events (TP or Fibo hit)
                event = self.check_positions()

                if event == 'tp_long':
                    self.handle_tp_long()
                elif event == 'tp_short':
                    self.handle_tp_short()
                elif event == 'fibo_long':
                    self.handle_fibo_long()
                elif event == 'fibo_short':
                    self.handle_fibo_short()

                # Status every 60 seconds
                if iteration % 60 == 0:  # 60 * 1s = 60s
                    real_pos = self.get_real_positions()
                    if real_pos['long'] or real_pos['short']:
                        long_pnl = real_pos['long']['pnl'] if real_pos['long'] else 0
                        short_pnl = real_pos['short']['pnl'] if real_pos['short'] else 0
                        total_pnl = long_pnl + short_pnl
                        self.log(f"💰 PnL: ${total_pnl:.2f} (L: ${long_pnl:.2f} | S: ${short_pnl:.2f})")

                time.sleep(1)  # 1 check per second

        except KeyboardInterrupt:
            self.log("\n⏹️  Arrêt demandé par utilisateur")
            self.cleanup_all()
        except Exception as e:
            self.log(f"❌ Erreur fatale: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='Bitget Hedge Bot V4 - Multi-paires')
    parser.add_argument('--pair', required=True, help='Paire à trader (ex: DOGE/USDT:USDT)')
    parser.add_argument('--api-key-id', type=int, default=1, choices=[1, 2],
                        help='API Key ID (1 ou 2)')

    args = parser.parse_args()

    bot = BitgetHedgeBotV4(pair=args.pair, api_key_id=args.api_key_id)
    bot.run()


if __name__ == '__main__':
    main()
