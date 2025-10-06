"""
Bitget Hedge Multi-Pairs Strategy with Fibonacci Grid
Stratégie de hedging sur memecoins volatiles avec réajustement Fibonacci
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
    """Gère une position hedge sur une paire"""

    def __init__(self, pair, initial_margin, entry_price):
        self.pair = pair
        self.initial_margin = initial_margin
        self.entry_price = entry_price

        # Positions
        self.long_open = True
        self.long_size = initial_margin / entry_price
        self.short_size = initial_margin / entry_price
        self.short_margin = initial_margin

        # Grille Fibonacci
        self.fib_levels = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]  # % de mouvement
        self.current_level = 0
        self.cumulative_move = 0  # % cumulé depuis début

        # Stats
        self.profit_realized = 0
        self.adjustments_count = 0

    def get_next_trigger(self):
        """Retourne le prochain niveau de déclenchement"""
        if self.current_level >= len(self.fib_levels):
            return None

        # Calculer le niveau cumulé
        next_cumulative = sum(self.fib_levels[:self.current_level + 1])
        return next_cumulative

    def get_profit_loss(self, current_price):
        """Calcule le P&L actuel"""
        pnl = 0

        # Long P&L (si ouvert)
        if self.long_open:
            long_pnl = (current_price - self.entry_price) * self.long_size
            pnl += long_pnl

        # Short P&L (toujours ouvert)
        short_pnl = (self.entry_price - current_price) * self.short_size
        pnl += short_pnl

        return pnl + self.profit_realized


class BitgetHedgeBot:
    """Bot de trading hedge multi-paires avec grille Fibonacci"""

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
                'defaultMarginMode': 'cross',  # Cross margin pour éviter liquidation
            },
            'headers': {'PAPTRADING': '1'},
            'enableRateLimit': True
        })

        # Paires volatiles (memecoins)
        self.volatile_pairs = [
            'DOGE/USDT:USDT',
            'PEPE/USDT:USDT',
            'SHIB/USDT:USDT',
            'WIF/USDT:USDT',
            'BONK/USDT:USDT',
            'FLOKI/USDT:USDT'
        ]

        self.available_pairs = self.volatile_pairs.copy()

        # Paramètres stratégie
        self.INITIAL_MARGIN = 1  # 1$ de marge par hedge initial
        self.LEVERAGE = 50  # Levier x50
        self.TRIGGER_PERCENT = 1.0  # 1% de mouvement pour trigger
        self.MAX_CAPITAL = 100  # Capital max à risquer (en marge réelle)

        # Configuration monitoring
        self.STATUS_UPDATE_INTERVAL = 30  # Envoyer status sur Telegram toutes les 30s
        self.last_status_update = time.time()

        # Positions actives
        self.active_positions = {}  # {pair: HedgePosition}

        # Stats globales
        self.total_profit = 0
        self.total_positions_opened = 0
        self.capital_used = 0

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

    def get_real_positions(self, symbol=None):
        """
        Récupère positions réelles avec P&L et frais depuis API Bitget

        Args:
            symbol: Symbole spécifique ou None pour toutes

        Returns:
            dict: {'long': {...}, 'short': {...}} ou None
        """
        try:
            positions = self.exchange.fetch_positions(symbols=[symbol] if symbol else None)

            result = {'long': None, 'short': None}

            for pos in positions:
                # Filtrer par symbole si spécifié
                if symbol and pos['symbol'] != symbol:
                    continue

                # Filtrer seulement les positions ouvertes
                contracts = float(pos.get('contracts', 0))
                if contracts <= 0:
                    continue

                side = pos.get('side', '').lower()  # 'long' ou 'short'

                if side in ['long', 'short']:
                    result[side] = {
                        'symbol': pos['symbol'],
                        'size': contracts,
                        'notional': float(pos.get('notional', 0)),
                        'leverage': float(pos.get('leverage', 0)),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'pnl_percentage': float(pos.get('percentage', 0)),
                        'margin': float(pos.get('initialMargin', 0)),
                    }

            return result

        except Exception as e:
            print(f"❌ Erreur récupération positions {symbol}: {e}")
            return None

    def get_trading_fees(self, symbol):
        """
        Récupère les vrais frais de trading depuis l'API

        Returns:
            dict: {'maker': 0.02, 'taker': 0.06} en %
        """
        try:
            fees = self.exchange.fetch_trading_fees()

            if symbol in fees:
                return {
                    'maker': fees[symbol]['maker'] * 100,
                    'taker': fees[symbol]['taker'] * 100
                }

            # Par défaut si pas trouvé
            return {'maker': 0.02, 'taker': 0.06}

        except Exception as e:
            print(f"⚠️  Frais par défaut utilisés: maker=0.02%, taker=0.06%")
            return {'maker': 0.02, 'taker': 0.06}

    def set_position_mode(self, symbol, hedge_mode=True):
        """Active le mode hedge (long + short simultanés)"""
        try:
            # Bitget nécessite le hedge mode pour avoir long et short en même temps
            self.exchange.set_position_mode(hedged=hedge_mode, symbol=symbol)
            print(f"⚙️  Mode hedge activé pour {symbol}")
            return True
        except Exception as e:
            print(f"⚠️  Mode hedge (tentative): {e}")
            # Peut déjà être activé, continuer
            return False

    def set_leverage(self, symbol, leverage):
        """Configure le levier pour une paire"""
        try:
            self.exchange.set_leverage(leverage, symbol)
            print(f"⚙️  Levier x{leverage} configuré pour {symbol}")
            return True
        except Exception as e:
            print(f"⚠️  Impossible de configurer levier pour {symbol}: {e}")
            # Continuer quand même, certains exchanges ne supportent pas cette fonction
            return False

    def calculate_safety_margin(self, real_position_data, next_trigger_pct):
        """
        Calcule marge de sécurité basée sur les VRAIES données API

        Args:
            real_position_data: Données position depuis API
            next_trigger_pct: Prochain niveau Fibonacci (%)

        Returns:
            float: Marge à ajouter
        """
        if not real_position_data or not next_trigger_pct:
            return 0

        # Récupérer prix de liquidation RÉEL depuis API
        current_liq_price = real_position_data['liquidation_price']
        entry_price = real_position_data['entry_price']

        # Calculer le prix au prochain trigger
        next_trigger_price = entry_price * (1 + next_trigger_pct / 100)

        # Si liquidation trop proche du prochain trigger, ajouter marge
        safety_buffer = next_trigger_price * 1.01  # 1% au-delà du trigger

        if current_liq_price < safety_buffer:
            # Besoin de plus de marge
            # Utiliser la marge actuelle comme référence
            current_margin = real_position_data['margin']
            return current_margin * 0.3  # Ajouter 30% de marge supplémentaire

        return 0  # Pas besoin de marge additionnelle

    def open_hedge_position(self, pair):
        """Ouvre une nouvelle position hedge sur une paire"""
        if self.capital_used + (self.INITIAL_MARGIN * 2) > self.MAX_CAPITAL:
            print(f"⚠️  Capital max atteint, impossible d'ouvrir {pair}")
            return False

        price = self.get_price(pair)
        if not price:
            return False

        print(f"\n{'='*80}")
        print(f"🎯 OUVERTURE HEDGE: {pair}")
        print(f"{'='*80}")

        # Activer mode hedge (long + short simultanés)
        self.set_position_mode(pair, hedge_mode=True)

        # Configurer levier x50
        self.set_leverage(pair, self.LEVERAGE)

        # Calculer taille avec levier
        # Position notionnelle = Marge × Levier
        notional_value = self.INITIAL_MARGIN * self.LEVERAGE
        size = notional_value / price

        try:
            # Ordre Long MARKET (position initiale - exécution immédiate)
            long_order = self.exchange.create_order(
                symbol=pair,
                type='market',  # MARKET pour première position
                side='buy',
                amount=size,
                params={
                    'tradeSide': 'open'
                }
            )
            print(f"✅ Long ouvert (MARKET): {size:.4f} @ ${price:,.4f} (Notionnel: ${notional_value})")

            # Ordre Short MARKET (position initiale - exécution immédiate)
            short_order = self.exchange.create_order(
                symbol=pair,
                type='market',  # MARKET pour première position
                side='sell',
                amount=size,
                params={
                    'tradeSide': 'open'
                }
            )
            print(f"✅ Short ouvert (MARKET): {size:.4f} @ ${price:,.4f} (Notionnel: ${notional_value})")

            # Attendre que les ordres soient exécutés
            time.sleep(2)

            # Créer position (tracking interne)
            position = HedgePosition(pair, self.INITIAL_MARGIN, price)
            self.active_positions[pair] = position

            self.capital_used += self.INITIAL_MARGIN * 2
            self.total_positions_opened += 1

            # Retirer de la liste disponible
            if pair in self.available_pairs:
                self.available_pairs.remove(pair)

            # Récupérer les vraies données de position depuis l'API
            print("\n📊 Récupération données réelles API...")
            real_pos = self.get_real_positions(pair)

            if real_pos:
                long_data = real_pos.get('long')
                short_data = real_pos.get('short')

                # Afficher les vraies données
                if long_data and short_data:
                    print(f"   📈 Long  - Prix entrée: ${long_data['entry_price']:.4f} | Marge: ${long_data['margin']:.2f}")
                    print(f"   📉 Short - Prix entrée: ${short_data['entry_price']:.4f} | Marge: ${short_data['margin']:.2f}")
                    print(f"   💀 Liquidation Long: ${long_data['liquidation_price']:.4f}")
                    print(f"   💀 Liquidation Short: ${short_data['liquidation_price']:.4f}")

                    # Telegram avec vraies données
                    total_pnl = long_data['unrealized_pnl'] + short_data['unrealized_pnl']

                    message = f"""
