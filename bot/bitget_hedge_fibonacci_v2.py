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
import hmac
import base64
import hashlib
import json
import subprocess
import sys
import logging
from collections import deque

# Import du module de commandes Telegram
from telegram_commands import TelegramCommands

# Charger .env
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configuration du logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'bot_{datetime.now().strftime("%Y%m%d")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Buffer circulaire pour les derniers logs (pour /logs Telegram)
log_buffer = deque(maxlen=50)  # Garde les 50 derniers logs

class TelegramLogHandler(logging.Handler):
    """Handler personnalisé pour capturer les logs dans le buffer"""
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append(log_entry)

# Ajouter le handler au logger
telegram_handler = TelegramLogHandler()
telegram_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(telegram_handler)


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

        # Grille Fibonacci (en %) - Index 0 = Fib 0 (MARKET), 1 = Fib 1 (0.3%), etc.
        self.fib_levels = [0, 0.3, 0.382, 0.5, 0.618, 1.0, 1.618, 2.618, 4.236, 6.854, 11.09]

        # Niveaux Fibonacci SÉPARÉS pour Long et Short
        self.long_fib_level = 0   # Long commence à Fib 0
        self.short_fib_level = 0  # Short commence à Fib 0

        # Tracking tailles pour détecter doublements (CAS 3)
        self.long_size_previous = 0   # Sera mis à jour après API
        self.short_size_previous = 0  # Sera mis à jour après API

        # Tracking marges pour détecter les TP (marge diminue = TP touché)
        self.long_margin_previous = 0   # Sera mis à jour après API
        self.short_margin_previous = 0  # Sera mis à jour après API

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

    def get_next_long_trigger_pct(self):
        """Retourne le prochain niveau Fibonacci pour LONG (en %)"""
        next_level = self.long_fib_level + 1
        if next_level >= len(self.fib_levels):
            return None
        return self.fib_levels[next_level]

    def get_next_short_trigger_pct(self):
        """Retourne le prochain niveau Fibonacci pour SHORT (en %)"""
        next_level = self.short_fib_level + 1
        if next_level >= len(self.fib_levels):
            return None
        return self.fib_levels[next_level]


class BitgetHedgeBotV2:
    """Bot hedge avec système d'ordres limites automatique"""

    def __init__(self):
        # Configuration API
        self.api_key = os.getenv('BITGET_API_KEY')
        self.api_secret = os.getenv('BITGET_SECRET')
        self.api_password = os.getenv('BITGET_PASSPHRASE')

        # Debug: Vérifier si les clés sont chargées
        import sys
        print(f"🔑 API Key chargée: {'✅' if self.api_key else '❌'} (longueur: {len(self.api_key) if self.api_key else 0})", flush=True)
        print(f"🔑 Secret chargé: {'✅' if self.api_secret else '❌'} (longueur: {len(self.api_secret) if self.api_secret else 0})", flush=True)
        print(f"🔑 Passphrase chargée: {'✅' if self.api_password else '❌'}", flush=True)
        sys.stdout.flush()

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

        # Paires volatiles (disponibles sur Bitget testnet)
        self.volatile_pairs = [
            'DOGE/USDT:USDT',
            'PEPE/USDT:USDT',
            'SHIB/USDT:USDT'
        ]

        self.available_pairs = self.volatile_pairs.copy()

        # Paramètres
        self.INITIAL_MARGIN = 1  # 1€ de marge par position
        self.LEVERAGE = 50  # Levier x50 (max sur Bitget testnet)
        self.MAX_CAPITAL = 1000  # Capital max: 1000€

        # Positions actives
        self.active_positions = {}  # {pair: HedgePosition}

        # Stats
        self.total_profit = 0
        self.capital_used = 0
        self.last_status_update = time.time()

        # Historique des trades
        self.pnl_history = []  # [{timestamp, pair, pnl, action}]

        # Tracking des frais (SEULEMENT cette session)
        self.total_fees_paid = 0
        self.session_start_time = datetime.now()

        # Telegram bot (commandes)
        self.last_telegram_update_id = self.load_last_update_id()
        self.startup_time = time.time()  # Pour ignorer vieux messages au démarrage

        # Vérification automatique
        self.last_health_check = time.time()
        self.health_check_interval = 60  # Vérifier toutes les 60 secondes
        self.error_count = 0

        # Log buffer pour les commandes
        self.log_buffer = log_buffer  # Référence au buffer global

        # Module de commandes Telegram
        self.telegram_commands = TelegramCommands(self)
        # Ne PAS démarrer le monitoring tout de suite - attendre après cleanup

    def load_last_update_id(self):
        """Charge le dernier update_id depuis fichier pour éviter de retraiter les vieux messages"""
        try:
            update_id_file = Path(__file__).parent.parent / '.last_telegram_update'
            if update_id_file.exists():
                saved_id = int(update_id_file.read_text().strip())
                logger.info(f"Dernier update_id chargé: {saved_id}")
                return saved_id
        except Exception as e:
            logger.warning(f"Impossible de charger last_update_id: {e}")
        return 0

    def save_last_update_id(self):
        """Sauvegarde le dernier update_id dans un fichier"""
        try:
            update_id_file = Path(__file__).parent.parent / '.last_telegram_update'
            update_id_file.write_text(str(self.last_telegram_update_id))
        except Exception as e:
            logger.warning(f"Impossible de sauvegarder last_update_id: {e}")

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

    def send_detailed_position_update(self, pair, position):
        """
        Envoie des messages Telegram détaillés SÉPARÉS pour chaque position
        Un message pour LONG, un message pour SHORT avec tous les détails
        """
        try:
            # Récupérer positions réelles depuis API
            real_pos = self.get_real_positions(pair)
            if not real_pos:
                return

            # Récupérer les ordres ouverts
            open_orders = self.exchange.fetch_open_orders(symbol=pair)
            tpsl_orders = self.get_tpsl_orders(pair)

            # MESSAGE POUR POSITION LONG
            if real_pos.get('long'):
                long_data = real_pos['long']
                message_long = [f"🟢 <b>POSITION LONG - {pair.split('/')[0]}</b>"]
                message_long.append("━━━━━━━━━━━━━━━━━━")

                # Info position
                message_long.append(f"📊 <b>Position Actuelle:</b>")
                message_long.append(f"• Contrats: {long_data['size']:.0f}")
                message_long.append(f"• Entrée: ${long_data['entry_price']:.5f}")
                message_long.append(f"• Marge: {long_data['margin']:.7f} USDT")
                message_long.append(f"• PnL: {long_data['unrealized_pnl']:.7f} USDT ({long_data['pnl_percentage']:.2f}%)")
                message_long.append(f"• ROE: {long_data['pnl_percentage']:.2f}%")
                message_long.append(f"• Niveau Fib: {position.long_fib_level}")

                # Info TP (calculé par défaut)
                message_long.append(f"\n🎯 <b>Take Profit Long:</b>")
                TP_FIXE = 0.3
                tp_long_price = long_data['entry_price'] * (1 + TP_FIXE / 100)
                message_long.append(f"• Prix TP: ${tp_long_price:.5f} (+{TP_FIXE}%)")
                message_long.append(f"• Contrats: {long_data['size']:.0f}")
                message_long.append(f"• Status: ✅ Actif")

                # Info Double Short (Fibonacci)
                message_long.append(f"\n📉 <b>Ordre Double Short (Fib {position.long_fib_level + 1}):</b>")
                double_short_found = False
                for order in open_orders:
                    if order.get('side') == 'sell' and order.get('type') == 'limit':
                        double_short_found = True
                        double_price = float(order.get('price', 0))
                        double_size = float(order.get('amount', 0))
                        next_margin = self.INITIAL_MARGIN * (3 ** (position.short_fib_level + 1))
                        message_long.append(f"• Prix déclenchement: ${double_price:.5f}")
                        message_long.append(f"• Distance: {((double_price - long_data['entry_price']) / long_data['entry_price'] * 100):.2f}%")
                        message_long.append(f"• Contrats: {double_size:.0f}")
                        message_long.append(f"• Marge prévue: {next_margin:.2f} USDT")
                        break
                if not double_short_found:
                    message_long.append("• ⚠️ Ordre non placé!")

                message_long.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                self.send_telegram("\n".join(message_long))

            # MESSAGE POUR POSITION SHORT
            if real_pos.get('short'):
                short_data = real_pos['short']
                message_short = [f"🔴 <b>POSITION SHORT - {pair.split('/')[0]}</b>"]
                message_short.append("━━━━━━━━━━━━━━━━━━")

                # Info position
                message_short.append(f"📊 <b>Position Actuelle:</b>")
                message_short.append(f"• Contrats: {short_data['size']:.0f}")
                message_short.append(f"• Entrée: ${short_data['entry_price']:.5f}")
                message_short.append(f"• Marge: {short_data['margin']:.7f} USDT")
                message_short.append(f"• PnL: {short_data['unrealized_pnl']:.7f} USDT ({short_data['pnl_percentage']:.2f}%)")
                message_short.append(f"• ROE: {short_data['pnl_percentage']:.2f}%")
                message_short.append(f"• Niveau Fib: {position.short_fib_level}")

                # Info TP
                message_short.append(f"\n🎯 <b>Take Profit Short:</b>")
                TP_FIXE = 0.3
                tp_short_price = short_data['entry_price'] * (1 - TP_FIXE / 100)
                message_short.append(f"• Prix TP: ${tp_short_price:.5f} (-{TP_FIXE}%)")
                message_short.append(f"• Contrats: {short_data['size']:.0f}")
                message_short.append(f"• Status: ✅ Actif")

                # Info Double Long (Fibonacci)
                message_short.append(f"\n📈 <b>Ordre Double Long (Fib {position.short_fib_level + 1}):</b>")
                double_long_found = False
                for order in open_orders:
                    if order.get('side') == 'buy' and order.get('type') == 'limit':
                        double_long_found = True
                        double_price = float(order.get('price', 0))
                        double_size = float(order.get('amount', 0))
                        next_margin = self.INITIAL_MARGIN * (3 ** (position.long_fib_level + 1))
                        message_short.append(f"• Prix déclenchement: ${double_price:.5f}")
                        message_short.append(f"• Distance: {((short_data['entry_price'] - double_price) / short_data['entry_price'] * 100):.2f}%")
                        message_short.append(f"• Contrats: {double_size:.0f}")
                        message_short.append(f"• Marge prévue: {next_margin:.2f} USDT")
                        break
                if not double_long_found:
                    message_short.append("• ⚠️ Ordre non placé!")

                message_short.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                self.send_telegram("\n".join(message_short))

        except Exception as e:
            logger.error(f"Erreur send_detailed_position_update: {e}")
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

    def handle_telegram_command(self, command):
        """
        Traite les commandes Telegram reçues
        Délègue au module telegram_commands
        """
        try:
            self.telegram_commands.process_command(command)
        except Exception as e:
            logger.error(f"Erreur traitement commande {command}: {e}")
            self.send_telegram(f"❌ Erreur: {e}")

    def OLD_handle_telegram_command_BACKUP(self, command):
        """BACKUP - Ancienne version des commandes"""
        if command == '/pnl':
            # Afficher P&L actuel
            total_unrealized = 0
            for pair in self.active_positions:
                real_pos = self.get_real_positions(pair)
                if real_pos:
                    if real_pos.get('long'):
                        total_unrealized += real_pos['long']['unrealized_pnl'] or 0
                    if real_pos.get('short'):
                        total_unrealized += real_pos['short']['unrealized_pnl'] or 0

            # Récupérer les VRAIS frais depuis l'API
            total_fees = self.get_total_fees()
            pnl_net = self.total_profit + total_unrealized - total_fees

            message = f"""
💰 <b>P&L SESSION (Données API réelles)</b>

💵 P&L Réalisé: {self.total_profit:+.7f} USDT
📊 P&L Non Réalisé: {total_unrealized:+.7f} USDT
💸 Frais payés (API): {total_fees:.7f} USDT
━━━━━━━━━━━━━━━━━
💎 <b>P&L Net: {pnl_net:+.7f} USDT</b>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.send_telegram(message)

        elif command == '/positions':
            # Afficher positions avec VRAIES données API détaillées
            message_parts = ["📊 <b>POSITIONS OUVERTES</b>\n"]

            has_positions = False
            for pair in self.volatile_pairs:
                real_pos = self.get_real_positions(pair)
                if not real_pos:
                    continue

                long_data = real_pos.get('long')
                short_data = real_pos.get('short')

                if not long_data and not short_data:
                    continue

                has_positions = True
                pair_name = pair.split('/')[0]
                current_price = self.get_price(pair)

                message_parts.append(f"\n━━━━ <b>{pair_name}</b> ━━━━")
                message_parts.append(f"💰 Prix: ${current_price:.5f}\n")

                # LONG - EN VERT
                if long_data:
                    message_parts.append(f"🟢 <b>LONG</b>")
                    message_parts.append(f"🟢 Contrats: {long_data['size']:.0f}")
                    message_parts.append(f"🟢 Entrée: ${long_data['entry_price']:.5f}")
                    message_parts.append(f"🟢 Marge: {long_data['margin']:.7f} USDT")
                    message_parts.append(f"🟢 P&L: {long_data['unrealized_pnl']:+.7f} USDT")
                    message_parts.append(f"🟢 ROE: {long_data['pnl_percentage']:+.2f}%\n")

                # SHORT - EN ROUGE
                if short_data:
                    message_parts.append(f"🔴 <b>SHORT</b>")
                    message_parts.append(f"🔴 Contrats: {short_data['size']:.0f}")
                    message_parts.append(f"🔴 Entrée: ${short_data['entry_price']:.5f}")
                    message_parts.append(f"🔴 Marge: {short_data['margin']:.7f} USDT")
                    message_parts.append(f"🔴 P&L: {short_data['unrealized_pnl']:+.7f} USDT")
                    message_parts.append(f"🔴 ROE: {short_data['pnl_percentage']:+.2f}%")
                    if short_data.get('liquidation_price', 0) > 0:
                        message_parts.append(f"🔴 💀 Liq: ${short_data['liquidation_price']:.5f}")

            if not has_positions:
                self.send_telegram("⚠️ Aucune position active")
                return

            message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            self.send_telegram("\n".join(message_parts))

        elif command == '/history':
            # Afficher historique des P&L
            if not self.pnl_history:
                self.send_telegram("📋 Aucun historique pour cette session")
                return

            message_parts = ["📋 <b>HISTORIQUE P&L</b>\n"]

            for entry in self.pnl_history[-10:]:  # 10 derniers
                timestamp = entry['timestamp'].strftime('%H:%M:%S')
                pair = entry['pair'].split('/')[0]
                pnl = entry['pnl']
                action = entry['action']

                message_parts.append(f"\n{timestamp} | {pair} | {action}: ${pnl:+.2f}")

            message_parts.append(f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            self.send_telegram("".join(message_parts))

        elif command == '/balance':
            # Afficher balance et capital
            balance = self.MAX_CAPITAL - self.capital_used

            message = f"""
