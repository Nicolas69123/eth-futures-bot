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

        # Sauvegarder commit actuel pour log
        CURRENT_COMMIT=$(git rev-parse --short HEAD)
        echo "📍 Commit actuel: $CURRENT_COMMIT"

        # Fetch pour voir les changements disponibles
        git fetch origin main
        LATEST_COMMIT=$(git rev-parse --short origin/main)
        echo "📍 Dernier commit GitHub: $LATEST_COMMIT"

        if [ "$CURRENT_COMMIT" = "$LATEST_COMMIT" ]; then
            echo "✅ Déjà à jour (même commit)"
        else
            echo "📥 Changements détectés, mise à jour forcée..."

            # FORCER la mise à jour (écraser modifications locales)
            git reset --hard origin/main

            if [ $? -eq 0 ]; then
                NEW_COMMIT=$(git rev-parse --short HEAD)
                echo "✅ Mise à jour réussie: $CURRENT_COMMIT → $NEW_COMMIT"
            else
                echo "❌ Erreur lors de git reset"
                exit 1
            fi
        fi

        # Redémarrer
        echo "♻️ Redémarrage du bot..."
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