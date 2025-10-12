"""
Client Telegram pour envoi de messages
"""

import requests
import logging

logger = logging.getLogger('trading_bot')


class TelegramClient:
    """Gère l'envoi de messages Telegram"""

    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send_message(self, message):
        """Envoie un message sur Telegram"""
        if not self.token or not self.chat_id:
            logger.warning("Token ou Chat ID Telegram manquant")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Erreur Telegram API: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Erreur envoi Telegram: {e}")
            return False

    def get_updates(self, offset=0):
        """Récupère les nouveaux messages Telegram (commandes)"""
        if not self.token:
            return []

        url = f"https://api.telegram.org/bot{self.token}/getUpdates"
        params = {'offset': offset + 1, 'timeout': 0}

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    return data['result']
        except Exception as e:
            logger.error(f"Erreur récupération updates Telegram: {e}")

        return []
