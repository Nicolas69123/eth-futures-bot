#!/bin/bash

# Script de lancement rapide du bot
# Place ce script où tu veux sur ton Mac et lance-le

echo "🚀 LANCEMENT RAPIDE DU BOT TRADING"
echo "==================================="
echo ""

# Se connecter et lancer en une commande
ssh -i "$HOME/Downloads/ssh-key-2025-10-12 (1).key" ubuntu@130.110.243.130 << 'EOF'
cd eth-futures-bot

# Vérifier si le bot tourne déjà
if screen -list | grep -q "trading"; then
    echo "⚠️  Le bot tourne déjà!"
    echo "Pour voir les logs: screen -r trading"
else
    echo "🚀 Lancement du bot..."
    screen -dmS trading bash -c './start_bot.sh'
    sleep 2

    if screen -list | grep -q "trading"; then
        echo "✅ Bot démarré avec succès!"
        echo ""
        echo "📊 Commandes utiles:"
        echo "  - Voir les logs: screen -r trading"
        echo "  - Détacher: Ctrl+A puis D"
        echo "  - Arrêter: screen -X -S trading quit"
    else
        echo "❌ Erreur au démarrage"
    fi
fi
EOF

echo ""
echo "✅ Terminé! Le bot tourne sur Oracle Cloud 24/7"