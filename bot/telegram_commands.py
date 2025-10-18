"""
Module de commandes Telegram pour Bot Trading Fibonacci
Sépare la logique des commandes du bot principal
Inclut système de monitoring et détection d'anomalies
"""

import time
import subprocess
import sys
import logging
from datetime import datetime
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class TelegramCommands:
    """Gestionnaire de toutes les commandes Telegram et monitoring"""

    def __init__(self, bot):
        """
        Args:
            bot: Instance du bot principal (HedgeFibonacciBot)
        """
        self.bot = bot
        self.alerts_enabled = True
        self.is_paused = False
        self.emergency_mode = False
        self.last_anomaly_check = 0
        self.anomalies_detected = []

        # Paramètres modifiables
        self.custom_leverage = None
        self.custom_margin = None
        self.custom_tp_pct = None

        # Thread de monitoring
        self.monitoring_thread = None
        self.monitoring_active = False

    def start_monitoring(self):
        """Démarre le thread de monitoring des anomalies"""
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            logger.info("Thread de monitoring démarré")

    def stop_monitoring(self):
        """Arrête le thread de monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
            logger.info("Thread de monitoring arrêté")

    def _monitoring_loop(self):
        """Boucle de monitoring qui tourne toutes les secondes"""
        while self.monitoring_active:
            try:
                # Vérifier les anomalies toutes les secondes
                self.check_for_anomalies()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Erreur dans monitoring loop: {e}")
                time.sleep(5)

    def check_for_anomalies(self):
        """
        Vérifie les anomalies dans les positions et ordres
        Appelé toutes les secondes par le thread de monitoring
        """
        try:
            anomalies = []

            for pair, position in self.bot.active_positions.items():
                # Récupérer positions réelles
                real_pos = self.bot.get_real_positions(pair)
                if not real_pos:
                    continue

                # Récupérer ordres
                open_orders = self.bot.exchange.fetch_open_orders(symbol=pair)
                tpsl_orders = self.bot.get_tpsl_orders(pair)

                # VÉRIFICATION 1: Cohérence des marges Fibonacci
                if real_pos.get('long'):
                    long_margin = real_pos['long']['margin']
                    expected_next_margin = long_margin * 3  # Fibonacci x3

                    # Chercher l'ordre double short
                    for order in open_orders:
                        if order.get('side') == 'sell' and order.get('type') == 'limit':
                            order_value = float(order.get('amount', 0)) * float(order.get('price', 0))
                            expected_value = expected_next_margin * self.bot.LEVERAGE

                            # Si différence > 20%, c'est une anomalie
                            if abs(order_value - expected_value) / expected_value > 0.2:
                                anomalies.append({
                                    'type': 'MARGE_INCOHERENTE',
                                    'pair': pair,
                                    'side': 'long',
                                    'message': f"Marge Long: {long_margin:.2f} USDT, Ordre Double Short incorrect: {order_value:.2f} (attendu: {expected_value:.2f})"
                                })

                if real_pos.get('short'):
                    short_margin = real_pos['short']['margin']
                    expected_next_margin = short_margin * 3  # Fibonacci x3

                    # Chercher l'ordre double long
                    for order in open_orders:
                        if order.get('side') == 'buy' and order.get('type') == 'limit':
                            order_value = float(order.get('amount', 0)) * float(order.get('price', 0))
                            expected_value = expected_next_margin * self.bot.LEVERAGE

                            # Si différence > 20%, c'est une anomalie
                            if abs(order_value - expected_value) / expected_value > 0.2:
                                anomalies.append({
                                    'type': 'MARGE_INCOHERENTE',
                                    'pair': pair,
                                    'side': 'short',
                                    'message': f"Marge Short: {short_margin:.2f} USDT, Ordre Double Long incorrect: {order_value:.2f} (attendu: {expected_value:.2f})"
                                })

                # VÉRIFICATION 2: TP manquant
                if real_pos.get('long') and position.long_open:
                    tp_found = False
                    for order in tpsl_orders:
                        if order.get('planType') == 'profit_plan' and order.get('side') == 'sell_single':
                            tp_found = True
                            break

                    if not tp_found:
                        anomalies.append({
                            'type': 'TP_MANQUANT',
                            'pair': pair,
                            'side': 'long',
                            'message': f"Position Long ouverte mais TP manquant!"
                        })

                if real_pos.get('short') and position.short_open:
                    tp_found = False
                    for order in tpsl_orders:
                        if order.get('planType') == 'profit_plan' and order.get('side') == 'buy_single':
                            tp_found = True
                            break

                    if not tp_found:
                        anomalies.append({
                            'type': 'TP_MANQUANT',
                            'pair': pair,
                            'side': 'short',
                            'message': f"Position Short ouverte mais TP manquant!"
                        })

                # VÉRIFICATION 3: Ordre double manquant
                if real_pos.get('long'):
                    double_short_found = False
                    for order in open_orders:
                        if order.get('side') == 'sell' and order.get('type') == 'limit':
                            double_short_found = True
                            break

                    if not double_short_found:
                        anomalies.append({
                            'type': 'ORDRE_DOUBLE_MANQUANT',
                            'pair': pair,
                            'side': 'long',
                            'message': f"Position Long mais ordre Double Short manquant!"
                        })

                if real_pos.get('short'):
                    double_long_found = False
                    for order in open_orders:
                        if order.get('side') == 'buy' and order.get('type') == 'limit':
                            double_long_found = True
                            break

                    if not double_long_found:
                        anomalies.append({
                            'type': 'ORDRE_DOUBLE_MANQUANT',
                            'pair': pair,
                            'side': 'short',
                            'message': f"Position Short mais ordre Double Long manquant!"
                        })

                # VÉRIFICATION 4: Position fantôme (dans bot mais pas sur API)
                if position.long_open and not real_pos.get('long'):
                    anomalies.append({
                        'type': 'POSITION_FANTOME',
                        'pair': pair,
                        'side': 'long',
                        'message': f"Bot pense Long ouvert mais API dit non!"
                    })

                if position.short_open and not real_pos.get('short'):
                    anomalies.append({
                        'type': 'POSITION_FANTOME',
                        'pair': pair,
                        'side': 'short',
                        'message': f"Bot pense Short ouvert mais API dit non!"
                    })

            # Si nouvelles anomalies détectées, alerter
            if anomalies and self.alerts_enabled:
                # Éviter spam - alerter seulement si différent de la dernière vérification
                if anomalies != self.anomalies_detected:
                    self.send_anomaly_alert(anomalies)
                    self.anomalies_detected = anomalies
            elif not anomalies and self.anomalies_detected:
                # Anomalies résolues
                self.bot.send_telegram("✅ Toutes les anomalies ont été résolues")
                self.anomalies_detected = []

        except Exception as e:
            logger.error(f"Erreur check_for_anomalies: {e}")

    def send_anomaly_alert(self, anomalies):
        """Envoie une alerte Telegram pour les anomalies détectées"""
        message = ["🚨 <b>ANOMALIES DÉTECTÉES</b>\n"]

        for anomaly in anomalies[:5]:  # Limiter à 5 pour éviter spam
            message.append(f"\n❌ <b>{anomaly['type']}</b>")
            message.append(f"📍 {anomaly['pair'].split('/')[0]} - {anomaly['side'].upper()}")
            message.append(f"💬 {anomaly['message']}")

        if len(anomalies) > 5:
            message.append(f"\n... et {len(anomalies) - 5} autres anomalies")

        message.append(f"\n\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        message.append("\nUtilisez /debug pour plus de détails")

        self.bot.send_telegram("\n".join(message))

    # ========== COMMANDES TRADING ==========

    def cmd_orders(self):
        """Affiche tous les ordres limites et TP actifs"""
        try:
            message = ["📋 <b>ORDRES ACTIFS</b>\n"]
            has_orders = False

            for pair in self.bot.volatile_pairs:
                # Ordres limites
                open_orders = self.bot.exchange.fetch_open_orders(symbol=pair)
                # Ordres TP/SL
                tpsl_orders = self.bot.get_tpsl_orders(pair)

                if not open_orders and not tpsl_orders:
                    continue

                has_orders = True
                pair_name = pair.split('/')[0]
                message.append(f"\n━━━━ <b>{pair_name}</b> ━━━━")

                # Ordres limites (Double)
                for order in open_orders:
                    order_type = "🔵 Double Long" if order['side'] == 'buy' else "🔴 Double Short"
                    price = float(order.get('price', 0))
                    amount = float(order.get('amount', 0))
                    message.append(f"{order_type}: ${price:.5f} ({amount:.0f} contrats)")

                # Ordres TP
                for order in tpsl_orders:
                    if order.get('planType') == 'profit_plan':
                        tp_type = "🟢 TP Long" if order['side'] == 'sell_single' else "🔴 TP Short"
                        price = float(order.get('triggerPrice', 0))
                        size = float(order.get('size', 0))
                        message.append(f"{tp_type}: ${price:.5f} ({size:.0f} contrats)")

            if not has_orders:
                message.append("⚠️ Aucun ordre actif")

            message.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            self.bot.send_telegram("\n".join(message))

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /orders: {e}")

    def cmd_performance(self):
        """Affiche les statistiques de performance"""
        try:
            total_trades = len(self.bot.pnl_history)
            if total_trades == 0:
                self.bot.send_telegram("📊 Aucune statistique disponible (pas de trades)")
                return

            # Calculer statistiques
            wins = [t for t in self.bot.pnl_history if t['pnl'] > 0]
            losses = [t for t in self.bot.pnl_history if t['pnl'] < 0]

            win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
            avg_win = sum(w['pnl'] for w in wins) / len(wins) if wins else 0
            avg_loss = sum(l['pnl'] for l in losses) / len(losses) if losses else 0

            # P&L total
            total_unrealized = 0
            for pair in self.bot.active_positions:
                real_pos = self.bot.get_real_positions(pair)
                if real_pos:
                    if real_pos.get('long'):
                        total_unrealized += real_pos['long'].get('unrealized_pnl', 0)
                    if real_pos.get('short'):
                        total_unrealized += real_pos['short'].get('unrealized_pnl', 0)

            total_fees = self.bot.get_total_fees()
            pnl_net = self.bot.total_profit + total_unrealized - total_fees

            message = f"""
