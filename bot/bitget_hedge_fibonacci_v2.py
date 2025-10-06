"""
Bitget Hedge Fibonacci Bot V2 - Stratégie avec Ordres Limites
Place automatiquement TP et ordres de doublement, gère les annulations
"""

import ccxt
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import requests

# Charger .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class HedgePosition:
    """Gère une position hedge avec ordres limites"""

    def __init__(self, pair, initial_margin, entry_price_long, entry_price_short):
        self.pair = pair
        self.initial_margin = initial_margin
        self.entry_price_long = entry_price_long
        self.entry_price_short = entry_price_short

        # État positions
        self.long_open = True
        self.short_open = True

        # Grille Fibonacci
        self.fib_levels = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        self.current_level = 0

        # IDs des ordres actifs
        self.orders = {
            'tp_long': None,      # Take profit long
            'tp_short': None,     # Take profit short
            'double_short': None, # Doubler short
            'double_long': None   # Doubler long
        }

        # Stats
        self.profit_realized = 0
        self.adjustments_count = 0

    def get_next_trigger_pct(self):
        """Retourne le prochain niveau Fibonacci en %"""
        if self.current_level >= len(self.fib_levels):
            return None

        return sum(self.fib_levels[:self.current_level + 1])


class BitgetHedgeBotV2:
    """Bot hedge avec système d'ordres limites automatique"""

    def __init__(self):
        # Configuration API
        self.api_key = os.getenv('BITGET_API_KEY')
        self.api_secret = os.getenv('BITGET_SECRET')
        self.api_password = os.getenv('BITGET_PASSPHRASE')

        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')

        # Exchange
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

        # Paires volatiles
        self.volatile_pairs = [
            'DOGE/USDT:USDT',
            'PEPE/USDT:USDT',
            'SHIB/USDT:USDT',
            'WIF/USDT:USDT',
            'BONK/USDT:USDT',
            'FLOKI/USDT:USDT'
        ]

        self.available_pairs = self.volatile_pairs.copy()

        # Paramètres
        self.INITIAL_MARGIN = 1  # 1$ de marge
        self.LEVERAGE = 50  # Levier x50
        self.MAX_CAPITAL = 100

        # Positions actives
        self.active_positions = {}  # {pair: HedgePosition}

        # Stats
        self.total_profit = 0
        self.capital_used = 0
        self.last_status_update = time.time()

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

    def get_price(self, symbol):
        """Récupère prix actuel"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"❌ Erreur prix {symbol}: {e}")
            return None

    def get_real_positions(self, symbol):
        """Récupère positions réelles depuis API"""
        try:
            positions = self.exchange.fetch_positions(symbols=[symbol])
            result = {'long': None, 'short': None}

            for pos in positions:
                if float(pos.get('contracts', 0)) <= 0:
                    continue

                side = pos.get('side', '').lower()
                if side in ['long', 'short']:
                    result[side] = {
                        'symbol': pos['symbol'],
                        'size': float(pos['contracts']),
                        'entry_price': float(pos['entryPrice']),
                        'mark_price': float(pos['markPrice']),
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'pnl_percentage': float(pos.get('percentage', 0)),
                        'margin': float(pos.get('initialMargin', 0)),
                    }

            return result
        except Exception as e:
            print(f"❌ Erreur positions {symbol}: {e}")
            return None

    def set_leverage(self, symbol, leverage):
        """Configure le levier"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            print(f"⚙️  Levier x{leverage} configuré")
            return True
        except Exception as e:
            print(f"⚠️  Erreur levier: {e}")
            return False

    def set_position_mode(self, symbol):
        """Active mode hedge"""
        try:
            self.exchange.set_position_mode(hedged=True, symbol=symbol)
            print(f"⚙️  Mode hedge activé")
            return True
        except Exception as e:
            print(f"⚠️  Mode hedge: {e}")
            return False

    def cancel_order(self, order_id, symbol):
        """Annule un ordre (ignore si ordre n'existe plus)"""
        try:
            self.exchange.cancel_order(order_id, symbol)
            print(f"🗑️  Ordre {order_id[:8]}... annulé")
            return True
        except Exception as e:
            error_msg = str(e)
            # Ignorer si ordre n'existe pas/déjà exécuté (code 40768)
            if '40768' in error_msg or 'does not exist' in error_msg.lower():
                print(f"ℹ️  Ordre {order_id[:8]}... déjà exécuté/annulé")
                return True
            else:
                print(f"⚠️  Erreur annulation: {e}")
                return False

    def open_hedge_with_limit_orders(self, pair):
        """
        Ouvre hedge + Place immédiatement les 4 ordres limites
        """
        if self.capital_used + (self.INITIAL_MARGIN * 2) > self.MAX_CAPITAL:
            print(f"⚠️  Capital max atteint")
            return False

        print(f"\n{'='*80}")
        print(f"🎯 OUVERTURE HEDGE: {pair}")
        print(f"{'='*80}")

        # Configuration
        self.set_position_mode(pair)
        self.set_leverage(pair, self.LEVERAGE)

        price = self.get_price(pair)
        if not price:
            return False

        notional = self.INITIAL_MARGIN * self.LEVERAGE
        size = notional / price

        try:
            # 1. Ouvrir Long et Short en MARKET
            print("\n1️⃣ Ouverture positions MARKET...")

            long_order = self.exchange.create_order(
                symbol=pair, type='market', side='buy', amount=size,
                params={'tradeSide': 'open'}
            )
            print(f"✅ Long ouvert: {size:.4f}")

            short_order = self.exchange.create_order(
                symbol=pair, type='market', side='sell', amount=size,
                params={'tradeSide': 'open'}
            )
            print(f"✅ Short ouvert: {size:.4f}")

            time.sleep(2)  # Attendre exécution

            # Récupérer vraies positions
            real_pos = self.get_real_positions(pair)
            if not real_pos or not real_pos.get('long') or not real_pos.get('short'):
                print("❌ Impossible de récupérer positions")
                return False

            entry_long = real_pos['long']['entry_price']
            entry_short = real_pos['short']['entry_price']

            print(f"📊 Prix entrée Long (API): ${entry_long:.4f}")
            print(f"📊 Prix entrée Short (API): ${entry_short:.4f}")

            # Créer position tracking
            position = HedgePosition(pair, self.INITIAL_MARGIN, entry_long, entry_short)
            self.active_positions[pair] = position

            # 2. Placer les 4 ordres limites
            print("\n2️⃣ Placement des 4 ordres limites...")

            next_trigger_pct = position.get_next_trigger_pct()
            if not next_trigger_pct:
                print("❌ Pas de niveau Fibonacci")
                return False

            # Calculer prix des triggers
            tp_long_price = entry_long * (1 + next_trigger_pct / 100)
            tp_short_price = entry_short * (1 - next_trigger_pct / 100)
            double_short_price = tp_long_price  # MÊME PRIX que TP Long
            double_long_price = tp_short_price  # MÊME PRIX que TP Short

            # a) TP Long (fermer long si prix monte)
            tp_long_order = self.exchange.create_order(
                symbol=pair, type='limit', side='sell', amount=size, price=tp_long_price,
                params={'tradeSide': 'close'}
            )
            position.orders['tp_long'] = tp_long_order['id']
            print(f"📝 TP Long @ ${tp_long_price:.4f} (+{next_trigger_pct}%)")

            # b) Doubler Short (si prix monte - MÊME PRIX)
            double_short_order = self.exchange.create_order(
                symbol=pair, type='limit', side='sell', amount=size * 2, price=double_short_price,
                params={'tradeSide': 'open'}
            )
            position.orders['double_short'] = double_short_order['id']
            print(f"📝 Doubler Short @ ${double_short_price:.4f}")

            # c) TP Short (fermer short si prix descend)
            tp_short_order = self.exchange.create_order(
                symbol=pair, type='limit', side='buy', amount=size, price=tp_short_price,
                params={'tradeSide': 'close'}
            )
            position.orders['tp_short'] = tp_short_order['id']
            print(f"📝 TP Short @ ${tp_short_price:.4f} (-{next_trigger_pct}%)")

            # d) Doubler Long (si prix descend - MÊME PRIX)
            double_long_order = self.exchange.create_order(
                symbol=pair, type='limit', side='buy', amount=size * 2, price=double_long_price,
                params={'tradeSide': 'open'}
            )
            position.orders['double_long'] = double_long_order['id']
            print(f"📝 Doubler Long @ ${double_long_price:.4f}")

            self.capital_used += self.INITIAL_MARGIN * 2
            self.available_pairs.remove(pair)

            # Telegram
            message = f"""
🎯 <b>HEDGE OUVERT - {pair.split('/')[0]}</b>

📈 Long: ${entry_long:.4f}
📉 Short: ${entry_short:.4f}
⚡ Levier: x{self.LEVERAGE}

📝 <b>Ordres limites placés:</b>

⬆️ Si hausse +{next_trigger_pct}% (${tp_long_price:.4f}):
   → TP Long
   → Doubler Short

⬇️ Si baisse -{next_trigger_pct}% (${tp_short_price:.4f}):
   → TP Short
   → Doubler Long

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.send_telegram(message)

            return True

        except Exception as e:
            print(f"❌ Erreur ouverture: {e}")
            return False

    def check_orders_status(self):
        """Vérifie l'état des ordres limites et annule si nécessaire"""

        for pair, position in list(self.active_positions.items()):
            try:
                # Récupérer tous les ordres ouverts sur cette paire
                open_orders = self.exchange.fetch_open_orders(pair)

                # Vérifier quels ordres de position sont encore actifs
                active_order_ids = [order['id'] for order in open_orders]

                # Vérifier si TP Long exécuté (n'est plus dans ordres ouverts)
                tp_long_executed = (position.orders['tp_long'] and
                                    position.orders['tp_long'] not in active_order_ids)

                # Vérifier si TP Short exécuté
                tp_short_executed = (position.orders['tp_short'] and
                                     position.orders['tp_short'] not in active_order_ids)

                # TP LONG EXÉCUTÉ (prix a monté)
                if tp_long_executed and position.long_open:
                    print(f"\n🔔 TP LONG EXÉCUTÉ - {pair}")
                    position.long_open = False

                    # Annuler ordres du côté opposé
                    if position.orders['tp_short']:
                        self.cancel_order(position.orders['tp_short'], pair)
                    if position.orders['double_long']:
                        self.cancel_order(position.orders['double_long'], pair)

                    # Replacer ordres au niveau Fibonacci suivant
                    position.current_level += 1
                    self.place_next_level_orders(pair, position, direction='up')

                    # Ouvrir nouveau hedge
                    self.open_next_hedge()

                # TP SHORT EXÉCUTÉ (prix a descendu)
                elif tp_short_executed and position.short_open:
                    print(f"\n🔔 TP SHORT EXÉCUTÉ - {pair}")
                    position.short_open = False

                    # Annuler ordres du côté opposé
                    if position.orders['tp_long']:
                        self.cancel_order(position.orders['tp_long'], pair)
                    if position.orders['double_short']:
                        self.cancel_order(position.orders['double_short'], pair)

                    # Replacer ordres au niveau Fibonacci suivant
                    position.current_level += 1
                    self.place_next_level_orders(pair, position, direction='down')

                    # Ouvrir nouveau hedge
                    self.open_next_hedge()

            except Exception as e:
                print(f"⚠️  Erreur vérification ordres {pair}: {e}")

    def place_next_level_orders(self, pair, position, direction):
        """Place les ordres pour le prochain niveau Fibonacci"""

        next_trigger = position.get_next_trigger_pct()
        if not next_trigger:
            print("✅ Fibonacci terminé pour cette paire")
            return

        real_pos = self.get_real_positions(pair)
        if not real_pos:
            return

        print(f"\n📝 Placement ordres niveau Fibonacci {position.current_level} (+{next_trigger}%)")

        if direction == 'up':  # Prix a monté
            # Il reste seulement le SHORT
            short_data = real_pos.get('short')
            if not short_data:
                return

            entry = short_data['entry_price']
            size = short_data['size']

            # Nouveau prix trigger
            new_trigger_price = position.entry_price_short * (1 + next_trigger / 100)

            # Placer ordre doubler short au nouveau niveau
            double_order = self.exchange.create_order(
                symbol=pair, type='limit', side='sell', amount=size * 2,
                price=new_trigger_price, params={'tradeSide': 'open'}
            )
            position.orders['double_short'] = double_order['id']
            print(f"📝 Doubler Short @ ${new_trigger_price:.4f}")

        elif direction == 'down':  # Prix a descendu
            # Il reste seulement le LONG
            long_data = real_pos.get('long')
            if not long_data:
                return

            entry = long_data['entry_price']
            size = long_data['size']

            # Nouveau prix trigger
            new_trigger_price = position.entry_price_long * (1 - next_trigger / 100)

            # Placer ordre doubler long au nouveau niveau
            double_order = self.exchange.create_order(
                symbol=pair, type='limit', side='buy', amount=size * 2,
                price=new_trigger_price, params={'tradeSide': 'open'}
            )
            position.orders['double_long'] = double_order['id']
            print(f"📝 Doubler Long @ ${new_trigger_price:.4f}")

    def open_next_hedge(self):
        """Ouvre un nouveau hedge sur la prochaine paire disponible"""
        if self.available_pairs and self.capital_used < self.MAX_CAPITAL:
            next_pair = self.available_pairs[0]
            print(f"\n🔄 Rotation vers {next_pair}")
            time.sleep(2)
            self.open_hedge_with_limit_orders(next_pair)

    def send_status_telegram(self):
        """Envoie status sur Telegram toutes les 30s"""
        current_time = time.time()
        if current_time - self.last_status_update < 30:
            return

        if not self.active_positions:
            return

        message_parts = ["📊 <b>STATUS POSITIONS</b>\n"]
        total_pnl = 0

        for pair, pos in self.active_positions.items():
            real_pos = self.get_real_positions(pair)
            price = self.get_price(pair)

            if not real_pos or not price:
                continue

            long_data = real_pos.get('long')
            short_data = real_pos.get('short')

            pair_msg = f"\n🎯 <b>{pair.split('/')[0]}</b> - ${price:.4f}\n"

            if long_data:
                pnl = long_data['unrealized_pnl']
                total_pnl += pnl
                next_trigger = pos.get_next_trigger_pct()
                next_price = pos.entry_price_long * (1 + next_trigger / 100) if next_trigger else 0

                pair_msg += f"📈 Long: ${long_data['entry_price']:.4f}\n"
                pair_msg += f"   P&L: ${pnl:+.2f}\n"
                if next_trigger:
                    pair_msg += f"   🎯 TP @ ${next_price:.4f} (+{next_trigger}%)\n"

            if short_data:
                pnl = short_data['unrealized_pnl']
                total_pnl += pnl
                next_trigger = pos.get_next_trigger_pct()
                next_price = pos.entry_price_short * (1 - next_trigger / 100) if next_trigger else 0

                pair_msg += f"📉 Short: ${short_data['entry_price']:.4f}\n"
                pair_msg += f"   P&L: ${pnl:+.2f}\n"
                pair_msg += f"   Liq: ${short_data['liquidation_price']:.4f}\n"
                if next_trigger:
                    pair_msg += f"   🎯 TP @ ${next_price:.4f} (-{next_trigger}%)\n"

            message_parts.append(pair_msg)

        message_parts.append(f"\n💰 P&L Total: ${total_pnl + self.total_profit:+.2f}")
        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

        self.send_telegram("".join(message_parts))
        self.last_status_update = current_time

    def run(self):
        """Boucle principale"""
        print("="*80)
        print("🚀 BITGET HEDGE BOT V2 - ORDRES LIMITES AUTO")
        print("="*80)

        if not self.api_key:
            print("❌ Clés API manquantes")
            return

        try:
            print("\n📡 Connexion Bitget Testnet...")
            self.exchange.load_markets()

            # Message démarrage
            startup = f"""
🤖 <b>BOT HEDGE V2 DÉMARRÉ</b>

💰 Capital: ${self.MAX_CAPITAL}
⚡ Levier: x{self.LEVERAGE}
📊 Marge initiale: ${self.INITIAL_MARGIN}

📝 <b>Système ordres limites:</b>
✅ TP + Doublement automatique
✅ Annulation intelligente
✅ Fibonacci: 1%, 2%, 4%, 7%, 12%...

Paires: {', '.join([p.split('/')[0] for p in self.volatile_pairs])}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(startup)

            # Ouvrir première position
            if self.available_pairs:
                self.open_hedge_with_limit_orders(self.available_pairs[0])

            # Boucle
            iteration = 0
            while True:
                # Vérifier ordres exécutés
                self.check_orders_status()

                # Status Telegram
                self.send_status_telegram()

                # Status console
                if iteration % 30 == 0 and self.active_positions:
                    print(f"\n📊 {len(self.active_positions)} positions actives | Capital: ${self.capital_used}/${self.MAX_CAPITAL}")

                iteration += 1
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n✋ Arrêt")
            self.send_telegram("🛑 Bot arrêté")
        except Exception as e:
            print(f"❌ Erreur: {e}")
            self.send_telegram(f"❌ Erreur: {e}")


def main():
    bot = BitgetHedgeBotV2()
    bot.run()


if __name__ == "__main__":
    main()
