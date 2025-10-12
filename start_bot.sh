#!/bin/bash

# Script de démarrage automatique pour le bot Bitget Hedge Fibonacci
# Usage: ./start_bot.sh

echo "🚀 Démarrage du Bot Bitget Hedge Fibonacci..."

# Vérifier que le .env existe
if [ ! -f .env ]; then
    echo "❌ Erreur: Fichier .env introuvable!"
    echo "📝 Créez un fichier .env à partir de .env.example"
    exit 1
fi

# Charger les variables d'environnement
export $(cat .env | grep -v '^#' | xargs)

# Vérifier les clés API
if [ -z "$BITGET_API_KEY" ] || [ -z "$BITGET_SECRET" ] || [ -z "$BITGET_PASSPHRASE" ]; then
    echo "❌ Erreur: Clés API Bitget manquantes dans .env"
    exit 1
fi

echo "✅ Variables d'environnement chargées"
echo "✅ Clés API Bitget configurées"

# Créer un dossier pour les logs
mkdir -p logs

# Démarrer le bot avec redirection des logs
echo "🤖 Lancement du bot..."
python3 bot/bitget_hedge_fibonacci_v2.py 2>&1 | tee logs/bot_$(date +%Y%m%d_%H%M%S).log