📊 <b>PERFORMANCE SESSION</b>

📈 <b>Statistiques:</b>
• Trades total: {total_trades}
• Trades gagnants: {len(wins)}
• Trades perdants: {len(losses)}
• Win rate: {win_rate:.1f}%

💰 <b>Moyennes:</b>
• Gain moyen: {avg_win:+.4f} USDT
• Perte moyenne: {avg_loss:+.4f} USDT
• Ratio W/L: {abs(avg_win/avg_loss):.2f} si perte

💎 <b>P&L Net:</b>
• Réalisé: {self.bot.total_profit:+.7f} USDT
• Non réalisé: {total_unrealized:+.7f} USDT
• Frais: -{total_fees:.7f} USDT
━━━━━━━━━━━━━━━━━
<b>TOTAL NET: {pnl_net:+.7f} USDT</b>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /performance: {e}")

    def cmd_fees(self):
        """Affiche le détail des frais"""
        try:
            total_fees = self.bot.get_total_fees()

            # Calculer frais par paire
            fees_by_pair = {}
            session_start_ms = int(self.bot.session_start_time.timestamp() * 1000)

            for pair in self.bot.volatile_pairs:
                trades = self.bot.exchange.fetch_my_trades(pair, since=session_start_ms, limit=500)
                pair_fees = sum(float(t.get('fee', {}).get('cost', 0)) for t in trades)
                if pair_fees > 0:
                    fees_by_pair[pair] = pair_fees

            message = ["💸 <b>FRAIS DE TRADING</b>\n"]

            if fees_by_pair:
                message.append("<b>Par paire:</b>")
                for pair, fees in sorted(fees_by_pair.items(), key=lambda x: x[1], reverse=True):
                    pair_name = pair.split('/')[0]
                    message.append(f"• {pair_name}: {fees:.7f} USDT")

            message.append(f"\n━━━━━━━━━━━━━━━━━")
            message.append(f"<b>TOTAL: {total_fees:.7f} USDT</b>")
            message.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")

            self.bot.send_telegram("\n".join(message))

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /fees: {e}")

    # ========== COMMANDES PARAMÈTRES ==========

    def cmd_setleverage(self, value):
        """Change le levier"""
        try:
            leverage = int(value)
            if leverage < 1 or leverage > 125:
                self.bot.send_telegram("❌ Levier doit être entre 1 et 125")
                return

            old_leverage = self.bot.LEVERAGE
            self.bot.LEVERAGE = leverage
            self.custom_leverage = leverage

            message = f"""
⚙️ <b>LEVIER MODIFIÉ</b>

Ancien: x{old_leverage}
Nouveau: x{leverage}

⚠️ Appliqué aux NOUVELLES positions seulement

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except ValueError:
            self.bot.send_telegram("❌ Usage: /setleverage <nombre>")

    def cmd_setmargin(self, value):
        """Change la marge initiale"""
        try:
            margin = float(value)
            if margin < 0.1 or margin > 100:
                self.bot.send_telegram("❌ Marge doit être entre 0.1 et 100 USDT")
                return

            old_margin = self.bot.INITIAL_MARGIN
            self.bot.INITIAL_MARGIN = margin
            self.custom_margin = margin

            message = f"""
