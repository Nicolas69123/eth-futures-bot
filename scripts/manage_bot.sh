#!/bin/bash

# Script de gestion du bot sur Oracle Cloud
# Usage: ./manage_bot.sh [start|stop|restart|update|status|logs]

# Configuration
SERVER_IP="130.110.243.130"
SSH_KEY="$HOME/Downloads/ssh-key-2025-10-12 (1).key"
SERVER_USER="ubuntu"

# Couleurs pour l'affichage
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🤖 GESTIONNAIRE BOT TRADING${NC}"
echo "================================"

case "$1" in
    start)
        echo -e "${GREEN}▶️  Démarrage du bot...${NC}"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP << 'EOF'
            cd eth-futures-bot
            # Vérifier si une session existe déjà
            if screen -list | grep -q "trading"; then
                echo "⚠️  Le bot tourne déjà!"
                exit 1
            fi
            # Créer une nouvelle session screen et lancer le bot
            screen -dmS trading bash -c 'python3 bot/bitget_hedge_fibonacci_v2.py'
            sleep 2
            if screen -list | grep -q "trading"; then
                echo "✅ Bot démarré avec succès!"
            else
                echo "❌ Erreur au démarrage"
            fi
EOF
        ;;

    stop)
        echo -e "${RED}⏹️  Arrêt du bot...${NC}"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP << 'EOF'
            screen -X -S trading quit
            echo "✅ Bot arrêté"
EOF
        ;;

    restart)
        echo -e "${YELLOW}🔄 Redémarrage du bot...${NC}"
        $0 stop
        sleep 2
        $0 start
        ;;

    update)
        echo -e "${YELLOW}🔄 Mise à jour depuis GitHub...${NC}"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP << 'EOF'
            cd eth-futures-bot
            # Arrêter le bot
            screen -X -S trading quit 2>/dev/null
            echo "📥 Récupération des dernières modifications..."
            git pull
            echo "📦 Mise à jour des dépendances..."
            pip3 install -r requirements.txt --upgrade
            # Redémarrer le bot
            screen -dmS trading bash -c 'python3 bot/bitget_hedge_fibonacci_v2.py'
            echo "✅ Mise à jour complète et bot redémarré!"
EOF
        ;;

    status)
        echo -e "${GREEN}📊 Status du bot...${NC}"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP << 'EOF'
            if screen -list | grep -q "trading"; then
                echo "✅ Bot en cours d'exécution"
                echo ""
                echo "Sessions screen actives:"
                screen -ls | grep trading
            else
                echo "❌ Bot arrêté"
            fi
            echo ""
            echo "Processus Python actifs:"
            ps aux | grep -E "bitget|fibonacci" | grep -v grep
EOF
        ;;

    logs)
        echo -e "${GREEN}📜 Connexion aux logs du bot...${NC}"
        echo "Pour quitter les logs: Ctrl+A puis D"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP -t "screen -r trading"
        ;;

    ssh)
        echo -e "${GREEN}🔌 Connexion SSH au serveur...${NC}"
        ssh -i "$SSH_KEY" $SERVER_USER@$SERVER_IP
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|update|status|logs|ssh}"
        echo ""
        echo "Commandes disponibles:"
        echo "  start   - Démarre le bot"
        echo "  stop    - Arrête le bot"
        echo "  restart - Redémarre le bot"
        echo "  update  - Met à jour depuis GitHub et redémarre"
        echo "  status  - Vérifie si le bot tourne"
        echo "  logs    - Voir les logs en temps réel"
        echo "  ssh     - Se connecter au serveur"
        exit 1
        ;;
esac