🎯 <b>HEDGE OUVERT</b>

Paire: {pair}
Levier: x{self.LEVERAGE}

📈 Long: ${long_data['entry_price']:.4f}
📉 Short: ${short_data['entry_price']:.4f}

💰 Marge totale: ${long_data['margin'] + short_data['margin']:.2f}
📊 P&L actuel: ${total_pnl:+.2f}

💀 Liq Long: ${long_data['liquidation_price']:.4f}
💀 Liq Short: ${short_data['liquidation_price']:.4f}

🎯 Prochain trigger: +{position.get_next_trigger()}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                    self.send_telegram(message)
                else:
                    # Fallback si données API pas disponibles
                    message = f"""
🎯 <b>HEDGE OUVERT</b>

Paire: {pair}
Prix: ${price:,.4f}
Levier: x{self.LEVERAGE}
Marge: ${self.INITIAL_MARGIN * 2}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                    self.send_telegram(message)

            return True

        except Exception as e:
            print(f"❌ Erreur ouverture hedge {pair}: {e}")
            return False

    def close_long_and_adjust_short(self, pair, position, current_price):
        """Ferme le long, double le short, ouvre nouveau hedge"""

        print(f"\n{'='*80}")
        print(f"🔄 TRIGGER ATTEINT: {pair}")
        print(f"{'='*80}")

        try:
            # 1. Récupérer position LONG réelle AVANT de fermer
            real_pos_before = self.get_real_positions(pair)
            long_pnl_before = 0

            if real_pos_before and real_pos_before.get('long'):
                long_pnl_before = real_pos_before['long']['unrealized_pnl']
                print(f"📊 Long P&L avant fermeture (API): ${long_pnl_before:+.2f}")

            # 2. Fermer Long (mode hedge : side=sell, tradeSide=close)
            if position.long_open:
                self.exchange.create_order(
                    symbol=pair,
                    type='market',
                    side='sell',  # Vendre pour fermer un long
                    amount=position.long_size,
                    params={
                        'tradeSide': 'close'  # Fermer la position (mode hedge)
                    }
                )

                # Utiliser le P&L RÉEL de l'API (avec frais inclus)
                long_profit = long_pnl_before
                position.profit_realized += long_profit
                position.long_open = False
                self.total_profit += long_profit

                print(f"✅ Long fermé (MARKET): Profit RÉEL = ${long_profit:.2f}")

            # 2. Récupérer position SHORT réelle depuis API
            time.sleep(1)  # Attendre mise à jour
            real_pos = self.get_real_positions(pair)

            if not real_pos or not real_pos.get('short'):
                print("⚠️  Impossible de récupérer position short, utilisation valeurs par défaut")
                safety_margin = position.short_margin * 0.3
            else:
                short_data = real_pos['short']
                next_trigger = position.get_next_trigger()

                print(f"\n📊 Position SHORT actuelle (API):")
                print(f"   Prix entrée: ${short_data['entry_price']:.4f}")
                print(f"   Marge: ${short_data['margin']:.2f}")
                print(f"   P&L: ${short_data['unrealized_pnl']:+.2f}")
                print(f"   Liquidation: ${short_data['liquidation_price']:.4f}")

                # Calculer marge de sécurité basée sur vraies données
                safety_margin = self.calculate_safety_margin(short_data, next_trigger)

            # 3. Doubler le Short + Ajouter marge de sécurité
            additional_margin = (position.short_margin * 2) + safety_margin
            additional_size = (position.short_margin * 2) / current_price  # Taille basée sur doublement

            # Ajouter au short en ORDRE LIMITE (meilleur prix, maker fee)
            limit_price = current_price * 1.0001  # Légèrement au-dessus pour exécution rapide

            self.exchange.create_order(
                symbol=pair,
                type='limit',  # LIMITE au lieu de MARKET
                side='sell',
                amount=additional_size,
                price=limit_price,
                params={
                    'tradeSide': 'open',
                    'timeInForce': 'IOC'  # Immediate or Cancel (exécution rapide ou annulé)
                }
            )

            position.short_size += additional_size
            position.short_margin += additional_margin
            position.adjustments_count += 1
            position.current_level += 1

            self.capital_used += additional_margin

            print(f"✅ Short ajusté (ORDRE LIMITE): +${position.short_margin * 2:.2f} (doublement)")
            print(f"🛡️  Marge sécurité: +${safety_margin:.2f} (anti-liquidation)")
            print(f"   📝 Prix limite: ${limit_price:.4f} (maker fee ~0.02%)")

            # Attendre exécution de l'ordre limite et récupérer vraies données API
            time.sleep(3)
            print("\n📊 Récupération données RÉELLES API après ajustement...")

            real_pos_after = self.get_real_positions(pair)

            if real_pos_after and real_pos_after.get('short'):
                short_data_after = real_pos_after['short']

                print(f"\n   📉 SHORT APRÈS AJUSTEMENT (API RÉELLE):")
                print(f"      Prix entrée moyen: ${short_data_after['entry_price']:.4f}")
                print(f"      Taille: {short_data_after['size']:.4f}")
                print(f"      Marge RÉELLE: ${short_data_after['margin']:.2f}")
                print(f"      P&L: ${short_data_after['unrealized_pnl']:+.2f}")
                print(f"      💀 Liquidation RÉELLE API: ${short_data_after['liquidation_price']:.4f}")

                # Telegram avec vraies données
                next_trigger = position.get_next_trigger()
                next_price = position.entry_price * (1 + next_trigger / 100) if next_trigger else 0

                message = f"""
