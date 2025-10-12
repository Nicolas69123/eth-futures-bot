#!/bin/bash

# Script de gestion LOCAL sur le serveur Oracle
# Ce fichier sera copié sur le serveur et appelé par les commandes Telegram

ACTION="$1"

case "$ACTION" in
    restart)
        echo "♻️ Redémarrage du bot..."
        cd ~/eth-futures-bot
        screen -X -S trading quit 2>/dev/null
        sleep 3
        screen -dmS trading bash -c './start_bot.sh'
        sleep 2
        if screen -list | grep -q "trading"; then
            echo "✅ Bot redémarré"
        else
            echo "❌ Échec redémarrage"
            exit 1
        fi
        ;;

    update)
        echo "🔄 Mise à jour depuis GitHub..."
        cd ~/eth-futures-bot

        # Git pull
        git pull

        # Redémarrer
        screen -X -S trading quit 2>/dev/null
        sleep 3
        screen -dmS trading bash -c './start_bot.sh'
        sleep 2
        if screen -list | grep -q "trading"; then
            echo "✅ Bot mis à jour et redémarré"
        else
            echo "❌ Échec redémarrage"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {restart|update}"
        exit 1
        ;;
esac