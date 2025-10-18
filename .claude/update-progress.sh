#!/bin/bash

# Script pour mettre à jour progress.md facilement
# Usage: ./update-progress.sh

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)
PROGRESS_FILE=".claude/progress.md"

# Couleurs
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   📝 MISE À JOUR PROGRESS.MD 📝               ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
echo ""

# Backup ancien fichier
if [ -f "$PROGRESS_FILE" ]; then
    cp "$PROGRESS_FILE" "$PROGRESS_FILE.bak"
    echo -e "${GREEN}✅ Backup créé${NC}: $PROGRESS_FILE.bak"
fi

echo ""
echo "📅 Date: $DATE"
echo ""

# Demander le focus de la session
echo "🎯 Sur quoi avez-vous travaillé aujourd'hui ?"
read -p "Focus: " FOCUS

echo ""
echo "✅ Qu'avez-vous accompli ?"
echo "(Tapez 'done' quand vous avez fini)"
DONE_ITEMS=""
while true; do
    read -p "- " ITEM
    if [ "$ITEM" = "done" ]; then
        break
    fi
    DONE_ITEMS="$DONE_ITEMS\n- ✅ $ITEM"
done

echo ""
echo "📝 Prochaines étapes ?"
echo "(Tapez 'done' quand vous avez fini)"
TODO_ITEMS=""
i=1
while true; do
    read -p "$i. " ITEM
    if [ "$ITEM" = "done" ]; then
        break
    fi
    TODO_ITEMS="$TODO_ITEMS\n$i. $ITEM"
    ((i++))
done

# Mettre à jour le fichier progress.md
# Remplacer "Dernière mise à jour"
sed -i.bak "s/> \*\*Dernière mise à jour\*\* : .*/> **Dernière mise à jour** : $DATE/" "$PROGRESS_FILE"

# Ajouter nouvelle session en haut de "Dernières Sessions"
TEMP_FILE=$(mktemp)

awk -v date="$DATE" -v time="$TIME" -v focus="$FOCUS" -v done_items="$DONE_ITEMS" -v todo="$TODO_ITEMS" '
    /## 🗓️ Dernières Sessions/ {
        print $0
        print ""
        print "### Session " date
        print "**Focus** : " focus
        print ""
        print "**Accompli** :"
        printf "%s\n", done_items
        print ""
        if (todo != "") {
            print "**Prochaines étapes** :"
            printf "%s\n", todo
            print ""
        }
        next
    }
    { print }
' "$PROGRESS_FILE" > "$TEMP_FILE"

mv "$TEMP_FILE" "$PROGRESS_FILE"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ PROGRESS.MD MIS À JOUR ! ✅              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "Fichier : $PROGRESS_FILE"
echo "Backup  : $PROGRESS_FILE.bak"
echo ""
echo "💡 Conseil : Commit ces changements dans git"
echo ""