🔄 <b>AJUSTEMENT {pair}</b>

Niveau Fibonacci: {position.current_level}
Long fermé (MARKET): +${long_profit:.2f}

📉 <b>SHORT (Ordre LIMITE placé):</b>
Prix limite: ${limit_price:.4f}
Marge ajoutée: ${additional_margin:.2f}
💸 Frais: ~0.02% (maker)

📊 <b>Position SHORT (DONNÉES API RÉELLES):</b>
Prix entrée moyen: ${short_data_after['entry_price']:.4f}
Marge RÉELLE: ${short_data_after['margin']:.2f}
P&L RÉEL: ${short_data_after['unrealized_pnl']:+.2f} ({short_data_after['pnl_percentage']:+.2f}%)

💀 Liquidation (API): ${short_data_after['liquidation_price']:.4f}
🎯 Prochain trigger: {f"+{next_trigger}% @ ${next_price:.4f}" if next_trigger else "MAX"}

Capital utilisé: ${self.capital_used:.0f}/{self.MAX_CAPITAL}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
            else:
                # Fallback si API ne répond pas
                next_trigger = position.get_next_trigger()
                message = f"""
🔄 <b>AJUSTEMENT {pair}</b>

Niveau: {position.current_level}
Long fermé: +${long_profit:.2f}
Short doublé + marge sécurité
Prochain: {f"+{next_trigger}%" if next_trigger else "MAX"}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)

            # 3. Ouvrir nouveau hedge sur autre paire
            if self.available_pairs and self.capital_used < self.MAX_CAPITAL:
                next_pair = self.available_pairs[0]
                print(f"\n🔄 Rotation vers nouvelle paire: {next_pair}")
                time.sleep(2)  # Petit délai
                self.open_hedge_position(next_pair)
            else:
                print(f"\n⚠️  Pas de nouvelle paire disponible ou capital max atteint")

            return True

        except Exception as e:
            print(f"❌ Erreur ajustement {pair}: {e}")
            return False

    def send_positions_status_telegram(self):
        """Envoie le statut détaillé de toutes les positions sur Telegram"""

        if not self.active_positions:
            return

        current_time = time.time()
        if current_time - self.last_status_update < self.STATUS_UPDATE_INTERVAL:
            return  # Pas encore le moment

        message_parts = ["📊 <b>STATUS POSITIONS HEDGE</b>\n"]

        total_pnl_unrealized = 0

        for pair, pos in self.active_positions.items():
            # Récupérer données réelles API
            real_pos = self.get_real_positions(pair)
            current_price = self.get_price(pair)

            if not real_pos or not current_price:
                continue

            long_data = real_pos.get('long')
            short_data = real_pos.get('short')

            # Calculer prochain trigger Fibonacci
            next_trigger_pct = pos.get_next_trigger()

            pair_status = f"\n🎯 <b>{pair.split('/')[0]}</b>\n"
            pair_status += f"Prix actuel: ${current_price:.4f}\n"

            # LONG (si ouvert)
            if long_data:
                long_pnl = long_data['unrealized_pnl']
                total_pnl_unrealized += long_pnl

                pair_status += f"\n📈 <b>LONG</b>\n"
                pair_status += f"  Entrée: ${long_data['entry_price']:.4f}\n"
                pair_status += f"  P&L: ${long_pnl:+.2f} ({long_data['pnl_percentage']:+.2f}%)\n"
                pair_status += f"  Marge: ${long_data['margin']:.2f}\n"

                # Actions si prix MONTE (hausse)
                if next_trigger_pct:
                    next_price_up = pos.entry_price * (1 + next_trigger_pct / 100)
                    distance_up = ((next_price_up - current_price) / current_price) * 100

                    pair_status += f"\n  ⬆️ Si hausse à ${next_price_up:.4f} (+{next_trigger_pct}%):\n"
                    pair_status += f"     → Fermer Long (profit)\n"
                    pair_status += f"     → Doubler Short\n"
                    pair_status += f"     📏 Distance: {distance_up:+.2f}%\n"

                # Actions si prix DESCEND (baisse)
                if next_trigger_pct:
                    next_price_down = pos.entry_price * (1 - next_trigger_pct / 100)
                    distance_down_trigger = ((next_price_down - current_price) / current_price) * 100

                    pair_status += f"\n  ⬇️ Si baisse à ${next_price_down:.4f} (-{next_trigger_pct}%):\n"
                    pair_status += f"     → Ajuster marge Long\n"
                    pair_status += f"     📏 Distance: {distance_down_trigger:+.2f}%\n"

            # SHORT (toujours ouvert)
            if short_data:
                short_pnl = short_data['unrealized_pnl']
                total_pnl_unrealized += short_pnl

                pair_status += f"\n📉 <b>SHORT</b>\n"
                pair_status += f"  Entrée: ${short_data['entry_price']:.4f}\n"
                pair_status += f"  P&L: ${short_pnl:+.2f} ({short_data['pnl_percentage']:+.2f}%)\n"
                pair_status += f"  Marge: ${short_data['margin']:.2f}\n"
                pair_status += f"  💀 Liquidation: ${short_data['liquidation_price']:.4f}\n"

                # Actions si prix MONTE (hausse)
                if next_trigger_pct and long_data:
                    next_price_up = pos.entry_price * (1 + next_trigger_pct / 100)
                    pair_status += f"\n  ⬆️ Si hausse à ${next_price_up:.4f}:\n"
                    pair_status += f"     → Doubler marge Short\n"

                # Actions si prix DESCEND (baisse)
                if next_trigger_pct:
                    next_price_down = pos.entry_price * (1 - next_trigger_pct / 100)
                    distance_down = ((next_price_down - current_price) / current_price) * 100

                    pair_status += f"\n  ⬇️ Si baisse à ${next_price_down:.4f} (-{next_trigger_pct}%):\n"
                    pair_status += f"     → Fermer Short (profit)\n"
                    pair_status += f"     → Doubler Long\n"
                    pair_status += f"     📏 Distance: {distance_down:+.2f}%\n"

            # Niveau Fibonacci actuel
            pair_status += f"\n🔢 Niveau Fibonacci: {pos.current_level}\n"

            message_parts.append(pair_status)

        # Footer
        message_parts.append(f"\n💰 <b>P&L Total Non Réalisé: ${total_pnl_unrealized:+.2f}</b>")
        message_parts.append(f"💵 P&L Réalisé: ${self.total_profit:+.2f}")
        message_parts.append(f"📊 P&L TOTAL: ${self.total_profit + total_pnl_unrealized:+.2f}\n")
        message_parts.append(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

        full_message = "".join(message_parts)
        self.send_telegram(full_message)
        self.last_status_update = current_time

    def close_short_and_adjust_long(self, pair, position, current_price):
        """Ferme le short, double le long (si prix descend)"""

        print(f"\n{'='*80}")
        print(f"🔄 TRIGGER BAISSE ATTEINT: {pair}")
        print(f"{'='*80}")

        try:
            # 1. Récupérer position SHORT réelle AVANT de fermer
            real_pos_before = self.get_real_positions(pair)
            short_pnl_before = 0

            if real_pos_before and real_pos_before.get('short'):
                short_pnl_before = real_pos_before['short']['unrealized_pnl']
                print(f"📊 Short P&L avant fermeture (API): ${short_pnl_before:+.2f}")

            # 2. Fermer Short (profit si prix a baissé)
            if position.short_size > 0:
                self.exchange.create_order(
                    symbol=pair,
                    type='market',
                    side='buy',  # Acheter pour fermer un short
                    amount=position.short_size,
                    params={
                        'tradeSide': 'close'
                    }
                )

                # Utiliser le P&L RÉEL de l'API (avec frais inclus)
                short_profit = short_pnl_before
                position.profit_realized += short_profit
                self.total_profit += short_profit

                print(f"✅ Short fermé (MARKET): Profit RÉEL = ${short_profit:.2f}")

            # 2. Récupérer position LONG réelle depuis API
            time.sleep(1)
            real_pos_long = self.get_real_positions(pair)

            if not real_pos_long or not real_pos_long.get('long'):
                print("⚠️  Impossible de récupérer position long")
                safety_margin = position.initial_margin * 0.3
            else:
                long_data = real_pos_long['long']
                next_trigger = position.get_next_trigger()

                print(f"\n📊 Position LONG actuelle (API):")
                print(f"   Prix entrée: ${long_data['entry_price']:.4f}")
                print(f"   Marge: ${long_data['margin']:.2f}")
                print(f"   P&L: ${long_data['unrealized_pnl']:+.2f}")
                print(f"   Liquidation: ${long_data['liquidation_price']:.4f}")

                # Calculer marge de sécurité basée sur vraies données
                safety_margin = self.calculate_safety_margin(long_data, next_trigger)

            # 3. Doubler le Long + Ajouter marge de sécurité
            if position.long_open:
                additional_margin = (position.initial_margin * 2) + safety_margin
                additional_size = (position.initial_margin * 2) / current_price

                # Ordre LIMITE (meilleur prix, maker fee)
                limit_price = current_price * 0.9999  # Légèrement en dessous pour exécution rapide

                self.exchange.create_order(
                    symbol=pair,
                    type='limit',  # LIMITE au lieu de MARKET
                    side='buy',
                    amount=additional_size,
                    price=limit_price,
                    params={
                        'tradeSide': 'open',
                        'timeInForce': 'IOC'  # Immediate or Cancel
                    }
                )

                position.long_size += additional_size
                position.adjustments_count += 1
                position.current_level += 1
                self.capital_used += additional_margin

                print(f"✅ Long ajusté (ORDRE LIMITE): doublement + marge sécurité")
                print(f"   📝 Prix limite: ${limit_price:.4f} (maker fee ~0.02%)")

                # Telegram
                message = f"""
