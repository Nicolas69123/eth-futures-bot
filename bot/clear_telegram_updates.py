#!/usr/bin/env python3
"""
Script pour vider les commandes Telegram en attente
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')

if not token:
    print("❌ TELEGRAM_BOT_TOKEN manquant dans .env")
    exit(1)

# Get all pending updates
url = f"https://api.telegram.org/bot{token}/getUpdates"
response = requests.get(url)
data = response.json()

if not data.get('ok'):
    print(f"❌ Erreur API: {data}")
    exit(1)

updates = data.get('result', [])
print(f"📊 {len(updates)} commandes Telegram en attente")

if updates:
    # Get last update_id
    last_id = max([u['update_id'] for u in updates])

    # Mark all as read by calling with offset = last_id + 1
    clear_url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_id + 1}"
    clear_response = requests.get(clear_url)

    if clear_response.json().get('ok'):
        print(f"✅ Toutes les commandes ({len(updates)}) ont été vidées!")
        print(f"   Dernier update_id: {last_id}")
    else:
        print(f"❌ Erreur lors du vidage: {clear_response.json()}")
else:
    print("✅ Aucune commande en attente")
