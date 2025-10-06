#!/usr/bin/env python3
"""
Telegram News Bot - Envoie les dernières actualités toutes les 5 minutes
Utilise Claude API pour analyser et résumer les news
"""

import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
MARKETAUX_API_KEY = os.environ.get("MARKETAUX_API_KEY", "")

# News categories
CATEGORIES = ["finance", "trading", "politics", "economy"]

def get_news_finnhub():
    """Récupère les news depuis Finnhub (finance/trading)"""
    if not FINNHUB_API_KEY:
        return []

    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        news = response.json()
        return news[:10]  # Limite à 10 articles
    except Exception as e:
        print(f"Erreur Finnhub: {e}")
        return []


def get_news_marketaux():
    """Récupère les news depuis Marketaux (finance/politique/économie)"""
    if not MARKETAUX_API_KEY:
        return []

    url = f"https://api.marketaux.com/v1/news/all?api_token={MARKETAUX_API_KEY}&limit=10"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except Exception as e:
        print(f"Erreur Marketaux: {e}")
        return []


def analyze_news_with_claude(news_articles):
    """Utilise Claude pour analyser et résumer les news"""
    if not ANTHROPIC_API_KEY or not news_articles:
        return None

    # Prépare le contexte des news
    news_text = "\n\n".join([
        f"Titre: {article.get('headline', article.get('title', 'Sans titre'))}\n"
        f"Source: {article.get('source', 'Inconnue')}\n"
        f"Résumé: {article.get('summary', article.get('description', 'N/A'))[:200]}"
        for article in news_articles[:5]  # Top 5 news
    ])

    prompt = f"""Analyse ces actualités récentes et fournis un résumé concis et informatif en français:

{news_text}

Instructions:
- Résume les 3-5 points les plus importants
- Focus sur finance, trading, politique et économie
- Style: professionnel mais accessible
- Maximum 10 lignes
- Ajoute des émojis pertinents (📈📉💰🏦🌍)
"""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Erreur Claude API: {e}")
        return None


def send_telegram_message(text):
    """Envoie un message via Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Configuration Telegram manquante!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Erreur Telegram: {e}")
        return False


def main_loop():
    """Boucle principale - envoie des news toutes les 5 minutes"""
    print("🤖 Bot Telegram News démarré!")
    print(f"Envoi de news toutes les 5 minutes...")

    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Récupération des news...")

            # Récupère les news de différentes sources
            finnhub_news = get_news_finnhub()
            marketaux_news = get_news_marketaux()

            # Combine toutes les news
            all_news = finnhub_news + marketaux_news

            if all_news:
                print(f"✅ {len(all_news)} articles trouvés")

                # Analyse avec Claude
                summary = analyze_news_with_claude(all_news)

                if summary:
                    # Prépare le message
                    timestamp = datetime.now().strftime("%H:%M")
                    message = f"📰 <b>News Update - {timestamp}</b>\n\n{summary}"

                    # Envoie via Telegram
                    if send_telegram_message(message):
                        print("✅ Message envoyé sur Telegram")
                    else:
                        print("❌ Échec envoi Telegram")
                else:
                    print("❌ Échec analyse Claude")
            else:
                print("⚠️ Aucune news trouvée")

            # Attendre 5 minutes
            print("⏳ Attente 5 minutes...")
            time.sleep(300)  # 300 secondes = 5 minutes

        except KeyboardInterrupt:
            print("\n\n🛑 Bot arrêté par l'utilisateur")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")
            time.sleep(60)  # Attente 1 minute en cas d'erreur


if __name__ == "__main__":
    # Vérification de la configuration
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY]):
        print("❌ Configuration manquante!")
        print("Vérifiez que ces variables sont définies dans .env:")
        print("- TELEGRAM_BOT_TOKEN")
        print("- TELEGRAM_CHAT_ID")
        print("- ANTHROPIC_API_KEY")
        print("- FINNHUB_API_KEY (optionnel)")
        print("- MARKETAUX_API_KEY (optionnel)")
    else:
        main_loop()