🔄 <b>AJUSTEMENT BAISSE {pair}</b>

Niveau Fibonacci: {position.current_level}
Short fermé (MARKET): +${short_profit:.2f}

📈 LONG (Ordre LIMITE placé):
Prix limite: ${limit_price:.4f}
Marge ajoutée: ${additional_margin:.2f}
💸 Frais: ~0.02% (maker)

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)

                # Ouvrir nouveau hedge
                if self.available_pairs and self.capital_used < self.MAX_CAPITAL:
                    next_pair = self.available_pairs[0]
                    print(f"\n🔄 Rotation vers: {next_pair}")
                    time.sleep(2)
                    self.open_hedge_position(next_pair)

            return True

        except Exception as e:
            print(f"❌ Erreur ajustement baisse {pair}: {e}")
            return False

    def monitor_positions(self):
        """Surveille toutes les positions actives"""

        for pair, position in list(self.active_positions.items()):
            current_price = self.get_price(pair)
            if not current_price:
                continue

            # Calculer mouvement en %
            price_change_pct = ((current_price - position.entry_price) / position.entry_price) * 100

            # Vérifier si on a atteint le prochain trigger
            next_trigger = position.get_next_trigger()

            # TRIGGER HAUSSE : Fermer long, doubler short
            if next_trigger and price_change_pct >= next_trigger:
                self.close_long_and_adjust_short(pair, position, current_price)

            # TRIGGER BAISSE : Fermer short, doubler long
            elif next_trigger and price_change_pct <= -next_trigger:
                self.close_short_and_adjust_long(pair, position, current_price)

    def display_status(self):
        """Affiche le statut avec données réelles de l'API"""
        print(f"\n{'='*80}")
        print(f"📊 STATUT GLOBAL - DONNÉES RÉELLES API")
        print(f"{'='*80}")
        print(f"Positions actives: {len(self.active_positions)}")
        print(f"Capital utilisé: ${self.capital_used:,.0f} / ${self.MAX_CAPITAL:,.0f}")
        print(f"Profit réalisé total: ${self.total_profit:.2f}")
        print(f"Paires disponibles: {len(self.available_pairs)}")

        if self.active_positions:
            print(f"\n📋 POSITIONS (données API réelles) :")

            total_unrealized_pnl = 0

            for pair, pos in self.active_positions.items():
                # Récupérer les vraies positions depuis l'API
                real_pos = self.get_real_positions(pair)

                if real_pos:
                    long_data = real_pos.get('long')
                    short_data = real_pos.get('short')

                    print(f"\n  🎯 {pair} - Niveau Fibonacci: {pos.current_level}")

                    # Afficher Long si ouvert
                    if long_data:
                        print(f"    📈 LONG:")
                        print(f"       Prix entrée: ${long_data['entry_price']:.4f}")
                        print(f"       Prix mark: ${long_data['mark_price']:.4f}")
                        print(f"       P&L: ${long_data['unrealized_pnl']:+.2f} ({long_data['pnl_percentage']:+.2f}%)")
                        print(f"       Marge: ${long_data['margin']:.2f}")
                        print(f"       Liquidation: ${long_data['liquidation_price']:.4f}")
                        total_unrealized_pnl += long_data['unrealized_pnl']

                    # Afficher Short (toujours présent)
                    if short_data:
                        print(f"    📉 SHORT:")
                        print(f"       Prix entrée: ${short_data['entry_price']:.4f}")
                        print(f"       Prix mark: ${short_data['mark_price']:.4f}")
                        print(f"       P&L: ${short_data['unrealized_pnl']:+.2f} ({short_data['pnl_percentage']:+.2f}%)")
                        print(f"       Marge: ${short_data['margin']:.2f}")
                        print(f"       Liquidation: ${short_data['liquidation_price']:.4f}")
                        total_unrealized_pnl += short_data['unrealized_pnl']

                    # Next trigger
                    next_t = pos.get_next_trigger()
                    if next_t:
                        print(f"    🎯 Prochain trigger: +{next_t}%")

            print(f"\n💰 P&L non réalisé total: ${total_unrealized_pnl:+.2f}")
            print(f"💵 P&L réalisé total: ${self.total_profit:+.2f}")
            print(f"📊 P&L TOTAL: ${self.total_profit + total_unrealized_pnl:+.2f}")

        print(f"{'='*80}\n")

    def run(self):
        """Boucle principale"""
        print("="*80)
        print("🚀 BITGET HEDGE FIBONACCI BOT - LEVIER x50")
        print("="*80)
        print(f"💬 Telegram: {'✅' if self.telegram_token else '❌'}")
        print(f"🔑 API: {'✅' if self.api_key else '❌'}")
        print(f"⚡ Levier: x{self.LEVERAGE}")
        print(f"💰 Marge initiale: ${self.INITIAL_MARGIN} → Position: ${self.INITIAL_MARGIN * self.LEVERAGE}")
        print("="*80)

        if not self.api_key:
            print("❌ Clés API manquantes!")
            return

        try:
            # Charger marchés
            print("\n📡 Connexion Bitget Testnet...")
            self.exchange.load_markets()

            # Récupérer les vrais frais de trading
            print("\n💸 Récupération des frais de trading...")
            fees_example = self.get_trading_fees(self.volatile_pairs[0])
            print(f"   Maker: {fees_example['maker']}%")
            print(f"   Taker: {fees_example['taker']}%")

            # Message démarrage
            startup_msg = f"""
🤖 <b>BOT HEDGE FIBONACCI DÉMARRÉ</b>

💰 Capital max: ${self.MAX_CAPITAL} (marge)
⚡ Levier: x{self.LEVERAGE}
📊 Position initiale: ${self.INITIAL_MARGIN * self.LEVERAGE} (notionnel)
📈 Trigger: {self.TRIGGER_PERCENT}%
🔢 Grille: Fibonacci (1%, 2%, 4%, 7%, 12%, 20%...)
🛡️ Protection: Anti-liquidation (Cross Margin)
💸 Frais: Maker {fees_example['maker']}% / Taker {fees_example['taker']}%

Paires: {len(self.volatile_pairs)}
{', '.join([p.split('/')[0] for p in self.volatile_pairs])}

⚠️ Mode: DEMO Bitget Testnet
📊 Analyse: Données réelles API (P&L, frais, liquidation)

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(startup_msg)

            # Ouvrir première position
            print("\n🎯 Ouverture première position hedge...")
            if self.available_pairs:
                self.open_hedge_position(self.available_pairs[0])

            # Boucle monitoring
            iteration = 0
            while True:
                # 1. Surveiller et déclencher les triggers
                self.monitor_positions()

                # 2. Envoyer status sur Telegram (automatique toutes les 30s)
                self.send_positions_status_telegram()

                # 3. Status console toutes les 30 secondes
                if iteration % 30 == 0:
                    self.display_status()

                iteration += 1
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\n✋ Arrêt demandé")
            self.send_telegram("🛑 Bot arrêté")
        except Exception as e:
            print(f"\n❌ Erreur: {e}")
            self.send_telegram(f"❌ Erreur: {e}")


def main():
    bot = BitgetHedgeBot()
    bot.run()


if __name__ == "__main__":
    main()