💰 <b>BALANCE</b>

Capital total: ${self.MAX_CAPITAL:.0f}€
Capital utilisé: ${self.capital_used:.0f}€
Balance disponible: ${balance:.0f}€

📊 Utilisation: {(self.capital_used / self.MAX_CAPITAL * 100):.1f}%

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.send_telegram(message)

        elif command == '/help':
            message = """
🤖 <b>COMMANDES DISPONIBLES</b>

📊 <b>Trading:</b>
/pnl - P&L total de la session
/positions - Positions ouvertes
/history - Historique des 10 derniers trades
/balance - Balance et capital disponible

🔧 <b>Contrôle:</b>
/status - État du système
/admin - Commandes administrateur

/help - Liste des commandes
"""
            self.send_telegram(message)

        elif command == '/admin':
            message = """
🔐 <b>COMMANDES ADMIN</b>

🔄 /update - Mettre à jour depuis GitHub et redémarrer
♻️ /restart - Redémarrer le bot
🧹 /cleanup - Fermer TOUTES les positions et ordres
🔍 /checkapi - Vérifier positions réelles sur Bitget API
🔥 /forceclose - Force fermeture avec Flash Close API
📜 /logs - Voir les derniers logs du bot
🐛 /debugrestart - Voir le log du dernier redémarrage
⏹️ /stop - Arrêter le bot (nécessite confirmation)
📊 /status - État système détaillé

⚠️ <b>Attention:</b> Ces commandes affectent le bot!
"""
            self.send_telegram(message)

        elif command == '/forceclose':
            self.send_telegram("🔥 <b>FORCE CLOSE - Flash Close API</b>\n\nFermeture de TOUTES les positions...")
            logger.info("Commande /forceclose reçue")

            try:
                closed_positions = []

                for pair in self.volatile_pairs:
                    positions = self.exchange.fetch_positions(symbols=[pair])
                    for pos in positions:
                        size = float(pos.get('contracts', 0))
                        if size > 0:
                            side = pos.get('side', '').lower()

                            logger.info(f"Force Close: {side.upper()} {pair} - {size} contrats")

                            # Utiliser Flash Close API
                            success = self.flash_close_position(pair, side)

                            if success:
                                closed_positions.append(f"✅ {side.upper()} {pair.split('/')[0]} ({size:.0f})")
                            else:
                                closed_positions.append(f"❌ Échec {side.upper()} {pair.split('/')[0]}")

                            time.sleep(1)

                if closed_positions:
                    message = f"""
🔥 <b>FORCE CLOSE TERMINÉ</b>

{chr(10).join(closed_positions)}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                    self.send_telegram(message)
                else:
                    self.send_telegram("✅ Aucune position à fermer")

            except Exception as e:
                error_msg = f"❌ Erreur /forceclose: {e}"
                logger.error(error_msg)
                self.send_telegram(error_msg)

        elif command == '/debugrestart':
            # Lire le log du script de redémarrage
            try:
                restart_log_path = Path('/tmp/bot_restart.log')
                if restart_log_path.exists():
                    log_content = restart_log_path.read_text()
                    # Prendre les 30 dernières lignes
                    log_lines = log_content.split('\n')[-30:]
                    log_text = '\n'.join(log_lines)

                    message = f"""
🐛 <b>LOG REDÉMARRAGE</b>

<pre>{log_text[:3000]}</pre>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                    self.send_telegram(message)
                else:
                    self.send_telegram("📝 Aucun log de redémarrage trouvé.\n\nLe bot n'a jamais utilisé /update ou /restart.")
            except Exception as e:
                self.send_telegram(f"❌ Erreur lecture log: {e}")

        elif command == '/cleanup':
            self.send_telegram("🧹 <b>NETTOYAGE FORCÉ...</b>\n\nFermeture de toutes les positions et ordres...")
            logger.info("Commande /cleanup reçue - nettoyage forcé")

            try:
                self.cleanup_all_positions_and_orders()

                # Vérification finale après 5 secondes
                time.sleep(5)
                final_check = []
                for pair in self.volatile_pairs:
                    real_pos = self.get_real_positions(pair)
                    if real_pos:
                        if real_pos.get('long'):
                            final_check.append(f"⚠️ LONG {pair.split('/')[0]} encore ouvert!")
                        if real_pos.get('short'):
                            final_check.append(f"⚠️ SHORT {pair.split('/')[0]} encore ouvert!")

                if final_check:
                    self.send_telegram(f"⚠️ Positions restantes:\n{chr(10).join(final_check)}\n\nRéessayez /cleanup ou utilisez /forceclose")
                else:
                    self.send_telegram("✅ Nettoyage terminé!\n\nToutes les positions sont fermées.\n\nLe bot continue.")
            except Exception as e:
                error_msg = f"❌ Erreur cleanup: {e}"
                logger.error(error_msg)
                self.send_telegram(error_msg)

        elif command == '/checkapi':
            # Vérifier positions réelles avec TOUTES les données API Bitget
            self.send_telegram("🔍 <b>VÉRIFICATION API BITGET...</b>")

            try:
                report = ["📊 <b>POSITIONS RÉELLES (API)</b>\n"]
                has_positions = False

                for pair in self.volatile_pairs:
                    real_pos = self.get_real_positions(pair)
                    if not real_pos:
                        continue

                    long_data = real_pos.get('long')
                    short_data = real_pos.get('short')

                    if not long_data and not short_data:
                        continue

                    has_positions = True
                    pair_name = pair.split('/')[0]
                    current_price = self.get_price(pair)

                    report.append(f"\n━━━━ <b>{pair_name}</b> ━━━━")
                    report.append(f"💰 Mark Price: ${current_price:.5f}\n")

                    # LONG - EN VERT
                    if long_data:
                        report.append(f"🟢 <b>LONG</b>")
                        report.append(f"🟢 Contrats: {long_data['size']:.0f}")
                        report.append(f"🟢 Entrée: ${long_data['entry_price']:.5f}")
                        report.append(f"🟢 Marge: {long_data['margin']:.7f} USDT")
                        report.append(f"🟢 P&L: {long_data['unrealized_pnl']:+.7f} USDT")
                        report.append(f"🟢 ROE: {long_data['pnl_percentage']:+.2f}%\n")

                    # SHORT - EN ROUGE
                    if short_data:
                        report.append(f"🔴 <b>SHORT</b>")
                        report.append(f"🔴 Contrats: {short_data['size']:.0f}")
                        report.append(f"🔴 Entrée: ${short_data['entry_price']:.5f}")
                        report.append(f"🔴 Marge: {short_data['margin']:.7f} USDT")
                        report.append(f"🔴 P&L: {short_data['unrealized_pnl']:+.7f} USDT")
                        report.append(f"🔴 ROE: {short_data['pnl_percentage']:+.2f}%")
                        liq = short_data.get('liquidation_price', 0)
                        if liq > 0:
                            report.append(f"🔴 💀 Liq: ${liq:.5f}")

                if not has_positions:
                    report.append("\n✅ Aucune position ouverte")

                report.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                self.send_telegram("\n".join(report))

            except Exception as e:
                self.send_telegram(f"❌ Erreur vérification API: {e}")

        elif command == '/logs':
            try:
                if not log_buffer:
                    self.send_telegram("📜 Aucun log disponible")
                    return

                # Prendre les 20 derniers logs
                recent_logs = list(log_buffer)[-20:]
                logs_text = "\n".join(recent_logs)

                # Tronquer si trop long (limite Telegram 4096 caractères)
                if len(logs_text) > 3500:
                    logs_text = logs_text[-3500:]
                    logs_text = "...\n" + logs_text

                message = f"""
📜 <b>DERNIERS LOGS</b>

<pre>{logs_text}</pre>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
            except Exception as e:
                self.send_telegram(f"❌ Erreur logs: {e}")

        elif command == '/status':
            # Status système détaillé
            try:
                # Uptime du système
                uptime_result = subprocess.run(['uptime'], capture_output=True, text=True)
                uptime = uptime_result.stdout.strip() if uptime_result.returncode == 0 else "N/A"

                # Mémoire disponible
                mem_result = subprocess.run(['free', '-h'], capture_output=True, text=True)
                mem_lines = mem_result.stdout.split('\n') if mem_result.returncode == 0 else []
                mem_info = mem_lines[1] if len(mem_lines) > 1 else "N/A"

                # Git status
                git_result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                          capture_output=True, text=True, cwd=Path(__file__).parent.parent)
                git_hash = git_result.stdout.strip() if git_result.returncode == 0 else "N/A"

                message = f"""
📊 <b>STATUS SYSTÈME</b>

🖥️ <b>Serveur:</b>
{uptime}

💾 <b>Mémoire:</b>
{mem_info}

📦 <b>Version:</b>
Git commit: {git_hash}