⚙️ <b>MARGE MODIFIÉE</b>

Ancienne: {old_margin} USDT
Nouvelle: {margin} USDT

⚠️ Appliqué aux NOUVELLES positions seulement

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except ValueError:
            self.bot.send_telegram("❌ Usage: /setmargin <nombre>")

    def cmd_settpct(self, value):
        """Change le pourcentage de TP"""
        try:
            tp_pct = float(value)
            if tp_pct < 0.1 or tp_pct > 5:
                self.bot.send_telegram("❌ TP% doit être entre 0.1 et 5")
                return

            self.custom_tp_pct = tp_pct

            message = f"""
⚙️ <b>TP% MODIFIÉ</b>

Nouveau: {tp_pct}%

⚠️ Appliqué aux NOUVEAUX ordres TP seulement

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except ValueError:
            self.bot.send_telegram("❌ Usage: /settpct <nombre>")

    def cmd_pause(self):
        """Met en pause l'ouverture de nouvelles positions"""
        self.is_paused = True
        message = f"""
⏸️ <b>BOT EN PAUSE</b>

• Positions existantes: Continuent
• Nouvelles positions: Bloquées

Utilisez /resume pour reprendre

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        self.bot.send_telegram(message)

    def cmd_resume(self):
        """Reprend après une pause"""
        self.is_paused = False
        message = f"""
