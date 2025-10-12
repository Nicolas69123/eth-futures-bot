"""
Configuration du système de logging
"""

import logging
from pathlib import Path
from datetime import datetime
from collections import deque

# Buffer circulaire pour les derniers logs (pour /logs Telegram)
log_buffer = deque(maxlen=50)


class TelegramLogHandler(logging.Handler):
    """Handler personnalisé pour capturer les logs dans le buffer"""
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append(log_entry)


def setup_logging():
    """Configure le système de logging"""
    # Créer dossier logs
    log_dir = Path(__file__).parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f'bot_{datetime.now().strftime("%Y%m%d")}.log'

    # Configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger('trading_bot')

    # Ajouter le handler Telegram
    telegram_handler = TelegramLogHandler()
    telegram_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(telegram_handler)

    return logger


def get_recent_logs(count=20):
    """Retourne les N derniers logs"""
    return list(log_buffer)[-count:]
