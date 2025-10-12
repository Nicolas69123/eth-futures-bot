"""
Système d'auto-recovery pour détecter et corriger les problèmes automatiquement
"""

import logging
import time

logger = logging.getLogger('trading_bot')


class AutoRecovery:
    """
    Système d'auto-correction qui tourne en arrière-plan
    Vérifie et corrige automatiquement les problèmes d'ordres
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.last_check = time.time()
        self.check_interval = 30  # Vérifier toutes les 30 secondes
        self.recovery_count = 0

    def run_check(self):
        """
        Exécute les vérifications et corrections
        Appelé depuis la boucle principale
        """
        current_time = time.time()

        if current_time - self.last_check < self.check_interval:
            return

        self.last_check = current_time

        try:
            logger.info("=== AUTO-RECOVERY: Démarrage ===")
            corrections = []

            # Vérifier chaque position active
            for pair, position in list(self.bot.active_positions.items()):
                try:
                    pair_corrections = self.check_position_orders(pair, position)
                    if pair_corrections:
                        corrections.extend(pair_corrections)
                except Exception as e:
                    logger.error(f"Erreur vérification {pair}: {e}")

            if corrections:
                self.recovery_count += len(corrections)
                logger.info(f"✅ AUTO-RECOVERY: {len(corrections)} corrections effectuées")
                logger.info(f"Corrections: {corrections}")

                # Notifier sur Telegram si beaucoup de corrections
                if len(corrections) >= 3:
                    self.bot.send_telegram(f"🔧 <b>Auto-Recovery</b>\n\n{len(corrections)} corrections effectuées:\n" + "\n".join(corrections[:5]))

            logger.info("=== AUTO-RECOVERY: Terminé ===")

        except Exception as e:
            logger.error(f"Erreur générale auto-recovery: {e}")

    def check_position_orders(self, pair, position):
        """
        Vérifie qu'une position a tous ses ordres nécessaires
        Retourne liste des corrections effectuées
        """
        corrections = []

        try:
            real_pos = self.bot.get_real_positions(pair)
            if not real_pos:
                return corrections

            # VÉRIFIER TP LONG MANQUANT
            if real_pos.get('long') and not position.orders.get('tp_long'):
                logger.warning(f"⚠️ TP Long manquant sur {pair}")
                corrections.append(f"TP Long manquant sur {pair.split('/')[0]}")
                # TODO: Replacer TP Long
                # self.replace_tp_long(pair, position, real_pos['long'])

            # VÉRIFIER TP SHORT MANQUANT
            if real_pos.get('short') and not position.orders.get('tp_short'):
                logger.warning(f"⚠️ TP Short manquant sur {pair}")
                corrections.append(f"TP Short manquant sur {pair.split('/')[0]}")
                # TODO: Replacer TP Short
                # self.replace_tp_short(pair, position, real_pos['short'])

            # SYNC ÉTAT POSITIONS
            # Si API dit Long fermé mais bot pense ouvert
            if not real_pos.get('long') and position.long_open:
                logger.info(f"Sync: Long fermé sur {pair}")
                position.long_open = False
                corrections.append(f"Sync Long fermé {pair.split('/')[0]}")

            if not real_pos.get('short') and position.short_open:
                logger.info(f"Sync: Short fermé sur {pair}")
                position.short_open = False
                corrections.append(f"Sync Short fermé {pair.split('/')[0]}")

            # Si API dit Long ouvert mais bot pense fermé
            if real_pos.get('long') and not position.long_open:
                logger.info(f"Sync: Long ouvert sur {pair}")
                position.long_open = True
                position.entry_price_long = real_pos['long']['entry_price']
                corrections.append(f"Sync Long ouvert {pair.split('/')[0]}")

            if real_pos.get('short') and not position.short_open:
                logger.info(f"Sync: Short ouvert sur {pair}")
                position.short_open = True
                position.entry_price_short = real_pos['short']['entry_price']
                corrections.append(f"Sync Short ouvert {pair.split('/')[0]}")

        except Exception as e:
            logger.error(f"Erreur check_position_orders {pair}: {e}")

        return corrections

    def replace_tp_long(self, pair, position, long_data):
        """Replace un TP Long manquant (TODO)"""
        pass

    def replace_tp_short(self, pair, position, short_data):
        """Replace un TP Short manquant (TODO)"""
        pass
