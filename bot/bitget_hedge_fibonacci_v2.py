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

        # Grille Fibonacci (en % - 0.3% partout pour stabilité et test)
        self.fib_levels = [0.3, 0.3, 0.6, 0.9, 1.5, 2.4, 3.9, 6.3, 10.2, 16.5]
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
        """Traite les commandes Telegram reçues"""

        if command == '/pnl':
            # Afficher P&L actuel
            total_unrealized = 0
            for pair in self.active_positions:
                real_pos = self.get_real_positions(pair)
                if real_pos:
                    if real_pos.get('long'):
                        total_unrealized += real_pos['long']['unrealized_pnl']
                    if real_pos.get('short'):
                        total_unrealized += real_pos['short']['unrealized_pnl']

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
                time.sleep(0.5)
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
                time.sleep(0.5)
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
                        'liquidation_price': float(pos.get('liquidationPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'pnl_percentage': float(pos.get('percentage', 0)),
                        'margin': float(pos.get('initialMargin', 0)),
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
                time.sleep(0.5)  # Délai pour propagation
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
        Calcule le prix de TP pour garantir un profit global positif

        Args:
            position: HedgePosition object
            real_pos_data: Données réelles de la position depuis API
            direction: 'up' (prix a monté) ou 'down' (prix a descendu)

        Returns:
            float: Prix du TP qui garantit profit
        """
        if direction == 'up':
            # Le short a été doublé, on veut fermer avec profit
            short_data = real_pos_data.get('short')
            if not short_data:
                return None

            # Prix moyen du short après doublement
            avg_entry = short_data['entry_price']

            # Pour un short, profit si prix descend
            # On veut au moins 0.5% de profit global
            target_profit_pct = 0.5
            tp_price = avg_entry * (1 - target_profit_pct / 100)

            return tp_price

        elif direction == 'down':
            # Le long a été doublé, on veut fermer avec profit
            long_data = real_pos_data.get('long')
            if not long_data:
                return None

            # Prix moyen du long après doublement
            avg_entry = long_data['entry_price']

            # Pour un long, profit si prix monte
            target_profit_pct = 0.5
            tp_price = avg_entry * (1 + target_profit_pct / 100)

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
            # Convertir symbol au format Bitget
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '').lower()

            # Arrondir le prix selon les règles Bitget
            trigger_price_rounded = self.round_price(trigger_price, symbol)

            # Endpoint et body
            endpoint = '/api/v2/mix/order/place-tpsl-order'
            body = {
                'marginCoin': 'USDT',
                'productType': 'USDT-FUTURES',  # Majuscules
                'symbol': symbol_bitget,
                'planType': 'pos_profit' if plan_type == 'profit_plan' else 'pos_loss',  # pos_profit au lieu de profit_plan
                'triggerPrice': str(trigger_price_rounded),
                'triggerType': 'mark_price',
                'executePrice': '0',  # 0 = ordre market au trigger
                'holdSide': hold_side,
                'size': str(int(size))
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

    def get_tpsl_orders(self, symbol):
        """Récupère les ordres TP/SL plan en cours via HTTP direct"""
        try:
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '').lower()

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
        """Annule un ordre (LIMIT ou TP/SL plan)"""
        # Essayer d'annuler comme ordre LIMIT standard
        try:
            self.exchange.cancel_order(order_id, symbol)
            print(f"🗑️  Ordre LIMIT {order_id[:8]}... annulé")
            return True
        except Exception as e:
            error_msg = str(e)
            # Si ordre n'existe pas comme LIMIT, essayer comme TP/SL plan
            if '40768' in error_msg or 'does not exist' in error_msg.lower():
                # Essayer d'annuler comme TP/SL plan
                try:
                    return self.cancel_tpsl_order(order_id, symbol)
                except:
                    print(f"ℹ️  Ordre {order_id[:8]}... déjà exécuté/annulé")
                    return True
            else:
                print(f"⚠️  Erreur annulation: {e}")
                return False

    def cancel_tpsl_order(self, order_id, symbol):
        """Annule un ordre TP/SL plan"""
        try:
            symbol_bitget = symbol.replace('/USDT:USDT', 'USDT').replace('/', '').lower()

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
            self.active_positions[pair] = position

            # Attendre 3s avant de placer les TP (Bitget refuse si trop rapide)
            print("\n⏳ Attente 3s avant placement TP...")
            time.sleep(3)

            # 2. Placer les 4 ordres limites avec vérification
            print("\n2️⃣ Placement des 4 ordres limites...")

            next_trigger_pct = position.get_next_trigger_pct()
            if not next_trigger_pct:
                print("❌ Pas de niveau Fibonacci")
                return False

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

            # Récupérer les VRAIES données API après ouverture
            final_real_pos = self.get_real_positions(pair)
            if final_real_pos:
                long_final = final_real_pos.get('long')
                short_final = final_real_pos.get('short')

                # Message Telegram avec VRAIES données + COULEURS
                message_parts = [f"🎯 <b>HEDGE OUVERT - {pair.split('/')[0]}</b>\n"]

                if long_final:
                    message_parts.append(f"🟢 <b>LONG</b>")
                    message_parts.append(f"🟢 Contrats: {long_final['size']:.0f}")
                    message_parts.append(f"🟢 Entrée: ${long_final['entry_price']:.5f}")
                    message_parts.append(f"🟢 Marge: {long_final['margin']:.7f} USDT\n")

                if short_final:
                    message_parts.append(f"🔴 <b>SHORT</b>")
                    message_parts.append(f"🔴 Contrats: {short_final['size']:.0f}")
                    message_parts.append(f"🔴 Entrée: ${short_final['entry_price']:.5f}")
                    message_parts.append(f"🔴 Marge: {short_final['margin']:.7f} USDT\n")

                message_parts.append(f"⚡ Levier: x{self.LEVERAGE}")
                message_parts.append(f"\n📝 <b>Ordres:</b>")
                message_parts.append(f"⬆️ Si +{next_trigger_pct}%: TP Long + Double Short")
                message_parts.append(f"⬇️ Si -{next_trigger_pct}%: TP Short + Double Long")
                message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

                self.send_telegram("\n".join(message_parts))
            else:
                # Fallback si impossible de récupérer données
                message = f"""
🎯 <b>HEDGE OUVERT - {pair.split('/')[0]}</b>

📈 Long: ${entry_long:.5f}
📉 Short: ${entry_short:.5f}
⚡ Levier: x{self.LEVERAGE}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
                self.send_telegram(message)

            return True

        except Exception as e:
            print(f"❌ Erreur ouverture: {e}")
            return False

    def check_orders_status(self, iteration=0):
        """Vérifie l'état des ordres (LIMIT + TP/SL plan)"""

        for pair, position in list(self.active_positions.items()):
            try:
                # Vérifier si TP Long exécuté (par disparition de position)
                tp_long_executed = False
                if position.orders['tp_long'] and position.long_open:
                    # Vérifier si la position Long existe encore
                    real_pos = self.get_real_positions(pair)
                    if not real_pos or not real_pos.get('long'):
                        print(f"   ✅ TP Long EXÉCUTÉ (position fermée)")
                        tp_long_executed = True
                    else:
                        # Position existe encore, TP pas encore atteint
                        if iteration % 30 == 0:  # Log toutes les 30s
                            print(f"   ⏳ TP Long en attente")

                # Vérifier si TP Short exécuté (par disparition de position)
                tp_short_executed = False
                if position.orders['tp_short'] and position.short_open:
                    # Vérifier si la position Short existe encore
                    real_pos = self.get_real_positions(pair) if not tp_long_executed else self.get_real_positions(pair)
                    if not real_pos or not real_pos.get('short'):
                        print(f"   ✅ TP Short EXÉCUTÉ (position fermée)")
                        tp_short_executed = True
                    else:
                        # Position existe encore, TP pas encore atteint
                        if iteration % 30 == 0:  # Log toutes les 30s
                            print(f"   ⏳ TP Short en attente")

                # TP LONG EXÉCUTÉ (prix a monté)
                if tp_long_executed:
                    print(f"\n{'='*80}")
                    print(f"🔔 TP LONG EXÉCUTÉ - {pair}")
                    print(f"{'='*80}")

                    # Afficher le prix actuel et calcul de variation
                    current_price = self.get_price(pair)
                    if current_price:
                        entry = position.entry_price_long
                        variation = ((current_price - entry) / entry) * 100
                        print(f"   Prix entrée Long: {self.format_price(entry, pair)}")
                        print(f"   Prix actuel: {self.format_price(current_price, pair)}")
                        print(f"   Variation réelle: {variation:+.4f}%")

                    position.long_open = False

                    # Récupérer P&L réel du Long fermé
                    real_pos_after = self.get_real_positions(pair)
                    long_profit = 0
                    if real_pos_after and real_pos_after.get('long'):
                        # Le long n'existe plus, mais on peut estimer le profit
                        long_profit = variation * self.INITIAL_MARGIN / 100  # Approximation

                    # Enregistrer dans l'historique
                    self.pnl_history.append({
                        'timestamp': datetime.now(),
                        'pair': pair,
                        'pnl': long_profit,
                        'action': 'TP Long'
                    })

                    # Annuler ordres du côté opposé
                    if position.orders['tp_short']:
                        self.cancel_order(position.orders['tp_short'], pair)
                        position.orders['tp_short'] = None
                    if position.orders['double_long']:
                        self.cancel_order(position.orders['double_long'], pair)
                        position.orders['double_long'] = None

                    # RÉ-OUVRIR UN NOUVEAU LONG (niveau Fib 0 - marge initiale)
                    logger.info(f"Réouverture nouveau Long {pair} au niveau Fib 0")
                    print(f"\n🔄 RÉ-OUVERTURE NOUVEAU LONG {pair}")

                    try:
                        current_price = self.get_price(pair)
                        notional = self.INITIAL_MARGIN * self.LEVERAGE
                        new_long_size = notional / current_price

                        # Ouvrir nouveau Long au prix actuel
                        new_long = self.exchange.create_order(
                            symbol=pair, type='market', side='buy', amount=new_long_size,
                            params={'tradeSide': 'open', 'holdSide': 'long'}
                        )
                        logger.info(f"✅ Nouveau Long ouvert: {new_long_size:.4f} @ {self.format_price(current_price, pair)}")
                        print(f"✅ Nouveau Long ouvert: {new_long_size:.4f} @ {self.format_price(current_price, pair)}")

                        time.sleep(2)

                        # Récupérer prix entrée réel
                        real_pos_new = self.get_real_positions(pair)
                        if real_pos_new and real_pos_new.get('long'):
                            new_entry_long = real_pos_new['long']['entry_price']
                            position.entry_price_long = new_entry_long
                            position.long_open = True
                            logger.info(f"Position Long mise à jour: entrée = {self.format_price(new_entry_long, pair)}")

                    except Exception as e:
                        logger.error(f"❌ Erreur réouverture Long: {e}")
                        print(f"❌ Erreur réouverture Long: {e}")

                    # Replacer ordres au niveau Fibonacci suivant
                    position.current_level += 1
                    self.place_next_level_orders(pair, position, direction='up')

                    # MESSAGE TELEGRAM AVEC VRAIES DONNÉES
                    time.sleep(2)
                    final_pos = self.get_real_positions(pair)
                    if final_pos:
                        message_parts = [f"🔔 <b>TP LONG EXÉCUTÉ - {pair.split('/')[0]}</b>\n"]
                        message_parts.append(f"💰 Prix TP: ${current_price:.5f}")
                        message_parts.append(f"💵 Profit réalisé: ~{long_profit:+.4f} USDT\n")

                        # Short (doublé) - EN ROUGE
                        if final_pos.get('short'):
                            sd = final_pos['short']
                            message_parts.append(f"🔴 <b>SHORT</b> (doublé - Fib {position.current_level})")
                            message_parts.append(f"🔴 Contrats: {sd['size']:.0f}")
                            message_parts.append(f"🔴 Entrée: ${sd['entry_price']:.5f}")
                            message_parts.append(f"🔴 Marge: {sd['margin']:.7f} USDT")
                            message_parts.append(f"🔴 P&L: {sd['unrealized_pnl']:+.7f} USDT")
                            message_parts.append(f"🔴 ROE: {sd['pnl_percentage']:+.2f}%\n")

                        # Long (réouvert) - EN VERT
                        if final_pos.get('long'):
                            ld = final_pos['long']
                            message_parts.append(f"🟢 <b>LONG</b> (réouvert - Fib 0)")
                            message_parts.append(f"🟢 Contrats: {ld['size']:.0f}")
                            message_parts.append(f"🟢 Entrée: ${ld['entry_price']:.5f}")
                            message_parts.append(f"🟢 Marge: {ld['margin']:.7f} USDT")

                        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                        self.send_telegram("\n".join(message_parts))

                    # NE PLUS ouvrir nouveau hedge (on reste sur les mêmes paires)
                    # self.open_next_hedge()  # DÉSACTIVÉ

                # TP SHORT EXÉCUTÉ (prix a descendu)
                elif tp_short_executed:
                    print(f"\n{'='*80}")
                    print(f"🔔 TP SHORT EXÉCUTÉ - {pair}")
                    print(f"{'='*80}")

                    # Afficher le prix actuel et calcul de variation
                    current_price = self.get_price(pair)
                    if current_price:
                        entry = position.entry_price_short
                        variation = ((current_price - entry) / entry) * 100
                        print(f"   Prix entrée Short: {self.format_price(entry, pair)}")
                        print(f"   Prix actuel: {self.format_price(current_price, pair)}")
                        print(f"   Variation réelle: {variation:+.4f}%")

                    position.short_open = False

                    # Récupérer P&L réel du Short fermé
                    short_profit = 0
                    if current_price:
                        entry = position.entry_price_short
                        variation = ((current_price - entry) / entry) * 100
                        short_profit = -variation * self.INITIAL_MARGIN / 100  # Négatif car short profite de la baisse

                    # Enregistrer dans l'historique
                    self.pnl_history.append({
                        'timestamp': datetime.now(),
                        'pair': pair,
                        'pnl': short_profit,
                        'action': 'TP Short'
                    })

                    # Annuler ordres du côté opposé
                    if position.orders['tp_long']:
                        self.cancel_order(position.orders['tp_long'], pair)
                        position.orders['tp_long'] = None
                    if position.orders['double_short']:
                        self.cancel_order(position.orders['double_short'], pair)
                        position.orders['double_short'] = None

                    # RÉ-OUVRIR UN NOUVEAU SHORT (niveau Fib 0 - marge initiale)
                    logger.info(f"Réouverture nouveau Short {pair} au niveau Fib 0")
                    print(f"\n🔄 RÉ-OUVERTURE NOUVEAU SHORT {pair}")

                    try:
                        current_price = self.get_price(pair)
                        notional = self.INITIAL_MARGIN * self.LEVERAGE
                        new_short_size = notional / current_price

                        # Ouvrir nouveau Short au prix actuel
                        new_short = self.exchange.create_order(
                            symbol=pair, type='market', side='sell', amount=new_short_size,
                            params={'tradeSide': 'open', 'holdSide': 'short'}
                        )
                        logger.info(f"✅ Nouveau Short ouvert: {new_short_size:.4f} @ {self.format_price(current_price, pair)}")
                        print(f"✅ Nouveau Short ouvert: {new_short_size:.4f} @ {self.format_price(current_price, pair)}")

                        time.sleep(2)

                        # Récupérer prix entrée réel
                        real_pos_new = self.get_real_positions(pair)
                        if real_pos_new and real_pos_new.get('short'):
                            new_entry_short = real_pos_new['short']['entry_price']
                            position.entry_price_short = new_entry_short
                            position.short_open = True
                            logger.info(f"Position Short mise à jour: entrée = {self.format_price(new_entry_short, pair)}")

                    except Exception as e:
                        logger.error(f"❌ Erreur réouverture Short: {e}")
                        print(f"❌ Erreur réouverture Short: {e}")

                    # Replacer ordres au niveau Fibonacci suivant
                    position.current_level += 1
                    self.place_next_level_orders(pair, position, direction='down')

                    # MESSAGE TELEGRAM AVEC VRAIES DONNÉES
                    time.sleep(2)
                    final_pos = self.get_real_positions(pair)
                    if final_pos:
                        message_parts = [f"🔔 <b>TP SHORT EXÉCUTÉ - {pair.split('/')[0]}</b>\n"]
                        message_parts.append(f"💰 Prix TP: ${current_price:.5f}")
                        message_parts.append(f"💵 Profit réalisé: ~{short_profit:+.4f} USDT\n")

                        # Long (doublé) - EN VERT
                        if final_pos.get('long'):
                            ld = final_pos['long']
                            message_parts.append(f"🟢 <b>LONG</b> (doublé - Fib {position.current_level})")
                            message_parts.append(f"🟢 Contrats: {ld['size']:.0f}")
                            message_parts.append(f"🟢 Entrée: ${ld['entry_price']:.5f}")
                            message_parts.append(f"🟢 Marge: {ld['margin']:.7f} USDT")
                            message_parts.append(f"🟢 P&L: {ld['unrealized_pnl']:+.7f} USDT")
                            message_parts.append(f"🟢 ROE: {ld['pnl_percentage']:+.2f}%\n")

                        # Short (réouvert) - EN ROUGE
                        if final_pos.get('short'):
                            sd = final_pos['short']
                            message_parts.append(f"🔴 <b>SHORT</b> (réouvert - Fib 0)")
                            message_parts.append(f"🔴 Contrats: {sd['size']:.0f}")
                            message_parts.append(f"🔴 Entrée: ${sd['entry_price']:.5f}")
                            message_parts.append(f"🔴 Marge: {sd['margin']:.7f} USDT")

                        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
                        self.send_telegram("\n".join(message_parts))

                    # NE PLUS ouvrir nouveau hedge (on reste sur les mêmes paires)
                    # self.open_next_hedge()  # DÉSACTIVÉ

            except Exception as e:
                print(f"⚠️  Erreur vérification ordres {pair}: {e}")

    def place_next_level_orders(self, pair, position, direction):
        """
        Place les ordres pour le prochain niveau Fibonacci
        NOUVELLE LOGIQUE: Place ordres pour BOTH côtés (hedge permanent)
        """

        next_trigger = position.get_next_trigger_pct()
        if not next_trigger:
            logger.info("✅ Fibonacci terminé pour cette paire")
            print("✅ Fibonacci terminé pour cette paire")
            return

        real_pos = self.get_real_positions(pair)
        if not real_pos:
            logger.warning(f"Impossible de récupérer positions pour {pair}")
            return

        logger.info(f"Placement ordres niveau Fibonacci {position.current_level} (+{next_trigger}%)")
        print(f"\n📝 Placement ordres niveau Fibonacci {position.current_level} (+{next_trigger}%)")

        if direction == 'up':  # Prix a monté → SHORT doublé + NOUVEAU LONG réouvert

            # ORDRES POUR LE SHORT (doublé)
            short_data = real_pos.get('short')
            if short_data:
                current_size_short = short_data['size']
                current_entry_short = short_data['entry_price']

                # 1. Calculer prix du prochain doublement Short
                new_double_short_price = position.entry_price_short * (1 + next_trigger / 100)

                # 2. Calculer prix du TP Short
                tp_short_price = self.calculate_breakeven_tp_price(position, real_pos, 'up')
                if not tp_short_price:
                    tp_short_price = current_entry_short * 0.995  # Fallback

                # 3. Placer ordre DOUBLER SHORT
                try:
                    double_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='sell', amount=current_size_short * 2,
                        price=new_double_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
                    )
                    verified = self.verify_order_placed(double_order['id'], pair)
                    if verified:
                        position.orders['double_short'] = double_order['id']
                        logger.info(f"✅ Doubler Short @ {self.format_price(new_double_short_price, pair)}")
                        print(f"✅ Doubler Short @ {self.format_price(new_double_short_price, pair)} (+{next_trigger}%)")
                except Exception as e:
                    logger.error(f"Erreur Doubler Short: {e}")
                    print(f"❌ Erreur Doubler Short: {e}")

                # 4. Placer TP SHORT
                try:
                    tp_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='buy', amount=current_size_short,
                        price=tp_short_price, params={'tradeSide': 'close', 'holdSide': 'short'}
                    )
                    verified = self.verify_order_placed(tp_order['id'], pair)
                    if verified:
                        position.orders['tp_short'] = tp_order['id']
                        profit_pct = ((current_entry_short - tp_short_price) / current_entry_short) * 100
                        logger.info(f"✅ TP Short @ {self.format_price(tp_short_price, pair)}")
                        print(f"✅ Nouveau TP Short @ {self.format_price(tp_short_price, pair)} ({profit_pct:+.2f}%)")
                except Exception as e:
                    logger.error(f"Erreur TP Short: {e}")
                    print(f"❌ Erreur TP Short: {e}")

            # ORDRES POUR LE NOUVEAU LONG (réouvert au niveau Fib 0)
            long_data = real_pos.get('long')
            if long_data:
                new_long_size = long_data['size']
                new_long_entry = long_data['entry_price']

                # TP Long au premier niveau Fibonacci (utilise fib_levels[0])
                first_fib_level = position.fib_levels[0] if hasattr(position, 'fib_levels') else 0.1
                tp_long_price = new_long_entry * (1 + first_fib_level / 100)

                # Placer TP Long
                try:
                    tp_long_order = self.place_tpsl_order(
                        symbol=pair,
                        plan_type='profit_plan',
                        trigger_price=tp_long_price,
                        hold_side='long',
                        size=new_long_size
                    )
                    if tp_long_order and tp_long_order.get('id'):
                        position.orders['tp_long'] = tp_long_order['id']
                        logger.info(f"✅ TP Long (nouveau) @ {self.format_price(tp_long_price, pair)}")
                        print(f"✅ TP Long (nouveau) @ {self.format_price(tp_long_price, pair)} (+{first_fib_level}%)")
                except Exception as e:
                    logger.error(f"Erreur TP Long: {e}")
                    print(f"❌ Erreur TP Long: {e}")

                # Doubler Long (si prix descend depuis le nouveau point d'entrée)
                double_long_price = new_long_entry * (1 - first_fib_level / 100)

                try:
                    double_long_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='buy', amount=new_long_size * 2,
                        price=double_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                    )
                    verified = self.verify_order_placed(double_long_order['id'], pair)
                    if verified:
                        position.orders['double_long'] = double_long_order['id']
                        logger.info(f"✅ Doubler Long @ {self.format_price(double_long_price, pair)}")
                        print(f"✅ Doubler Long @ {self.format_price(double_long_price, pair)} (-{first_fib_level}%)")
                except Exception as e:
                    logger.error(f"Erreur Doubler Long: {e}")
                    print(f"❌ Erreur Doubler Long: {e}")

        elif direction == 'down':  # Prix a descendu → LONG doublé + NOUVEAU SHORT réouvert

            # ORDRES POUR LE LONG (doublé)
            long_data = real_pos.get('long')
            if long_data:
                current_size_long = long_data['size']
                current_entry_long = long_data['entry_price']

                # 1. Calculer prix du prochain doublement Long
                new_double_long_price = position.entry_price_long * (1 - next_trigger / 100)

                # 2. Calculer prix du TP Long
                tp_long_price = self.calculate_breakeven_tp_price(position, real_pos, 'down')
                if not tp_long_price:
                    tp_long_price = current_entry_long * 1.005  # Fallback

                # 3. Placer ordre DOUBLER LONG
                try:
                    double_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='buy', amount=current_size_long * 2,
                        price=new_double_long_price, params={'tradeSide': 'open', 'holdSide': 'long'}
                    )
                    verified = self.verify_order_placed(double_order['id'], pair)
                    if verified:
                        position.orders['double_long'] = double_order['id']
                        logger.info(f"✅ Doubler Long @ {self.format_price(new_double_long_price, pair)}")
                        print(f"✅ Doubler Long @ {self.format_price(new_double_long_price, pair)} (-{next_trigger}%)")
                except Exception as e:
                    logger.error(f"Erreur Doubler Long: {e}")
                    print(f"❌ Erreur Doubler Long: {e}")

                # 4. Placer TP LONG
                try:
                    tp_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='sell', amount=current_size_long,
                        price=tp_long_price, params={'tradeSide': 'close', 'holdSide': 'long'}
                    )
                    verified = self.verify_order_placed(tp_order['id'], pair)
                    if verified:
                        position.orders['tp_long'] = tp_order['id']
                        profit_pct = ((tp_long_price - current_entry_long) / current_entry_long) * 100
                        logger.info(f"✅ TP Long @ {self.format_price(tp_long_price, pair)}")
                        print(f"✅ Nouveau TP Long @ {self.format_price(tp_long_price, pair)} ({profit_pct:+.2f}%)")
                except Exception as e:
                    logger.error(f"Erreur TP Long: {e}")
                    print(f"❌ Erreur TP Long: {e}")

            # ORDRES POUR LE NOUVEAU SHORT (réouvert au niveau Fib 0)
            short_data = real_pos.get('short')
            if short_data:
                new_short_size = short_data['size']
                new_short_entry = short_data['entry_price']

                # TP Short au premier niveau Fibonacci (utilise fib_levels[0])
                first_fib_level = position.fib_levels[0] if hasattr(position, 'fib_levels') else 0.1
                tp_short_price = new_short_entry * (1 - first_fib_level / 100)

                # Placer TP Short
                try:
                    tp_short_order = self.place_tpsl_order(
                        symbol=pair,
                        plan_type='profit_plan',
                        trigger_price=tp_short_price,
                        hold_side='short',
                        size=new_short_size
                    )
                    if tp_short_order and tp_short_order.get('id'):
                        position.orders['tp_short'] = tp_short_order['id']
                        logger.info(f"✅ TP Short (nouveau) @ {self.format_price(tp_short_price, pair)}")
                        print(f"✅ TP Short (nouveau) @ {self.format_price(tp_short_price, pair)} (-{first_fib_level}%)")
                except Exception as e:
                    logger.error(f"Erreur TP Short: {e}")
                    print(f"❌ Erreur TP Short: {e}")

                # Doubler Short (si prix monte depuis le nouveau point d'entrée)
                double_short_price = new_short_entry * (1 + first_fib_level / 100)

                try:
                    double_short_order = self.exchange.create_order(
                        symbol=pair, type='limit', side='sell', amount=new_short_size * 2,
                        price=double_short_price, params={'tradeSide': 'open', 'holdSide': 'short'}
                    )
                    verified = self.verify_order_placed(double_short_order['id'], pair)
                    if verified:
                        position.orders['double_short'] = double_short_order['id']
                        logger.info(f"✅ Doubler Short @ {self.format_price(double_short_price, pair)}")
                        print(f"✅ Doubler Short @ {self.format_price(double_short_price, pair)} (+{first_fib_level}%)")
                except Exception as e:
                    logger.error(f"Erreur Doubler Short: {e}")
                    print(f"❌ Erreur Doubler Short: {e}")

    def open_next_hedge(self):
        """Ouvre un nouveau hedge sur la prochaine paire disponible"""
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
        Pour repartir sur des bases propres
        Utilise force_close_position pour garantir fermeture complète
        """
        logger.info("=== NETTOYAGE COMPLET DÉMARRÉ ===")
        print("\n🧹 NETTOYAGE DES POSITIONS ET ORDRES EXISTANTS...")
        self.send_telegram("🧹 <b>Nettoyage session précédente...</b>")

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

        # Attendre un peu avant de commencer
        time.sleep(2)

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

                            # Tolérance de 1% de différence
                            if abs(long_size - short_size) / max(long_size, short_size) > 0.01:
                                warnings.append(f"⚠️ {pair.split('/')[0]}: Hedge déséquilibré (L:{long_size:.2f} S:{short_size:.2f})")
                                logger.warning(f"Hedge déséquilibré sur {pair}")

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
                pnl = long_data['unrealized_pnl']
                total_pnl += pnl
                entry_long = long_data['entry_price']

                # Calcul variation % par rapport au prix d'entrée MARKET
                variation_pct = ((current_price - entry_long) / entry_long) * 100

                pair_msg += f"\n📈 <b>LONG</b> (Hedge)\n"
                pair_msg += f"   Entrée: {self.format_price(entry_long, pair)}\n"
                pair_msg += f"   Variation: {variation_pct:+.2f}%\n"
                pair_msg += f"   P&L: ${pnl:+.2f} (ROE: {long_data['pnl_percentage']:+.1f}%)\n"

                # Afficher TP
                next_trigger = pos.get_next_trigger_pct()
                if next_trigger:
                    next_price = pos.entry_price_long * (1 + next_trigger / 100)
                    pair_msg += f"   🎯 TP: {self.format_price(next_price, pair)} (+{next_trigger}%)\n"

            # SHORT (si ouvert)
            if short_data:
                pnl = short_data['unrealized_pnl']
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
                next_trigger = pos.get_next_trigger_pct()
                if next_trigger:
                    next_price = pos.entry_price_short * (1 - next_trigger / 100)
                    pair_msg += f"   🎯 TP: {self.format_price(next_price, pair)} (-{next_trigger}%)\n"

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

            # NETTOYER TOUTES LES POSITIONS ET ORDRES EXISTANTS
            self.cleanup_all_positions_and_orders()

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

            # Ouvrir hedges sur TOUTES les paires disponibles
            logger.info(f"Ouverture des hedges sur {len(self.available_pairs)} paires")
            print(f"\n📊 Ouverture des hedges sur {len(self.available_pairs)} paires...")

            pairs_to_open = self.available_pairs.copy()
            for idx, pair in enumerate(pairs_to_open):
                if self.capital_used >= self.MAX_CAPITAL:
                    logger.warning(f"Capital max atteint, arrêt ouverture à {idx} paires")
                    break

                logger.info(f"Ouverture hedge {idx+1}/{len(pairs_to_open)}: {pair}")
                success = self.open_hedge_with_limit_orders(pair)

                if success and idx < len(pairs_to_open) - 1:
                    # Attendre 3s entre chaque ouverture
                    logger.info(f"Attente 3s avant prochaine paire...")
                    time.sleep(3)

            # Boucle
            iteration = 0
            while True:
                # DEBUG: Afficher prix en temps réel
                if self.active_positions:
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
                            next_trigger = position.get_next_trigger_pct()

                            print(f"   📈 LONG:")
                            print(f"      Prix entrée: {self.format_price(entry_long, pair)}")
                            print(f"      Variation: {change_pct:+.4f}%")
                            print(f"      Trigger: +{next_trigger}%")
                            print(f"      Distance trigger: {(next_trigger - change_pct):.4f}%")

                        # Short (si ouvert)
                        if position.short_open:
                            entry_short = position.entry_price_short
                            change_pct = ((current_price - entry_short) / entry_short) * 100
                            next_trigger = position.get_next_trigger_pct()

                            print(f"   📉 SHORT:")
                            print(f"      Prix entrée: {self.format_price(entry_short, pair)}")
                            print(f"      Variation: {change_pct:+.4f}%")
                            print(f"      Trigger baisse: -{next_trigger}%")
                            print(f"      Distance trigger: {(abs(change_pct) - next_trigger):.4f}%")

                # Vérifier ordres exécutés
                self.check_orders_status(iteration)

                # Vérifier commandes Telegram (toutes les 2 secondes)
                if iteration % 2 == 0:
                    self.check_telegram_commands()

                # VÉRIFICATION AUTOMATIQUE DE SANTÉ (toutes les 60 secondes)
                self.perform_health_check()

                # Status Telegram (désactivé car remplacé par health check)
                # self.send_status_telegram()

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