▶️ <b>BOT REPRIS</b>

Le bot peut à nouveau ouvrir des positions

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        self.bot.send_telegram(message)

    # ========== COMMANDES SÉCURITÉ ==========

    def cmd_emergency(self):
        """Mode urgence: ferme tout et pause"""
        try:
            self.emergency_mode = True
            self.is_paused = True

            self.bot.send_telegram("🚨 <b>MODE URGENCE ACTIVÉ</b>\n\nFermeture de TOUTES les positions...")

            # Fermer toutes les positions
            self.bot.cleanup_all_positions_and_orders()

            message = f"""
🚨 <b>MODE URGENCE</b>

✅ Toutes positions fermées
✅ Tous ordres annulés
⏸️ Bot en pause

Pour reprendre: /resume

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur emergency: {e}")

    def cmd_alert(self, state):
        """Active/désactive les alertes"""
        if state.lower() == 'on':
            self.alerts_enabled = True
            self.bot.send_telegram("🔔 Alertes activées")
        elif state.lower() == 'off':
            self.alerts_enabled = False
            self.bot.send_telegram("🔕 Alertes désactivées")
        else:
            self.bot.send_telegram("❌ Usage: /alert on ou /alert off")

    # ========== COMMANDES MONITORING ==========

    def cmd_stats(self):
        """Statistiques complètes de la session"""
        try:
            # Durée session
            session_duration = datetime.now() - self.bot.session_start_time
            hours = session_duration.total_seconds() / 3600

            # Compter positions
            total_positions = 0
            for pair in self.bot.active_positions:
                real_pos = self.bot.get_real_positions(pair)
                if real_pos:
                    if real_pos.get('long'):
                        total_positions += 1
                    if real_pos.get('short'):
                        total_positions += 1

            message = f"""
📊 <b>STATISTIQUES SESSION</b>

⏱️ <b>Durée:</b> {hours:.1f} heures
📍 <b>Positions actives:</b> {total_positions}
💼 <b>Capital utilisé:</b> ${self.bot.capital_used:.0f}
📈 <b>Trades effectués:</b> {len(self.bot.pnl_history)}

