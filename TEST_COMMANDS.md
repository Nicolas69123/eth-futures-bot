# Test des Commandes Telegram - Bot V2 Fixed

## Checklist de Test

### ✅ Commandes d'Information

#### `/help`
- [ ] Envoyer `/help`
- [ ] Vérifier que la liste complète des commandes s'affiche
- [ ] Vérifier le format HTML

#### `/pnl`
- [ ] Envoyer `/pnl`
- [ ] Vérifier affichage:
  - [ ] Position LONG (si ouverte)
  - [ ] Position SHORT (si ouverte)
  - [ ] PnL total
  - [ ] Marge utilisée
  - [ ] Prix actuel
- [ ] Vérifier calculs de %

#### `/status`
- [ ] Envoyer `/status`
- [ ] Vérifier affichage:
  - [ ] Positions (taille + entrée + niveau Fib)
  - [ ] Ordres actifs (TP + LIMIT count)
  - [ ] Configuration (TP, Fibo, marge, levier)
  - [ ] Prix actuel

---

### ⚙️ Commandes de Configuration

#### `/setmargin`

**Test 1: Valeur valide**
- [ ] Envoyer `/setmargin 2`
- [ ] Vérifier confirmation
- [ ] Vérifier log: `💰 INITIAL_MARGIN modifié: $1 → $2`
- [ ] Vérifier `/status` affiche nouvelle marge

**Test 2: Sans argument**
- [ ] Envoyer `/setmargin`
- [ ] Vérifier message d'erreur avec usage

**Test 3: Valeur invalide (≤ 0)**
- [ ] Envoyer `/setmargin 0`
- [ ] Vérifier erreur "doit être > 0"
- [ ] Envoyer `/setmargin -1`
- [ ] Vérifier erreur "doit être > 0"

**Test 4: Valeur non numérique**
- [ ] Envoyer `/setmargin abc`
- [ ] Vérifier erreur "Montant invalide"

---

#### `/settp`

**Test 1: Valeur valide**
- [ ] Envoyer `/settp 0.5`
- [ ] Vérifier confirmation
- [ ] Vérifier log: `📊 TP_PERCENT modifié: 0.3% → 0.5%`
- [ ] Vérifier `/status` affiche nouveau TP

**Test 2: Sans argument**
- [ ] Envoyer `/settp`
- [ ] Vérifier message d'erreur avec usage

**Test 3: Valeur trop basse (< 0.1)**
- [ ] Envoyer `/settp 0.05`
- [ ] Vérifier erreur "entre 0.1% et 2%"

**Test 4: Valeur trop haute (> 2)**
- [ ] Envoyer `/settp 3`
- [ ] Vérifier erreur "entre 0.1% et 2%"

**Test 5: Valeur non numérique**
- [ ] Envoyer `/settp abc`
- [ ] Vérifier erreur "Valeur invalide"

---

#### `/setfibo`

**Test 1: Valeurs valides**
- [ ] Envoyer `/setfibo 0.3,0.6,1.2`
- [ ] Vérifier confirmation
- [ ] Vérifier log: `📐 FIBO_LEVELS modifié`
- [ ] Vérifier `/status` affiche nouveaux niveaux

**Test 2: Sans argument**
- [ ] Envoyer `/setfibo`
- [ ] Vérifier message d'erreur avec usage
- [ ] Vérifier affichage des niveaux actuels

**Test 3: Niveaux non croissants**
- [ ] Envoyer `/setfibo 0.6,0.3,1.2`
- [ ] Vérifier erreur "ordre croissant"

**Test 4: Un seul niveau**
- [ ] Envoyer `/setfibo 0.5`
- [ ] Vérifier erreur "au moins 2 niveaux"

**Test 5: Avec espaces**
- [ ] Envoyer `/setfibo 0.3, 0.6, 1.2`
- [ ] Vérifier que ça fonctionne (espaces supprimés)

**Test 6: Valeur non numérique**
- [ ] Envoyer `/setfibo 0.3,abc,1.2`
- [ ] Vérifier erreur "Format invalide"

---

#### `/stop`

**Test 1: Sans confirmation**
- [ ] Envoyer `/stop`
- [ ] Vérifier message d'avertissement
- [ ] Vérifier que le bot continue de fonctionner