🤖 <b>Bot:</b>
Positions actives: {len(self.active_positions)}
Capital utilisé: ${self.capital_used:.0f}€
Session démarrée: {self.session_start_time.strftime('%H:%M:%S')}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
            except Exception as e:
                self.send_telegram(f"⚠️ Erreur status: {e}")

        elif command == '/update':
            logger.info("Commande /update reçue")
            self.send_telegram("🔄 <b>MISE À JOUR...</b>\n\n⚠️ Le bot va redémarrer.\n\nPatientez 20 secondes.")

            try:
                # Utiliser le script manage_local.sh
                manage_script = Path(__file__).parent.parent / 'manage_local.sh'

                if not manage_script.exists():
                    self.send_telegram("❌ Script manage_local.sh introuvable!\n\nUtilisez le raccourci Bureau à la place.")
                    logger.error("manage_local.sh not found")
                    return

                # Lancer le script en arrière-plan
                logger.info("Lancement manage_local.sh update")
                subprocess.Popen(['bash', str(manage_script), 'update'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               start_new_session=True)

                logger.info("Script lancé, arrêt de cette instance")
                
                sys.exit(0)  # Arrêter cette instance

            except Exception as e:
                error_msg = f"❌ Erreur /update: {e}"
                logger.error(error_msg)
                self.send_telegram(error_msg)

        elif command == '/restart':
            logger.info("Commande /restart reçue")
            self.send_telegram("♻️ <b>REDÉMARRAGE...</b>\n\n⚠️ Le bot va redémarrer.\n\nPatientez 20 secondes.")

            try:
                # Utiliser le script manage_local.sh
                manage_script = Path(__file__).parent.parent / 'manage_local.sh'

                if not manage_script.exists():
                    self.send_telegram("❌ Script manage_local.sh introuvable!\n\nUtilisez le raccourci Bureau.")
                    logger.error("manage_local.sh not found")
                    return

                # Lancer le script en arrière-plan
                logger.info("Lancement manage_local.sh restart")
                subprocess.Popen(['bash', str(manage_script), 'restart'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL,
                               start_new_session=True)

                logger.info("Script lancé, arrêt de cette instance")
                
                sys.exit(0)

            except Exception as e:
                error_msg = f"❌ Erreur /restart: {e}"
                logger.error(error_msg)
                self.send_telegram(error_msg)

        elif command.startswith('/stop'):
            # Demander confirmation
            if command == '/stop':
                message = """
⚠️ <b>CONFIRMATION REQUISE</b>

Êtes-vous sûr de vouloir arrêter le bot?

Pour confirmer, envoyez:
/stop CONFIRM

Le bot sera complètement arrêté et devra être relancé manuellement.
"""
                self.send_telegram(message)

            elif command == '/stop CONFIRM':
                self.send_telegram("⏹️ <b>ARRÊT DU BOT...</b>\n\nFermeture des positions et ordres...")

                # Nettoyer avant d'arrêter
                self.cleanup_all_positions_and_orders()

                self.send_telegram("🛑 Bot arrêté.\n\nPour redémarrer:\n- Via Telegram: /restart ou /update\n- Via Terminal: screen -S trading")

                time.sleep(2)
                subprocess.run(['screen', '-X', '-S', 'trading', 'quit'])
                sys.exit(0)

    def check_telegram_commands(self):
        """Vérifie et traite les commandes Telegram"""
        updates = self.get_telegram_updates()

        for update in updates:
            # Mettre à jour l'ID
            update_id = update.get('update_id', 0)
            self.last_telegram_update_id = max(self.last_telegram_update_id, update_id)

            # Vérifier si c'est un message texte
            message = update.get('message', {})
            text = message.get('text', '')
            chat_id = message.get('chat', {}).get('id')
            message_date = message.get('date', 0)  # Timestamp Unix

            # IGNORER LES VIEUX MESSAGES AU DÉMARRAGE (plus de 5 minutes)
            message_age = time.time() - message_date
            if message_age > 300:  # 5 minutes
                logger.info(f"Message ignoré (trop vieux): {text} (âge: {message_age:.0f}s)")
                continue

            # Vérifier que c'est bien notre chat
            if str(chat_id) == str(self.telegram_chat_id) and text.startswith('/'):
                logger.info(f"📲 Commande reçue: {text} (update_id: {update_id})")
                print(f"📲 Commande reçue: {text}")
                self.handle_telegram_command(text.strip())

        # Sauvegarder l'ID après traitement
        if updates:
            self.save_last_update_id()

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
                        'liquidation_price': float(pos.get('liquidationPrice') or 0),
                        'unrealized_pnl': float(pos.get('unrealizedPnl') or 0),
                        'pnl_percentage': float(pos.get('percentage') or 0),
                        'margin': float(pos.get('initialMargin') or 0),
                    }

            return result
        except Exception as e:
            print(f"❌ Erreur positions {symbol}: {e}")
            return None

    def format_price(self, price, pair):
        """Formate le prix selon la paire (ex: PEPE/SHIB ont besoin de plus de décimales)"""
        if price == 0:
            return "$0.0000"

        # Paires à petits prix (memecoins)
        if any(coin in pair for coin in ['PEPE', 'SHIB', 'FLOKI', 'BONK']):
            if price < 0.0001:
                return f"${price:.8f}"
            elif price < 0.01:
                return f"${price:.6f}"

        return f"${price:.4f}"

    def round_price(self, price, pair):
        """Arrondit le prix selon les règles Bitget (max décimales)"""
        # PEPE/SHIB/FLOKI/BONK : 8 décimales max
        if any(coin in pair for coin in ['PEPE', 'SHIB', 'FLOKI', 'BONK']):
            return round(price, 8)

        # DOGE et autres : 5 décimales max
        return round(price, 5)

    def verify_order_placed(self, order_id, symbol, max_retries=3):
        """
        Vérifie qu'un ordre a bien été placé sur l'exchange

        Returns:
            dict: Order data si succès, None si échec
        """
        for attempt in range(max_retries):
            try:
                  # Délai pour propagation
                order = self.exchange.fetch_order(order_id, symbol)

                # Vérifier que l'ordre est bien ouvert ou rempli
                if order['status'] in ['open', 'closed']:
                    return order
                else:
                    print(f"⚠️  Ordre {order_id[:8]}... statut inattendu: {order['status']}")

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Tentative {attempt+1}/{max_retries} vérification ordre: {e}")
                    time.sleep(1)
                else:
                    print(f"❌ Échec vérification ordre {order_id[:8]}...: {e}")
                    return None

        return None

    def calculate_breakeven_tp_price(self, position, real_pos_data, direction):
        """
        Calcule le prix de TP pour position doublée (utilise prix moyen)

        Args:
            position: HedgePosition object
            real_pos_data: Données réelles de la position depuis API
            direction: 'up' (prix a monté, SHORT doublé) ou 'down' (prix a descendu, LONG doublé)

        Returns:
            float: Prix du TP à 0.3% du prix moyen, ou None si pas de données
        """
        TP_PCT = 0.3  # TP fixe à 0.3%

        if direction == 'up':
            # Le short a été doublé, on veut fermer avec profit
            short_data = real_pos_data.get('short')
            if not short_data:
                logger.warning("calculate_breakeven_tp_price: Pas de données SHORT")
                return None

            # Prix moyen du short après doublement
            avg_entry = short_data.get('entry_price')
            if not avg_entry:
                logger.warning("calculate_breakeven_tp_price: entry_price SHORT manquant")
                return None

            # Pour un short, profit si prix descend → TP à -0.3%
            tp_price = avg_entry * (1 - TP_PCT / 100)
            return tp_price

        elif direction == 'down':
            # Le long a été doublé, on veut fermer avec profit
            long_data = real_pos_data.get('long')
            if not long_data:
                logger.warning("calculate_breakeven_tp_price: Pas de données LONG")
                return None

            # Prix moyen du long après doublement
            avg_entry = long_data.get('entry_price')
            if not avg_entry:
                logger.warning("calculate_breakeven_tp_price: entry_price LONG manquant")
                return None

            # Pour un long, profit si prix monte → TP à +0.3%
            tp_price = avg_entry * (1 + TP_PCT / 100)
            return tp_price

        return None

    def bitget_sign_request(self, timestamp, method, request_path, body=''):
        """Génère la signature pour les requêtes API Bitget"""
        message = str(timestamp) + method.upper() + request_path + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()

    def place_tpsl_order(self, symbol, plan_type, trigger_price, hold_side, size):
        """
        Place un vrai ordre TP/SL (plan order) sur Bitget via HTTP direct

        Args:
            symbol: Paire (ex: 'DOGE/USDT:USDT')
            plan_type: 'profit_plan' (TP) ou 'loss_plan' (SL)
            trigger_price: Prix de déclenchement
            hold_side: 'long' ou 'short' (position à fermer)
            size: Quantité

        Returns:
            dict: Order data ou None
        """
        try:
            # Convertir symbol au format Bitget (ex: DOGE/USDT:USDT → DOGEUSDT en majuscules)
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')

            # Arrondir le prix selon les règles Bitget
            trigger_price_rounded = self.round_price(trigger_price, symbol)

            # Endpoint et body
            endpoint = '/api/mix/v1/order/place-tpsl-order'
            body = {
                'symbol': symbol_bitget,
                'planType': plan_type,  # 'profit_plan' ou 'loss_plan'
                'triggerPrice': str(trigger_price_rounded),
                'triggerType': 'mark_price',
                'holdSide': hold_side,
                'size': str(round(size, 2)),  # Arrondir à 2 décimales
                'executePrice': '0'
            }
            body_json = json.dumps(body)

            # Timestamp et signature
            timestamp = str(int(time.time() * 1000))
            signature = self.bitget_sign_request(timestamp, 'POST', endpoint, body_json)

            # Headers
            headers = {
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.api_password,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'
            }

            # Requête HTTP
            url = f"https://api.bitget.com{endpoint}"
            response = requests.post(url, headers=headers, data=body_json, timeout=10)
            data = response.json()

            if data.get('code') == '00000':
                order_id = data.get('data', {}).get('orderId')
                print(f"✅ TP/SL {plan_type} placé: ID {order_id}")
                return {'id': order_id, 'info': data}
            else:
                print(f"❌ Erreur TP/SL API: {data}")
                return None

        except Exception as e:
            print(f"❌ Erreur placement TP/SL: {e}")
            return None

    def get_tpsl_order_history(self, symbol, limit=100):
        """
        Récupère l'HISTORIQUE des ordres TP/SL exécutés
        Utilise l'API V2 Bitget pour les trigger orders
        """
        try:
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '').lower()

            # Endpoint pour l'historique des ordres plan (V2)
            endpoint_path = '/api/v2/mix/order/orders-plan-history'

            # Récupérer les ordres des 10 dernières minutes (suffisant pour TP)
            end_time = str(int(time.time() * 1000))
            start_time = str(int(time.time() * 1000) - 10 * 60 * 1000)  # 10 minutes avant

            query_params = f'?productType=USDT-FUTURES&startTime={start_time}&endTime={end_time}&pageSize={limit}'

            # Timestamp et signature
            timestamp = str(int(time.time() * 1000))
            signature = self.bitget_sign_request(timestamp, 'GET', endpoint_path + query_params, '')

            # Headers
            headers = {
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.api_password,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'
            }

            # Requête HTTP
            url = f"https://api.bitget.com{endpoint_path}{query_params}"
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if data.get('code') == '00000':
                all_orders = data.get('data', {}).get('entrustedList', [])

                # DEBUG: Logger tous les ordres reçus pour voir les statuts
                logger.info(f"Historique TP/SL {symbol}: {len(all_orders)} ordres reçus")
                for order in all_orders[:3]:  # Logger les 3 premiers
                    logger.info(f"  Ordre: status={order.get('status')}, planType={order.get('planType')}, side={order.get('side')}")

                # Filtrer par symbol et statuts qui indiquent exécution
                # Statuts possibles: 'triggered', 'executed', 'filled', 'cancelled_by_trigger'
                executed_statuses = ['triggered', 'executed', 'filled', 'cancelled_by_trigger']

                symbol_orders = [
                    o for o in all_orders
                    if o.get('symbol', '').lower() == symbol_bitget
                    and o.get('status', '') in executed_statuses
                    and o.get('planType') == 'profit_plan'  # Seulement les TP
                ]

                logger.info(f"TP exécutés filtrés pour {symbol}: {len(symbol_orders)} ordres")
                return symbol_orders
            else:
                logger.warning(f"Réponse historique TP/SL: {data}")
                return []

        except Exception as e:
            logger.error(f"Erreur récupération historique TP/SL: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def check_tp_exists_via_order_detail(self, order_id, pair):
        """
        Vérifie si un TP existe en récupérant les détails de l'ordre
        Méthode fiable via presetStopSurplusPrice

        Args:
            order_id: ID de l'ordre TP
            pair: La paire (ex: 'DOGE/USDT:USDT')

        Returns:
            bool: True si TP existe et est actif, False sinon
        """
        try:
            if not order_id:
                return False

            logger.info(f"🔍 Vérification TP via order detail: {order_id[:8]}...")

            # Fetch order details via ccxt
            order = self.exchange.fetch_order(order_id, pair)

            # Vérifier si ordre existe et est actif
            if order['status'] == 'open':
                # Vérifier si presetStopSurplusPrice existe dans info
                order_info = order.get('info', {})
                preset_tp = order_info.get('presetStopSurplusPrice')

                if preset_tp:
                    logger.info(f"✅ TP actif détecté: trigger @ {preset_tp}")
                    return True
                else:
                    logger.warning(f"⚠️ Ordre actif mais pas de preset TP trouvé")
                    return False
            else:
                logger.info(f"⚠️ Ordre status: {order['status']} - TP non actif")
                return False

        except Exception as e:
            logger.error(f"Erreur vérification TP via order detail: {e}")
            return False

    def check_if_tp_was_executed(self, pair, side):
        """
        Vérifie si un TP a vraiment été exécuté (pas juste position fermée)
        Méthode améliorée avec logs détaillés et vérification multiple

        Args:
            pair: La paire (ex: 'DOGE/USDT:USDT')
            side: 'long' ou 'short'

        Returns:
            bool: True si TP a été exécuté, False sinon
        """
        try:
            logger.info(f"🔍 Vérification TP {side.upper()} pour {pair}")

            # 1. Vérifier dans l'historique des ordres plan
            history = self.get_tpsl_order_history(pair)

            # Chercher un TP récent (dans les dernières 60 secondes - étendu de 30s)
            current_time_ms = int(time.time() * 1000)

            # TP Long = sell_single, TP Short = buy_single
            expected_side = 'sell_single' if side == 'long' else 'buy_single'

            for order in history:
                # Vérifier si c'est un profit_plan du bon côté
                if order.get('planType') == 'profit_plan':
                    order_side = order.get('side', '').lower()

                    if order_side == expected_side:
                        # Vérifier si exécuté récemment (60 dernières secondes)
                        trigger_time = int(order.get('triggerTime', 0))
                        execute_time = int(order.get('executeTime', 0))
                        check_time = trigger_time or execute_time

                        if check_time > 0 and (current_time_ms - check_time) < 60000:
                            logger.info(f"✅ TP {side.upper()} confirmé via historique")
                            logger.info(f"   Status: {order.get('status')}, Exécuté il y a {(current_time_ms - check_time) / 1000:.1f}s")
                            return True

            # 2. Vérifier que l'ordre TP n'est plus dans les ordres pending
            pending_orders = self.get_tpsl_orders(pair)
            tp_still_pending = False

            logger.info(f"   Ordres pending: {len(pending_orders)}")

            for order in pending_orders:
                if order.get('planType') == 'profit_plan':
                    order_side = order.get('side', '').lower()
                    if order_side == expected_side:
                        tp_still_pending = True
                        logger.info(f"   TP {side.upper()} toujours pending - NIET exécuté")
                        break

            if not tp_still_pending:
                logger.info(f"✅ TP {side.upper()} plus dans pending - Probablement exécuté")
                return True

            # 3. Dernière vérification: chercher dans les ordres récents (fallback)
            logger.info(f"⚠️ TP {side.upper()} ni dans historique ni disparu du pending")
            return False

        except Exception as e:
            logger.error(f"Erreur vérification TP: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # En cas d'erreur, retourner False pour éviter faux positifs
            return False

    def get_tpsl_orders(self, symbol):
        """Récupère les ordres TP/SL plan en cours via HTTP direct"""
        try:
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')  # Majuscules (DOGEUSDT)

            # Endpoint (sans query params dans le path pour la signature)
            endpoint_path = '/api/v2/mix/order/orders-plan-pending'
            query_params = f'?productType=USDT-FUTURES'  # Sans planType (récupérer tous)

            # Timestamp et signature
            timestamp = str(int(time.time() * 1000))
            signature = self.bitget_sign_request(timestamp, 'GET', endpoint_path + query_params, '')

            # Headers
            headers = {
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.api_password,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'
            }

            # Requête HTTP
            url = f"https://api.bitget.com{endpoint_path}{query_params}"
            response = requests.get(url, headers=headers, timeout=10)
            data = response.json()

            if data.get('code') == '00000':
                all_orders = data.get('data', {}).get('entrustedList', [])
                # Filtrer par symbol
                symbol_orders = [o for o in all_orders if o.get('symbol', '').lower() == symbol_bitget]
                return symbol_orders
            else:
                print(f"⚠️ Réponse TP/SL: {data}")
                return []

        except Exception as e:
            print(f"⚠️ Erreur récupération TP/SL: {e}")
            return []

    def get_total_fees(self):
        """
        Récupère le total RÉEL des frais payés depuis le démarrage du bot
        Appels API UNIQUEMENT, PAS d'estimation
        """
        try:
            total_fees = 0
            fee_details = []

            # Timestamp de début de session (en millisecondes)
            session_start_ms = int(self.session_start_time.timestamp() * 1000)

            logger.info(f"Récupération frais depuis {self.session_start_time.strftime('%H:%M:%S')}")

            for pair in self.volatile_pairs:
                try:
                    # Récupérer TOUS les trades depuis le début de la session
                    trades = self.exchange.fetch_my_trades(pair, since=session_start_ms, limit=500)

                    pair_fees = 0
                    for trade in trades:
                        fee = trade.get('fee', {})
                        if fee and fee.get('cost'):
                            fee_cost = float(fee['cost'])
                            total_fees += fee_cost
                            pair_fees += fee_cost

                    if pair_fees > 0:
                        logger.info(f"Frais {pair.split('/')[0]}: {pair_fees:.7f} USDT ({len(trades)} trades)")
                        fee_details.append(f"{pair.split('/')[0]}: {pair_fees:.7f}")

                except Exception as e:
                    logger.warning(f"Impossible de récupérer frais pour {pair}: {e}")

            logger.info(f"Total frais session: {total_fees:.7f} USDT")
            return total_fees

        except Exception as e:
            logger.error(f"Erreur get_total_fees: {e}")
            return 0

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
        """Annule un ordre (LIMIT ou TP/SL plan) avec logging détaillé"""
        if not order_id:
            logger.warning(f"Tentative annulation ordre None sur {symbol}")
            return True

        logger.info(f"Annulation ordre {order_id[:12]}... sur {symbol}")

        # Essayer d'annuler comme ordre LIMIT standard
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Ordre LIMIT {order_id[:12]}... annulé")
            print(f"🗑️  Ordre LIMIT {order_id[:8]}... annulé")
            return True
        except Exception as e:
            error_msg = str(e)
            # Si ordre n'existe pas comme LIMIT, essayer comme TP/SL plan
            if '40768' in error_msg or 'does not exist' in error_msg.lower():
                logger.info(f"Ordre pas trouvé comme LIMIT, essai comme TP/SL plan...")
                # Essayer d'annuler comme TP/SL plan
                try:
                    result = self.cancel_tpsl_order(order_id, symbol)
                    if result:
                        logger.info(f"✅ Ordre TP/SL {order_id[:12]}... annulé")
                    return result
                except:
                    logger.info(f"ℹ️ Ordre {order_id[:12]}... déjà exécuté/annulé")
                    print(f"ℹ️  Ordre {order_id[:8]}... déjà exécuté/annulé")
                    return True
            else:
                logger.error(f"⚠️ Erreur annulation {order_id[:12]}: {e}")
                print(f"⚠️  Erreur annulation: {e}")
                return False

    def cancel_tpsl_order(self, order_id, symbol):
        """Annule un ordre TP/SL plan"""
        try:
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')  # Majuscules (DOGEUSDT)

            endpoint = '/api/v2/mix/order/cancel-plan-order'
            body = {
                'productType': 'USDT-FUTURES',  # Majuscules
                'symbol': symbol_bitget,
                'marginCoin': 'USDT',
                'orderId': order_id,
                'planType': 'pos_profit'  # pos_profit au lieu de profit_plan
            }
            body_json = json.dumps(body)

            timestamp = str(int(time.time() * 1000))
            signature = self.bitget_sign_request(timestamp, 'POST', endpoint, body_json)

            headers = {
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.api_password,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'
            }

            url = f"https://api.bitget.com{endpoint}"
            response = requests.post(url, headers=headers, data=body_json, timeout=10)
            data = response.json()

            if data.get('code') == '00000':
                print(f"🗑️  TP/SL {order_id[:8]}... annulé")
                return True
            else:
                print(f"⚠️ Erreur annulation TP/SL: {data}")
                return False

        except Exception as e:
            print(f"⚠️ Erreur annulation TP/SL: {e}")
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
                params={'tradeSide': 'open', 'holdSide': 'long'}
            )
            print(f"✅ Long ouvert: {size:.4f}")

            short_order = self.exchange.create_order(
                symbol=pair, type='market', side='sell', amount=size,
                params={'tradeSide': 'open', 'holdSide': 'short'}
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

            print(f"📊 Prix entrée Long (API): {self.format_price(entry_long, pair)}")
            print(f"📊 Prix entrée Short (API): {self.format_price(entry_short, pair)}")

            # Créer position tracking
            position = HedgePosition(pair, self.INITIAL_MARGIN, entry_long, entry_short)

            # Stocker tailles initiales pour détection doublements (CAS 3)
            position.long_size_previous = real_pos['long']['size']
            position.short_size_previous = real_pos['short']['size']

            self.active_positions[pair] = position

            # Attendre 3s avant de placer les TP (Bitget refuse si trop rapide)
            print("\n⏳ Attente 3s avant placement TP...")
            time.sleep(3)

            # 2. Placer les 4 ordres limites avec vérification
            print("\n2️⃣ Placement des 4 ordres limites...")

            # Niveau initial = Fib 1 (0.3%) pour TOUS les ordres
            next_trigger_pct = position.fib_levels[1]  # Fib 1 = 0.3%

            # Récupérer le prix actuel du marché MAINTENANT
            current_market_price = self.get_price(pair)

            print(f"\n🔍 DEBUG PLACEMENT ORDRES:")
            print(f"   Prix entrée Long (API): {self.format_price(entry_long, pair)}")
            print(f"   Prix entrée Short (API): {self.format_price(entry_short, pair)}")
            print(f"   Prix marché ACTUEL: {self.format_price(current_market_price, pair)}")
            print(f"   Variation depuis entrée: {((current_market_price - entry_long) / entry_long * 100):+.4f}%")

            # Calculer prix des triggers
            tp_long_price = entry_long * (1 + next_trigger_pct / 100)
            tp_short_price = entry_short * (1 - next_trigger_pct / 100)
            double_short_price = tp_long_price  # MÊME PRIX que TP Long
            double_long_price = tp_short_price  # MÊME PRIX que TP Short

            print(f"\n   Ordres qui vont être placés:")
            print(f"   TP Long @ {self.format_price(tp_long_price, pair)} (+{next_trigger_pct}%)")
            print(f"   TP Short @ {self.format_price(tp_short_price, pair)} (-{next_trigger_pct}%)")
            print(f"   Distance TP Long: {((tp_long_price - current_market_price) / current_market_price * 100):+.4f}%")
            print(f"   Distance TP Short: {((tp_short_price - current_market_price) / current_market_price * 100):+.4f}%")

            # a) TP Long (VRAI ordre TP/SL Bitget)
            try:
                tp_long_order = self.place_tpsl_order(
                    symbol=pair,
                    plan_type='profit_plan',
                    trigger_price=tp_long_price,
                    hold_side='long',
                    size=size
                )
                if tp_long_order and tp_long_order.get('id'):
                    position.orders['tp_long'] = tp_long_order['id']
                    print(f"✅ TP Long (VRAI TP) @ {self.format_price(tp_long_price, pair)} (+{next_trigger_pct}%)")
                else:
                    print(f"❌ Échec placement TP Long")
                    return False
            except Exception as e:
                print(f"❌ Erreur TP Long: {e}")
                return False

            # b) Doubler Short (si prix monte - MÊME PRIX)
            try:
                double_short_order = self.exchange.create_order(
                    symbol=pair, type='limit', side='sell', amount=size * 2, price=double_short_price,
                    params={'tradeSide': 'open', 'holdSide': 'short'}  # Ouvrir SHORT
                )
                verified = self.verify_order_placed(double_short_order['id'], pair)
                if verified:
                    position.orders['double_short'] = double_short_order['id']
                    print(f"✅ Doubler Short @ {self.format_price(double_short_price, pair)}")
                else:
                    print(f"❌ Échec placement Doubler Short")
                    return False
            except Exception as e:
                print(f"❌ Erreur Doubler Short: {e}")
                return False

            # c) TP Short (VRAI ordre TP/SL Bitget)
            try:
                tp_short_order = self.place_tpsl_order(
                    symbol=pair,
                    plan_type='profit_plan',
                    trigger_price=tp_short_price,
                    hold_side='short',
                    size=size
                )
                if tp_short_order and tp_short_order.get('id'):
                    position.orders['tp_short'] = tp_short_order['id']
                    print(f"✅ TP Short (VRAI TP) @ {self.format_price(tp_short_price, pair)} (-{next_trigger_pct}%)")
                else:
                    print(f"❌ Échec placement TP Short")
                    return False
            except Exception as e:
                print(f"❌ Erreur TP Short: {e}")
                return False

            # d) Doubler Long (si prix descend - MÊME PRIX)
            try:
                double_long_order = self.exchange.create_order(
                    symbol=pair, type='limit', side='buy', amount=size * 2, price=double_long_price,
                    params={'tradeSide': 'open', 'holdSide': 'long'}  # Ouvrir LONG
                )
                verified = self.verify_order_placed(double_long_order['id'], pair)
                if verified:
                    position.orders['double_long'] = double_long_order['id']
                    print(f"✅ Doubler Long @ {self.format_price(double_long_price, pair)}")
                else:
                    print(f"❌ Échec placement Doubler Long")
                    return False
            except Exception as e:
                print(f"❌ Erreur Doubler Long: {e}")
                return False

            self.capital_used += self.INITIAL_MARGIN * 2
            self.available_pairs.remove(pair)

            # Envoyer les messages détaillés séparés pour chaque position
            self.send_detailed_position_update(pair, position)

            return True

        except Exception as e:
            print(f"❌ Erreur ouverture: {e}")
            return False

    def detect_fib_level_from_margin(self, margin):
        """Détecte niveau Fibonacci depuis marge (1→3→9→27→81 USDT)"""
        if margin < 2:
            return 0
        elif margin < 6:
            return 1
        elif margin < 18:
            return 2
        elif margin < 54:
            return 3
        elif margin < 162:
            return 4
        else:
            return 5

    def place_orders_for_long(self, pair, position, long_data):
        """RATTRAPAGE: Place TP + Double pour Long"""
        size_long = long_data['size']
        entry_long = long_data['entry_price']

        next_level = position.long_fib_level + 1
        if next_level >= len(position.fib_levels):
            return

        next_pct = position.fib_levels[next_level]

        # TP 0.3% fixe, Double niveau Fib
        tp_price = entry_long * 1.003
        double_price = entry_long * (1 - next_pct / 100)

        # TP Long
        if not position.orders['tp_long']:
            try:
                tp = self.place_tpsl_order(pair, 'profit_plan', tp_price, 'long', size_long)
                if tp and tp.get('id'):
                    position.orders['tp_long'] = tp['id']
                    logger.info(f"🔧 RATTRAPAGE TP Long @ {self.format_price(tp_price, pair)}")
            except Exception as e:
                logger.error(f"Rattrapage TP Long: {e}")

        # Double Long
        if not position.orders['double_long']:
            try:
                double = self.exchange.create_order(
                    pair, 'limit', 'buy', size_long * 2, double_price,
                    params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                if double and double.get('id'):
                    position.orders['double_long'] = double['id']
                    logger.info(f"🔧 RATTRAPAGE Double Long @ {self.format_price(double_price, pair)}")
            except Exception as e:
                logger.error(f"Rattrapage Double Long: {e}")

    def place_orders_for_short(self, pair, position, short_data):
        """RATTRAPAGE: Place TP + Double pour Short"""
        size_short = short_data['size']
        entry_short = short_data['entry_price']

        next_level = position.short_fib_level + 1
        if next_level >= len(position.fib_levels):
            return

        next_pct = position.fib_levels[next_level]

        # TP 0.3% fixe, Double niveau Fib
        tp_price = entry_short * 0.997
        double_price = entry_short * (1 + next_pct / 100)

        # TP Short
        if not position.orders['tp_short']:
            try:
                tp = self.place_tpsl_order(pair, 'profit_plan', tp_price, 'short', size_short)
                if tp and tp.get('id'):
                    position.orders['tp_short'] = tp['id']
                    logger.info(f"🔧 RATTRAPAGE TP Short @ {self.format_price(tp_price, pair)}")
            except Exception as e:
                logger.error(f"Rattrapage TP Short: {e}")

        # Double Short
        if not position.orders['double_short']:
            try:
                double = self.exchange.create_order(
                    pair, 'limit', 'sell', size_short * 2, double_price,
                    params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                if double and double.get('id'):
                    position.orders['double_short'] = double['id']
                    logger.info(f"🔧 RATTRAPAGE Double Short @ {self.format_price(double_price, pair)}")
            except Exception as e:
                logger.error(f"Rattrapage Double Short: {e}")

    def verify_and_fix_missing_orders(self, pair, position):
        """
        RATTRAPAGE COMPLET: Vérifie ordres RÉELS sur API Bitget
        Compare avec mémoire, replace si manquants ou invalides
        """
        try:
            real_pos = self.get_real_positions(pair)
            if not real_pos:
                return

            long_data = real_pos.get('long')
            short_data = real_pos.get('short')

            # Détecter + corriger niveaux Fib
            if long_data:
                detected = self.detect_fib_level_from_margin(long_data['margin'])
                if detected != position.long_fib_level:
                    logger.info(f"🔄 LONG Fib: {position.long_fib_level} → {detected}")
                    position.long_fib_level = detected

            if short_data:
                detected = self.detect_fib_level_from_margin(short_data['margin'])
                if detected != position.short_fib_level:
                    logger.info(f"🔄 SHORT Fib: {position.short_fib_level} → {detected}")
                    position.short_fib_level = detected

            # VÉRIFIER ORDRES RÉELS SUR L'API BITGET (pas juste mémoire)
            try:
                # Ordres LIMIT (Double Long/Short)
                limit_orders = self.exchange.fetch_open_orders(symbol=pair)
                limit_order_ids = [o['id'] for o in limit_orders]

                # Ordres TP/SL plan
                tpsl_orders = self.get_tpsl_orders(pair)
                tpsl_order_ids = [o.get('planId') or o.get('orderId') for o in tpsl_orders] if tpsl_orders else []

            except Exception as e:
                logger.error(f"Erreur récupération ordres API: {e}")
                return

            # Vérifier chaque ordre stocké vs API réelle
            missing = []

            if long_data:
                tp_long_id = position.orders.get('tp_long')
                if not tp_long_id or tp_long_id not in tpsl_order_ids:
                    missing.append('tp_long')
                    position.orders['tp_long'] = None  # Reset mémoire

                double_long_id = position.orders.get('double_long')
                if not double_long_id or double_long_id not in limit_order_ids:
                    missing.append('double_long')
                    position.orders['double_long'] = None  # Reset mémoire

            if short_data:
                tp_short_id = position.orders.get('tp_short')
                if not tp_short_id or tp_short_id not in tpsl_order_ids:
                    missing.append('tp_short')
                    position.orders['tp_short'] = None  # Reset mémoire

                double_short_id = position.orders.get('double_short')
                if not double_short_id or double_short_id not in limit_order_ids:
                    missing.append('double_short')
                    position.orders['double_short'] = None  # Reset mémoire

            # DEBUG: Afficher état
            logger.info(f"[RATTRAPAGE] Ordres API réels: LIMIT={len(limit_order_ids)}, TPSL={len(tpsl_order_ids)}")

            # Replacer si manquants
            if missing:
                logger.warning(f"⚠️ {pair}: {len(missing)} ordres manquants/invalides: {missing}")
                print(f"🔧 RATTRAPAGE {pair}: {missing}")

                if 'tp_long' in missing or 'double_long' in missing:
                    logger.info(f"Replacement ordres LONG...")
                    self.place_orders_for_long(pair, position, long_data)

                if 'tp_short' in missing or 'double_short' in missing:
                    logger.info(f"Replacement ordres SHORT...")
                    self.place_orders_for_short(pair, position, short_data)

        except Exception as e:
            logger.error(f"Erreur verify_and_fix: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_tp_long_executed(self, pair, position):
        """
        ✅ ÉVÉNEMENT 1: TP LONG EXÉCUTÉ

        Actions (4 seulement):
        1. Annuler FIBO LONG (l'ordre LIMIT de doublement)
        2. Réouvrir Long en MARKET
        3. Placer NOUVEAU TP Long
        4. Placer NOUVEAU FIBO Long (Fib 1)
        """
        print(f"\n🔔 HANDLE_TP_LONG_EXECUTED START - {pair}")
        logger.info(f"🔔 TP LONG EXÉCUTÉ - {pair}")

        try:
            # ✅ 1. Annuler FIBO LONG (double_long LIMIT)
            print(f"   [1/4] Annuler Double Long LIMIT...")
            if position.orders.get('double_long'):
                order_id = position.orders['double_long']
                print(f"       Order ID: {order_id}")
                result = self.cancel_order(order_id, pair)
                print(f"       Résultat: {result}")
                position.orders['double_long'] = None
                logger.info(f"   ✓ Annulé Double Long LIMIT: {order_id}")
            else:
                print(f"       ⚠️ Pas d'ordre double_long trouvé!")
                logger.warning(f"   ⚠️ Pas d'ordre double_long pour annuler")

            # ✅ 2. Réouvrir Long en MARKET
            print(f"   [2/4] Réouvrir Long MARKET...")
            current_price = self.get_price(pair)
            print(f"       Prix: {current_price}")
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size_long = notional / current_price
            print(f"       Size: {size_long}")

            try:
                long_order = self.exchange.create_order(
                    symbol=pair, type='market', side='buy', amount=size_long,
                    params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                print(f"       ✓ Ordre créé: {long_order.get('id')}")
                logger.info(f"   ✓ Réouvert Long MARKET @ {self.format_price(current_price, pair)}")
            except Exception as e:
                print(f"       ❌ ERREUR créer ordre: {e}")
                logger.error(f"   ❌ Erreur création ordre MARKET: {e}")
                return

            # Attendre puis récupérer position réelle
            print(f"   [2bis] Attente 2s + récupération position...")
            time.sleep(2)
            real_pos = self.get_real_positions(pair)
            print(f"       Real pos: {real_pos}")

            if not real_pos or not real_pos.get('long'):
                print(f"       ❌ Impossible de récupérer Long après réouverture")
                logger.error(f"❌ Impossible de récupérer Long après réouverture")
                return

            entry_long = real_pos['long']['entry_price']
            size_long_real = real_pos['long']['size']
            print(f"       Entry: {entry_long}, Size: {size_long_real}")

            position.entry_price_long = entry_long
            position.long_open = True
            position.long_fib_level = 0
            position.long_margin_previous = real_pos['long']['margin']

            # ✅ 3. Placer NOUVEAU TP Long (0.3% fixe)
            print(f"   [3/4] Placer NOUVEAU TP Long...")
            time.sleep(1)
            TP_FIXE = 0.3
            tp_long_price = entry_long * (1 + TP_FIXE / 100)
            print(f"       TP Price: {tp_long_price}")

            tp_order = self.place_tpsl_order(
                symbol=pair,
                plan_type='profit_plan',
                trigger_price=tp_long_price,
                hold_side='long',
                size=size_long_real
            )
            print(f"       TP Order Result: {tp_order}")

            if tp_order and tp_order.get('id'):
                position.orders['tp_long'] = tp_order['id']
                print(f"       ✓ TP Long créé: {tp_order.get('id')}")
                logger.info(f"   ✓ Nouveau TP Long @ {self.format_price(tp_long_price, pair)} (+{TP_FIXE}%)")
            else:
                print(f"       ⚠️ TP Long échoué!")

            # ✅ 4. Placer NOUVEAU FIBO Long (Fib 1 = 0.3%)
            print(f"   [4/4] Placer NOUVEAU FIBO Long...")
            time.sleep(1)
            next_pct = position.fib_levels[1]
            fibo_long_price = entry_long * (1 - next_pct / 100)
            print(f"       Fibo Price: {fibo_long_price}")

            try:
                fibo_order = self.exchange.create_order(
                    symbol=pair, type='limit', side='buy', amount=size_long_real * 2,
                    price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                print(f"       Fibo Order: {fibo_order}")

                if fibo_order and fibo_order.get('id'):
                    position.orders['double_long'] = fibo_order['id']
                    print(f"       ✓ Fibo Long créé: {fibo_order.get('id')}")
                    logger.info(f"   ✓ Nouveau Fibo Long @ {self.format_price(fibo_long_price, pair)} (-{next_pct}%, Fib 1)")
            except Exception as e:
                print(f"       ❌ ERREUR Fibo: {e}")
                logger.error(f"   ❌ Erreur Fibo Long: {e}")

            position.long_size_previous = size_long_real
            print(f"🔔 HANDLE_TP_LONG_EXECUTED DONE\n")

        except Exception as e:
            print(f"❌ EXCEPTION handle_tp_long_executed: {e}")
            logger.error(f"❌ Erreur handle_tp_long_executed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(traceback.format_exc())

    def handle_tp_short_executed(self, pair, position):
        """
        ✅ ÉVÉNEMENT 2: TP SHORT EXÉCUTÉ

        Actions (4 seulement):
        1. Annuler FIBO SHORT (l'ordre LIMIT de doublement)
        2. Réouvrir Short en MARKET
        3. Placer NOUVEAU TP Short
        4. Placer NOUVEAU FIBO Short (Fib 1)
        """
        logger.info(f"🔔 TP SHORT EXÉCUTÉ - {pair}")

        try:
            # ✅ 1. Annuler FIBO SHORT (double_short LIMIT)
            if position.orders.get('double_short'):
                self.cancel_order(position.orders['double_short'], pair)
                position.orders['double_short'] = None
                logger.info(f"   ✓ Annulé Double Short LIMIT")

            # ✅ 2. Réouvrir Short en MARKET
            current_price = self.get_price(pair)
            notional = self.INITIAL_MARGIN * self.LEVERAGE
            size_short = notional / current_price

            short_order = self.exchange.create_order(
                symbol=pair, type='market', side='sell', amount=size_short,
                params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            logger.info(f"   ✓ Réouvert Short MARKET @ {self.format_price(current_price, pair)}")

            # Attendre puis récupérer position réelle
            time.sleep(2)
            real_pos = self.get_real_positions(pair)
            if not real_pos or not real_pos.get('short'):
                logger.error(f"❌ Impossible de récupérer Short après réouverture")
                return

            entry_short = real_pos['short']['entry_price']
            size_short_real = real_pos['short']['size']
            position.entry_price_short = entry_short
            position.short_open = True
            position.short_fib_level = 0  # Réinitialisé à Fib 0
            position.short_margin_previous = real_pos['short']['margin']  # Mettre à jour marge

            # ✅ 3. Placer NOUVEAU TP Short (0.3% fixe)
            time.sleep(1)
            TP_FIXE = 0.3
            tp_short_price = entry_short * (1 - TP_FIXE / 100)

            tp_order = self.place_tpsl_order(
                symbol=pair,
                plan_type='profit_plan',
                trigger_price=tp_short_price,
                hold_side='short',
                size=size_short_real
            )
            if tp_order and tp_order.get('id'):
                position.orders['tp_short'] = tp_order['id']
                logger.info(f"   ✓ Nouveau TP Short @ {self.format_price(tp_short_price, pair)} (-{TP_FIXE}%)")

            # ✅ 4. Placer NOUVEAU FIBO Short (Fib 1 = 0.3%)
            time.sleep(1)
            next_pct = position.fib_levels[1]  # Fib 1 = 0.3%
            fibo_short_price = entry_short * (1 + next_pct / 100)

            fibo_order = self.exchange.create_order(
                symbol=pair, type='limit', side='sell', amount=size_short_real * 2,
                price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
            )
            if fibo_order and fibo_order.get('id'):
                position.orders['double_short'] = fibo_order['id']
                logger.info(f"   ✓ Nouveau Fibo Short @ {self.format_price(fibo_short_price, pair)} (+{next_pct}%, Fib 1)")

            position.short_size_previous = size_short_real

        except Exception as e:
            logger.error(f"❌ Erreur handle_tp_short_executed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_fib_long_executed(self, pair, position, size_before, size_after):
        """
        ✅ ÉVÉNEMENT 3: FIBO LONG EXÉCUTÉ

        Actions (4 seulement):
        1. Annuler TP LONG + Double LONG (ordres anciens)
        2. Augmenter Fib level (+1)
        3. Placer NOUVEAU TP Long (au prix moyen)
        4. Placer NOUVEAU Fibo Long (niveau suivant)
        """
        logger.info(f"⚡ FIBO LONG EXÉCUTÉ: {size_before:.0f} → {size_after:.0f} contrats")

        try:
            # ✅ 1. Annuler TP LONG + Double LONG (ordres anciens)
            if position.orders.get('tp_long'):
                self.cancel_order(position.orders['tp_long'], pair)
                position.orders['tp_long'] = None
                logger.info(f"   ✓ Annulé TP Long")

            if position.orders.get('double_long'):
                self.cancel_order(position.orders['double_long'], pair)
                position.orders['double_long'] = None
                logger.info(f"   ✓ Annulé Double Long")

            # Récupérer position réelle depuis API
            real_pos = self.get_real_positions(pair)
            if not real_pos or not real_pos.get('long'):
                logger.error(f"❌ Long data manquant après doublement")
                return

            entry_long_moyen = real_pos['long']['entry_price']
            size_long_total = real_pos['long']['size']

            # ✅ 2. Augmenter Fib level (+1)
            position.long_fib_level += 1
            position.entry_price_long = entry_long_moyen
            logger.info(f"   ✓ Fib level: {position.long_fib_level - 1} → {position.long_fib_level}")

            # ✅ 3. Placer NOUVEAU TP Long (0.3% fixe au prix moyen)
            time.sleep(1)
            TP_FIXE = 0.3
            tp_long_price = entry_long_moyen * (1 + TP_FIXE / 100)

            tp_order = self.place_tpsl_order(
                symbol=pair,
                plan_type='profit_plan',
                trigger_price=tp_long_price,
                hold_side='long',
                size=size_long_total
            )
            if tp_order and tp_order.get('id'):
                position.orders['tp_long'] = tp_order['id']
                logger.info(f"   ✓ Nouveau TP Long @ {self.format_price(tp_long_price, pair)} (+{TP_FIXE}%, {size_long_total:.0f} contrats)")

            # ✅ 4. Placer NOUVEAU Fibo Long (niveau suivant)
            time.sleep(1)
            next_level = position.long_fib_level + 1
            if next_level < len(position.fib_levels):
                next_pct = position.fib_levels[next_level]
                fibo_long_price = entry_long_moyen * (1 - next_pct / 100)

                fibo_order = self.exchange.create_order(
                    symbol=pair, type='limit', side='buy', amount=size_long_total * 2,
                    price=fibo_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                )
                if fibo_order and fibo_order.get('id'):
                    position.orders['double_long'] = fibo_order['id']
                    logger.info(f"   ✓ Nouveau Fibo Long @ {self.format_price(fibo_long_price, pair)} (-{next_pct}%, Fib {next_level})")

            position.long_size_previous = size_long_total

        except Exception as e:
            logger.error(f"❌ Erreur handle_fib_long_executed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def handle_fib_short_executed(self, pair, position, size_before, size_after):
        """
        ✅ ÉVÉNEMENT 4: FIBO SHORT EXÉCUTÉ

        Actions (4 seulement):
        1. Annuler TP SHORT + Double SHORT (ordres anciens)
        2. Augmenter Fib level (+1)
        3. Placer NOUVEAU TP Short (au prix moyen)
        4. Placer NOUVEAU Fibo Short (niveau suivant)
        """
        logger.info(f"⚡ FIBO SHORT EXÉCUTÉ: {size_before:.0f} → {size_after:.0f} contrats")

        try:
            # ✅ 1. Annuler TP SHORT + Double SHORT (ordres anciens)
            if position.orders.get('tp_short'):
                self.cancel_order(position.orders['tp_short'], pair)
                position.orders['tp_short'] = None
                logger.info(f"   ✓ Annulé TP Short")

            if position.orders.get('double_short'):
                self.cancel_order(position.orders['double_short'], pair)
                position.orders['double_short'] = None
                logger.info(f"   ✓ Annulé Double Short")

            # Récupérer position réelle depuis API
            real_pos = self.get_real_positions(pair)
            if not real_pos or not real_pos.get('short'):
                logger.error(f"❌ Short data manquant après doublement")
                return

            entry_short_moyen = real_pos['short']['entry_price']
            size_short_total = real_pos['short']['size']

            # ✅ 2. Augmenter Fib level (+1)
            position.short_fib_level += 1
            position.entry_price_short = entry_short_moyen
            logger.info(f"   ✓ Fib level: {position.short_fib_level - 1} → {position.short_fib_level}")

            # ✅ 3. Placer NOUVEAU TP Short (0.3% fixe au prix moyen)
            time.sleep(1)
            TP_FIXE = 0.3
            tp_short_price = entry_short_moyen * (1 - TP_FIXE / 100)

            tp_order = self.place_tpsl_order(
                symbol=pair,
                plan_type='profit_plan',
                trigger_price=tp_short_price,
                hold_side='short',
                size=size_short_total
            )
            if tp_order and tp_order.get('id'):
                position.orders['tp_short'] = tp_order['id']
                logger.info(f"   ✓ Nouveau TP Short @ {self.format_price(tp_short_price, pair)} (-{TP_FIXE}%, {size_short_total:.0f} contrats)")

            # ✅ 4. Placer NOUVEAU Fibo Short (niveau suivant)
            time.sleep(1)
            next_level = position.short_fib_level + 1
            if next_level < len(position.fib_levels):
                next_pct = position.fib_levels[next_level]
                fibo_short_price = entry_short_moyen * (1 + next_pct / 100)

                fibo_order = self.exchange.create_order(
                    symbol=pair, type='limit', side='sell', amount=size_short_total * 2,
                    price=fibo_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
                )
                if fibo_order and fibo_order.get('id'):
                    position.orders['double_short'] = fibo_order['id']
                    logger.info(f"   ✓ Nouveau Fibo Short @ {self.format_price(fibo_short_price, pair)} (+{next_pct}%, Fib {next_level})")

            position.short_size_previous = size_short_total

        except Exception as e:
            logger.error(f"❌ Erreur handle_fib_short_executed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # ============================================================================
    # MESSAGES TELEGRAM PAR POSITION
    # ============================================================================

    def send_position_message(self, pair, position):
        """
        Crée et envoie 1 message Telegram par position
        Format: Prix | LONG | SHORT | ORDRES ACTIFS
        """
        try:
            current_price = self.get_price(pair)
            if not current_price:
                return

            real_pos = self.get_real_positions(pair)
            if not real_pos:
                return

            pair_name = pair.split('/')[0]

            # === HEADER ===
            message = f"📊 <b>{pair_name}</b> | 💰 {self.format_price(current_price, pair)}\n"

            # === LONG ===
            if real_pos.get('long'):
                long_data = real_pos['long']
                message += f"🟢 LONG | {long_data['size']:.0f} @ {self.format_price(long_data['entry_price'], pair)} | "
                message += f"Marge: {long_data['margin']:.2f} | P&L: {long_data['unrealized_pnl']:+.2f}\n"
            else:
                message += f"🟢 LONG | Fermé\n"

            # === SHORT ===
            if real_pos.get('short'):
                short_data = real_pos['short']
                message += f"🔴 SHORT | {short_data['size']:.0f} @ {self.format_price(short_data['entry_price'], pair)} | "
                message += f"Marge: {short_data['margin']:.2f} | P&L: {short_data['unrealized_pnl']:+.2f}\n"
            else:
                message += f"🔴 SHORT | Fermé\n"

            # === ORDRES (AFFICHER LES PRIX RÉELS) ===
            message += f"\n📋 <b>Ordres Actifs:</b>\n"

            # Récupérer les ordres TP/SL RÉELS depuis Bitget
            tpsl_orders = self.get_tpsl_orders(pair)

            # TP Long
            tp_long_found = False
            if position.orders.get('tp_long'):
                for order in tpsl_orders:
                    if order.get('holdSide') == 'long' and order.get('planType') == 'pos_profit':
                        tp_price = float(order.get('triggerPrice', 0))
                        message += f"🎯 TP Long @ {self.format_price(tp_price, pair)} (+0.3%)\n"
                        tp_long_found = True
                        break
            if not tp_long_found:
                message += f"🎯 TP Long | -\n"

            # Fibo Long (Ordre LIMIT)
            fibo_long_found = False
            if position.orders.get('double_long'):
                open_orders = self.exchange.fetch_open_orders(symbol=pair)
                for order in open_orders:
                    if order.get('side') == 'buy' and order.get('type') == 'limit':
                        fibo_price = float(order.get('price', 0))
                        next_pct = position.fib_levels[position.long_fib_level + 1] if position.long_fib_level + 1 < len(position.fib_levels) else 0
                        message += f"📦 Fibo Long @ {self.format_price(fibo_price, pair)} (-{next_pct:.2f}%)\n"
                        fibo_long_found = True
                        break
            if not fibo_long_found:
                message += f"📦 Fibo Long | -\n"

            # TP Short
            tp_short_found = False
            if position.orders.get('tp_short'):
                for order in tpsl_orders:
                    if order.get('holdSide') == 'short' and order.get('planType') == 'pos_profit':
                        tp_price = float(order.get('triggerPrice', 0))
                        message += f"🎯 TP Short @ {self.format_price(tp_price, pair)} (-0.3%)\n"
                        tp_short_found = True
                        break
            if not tp_short_found:
                message += f"🎯 TP Short | -\n"

            # Fibo Short (Ordre LIMIT)
            fibo_short_found = False
            if position.orders.get('double_short'):
                open_orders = self.exchange.fetch_open_orders(symbol=pair)
                for order in open_orders:
                    if order.get('side') == 'sell' and order.get('type') == 'limit':
                        fibo_price = float(order.get('price', 0))
                        next_pct = position.fib_levels[position.short_fib_level + 1] if position.short_fib_level + 1 < len(position.fib_levels) else 0
                        message += f"📦 Fibo Short @ {self.format_price(fibo_price, pair)} (+{next_pct:.2f}%)\n"
                        fibo_short_found = True
                        break
            if not fibo_short_found:
                message += f"📦 Fibo Short | -\n"

            message += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"

            self.send_telegram(message)

        except Exception as e:
            logger.error(f"Erreur send_position_message {pair}: {e}")

    def send_all_position_messages(self):
        """Envoie les messages Telegram pour TOUTES les positions"""
        for pair, position in self.active_positions.items():
            self.send_position_message(pair, position)
            time.sleep(0.5)  # Petit délai pour éviter spam Telegram

    # ============================================================================
    # 4 DÉTECTEURS SIMPLES - Cœur de la stratégie
    # ============================================================================

    def detect_tp_long_executed(self, pair, position, real_pos):
        """
        Détecte si TP Long a été exécuté
        Signature SIMPLE: Position LONG DISPARUE = TP touché!
        """
        # Si position Long était ouverte AVANT mais n'existe PLUS maintenant = TP exécuté!
        if position.long_open and not real_pos.get('long'):
            print(f"🔴 TP LONG DÉTECTÉ: Position LONG DISPARUE!")
            logger.info(f"✅ TP Long exécuté: Position fermée (disparue)")
            return True

        return False

    def detect_tp_short_executed(self, pair, position, real_pos):
        """
        Détecte si TP Short a été exécuté
        Signature: Marge diminue de >50% OU position fermée
        """
        if not position.short_open or not real_pos.get('short'):
            return False

        short_margin_now = real_pos['short']['margin']

        # Si marge diminue de plus de 50% = TP touché
        if position.short_margin_previous > 0:
            margin_decrease_pct = ((position.short_margin_previous - short_margin_now) / position.short_margin_previous) * 100
            if margin_decrease_pct > 50:
                logger.info(f"✅ TP Short exécuté: marge {position.short_margin_previous:.2f} → {short_margin_now:.2f} (-{margin_decrease_pct:.0f}%)")
                return True

        # Mettre à jour pour prochaine vérification
        position.short_margin_previous = short_margin_now
        return False

    def detect_fibo_long_executed(self, pair, position, real_pos):
        """
        Détecte si Fibo Limite Long a été exécuté
        Signature: Taille augmente de >30%
        """
        if not real_pos.get('long'):
            return False

        long_size_now = real_pos['long']['size']

        # Si taille augmente de plus de 30% = Fibo exécuté
        if position.long_size_previous > 0:
            size_increase_pct = ((long_size_now - position.long_size_previous) / position.long_size_previous) * 100
            if size_increase_pct > 30:
                logger.info(f"✅ Fibo Long exécuté: taille {position.long_size_previous:.0f} → {long_size_now:.0f} (+{size_increase_pct:.0f}%)")
                return True

        return False

    def detect_fibo_short_executed(self, pair, position, real_pos):
        """
        Détecte si Fibo Limite Short a été exécuté
        Signature: Taille augmente de >30%
        """
        if not real_pos.get('short'):
            return False

        short_size_now = real_pos['short']['size']

        # Si taille augmente de plus de 30% = Fibo exécuté
        if position.short_size_previous > 0:
            size_increase_pct = ((short_size_now - position.short_size_previous) / position.short_size_previous) * 100
            if size_increase_pct > 30:
                logger.info(f"✅ Fibo Short exécuté: taille {position.short_size_previous:.0f} → {short_size_now:.0f} (+{size_increase_pct:.0f}%)")
                return True

        return False

    # ============================================================================

    def check_orders_status(self, iteration=0):
        """
        Boucle de détection (chaque 1 seconde)
        Détecte les 4 événements et déclenche les actions
        """

        for pair, position in list(self.active_positions.items()):
            try:
                # Récupérer l'état RÉEL de l'API
                real_pos = self.get_real_positions(pair)
                if not real_pos:
                    print(f"[{iteration}] ⚠️ get_real_positions retourne None pour {pair}")
                    continue

                # ⚙️ INITIALISATION PREMIÈRE ITÉRATION (valeurs _previous à 0)
                if position.long_margin_previous == 0 and real_pos.get('long'):
                    position.long_margin_previous = real_pos['long']['margin']
                    position.long_size_previous = real_pos['long']['size']
                    print(f"[{iteration}] ✓ INIT Long margin: {position.long_margin_previous:.4f}")

                if position.short_margin_previous == 0 and real_pos.get('short'):
                    position.short_margin_previous = real_pos['short']['margin']
                    position.short_size_previous = real_pos['short']['size']
                    print(f"[{iteration}] ✓ INIT Short margin: {position.short_margin_previous:.4f}")

                # ✅ ÉVÉNEMENT 1: TP LONG EXÉCUTÉ
                tp_long_detected = self.detect_tp_long_executed(pair, position, real_pos)
                if tp_long_detected:
                    print(f"[{iteration}] 🔴🔴🔴 TP LONG DÉTECTÉ - DÉCLENCHER HANDLER! 🔴🔴🔴")
                    self.handle_tp_long_executed(pair, position)
                    time.sleep(1)
                    self.send_position_message(pair, position)  # Message Telegram
                    continue

                # ✅ ÉVÉNEMENT 2: TP SHORT EXÉCUTÉ
                tp_short_detected = self.detect_tp_short_executed(pair, position, real_pos)
                if tp_short_detected:
                    print(f"[{iteration}] 🔴🔴🔴 TP SHORT DÉTECTÉ - DÉCLENCHER HANDLER! 🔴🔴🔴")
                    self.handle_tp_short_executed(pair, position)
                    time.sleep(1)
                    self.send_position_message(pair, position)  # Message Telegram
                    continue

                # ✅ ÉVÉNEMENT 3: FIBO LONG EXÉCUTÉ
                fibo_long_detected = self.detect_fibo_long_executed(pair, position, real_pos)
                if fibo_long_detected:
                    print(f"[{iteration}] 🟡🟡🟡 FIBO LONG DÉTECTÉ - DÉCLENCHER HANDLER! 🟡🟡🟡")
                    self.handle_fibo_long_executed(pair, position, position.long_size_previous, real_pos['long']['size'])
                    position.long_size_previous = real_pos['long']['size']
                    time.sleep(1)
                    self.send_position_message(pair, position)
                    continue

                # ✅ ÉVÉNEMENT 4: FIBO SHORT EXÉCUTÉ
                fibo_short_detected = self.detect_fibo_short_executed(pair, position, real_pos)
                if fibo_short_detected:
                    print(f"[{iteration}] 🟡🟡🟡 FIBO SHORT DÉTECTÉ - DÉCLENCHER HANDLER! 🟡🟡🟡")
                    self.handle_fibo_short_executed(pair, position, position.short_size_previous, real_pos['short']['size'])
                    position.short_size_previous = real_pos['short']['size']
                    time.sleep(1)
                    self.send_position_message(pair, position)
                    continue

            except Exception as e:
                print(f"❌ EXCEPTION check_orders_status {pair}: {e}")
                logger.error(f"Erreur check_orders_status {pair}: {e}")
                import traceback
                logger.error(traceback.format_exc())

    def open_next_hedge(self):
        """Ouvre un nouveau hedge sur la prochaine paire disponible"""
        # Vérifier si le bot est en pause
        if hasattr(self, 'telegram_commands') and self.telegram_commands.is_paused:
            logger.info("Bot en pause - pas de nouvelle position")
            return

        if self.available_pairs and self.capital_used < self.MAX_CAPITAL:
            next_pair = self.available_pairs[0]
            print(f"\n🔄 Rotation vers {next_pair}")
            time.sleep(2)
            self.open_hedge_with_limit_orders(next_pair)

    def flash_close_position(self, pair, side):
        """
        Ferme TOUTE une position en utilisant l'endpoint Bitget Flash Close Position
        API: /api/v2/mix/order/close-positions
        Ferme automatiquement 100% de la position, pas besoin de spécifier la quantité
        """
        logger.info(f"Flash Close Position: {side.upper()} {pair}")

        try:
            # Convertir symbol au format Bitget
            symbol_bitget = pair.replace('/USDT:USDT', 'USDT').replace('/', '').lower()

            # Endpoint Flash Close Position
            endpoint = '/api/v2/mix/order/close-positions'
            body = {
                'symbol': symbol_bitget,
                'productType': 'USDT-FUTURES',
                'holdSide': side  # 'long' ou 'short'
            }
            body_json = json.dumps(body)

            # Timestamp et signature
            timestamp = str(int(time.time() * 1000))
            signature = self.bitget_sign_request(timestamp, 'POST', endpoint, body_json)

            # Headers
            headers = {
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.api_password,
                'Content-Type': 'application/json',
                'locale': 'en-US',
                'PAPTRADING': '1'
            }

            # Requête HTTP
            url = f"https://api.bitget.com{endpoint}"
            response = requests.post(url, headers=headers, data=body_json, timeout=10)
            data = response.json()

            if data.get('code') == '00000':
                logger.info(f"✅ Flash Close réussi: {side} {pair}")
                print(f"✅ Position {side} fermée à 100% (Flash Close)")
                return True
            else:
                logger.error(f"Flash Close échoué: {data}")
                print(f"⚠️ Flash Close réponse: {data}")
                return False

        except Exception as e:
            logger.error(f"Erreur Flash Close: {e}")
            print(f"❌ Erreur Flash Close: {e}")
            return False

    def cleanup_all_positions_and_orders(self):
        """
        Nettoie TOUTES les positions et ordres au démarrage
        FORCE la fermeture de tout pour garantir une session propre
        """
        logger.info("=== NETTOYAGE COMPLET DÉMARRÉ ===")
        print("\n" + "="*50)
        print("🧹 NETTOYAGE FORCÉ - FERMETURE DE TOUT")
        print("="*50)
        self.send_telegram("🧹 <b>NETTOYAGE FORCÉ EN COURS...</b>\n\n⚠️ Fermeture de TOUTES les positions et ordres")

        cleanup_report = []

        try:
            # 1. FERMER TOUTES LES POSITIONS avec Flash Close API
            logger.info("Étape 1: Fermeture des positions avec Flash Close API")
            for pair in self.volatile_pairs:
                try:
                    positions = self.exchange.fetch_positions(symbols=[pair])
                    for pos in positions:
                        size = float(pos.get('contracts', 0))
                        if size > 0:
                            side = pos.get('side', '').lower()

                            logger.info(f"Position trouvée: {side.upper()} {pair} - {size} contrats")
                            print(f"   🔴 Fermeture {side.upper()} {pair}: {size} contrats")

                            # UTILISER FLASH CLOSE API (ferme 100% automatiquement)
                            success = self.flash_close_position(pair, side)

                            if success:
                                cleanup_report.append(f"✅ Fermé {side.upper()} {pair.split('/')[0]} ({size:.0f} contrats)")

                                # Vérifier que c'est bien fermé
                                time.sleep(2)
                                verify = self.exchange.fetch_positions(symbols=[pair])
                                for vpos in verify:
                                    if vpos.get('side', '').lower() == side:
                                        remaining = float(vpos.get('contracts', 0))
                                        if remaining > 0:
                                            logger.warning(f"⚠️ Flash Close n'a pas tout fermé: {remaining} reste")
                                            cleanup_report.append(f"⚠️ {side.upper()} {pair.split('/')[0]}: {remaining} restants")
                                        else:
                                            logger.info(f"✅ Vérification OK: {side} {pair} fermé à 100%")
                            else:
                                cleanup_report.append(f"❌ Échec fermeture {side.upper()} {pair.split('/')[0]}")
                                logger.error(f"Échec Flash Close pour {side} {pair}")

                            time.sleep(1)

                except Exception as e:
                    error_msg = f"Erreur fermeture positions {pair}: {e}"
                    logger.error(error_msg)
                    print(f"   ⚠️  {error_msg}")

            # 2. ANNULER TOUS LES ORDRES LIMITES EN ATTENTE
            for pair in self.volatile_pairs:
                try:
                    # Récupérer tous les ordres ouverts
                    open_orders = self.exchange.fetch_open_orders(symbol=pair)

                    for order in open_orders:
                        order_id = order['id']
                        print(f"   🗑️  Annulation ordre {order['type']} {order['side']} sur {pair}")
                        self.exchange.cancel_order(order_id, pair)
                        cleanup_report.append(f"🗑️ Annulé ordre {pair.split('/')[0]}")
                        time.sleep(0.2)

                except Exception as e:
                    print(f"   ⚠️  Erreur annulation ordres {pair}: {e}")

            # 3. ANNULER TOUS LES ORDRES TP/SL (PLAN ORDERS)
            for pair in self.volatile_pairs:
                try:
                    tpsl_orders = self.get_tpsl_orders(pair)

                    for order in tpsl_orders:
                        order_id = order.get('orderId')
                        plan_type = order.get('planType', '')

                        if order_id:
                            print(f"   🗑️  Annulation TP/SL {plan_type} sur {pair}")
                            self.cancel_tpsl_order(order_id, pair)
                            cleanup_report.append(f"🗑️ Annulé TP/SL {pair.split('/')[0]}")
                            time.sleep(0.2)

                except Exception as e:
                    print(f"   ⚠️  Erreur annulation TP/SL {pair}: {e}")

            # 4. RÉINITIALISER LES VARIABLES
            self.active_positions = {}
            self.available_pairs = self.volatile_pairs.copy()
            self.capital_used = 0
            self.total_profit = 0
            self.pnl_history = []
            self.total_fees_paid = 0

            # 5. ENVOYER RAPPORT
            if cleanup_report:
                message = f"""
🧹 <b>NETTOYAGE TERMINÉ</b>

{chr(10).join(cleanup_report[:10])}

✅ Prêt pour nouvelle session!

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
                print("✅ Nettoyage terminé!")
            else:
                print("✅ Aucune position/ordre à nettoyer")
                self.send_telegram("✅ Aucune position/ordre à nettoyer")

        except Exception as e:
            print(f"❌ Erreur pendant le nettoyage: {e}")
            self.send_telegram(f"⚠️ Erreur nettoyage: {e}")

        # VÉRIFICATION FINALE ABSOLUE - S'assurer que TOUT est vraiment fermé
        print("\n🔍 Vérification finale après cleanup...")
        logger.info("Vérification finale post-cleanup")

        positions_restantes = []
        ordres_restants = []

        for pair in self.volatile_pairs:
            try:
                # Vérifier positions
                positions = self.exchange.fetch_positions(symbols=[pair])
                for pos in positions:
                    if float(pos.get('contracts', 0)) > 0:
                        side = pos.get('side', '').lower()
                        size = float(pos.get('contracts', 0))
                        positions_restantes.append(f"{side.upper()} {pair}: {size}")
                        logger.error(f"❌ POSITION TOUJOURS OUVERTE APRÈS CLEANUP: {side} {pair} - {size} contrats")

                # Vérifier ordres limites
                open_orders = self.exchange.fetch_open_orders(symbol=pair)
                if open_orders:
                    ordres_restants.append(f"{pair}: {len(open_orders)} ordres")
                    logger.error(f"❌ ORDRES TOUJOURS ACTIFS APRÈS CLEANUP: {pair} - {len(open_orders)} ordres")

                # Vérifier ordres TP/SL
                tpsl = self.get_tpsl_orders(pair)
                if tpsl:
                    ordres_restants.append(f"{pair}: {len(tpsl)} TP/SL")
                    logger.error(f"❌ TP/SL TOUJOURS ACTIFS APRÈS CLEANUP: {pair} - {len(tpsl)} ordres")

            except Exception as e:
                logger.error(f"Erreur vérification finale {pair}: {e}")

        if positions_restantes or ordres_restants:
            alert_msg = "🚨 <b>ALERTE CLEANUP INCOMPLET!</b>\n\n"
            if positions_restantes:
                alert_msg += "❌ Positions restantes:\n"
                alert_msg += "\n".join(positions_restantes) + "\n\n"
            if ordres_restants:
                alert_msg += "❌ Ordres restants:\n"
                alert_msg += "\n".join(ordres_restants)

            self.send_telegram(alert_msg)
            print("⚠️ ATTENTION: Cleanup incomplet, voir logs")

            # Essayer une deuxième fois plus agressive
            print("🔄 Tentative de cleanup forcé supplémentaire...")
            for pair in self.volatile_pairs:
                try:
                    positions = self.exchange.fetch_positions(symbols=[pair])
                    for pos in positions:
                        if float(pos.get('contracts', 0)) > 0:
                            side = pos.get('side', '').lower()
                            self.flash_close_position(pair, side)
                            time.sleep(1)
                except:
                    pass
        else:
            print("✅ Vérification finale: TOUT est fermé!")
            logger.info("✅ Cleanup complet vérifié - aucune position ni ordre restant")

        # Attendre un peu avant de commencer
        time.sleep(3)

    def perform_health_check(self):
        """
        Vérification automatique de la santé du bot
        Vérifie l'état API, la cohérence des positions, les erreurs
        Envoie un rapport sur Telegram toutes les 60 secondes
        """
        current_time = time.time()

        # Ne vérifier que toutes les 60 secondes
        if current_time - self.last_health_check < self.health_check_interval:
            return

        self.last_health_check = current_time

        try:
            logger.info("=== HEALTH CHECK DÉMARRÉ ===")
            issues = []
            warnings = []

            # 1. VÉRIFIER CONNEXION API
            try:
                balance = self.exchange.fetch_balance()
                logger.info("✅ API Bitget: OK")
            except Exception as e:
                issues.append(f"❌ API Bitget: {str(e)[:50]}")
                logger.error(f"API Error: {e}")
                self.error_count += 1

            # 2. VÉRIFIER COHÉRENCE DES POSITIONS
            for pair in self.volatile_pairs:
                try:
                    real_pos = self.get_real_positions(pair)
                    if real_pos:
                        long_data = real_pos.get('long')
                        short_data = real_pos.get('short')

                        # Vérifier si hedge équilibré
                        if long_data and short_data:
                            long_size = long_data['size']
                            short_size = short_data['size']

                            # Note: Déséquilibre NORMAL dans stratégie Fibonacci
                            # Une position peut être à Fib 0 (250) et l'autre à Fib 3 (6750)
                            # Pas d'alerte nécessaire

                        # Vérifier P&L extrême
                        if long_data and abs(long_data.get('unrealized_pnl', 0)) > 50:
                            warnings.append(f"⚠️ {pair.split('/')[0]}: PNL Long élevé (${long_data['unrealized_pnl']:+.2f})")

                        if short_data and abs(short_data.get('unrealized_pnl', 0)) > 50:
                            warnings.append(f"⚠️ {pair.split('/')[0]}: PNL Short élevé (${short_data['unrealized_pnl']:+.2f})")

                except Exception as e:
                    issues.append(f"❌ Vérif {pair.split('/')[0]}: {str(e)[:30]}")
                    logger.error(f"Position check error {pair}: {e}")

            # 3. VÉRIFIER LES ORDRES EN ATTENTE
            total_orders = 0
            for pair in self.volatile_pairs:
                try:
                    open_orders = self.exchange.fetch_open_orders(symbol=pair)
                    total_orders += len(open_orders)
                except:
                    pass

            # 4. CONSTRUIRE RAPPORT DÉTAILLÉ AVEC VRAIES DONNÉES API
            if issues:
                # Problèmes critiques détectés
                message = f"""
🚨 <b>ALERTE - Problèmes détectés</b>

{chr(10).join(issues[:5])}

Erreurs totales: {self.error_count}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
                logger.warning(f"Health check: {len(issues)} issues")

            elif warnings:
                # Avertissements - afficher les vraies données
                message = f"""
⚠️ <b>Health Check: Avertissements</b>

{chr(10).join(warnings[:5])}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)
                logger.info(f"Health check: {len(warnings)} warnings")

            else:
                # Tout va bien - RAPPORT DÉTAILLÉ AVEC VRAIES DONNÉES API
                message_parts = ["✅ <b>SYSTÈME OK</b>\n"]

                # Parcourir chaque paire active et afficher VRAIES données
                for pair in self.volatile_pairs:
                    try:
                        real_pos = self.get_real_positions(pair)
                        if not real_pos:
                            continue

                        long_data = real_pos.get('long')
                        short_data = real_pos.get('short')

                        # Si au moins une position existe sur cette paire
                        if long_data or short_data:
                            pair_name = pair.split('/')[0]
                            current_price = self.get_price(pair)

                            message_parts.append(f"\n━━━━ <b>{pair_name}</b> ━━━━")
                            message_parts.append(f"💰 Prix: ${current_price:.5f}\n")

                            # LONG (si ouvert) - EN VERT
                            if long_data:
                                contracts = long_data['size']
                                entry = long_data['entry_price']
                                margin = long_data['margin']
                                pnl = long_data['unrealized_pnl']
                                roe = long_data['pnl_percentage']

                                message_parts.append(f"🟢 <b>LONG</b>")
                                message_parts.append(f"🟢 Contrats: {contracts:.0f}")
                                message_parts.append(f"🟢 Entrée: ${entry:.5f}")
                                message_parts.append(f"🟢 Marge: {margin:.7f} USDT")
                                message_parts.append(f"🟢 P&L: {pnl:+.7f} USDT")
                                message_parts.append(f"🟢 ROE: {roe:+.2f}%\n")

                            # SHORT (si ouvert) - EN ROUGE
                            if short_data:
                                contracts = short_data['size']
                                entry = short_data['entry_price']
                                margin = short_data['margin']
                                pnl = short_data['unrealized_pnl']
                                roe = short_data['pnl_percentage']
                                liq_price = short_data.get('liquidation_price', 0)

                                message_parts.append(f"🔴 <b>SHORT</b>")
                                message_parts.append(f"🔴 Contrats: {contracts:.0f}")
                                message_parts.append(f"🔴 Entrée: ${entry:.5f}")
                                message_parts.append(f"🔴 Marge: {margin:.7f} USDT")
                                message_parts.append(f"🔴 P&L: {pnl:+.7f} USDT")
                                message_parts.append(f"🔴 ROE: {roe:+.2f}%")
                                if liq_price > 0:
                                    message_parts.append(f"🔴 💀 Liq: ${liq_price:.5f}")

                    except Exception as e:
                        logger.error(f"Erreur affichage {pair}: {e}")

                # Footer avec résumé
                message_parts.append(f"\n━━━━━━━━━━━━━━")
                message_parts.append(f"📝 Ordres: {total_orders}")
                message_parts.append(f"🔧 API: OK")
                message_parts.append(f"🐛 Erreurs: {self.error_count}")
                message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

                self.send_telegram("\n".join(message_parts))
                logger.info("Health check: All OK - Detailed report sent")

                # Réinitialiser le compteur d'erreurs si tout va bien
                if self.error_count > 0:
                    self.error_count = max(0, self.error_count - 1)

            logger.info("=== HEALTH CHECK TERMINÉ ===")

        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            self.send_telegram(f"❌ Erreur health check: {e}")

    def send_status_telegram(self):
        """Envoie status détaillé sur Telegram toutes les 60s (1 minute)"""
        current_time = time.time()
        if current_time - self.last_status_update < 60:  # 1 minute
            return

        if not self.active_positions:
            return

        message_parts = ["📊 <b>STATUS POSITIONS</b>\n"]
        total_pnl = 0

        for pair, pos in self.active_positions.items():
            real_pos = self.get_real_positions(pair)
            current_price = self.get_price(pair)

            if not real_pos or not current_price:
                continue

            long_data = real_pos.get('long')
            short_data = real_pos.get('short')

            # En-tête de la paire avec prix actuel
            pair_name = pair.split('/')[0]
            pair_msg = f"\n━━━━━━━━━━━━━━━━━\n"
            pair_msg += f"<b>{pair_name}</b>\n"
            pair_msg += f"💰 Prix actuel: {self.format_price(current_price, pair)}\n"

            # LONG (si ouvert)
            if long_data:
                pnl = long_data['unrealized_pnl'] or 0
                total_pnl += pnl
                entry_long = long_data['entry_price']

                # Calcul variation % par rapport au prix d'entrée MARKET
                variation_pct = ((current_price - entry_long) / entry_long) * 100

                pair_msg += f"\n📈 <b>LONG</b> (Hedge)\n"
                pair_msg += f"   Entrée: {self.format_price(entry_long, pair)}\n"
                pair_msg += f"   Variation: {variation_pct:+.2f}%\n"
                pair_msg += f"   P&L: ${pnl:+.2f} (ROE: {long_data['pnl_percentage']:+.1f}%)\n"

                # Afficher TP
                next_trigger = pos.get_next_long_trigger_pct()
                if next_trigger:
                    next_price = long_data['entry_price'] * (1 + next_trigger / 100)
                    pair_msg += f"   🎯 TP: {self.format_price(next_price, pair)} (+{next_trigger}%, Fib {pos.long_fib_level + 1})\n"

            # SHORT (si ouvert)
            if short_data:
                pnl = short_data['unrealized_pnl'] or 0
                total_pnl += pnl
                entry_short = short_data['entry_price']

                # Calcul variation % par rapport au prix d'entrée MARKET
                variation_pct = ((current_price - entry_short) / entry_short) * 100

                pair_msg += f"\n📉 <b>SHORT</b> (Hedge)\n"
                pair_msg += f"   Entrée: {self.format_price(entry_short, pair)}\n"
                pair_msg += f"   Variation: {variation_pct:+.2f}%\n"
                pair_msg += f"   P&L: ${pnl:+.2f} (ROE: {short_data['pnl_percentage']:+.1f}%)\n"
                pair_msg += f"   💀 Liq: {self.format_price(short_data['liquidation_price'], pair)}\n"

                # Afficher TP
                next_trigger = pos.get_next_short_trigger_pct()
                if next_trigger:
                    next_price = short_data['entry_price'] * (1 - next_trigger / 100)
                    pair_msg += f"   🎯 TP: {self.format_price(next_price, pair)} (-{next_trigger}%, Fib {pos.short_fib_level + 1})\n"

            message_parts.append(pair_msg)

        # Récupérer les frais totaux
        total_fees = self.get_total_fees()
        self.total_fees_paid = total_fees

        # Footer avec balance et frais
        balance_available = self.MAX_CAPITAL - self.capital_used
        usage_pct = (self.capital_used / self.MAX_CAPITAL * 100)
        pnl_net = total_pnl + self.total_profit - total_fees

        message_parts.append(f"\n━━━━━━━━━━━━━━━━━")
        message_parts.append(f"\n💰 P&L Total: ${total_pnl + self.total_profit:+.2f}")
        message_parts.append(f"\n💸 Frais payés: ${total_fees:.2f}")
        message_parts.append(f"\n💎 <b>P&L Net: ${pnl_net:+.2f}</b>")
        message_parts.append(f"\n━━━━━━━━━━━━━━━━━")
        message_parts.append(f"\n📊 Positions: {len(self.active_positions)}")
        message_parts.append(f"\n💵 Balance: ${balance_available:.0f}€ / ${self.MAX_CAPITAL:.0f}€ ({usage_pct:.1f}% utilisé)")
        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

        self.send_telegram("".join(message_parts))
        self.last_status_update = current_time

    def restore_positions_from_api(self):
        """Restaure les positions actives depuis l'API après un restart"""
        try:
            logger.info("Restauration positions depuis API...")
            print("\n🔄 Restauration des positions depuis l'API...")

            # Parcourir toutes les paires volatiles
            for pair in self.volatile_pairs:
                real_pos = self.get_real_positions(pair)
                if real_pos and (real_pos.get('long') or real_pos.get('short')):
                    # Extraire prix d'entrée
                    entry_long = real_pos['long']['entry_price'] if real_pos.get('long') else 0
                    entry_short = real_pos['short']['entry_price'] if real_pos.get('short') else 0

                    # Créer HedgePosition avec bons paramètres
                    position = HedgePosition(pair, self.INITIAL_MARGIN, entry_long, entry_short)

                    # Restaurer états et tailles
                    if real_pos.get('long'):
                        position.long_open = True
                        position.long_size_previous = real_pos['long']['size']
                        logger.info(f"LONG restauré: {position.long_size_previous:.0f} contrats @ ${entry_long:.5f}")
                    else:
                        position.long_open = False

                    if real_pos.get('short'):
                        position.short_open = True
                        position.short_size_previous = real_pos['short']['size']
                        logger.info(f"SHORT restauré: {position.short_size_previous:.0f} contrats @ ${entry_short:.5f}")
                    else:
                        position.short_open = False

                    # Ajouter aux positions actives
                    self.active_positions[pair] = position
                    print(f"   ✅ {pair.split('/')[0]}: LONG={position.long_open}, SHORT={position.short_open}")

                    # Note: Les ordres (TP, double) ne sont pas restaurés ici
                    # Ils seront recréés lors du prochain cycle si nécessaire

            if self.active_positions:
                logger.info(f"{len(self.active_positions)} positions restaurées")
                print(f"\n✅ {len(self.active_positions)} positions restaurées\n")
            else:
                logger.info("Aucune position à restaurer")
                print("ℹ️  Aucune position active trouvée\n")

        except Exception as e:
            logger.error(f"Erreur restauration positions: {e}")
            print(f"⚠️  Erreur restauration: {e}")

    def run(self):
        """Boucle principale"""
        print("="*80)
        print("🚀 BITGET HEDGE BOT V2 - ORDRES LIMITES AUTO")
        print("="*80)

        # Message Telegram immédiat (avant Bitget)
        startup_test = f"""
🚀 <b>BOT DÉMARRAGE</b>

🌐 Oracle Cloud: ✅
🐍 Python: ✅
📱 Telegram: {'✅' if self.telegram_token else '❌'}
🔑 Bitget API: {'✅' if self.api_key else '❌'}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.send_telegram(startup_test)

        if not self.api_key:
            print("❌ Clés API manquantes")
            self.send_telegram("❌ Clés API Bitget manquantes!")
            return

        try:
            print("\n📡 Connexion Bitget Testnet...")
            self.exchange.load_markets()

            # TOUJOURS NETTOYER au démarrage (session propre)
            logger.info("Nettoyage complet au démarrage")
            print("\n🧹 Nettoyage de toutes les positions et ordres...")
            self.cleanup_all_positions_and_orders()

            # Attendre que le cleanup soit bien terminé
            print("⏳ Attente finalisation cleanup (5 secondes)...")
            time.sleep(5)

            # MAINTENANT démarrer le monitoring des anomalies
            logger.info("Démarrage du monitoring des anomalies")
            self.telegram_commands.start_monitoring()

            # Message démarrage
            startup = f"""
🤖 <b>CRYPTO HEDGE BOT V2 DÉMARRÉ</b>

💰 Capital: ${self.MAX_CAPITAL}€
⚡ Levier: x{self.LEVERAGE}
📊 Marge initiale: ${self.INITIAL_MARGIN}€

📝 <b>Système:</b>
✅ Hedge automatique avec TP/SL
✅ Grille Fibonacci adaptive
✅ Nettoyage auto au démarrage
✅ Vérification santé toutes les 60s
✅ Logs détaillés sauvegardés

🪙 Paires: {', '.join([p.split('/')[0] for p in self.volatile_pairs])}

📲 <b>Commandes:</b>
/pnl /positions /balance /history
/status /logs /admin /help

🔄 <b>Contrôle à distance:</b>
/update - Mise à jour GitHub
/restart - Redémarrage
/stop - Arrêt sécurisé

🛡️ Health Check: Vérifie API, positions, ordres
📊 Rapport système: Toutes les 60 secondes
🌐 Serveur: Oracle Cloud (Marseille)

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.send_telegram(startup)

            # Ouvrir hedge sur DOGE (session propre)
            logger.info(f"Ouverture hedge DOGE")
            print(f"\n📊 Ouverture hedge DOGE...")

            test_pair = 'DOGE/USDT:USDT'
            if test_pair in self.available_pairs:
                success = self.open_hedge_with_limit_orders(test_pair)
                if success:
                    logger.info(f"✅ Hedge DOGE ouvert")
                    print(f"✅ Hedge DOGE ouvert avec succès")
                else:
                    logger.error(f"❌ Échec ouverture hedge DOGE")
            else:
                logger.error(f"DOGE/USDT:USDT pas disponible!")

            # NE PAS ouvrir PEPE ni SHIB (mode test)
            # pairs_to_open = self.available_pairs.copy()
            # for idx, pair in enumerate(pairs_to_open):
            #     if self.capital_used >= self.MAX_CAPITAL:
            #         logger.warning(f"Capital max atteint, arrêt ouverture à {idx} paires")
            #         break
            #
            #     logger.info(f"Ouverture hedge {idx+1}/{len(pairs_to_open)}: {pair}")
            #     success = self.open_hedge_with_limit_orders(pair)
            #
            #     if success and idx < len(pairs_to_open) - 1:
            #         # Attendre 3s entre chaque ouverture
            #         logger.info(f"Attente 3s avant prochaine paire...")
            #         time.sleep(3)

            # Boucle
            iteration = 0
            last_pulse_time = time.time()

            while True:
                loop_start = time.time()

                # ✅ PRIORITÉ 1: DÉTECTION TP/FIBO (CRITIQUE - CHAQUE SECONDE)
                self.check_orders_status(iteration)

                # ✅ PRIORITÉ 2: COMMANDES TELEGRAM (toutes les 2 secondes)
                if iteration % 2 == 0:
                    self.check_telegram_commands()

                # ✅ PRIORITÉ 3: HEALTH CHECK (toutes les 60 secondes)
                if iteration % 60 == 0:
                    self.perform_health_check()

                # 🔄 PULSE: Confirmation API appelée (toutes les 10 secondes)
                if time.time() - last_pulse_time >= 10:
                    last_pulse_time = time.time()
                    pulse_msg = f"🔄 <b>API Pulse OK</b>\n"
                    pulse_msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
                    pulse_msg += f"📊 Itération: {iteration}\n"
                    pulse_msg += f"📍 Positions actives: {len(self.active_positions)}\n"

                    # Compter les ordres totaux
                    total_orders = 0
                    for pos in self.active_positions.values():
                        total_orders += sum(1 for o in pos.orders.values() if o)
                    pulse_msg += f"📋 Ordres: {total_orders}"

                    self.send_telegram(pulse_msg)
                    logger.info(f"🔄 Pulse: Itération {iteration}, {len(self.active_positions)} positions, {total_orders} ordres")

                # 📊 DEBUG: Afficher prix en temps réel (toutes les 30 secondes seulement)
                if iteration % 30 == 0 and self.active_positions:
                    print(f"\n{'='*80}")
                    print(f"🔍 DEBUG - Itération {iteration} - {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'='*80}")

                    for pair, position in self.active_positions.items():
                        current_price = self.get_price(pair)
                        if not current_price:
                            continue

                        print(f"\n📊 {pair}")
                        print(f"   Prix actuel: {self.format_price(current_price, pair)}")

                        # Long (si ouvert)
                        if position.long_open:
                            entry_long = position.entry_price_long
                            change_pct = ((current_price - entry_long) / entry_long) * 100
                            next_trigger = position.get_next_long_trigger_pct()

                            print(f"   📈 LONG (Fib {position.long_fib_level}):")
                            print(f"      Prix entrée: {self.format_price(entry_long, pair)}")
                            print(f"      Variation: {change_pct:+.4f}%")
                            if next_trigger:
                                print(f"      Trigger TP: +{next_trigger}% (Fib {position.long_fib_level + 1})")
                                print(f"      Distance trigger: {(next_trigger - change_pct):.4f}%")

                        # Short (si ouvert)
                        if position.short_open and position.entry_price_short > 0:
                            entry_short = position.entry_price_short
                            change_pct = ((current_price - entry_short) / entry_short) * 100
                            next_trigger = position.get_next_short_trigger_pct()

                            print(f"   📉 SHORT (Fib {position.short_fib_level}):")
                            print(f"      Prix entrée: {self.format_price(entry_short, pair)}")
                            print(f"      Variation: {change_pct:+.4f}%")
                            if next_trigger:
                                print(f"      Trigger TP: -{next_trigger}% (Fib {position.short_fib_level + 1})")
                                print(f"      Distance trigger: {(abs(change_pct) - next_trigger):.4f}%")

                    print(f"\n📊 {len(self.active_positions)} positions actives | Capital: ${self.capital_used}/${self.MAX_CAPITAL}")

                iteration += 1

                # ⏱️ Assurer une itération par seconde exacte
                loop_time = time.time() - loop_start
                sleep_time = max(0.1, 1.0 - loop_time)  # Min 0.1s pour éviter CPU 100%
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n✋ Arrêt")
            self.send_telegram("🛑 Bot arrêté")
            raise  # Propager pour que main() sache que c'est un arrêt manuel
        except Exception as e:
            print(f"❌ Erreur dans run(): {e}")
            import traceback
            logger.error(f"Exception dans run(): {traceback.format_exc()}")
            self.send_telegram(f"❌ Erreur détectée: {str(e)[:150]}")
            raise  # Propager l'erreur vers main() pour redémarrage auto


def main():
    """Fonction principale - manage_local.sh gère les redémarrages"""
    try:
        bot = BitgetHedgeBotV2()
        bot.run()
    except KeyboardInterrupt:
        print("\n✋ Arrêt manuel du bot (Ctrl+C)")
        try:
            bot.send_telegram("🛑 Bot arrêté manuellement (Ctrl+C)")
        except:
            pass
    except SystemExit:
        # /restart ou /stop appelé - laisser manage_local.sh gérer
        print("\n🔄 Sortie normale (commande admin)")
    except Exception as e:
        # Erreur critique - logger et quitter
        error_msg = f"❌ ERREUR CRITIQUE: {str(e)[:200]}"
        print(f"\n{error_msg}")
        import traceback
        logger.error(f"Erreur critique:")
        logger.error(traceback.format_exc())

        try:
            temp_bot = BitgetHedgeBotV2()
            temp_bot.send_telegram(f"❌ BOT CRASH\n\n{str(e)[:150]}\n\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        except:
            pass
        raise  # Re-lever l'erreur pour que le process se termine


if __name__ == "__main__":
    main()