🔧 <b>Paramètres:</b>
• Levier: x{self.bot.LEVERAGE}
• Marge initiale: {self.bot.INITIAL_MARGIN} USDT
• TP: {self.custom_tp_pct or 0.3}%

📡 <b>État:</b>
• Pause: {'Oui' if self.is_paused else 'Non'}
• Alertes: {'Oui' if self.alerts_enabled else 'Non'}
• Mode urgence: {'Oui' if self.emergency_mode else 'Non'}
• Anomalies: {len(self.anomalies_detected)}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /stats: {e}")

    def cmd_logs(self):
        """Affiche les derniers logs"""
        try:
            # Utiliser le log_buffer du bot principal
            if not hasattr(self.bot, 'log_buffer') or not self.bot.log_buffer:
                self.bot.send_telegram("📜 Aucun log disponible")
                return

            recent_logs = list(self.bot.log_buffer)[-30:]
            logs_text = "\n".join(recent_logs)

            if len(logs_text) > 3500:
                logs_text = logs_text[-3500:]
                logs_text = "...\n" + logs_text

            message = f"""
📜 <b>DERNIERS LOGS</b>

<pre>{logs_text}</pre>

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
            self.bot.send_telegram(message)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /logs: {e}")

    def cmd_debug(self):
        """Affiche les informations de debug et anomalies"""
        try:
            message = ["🔍 <b>DEBUG - ÉTAT DÉTAILLÉ</b>\n"]

            # Anomalies actuelles
            if self.anomalies_detected:
                message.append("🚨 <b>ANOMALIES ACTUELLES:</b>")
                for anomaly in self.anomalies_detected:
                    message.append(f"\n• {anomaly['type']}")
                    message.append(f"  {anomaly['pair']} - {anomaly['side']}")
                    message.append(f"  {anomaly['message']}")
            else:
                message.append("✅ Aucune anomalie détectée")

            message.append("\n━━━━━━━━━━━━━━━━━")
            message.append("\n<b>ÉTAT PAR POSITION:</b>")

            for pair, position in self.bot.active_positions.items():
                pair_name = pair.split('/')[0]
                message.append(f"\n<b>{pair_name}:</b>")

                # État interne
                message.append(f"• Bot Long: {'Oui' if position.long_open else 'Non'}")
                message.append(f"• Bot Short: {'Oui' if position.short_open else 'Non'}")
                message.append(f"• Fib Long: {position.long_fib_level}")
                message.append(f"• Fib Short: {position.short_fib_level}")

                # État API
                real_pos = self.bot.get_real_positions(pair)
                if real_pos:
                    message.append(f"• API Long: {'Oui' if real_pos.get('long') else 'Non'}")
                    message.append(f"• API Short: {'Oui' if real_pos.get('short') else 'Non'}")

                # Ordres
                open_orders = self.bot.exchange.fetch_open_orders(symbol=pair)
                tpsl_orders = self.bot.get_tpsl_orders(pair)
                message.append(f"• Ordres limites: {len(open_orders)}")
                message.append(f"• Ordres TP/SL: {len(tpsl_orders)}")

            message.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
            self.bot.send_telegram("\n".join(message))

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /debug: {e}")

    # ========== COMMANDES SYSTÈME ==========

    def cmd_help(self):
        """Affiche l'aide des commandes"""
        message = """
🤖 <b>COMMANDES BOT TRADING</b>

📊 <b>Trading:</b>
/orders - Tous les ordres actifs
/performance - Statistiques de performance
/fees - Détail des frais

⚙️ <b>Paramètres:</b>
/setleverage <X> - Changer levier (1-125)
/setmargin <X> - Marge initiale (0.1-100)
/settpct <X> - TP en % (0.1-5)
/pause - Pause nouvelles positions
/resume - Reprendre après pause

🛡️ <b>Sécurité:</b>
/emergency - Fermer tout + pause
/alert on/off - Activer/désactiver alertes

📈 <b>Monitoring:</b>
/stats - Statistiques session
/logs - Derniers logs
/debug - Infos debug + anomalies

🔧 <b>Système:</b>
/update - Mise à jour + restart
/restart - Redémarrer bot
/stop - Arrêter bot
/help - Cette aide
"""
        self.bot.send_telegram(message)

    def cmd_update(self):
        """Met à jour depuis GitHub et redémarre"""
        logger.info("Commande /update reçue")
        self.bot.send_telegram("🔄 <b>MISE À JOUR...</b>\n\n⚠️ Le bot va redémarrer.\n\nPatientez 20 secondes.")

        try:
            # IMPORTANT: Sauvegarder l'ID AVANT de quitter pour éviter la boucle
            self.bot.save_last_update_id()
            logger.info("last_telegram_update_id sauvegardé avant update")

            manage_script = Path(__file__).parent.parent / 'manage_local.sh'

            if not manage_script.exists():
                self.bot.send_telegram("❌ Script manage_local.sh introuvable!")
                return

            subprocess.Popen(['bash', str(manage_script), 'update'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           start_new_session=True)

            time.sleep(1)  # Petite attente pour que le message parte
            sys.exit(0)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /update: {e}")

    def cmd_restart(self):
        """Redémarre le bot"""
        logger.info("Commande /restart reçue")
        self.bot.send_telegram("♻️ <b>REDÉMARRAGE...</b>\n\n⚠️ Le bot va redémarrer.\n\nPatientez 20 secondes.")

        try:
            # IMPORTANT: Sauvegarder l'ID AVANT de quitter pour éviter la boucle
            self.bot.save_last_update_id()
            logger.info("last_telegram_update_id sauvegardé avant restart")

            manage_script = Path(__file__).parent.parent / 'manage_local.sh'

            if not manage_script.exists():
                self.bot.send_telegram("❌ Script manage_local.sh introuvable!")
                return

            subprocess.Popen(['bash', str(manage_script), 'restart'],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           start_new_session=True)

            time.sleep(1)  # Petite attente pour que le message parte
            sys.exit(0)

        except Exception as e:
            self.bot.send_telegram(f"❌ Erreur /restart: {e}")

    def cmd_stop(self, confirm=False):
        """Arrête le bot"""
        if not confirm:
            message = """
⚠️ <b>CONFIRMATION REQUISE</b>

Pour confirmer l'arrêt, envoyez:
/stop CONFIRM
"""
            self.bot.send_telegram(message)
        else:
            self.bot.send_telegram("⏹️ <b>ARRÊT DU BOT...</b>\n\nFermeture des positions...")
            self.bot.cleanup_all_positions_and_orders()
            self.bot.send_telegram("🛑 Bot arrêté.")
            time.sleep(2)
            sys.exit(0)

    def process_command(self, command):
        """
        Point d'entrée principal pour traiter les commandes

        Args:
            command: La commande Telegram reçue (ex: "/help", "/setleverage 50")
        """
        try:
            parts = command.split(maxsplit=1)
            cmd = parts[0].lower()
            args = parts[1] if len(parts) > 1 else None

            # Commandes Trading
            if cmd == '/orders':
                self.cmd_orders()
            elif cmd == '/performance':
                self.cmd_performance()
            elif cmd == '/fees':
                self.cmd_fees()

            # Commandes Paramètres
            elif cmd == '/setleverage' and args:
                self.cmd_setleverage(args)
            elif cmd == '/setmargin' and args:
                self.cmd_setmargin(args)
            elif cmd == '/settpct' and args:
                self.cmd_settpct(args)
            elif cmd == '/pause':
                self.cmd_pause()
            elif cmd == '/resume':
                self.cmd_resume()

            # Commandes Sécurité
            elif cmd == '/emergency':
                self.cmd_emergency()
            elif cmd == '/alert' and args:
                self.cmd_alert(args)

            # Commandes Monitoring
            elif cmd == '/stats':
                self.cmd_stats()
            elif cmd == '/logs':
                self.cmd_logs()
            elif cmd == '/debug':
                self.cmd_debug()

            # Commandes Système
            elif cmd == '/help':
                self.cmd_help()
            elif cmd == '/update':
                self.cmd_update()
            elif cmd == '/restart':
                self.cmd_restart()
            elif cmd == '/stop':
                if args == 'CONFIRM':
                    self.cmd_stop(confirm=True)
                else:
                    self.cmd_stop(confirm=False)

            else:
                self.bot.send_telegram(f"❌ Commande inconnue: {cmd}\n\nTapez /help pour l'aide")

        except Exception as e:
            logger.error(f"Erreur traitement commande {command}: {e}")
            self.bot.send_telegram(f"❌ Erreur: {e}")