**Test 2: Avec confirmation**
- [ ] Envoyer `/stop CONFIRM`
- [ ] Vérifier message "BOT ARRÊTÉ"
- [ ] Vérifier log: `🛑 Arrêt demandé via /stop CONFIRM`
- [ ] Vérifier que le bot s'arrête (pas de logs après)

**Test 3: Confirmation en minuscules**
- [ ] Envoyer `/stop confirm`
- [ ] Vérifier que ça ne fonctionne **PAS** (nécessite majuscules)

---

### ❌ Commande Inconnue

**Test: Commande invalide**
- [ ] Envoyer `/invalid`
- [ ] Vérifier message "Commande inconnue"
- [ ] Vérifier suggestion d'utiliser `/help`

---

## Test de Performance

### Polling Telegram
- [ ] Envoyer plusieurs commandes espacées de 1s
- [ ] Vérifier que toutes sont traitées
- [ ] Vérifier que la détection d'événements continue (4x/sec)

### Spam de Commandes
- [ ] Envoyer 5 commandes rapidement
- [ ] Vérifier que toutes sont traitées
- [ ] Vérifier qu'il n'y a pas de doublons

---

## Test d'Intégration

### Workflow Complet

1. **Démarrer bot**
   - [ ] Vérifier message de démarrage Telegram

2. **Vérifier état initial**
   - [ ] `/status`
   - [ ] Vérifier config par défaut (TP: 0.3%, Fibo: [0.1, 0.2, 0.4, 0.7, 1.2], Marge: $1)

3. **Modifier configuration**
   - [ ] `/setmargin 2`
   - [ ] `/settp 0.5`
   - [ ] `/setfibo 0.2,0.5,1.0`

4. **Vérifier changements**
   - [ ] `/status`
   - [ ] Vérifier que les nouvelles valeurs s'affichent

5. **Attendre événement TP**
   - [ ] Attendre qu'un TP soit touché
   - [ ] Vérifier que la **nouvelle** position utilise:
     - Marge de $2
     - TP à 0.5%
     - Fibo à 0.2%

6. **Vérifier PnL**
   - [ ] `/pnl`
   - [ ] Vérifier calculs corrects

7. **Arrêter proprement**
   - [ ] `/stop CONFIRM`
   - [ ] Vérifier arrêt

---

## Logs à Vérifier

```bash
# Sur le serveur Oracle
screen -r trading

# Rechercher dans les logs:
grep "📱 Commande Telegram" logs/bot_*.log
grep "INITIAL_MARGIN modifié" logs/bot_*.log
grep "TP_PERCENT modifié" logs/bot_*.log
grep "FIBO_LEVELS modifié" logs/bot_*.log
```

---

## Erreurs Fréquentes

### Erreur: Pas de réponse Telegram

**Causes possibles:**
- Token Telegram invalide
- Chat ID incorrect
- Bot Telegram bloqué

**Vérifier:**
```python
# Dans .env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### Erreur: Commandes non traitées

**Causes possibles:**
- `last_telegram_update_id` bloqué
- Exception dans `check_telegram_updates()`

**Vérifier logs:**
```bash
grep "Erreur traitement commande" logs/bot_*.log
```

### Erreur: Modifications non appliquées

**Rappel:**
- Les modifications s'appliquent aux **PROCHAINS** ordres
- Les ordres **ACTUELS** ne changent **PAS**

---

## Checklist Finale

- [ ] Toutes les commandes fonctionnent
- [ ] Validations d'arguments fonctionnent
- [ ] Messages d'erreur clairs
- [ ] Logs corrects
- [ ] Modifications appliquées aux prochains ordres
- [ ] Bot continue de détecter événements pendant traitement commandes
- [ ] `/stop CONFIRM` arrête proprement le bot

---

## Notes

- **Durée estimée du test complet:** 30 minutes
- **Nécessite:** Bot en production avec positions actives
- **Optionnel:** Attendre TP touché pour vérifier modifications appliquées

---

## Rapport de Test

**Date:** _______________
**Testeur:** _______________

**Résultats:**
- [ ] ✅ Tous les tests passent
- [ ] ⚠️ Quelques tests échouent (détails ci-dessous)
- [ ] ❌ Tests critiques échouent

**Détails des échecs:**
```
[Décrire les erreurs rencontrées]
```

**Améliorations suggérées:**
```
[Suggestions]
```
