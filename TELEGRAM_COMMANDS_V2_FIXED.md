# Commandes Telegram - Bot V2 Fixed

## Commandes Disponibles

### 📊 Informations

#### `/pnl`
Affiche le P&L total de la session

**Informations affichées:**
- Position LONG (si ouverte):
  - Nombre de contrats
  - Prix d'entrée
  - PnL en USDT et en %
- Position SHORT (si ouverte):
  - Nombre de contrats
  - Prix d'entrée
  - PnL en USDT et en %
- **PnL Total** (somme LONG + SHORT)
- Marge utilisée totale
- Prix actuel

**Exemple de réponse:**
```
💰 P&L - DOGE

📊 Positions:
🟢 LONG: 1500 contrats
   Entrée: $0.12345
   PnL: +0.0012345 USDT (+0.25%)
🔴 SHORT: 1500 contrats
   Entrée: $0.12350
   PnL: -0.0008123 USDT (-0.15%)

━━━━━━━━━━━━━━━━━
💎 PnL Total: +0.0004222 USDT
💵 Marge utilisée: 0.0050000 USDT
💰 Prix actuel: $0.12348

⏰ 14:35:22
```

---

#### `/status`
Affiche l'état complet du bot

**Informations affichées:**
- Positions ouvertes (LONG/SHORT) avec:
  - Taille (contrats)
  - Prix d'entrée
  - Niveau Fibonacci actuel
- Ordres actifs:
  - Nombre d'ordres TP
  - Nombre d'ordres LIMIT
- Configuration actuelle:
  - TP %
  - Niveaux Fibonacci
  - Marge initiale
  - Levier
- Prix actuel

**Exemple de réponse:**
```
🤖 STATUS BOT - DOGE

📊 Positions:
🟢 LONG: 1500 @ $0.12345
   Niveau Fib: 0
🔴 SHORT: 1500 @ $0.12350
   Niveau Fib: 0

📋 Ordres actifs:
• TP orders: 2
• LIMIT orders: 2

⚙️ Configuration:
• TP: 0.3%
• Fibo levels: [0.1, 0.2, 0.4, 0.7, 1.2]
• Marge initiale: $1
• Levier: 50x

💰 Prix actuel: $0.12348

⏰ 14:35:22
```

---

### ⚙️ Configuration

#### `/setmargin <montant>`
Change la marge initiale pour les **prochaines** positions

**Paramètres:**
- `<montant>` : Montant en $ (doit être > 0)

**Validation:**
- ✅ Montant > 0
- ❌ Sinon: erreur

**Impact:**
- ⚠️ S'applique uniquement aux **PROCHAINES** positions
- Les positions actuelles ne sont **PAS** modifiées

**Exemples:**
```
/setmargin 2      → Marge de $2 par position
/setmargin 0.5    → Marge de $0.50 par position
/setmargin 5      → Marge de $5 par position
```

**Réponse:**
```
✅ MARGE MODIFIÉE

Ancienne marge: $1
Nouvelle marge: $2

⚠️ La modification s'appliquera aux PROCHAINES positions ouvertes.
Les positions actuelles ne sont pas affectées.

⏰ 14:35:22
```

---

#### `/settp <pourcent>`
Change le Take Profit en % pour les **prochains** ordres TP

**Paramètres:**
- `<pourcent>` : Pourcentage TP (entre 0.1% et 2%)

**Validation:**
- ✅ 0.1% ≤ TP ≤ 2%
- ❌ Sinon: erreur

**Impact:**
- ⚠️ S'applique uniquement aux **PROCHAINS** ordres TP
- Les ordres TP actuels ne sont **PAS** modifiés

**Exemples:**
```
/settp 0.5    → TP à 0.5%
/settp 0.3    → TP à 0.3%
/settp 1.0    → TP à 1.0%
```

**Réponse:**
```
✅ TP MODIFIÉ

Ancien TP: 0.3%
Nouveau TP: 0.5%

⚠️ La modification s'appliquera aux PROCHAINS ordres TP.
Les ordres TP actuels ne sont pas modifiés.

⏰ 14:35:22
```

---

#### `/setfibo <niveaux>`
Change les niveaux Fibonacci pour les **prochains** ordres LIMIT

**Paramètres:**
- `<niveaux>` : Niveaux séparés par virgule (ex: `0.3,0.6,1.2`)

**Validation:**
- ✅ Niveaux en ordre **croissant**
- ✅ Au moins **2 niveaux**
- ❌ Sinon: erreur

**Impact:**
- ⚠️ S'applique uniquement aux **PROCHAINS** ordres LIMIT
- Les ordres LIMIT actuels ne sont **PAS** modifiés

**Exemples:**
```
/setfibo 0.3,0.6,1.2           → 3 niveaux
/setfibo 0.1,0.2,0.4,0.7,1.2   → 5 niveaux (défaut)
/setfibo 0.5,1.0,2.0,4.0       → 4 niveaux
```

**Réponse:**
```
✅ NIVEAUX FIBO MODIFIÉS

Anciens niveaux: [0.1, 0.2, 0.4, 0.7, 1.2]
Nouveaux niveaux: [0.3, 0.6, 1.2]

⚠️ La modification s'appliquera aux PROCHAINS ordres LIMIT.
Les ordres LIMIT actuels ne sont pas modifiés.

⏰ 14:35:22
```

---

### 🛠️ Contrôle

#### `/stop`
Arrête le bot (demande confirmation)

**Première utilisation:**
```
/stop
```

**Réponse:**
```
⚠️ ARRÊT DU BOT

Cette commande va arrêter le bot.

⚠️ Les positions resteront ouvertes!

Pour confirmer, tapez:
/stop CONFIRM
```

**Confirmation:**
```
/stop CONFIRM
```

**Réponse:**
```
🛑 BOT ARRÊTÉ

Arrêt en cours...
```

⚠️ **ATTENTION:** Les positions restent ouvertes ! Le bot s'arrête simplement de surveiller.

---

#### `/help`
Affiche la liste complète des commandes

**Réponse:**
```
🤖 COMMANDES DISPONIBLES

📊 Informations:
/pnl - P&L total et positions
/status - État du bot et ordres

⚙️ Configuration:
/setmargin <montant> - Changer marge initiale
/settp <pourcent> - Changer TP %
/setfibo <niveaux> - Changer niveaux Fibo

🛠️ Contrôle:
/stop - Arrêter le bot (demande confirmation)

❓ /help - Cette aide
```

---

## Fonctionnement Technique

### Polling Telegram
- Le bot vérifie les commandes Telegram **toutes les 5 secondes**
- Utilise l'API `getUpdates` avec offset pour éviter de traiter plusieurs fois la même commande
- Les commandes sont traitées **immédiatement** dès réception

### Variables Modifiables
- `INITIAL_MARGIN` → `/setmargin`
- `TP_PERCENT` → `/settp`
- `FIBO_LEVELS` → `/setfibo`

### Impacts des Modifications
- ⚠️ Les modifications ne s'appliquent **QU'AUX PROCHAINS** ordres/positions
- Les positions et ordres **ACTUELS** restent **INCHANGÉS**
- Pour appliquer les changements, il faut que:
  - Un TP soit touché → nouvelles positions avec nouvelle config
  - Un niveau Fibo soit touché → nouveaux ordres avec nouvelle config

---

## Exemple de Workflow

### 1. Vérifier l'état actuel
```
/status
```

### 2. Ajuster la configuration
```
/settp 0.5          # Augmenter TP à 0.5%
/setmargin 2        # Augmenter marge à $2
```

### 3. Vérifier les positions et PnL
```
/pnl
```

### 4. Attendre qu'un TP soit touché
- Le bot réouvrira automatiquement avec la **nouvelle** configuration
- TP à 0.5% au lieu de 0.3%
- Marge de $2 au lieu de $1

### 5. Arrêter le bot si nécessaire
```
/stop CONFIRM
```

---

## Notes Importantes

1. **Modifications en temps réel:**
   - Les variables sont modifiées **immédiatement**
   - Mais les ordres déjà placés **ne changent pas**
   - Les nouvelles valeurs s'appliquent aux **prochaines** opérations

2. **Sécurité:**
   - `/stop` demande une **confirmation** pour éviter les arrêts accidentels
   - Les modifications de configuration sont **loggées**

3. **Erreurs:**
   - Toutes les erreurs sont capturées et renvoyées via Telegram
   - Le bot continue de fonctionner même en cas d'erreur de commande

4. **Performances:**
   - Le polling Telegram n'impacte **pas** la vitesse de détection des événements
   - Les événements sont toujours détectés **4 fois par seconde** (250ms)
   - Telegram est vérifié séparément toutes les **5 secondes**

---

## Variables Techniques

```python
# Dans __init__()
self.last_telegram_update_id = 0
self.telegram_check_interval = 5  # Check toutes les 5 secondes
self.last_telegram_check = 0

# Variables modifiables
self.INITIAL_MARGIN = 1     # $ par position
self.TP_PERCENT = 0.3       # % TP
self.FIBO_LEVELS = [0.1, 0.2, 0.4, 0.7, 1.2]  # Niveaux Fibo
```

---

## Logs

Toutes les commandes Telegram sont loggées:

```
📱 Commande Telegram reçue: /pnl
💰 INITIAL_MARGIN modifié: $1 → $2
📊 TP_PERCENT modifié: 0.3% → 0.5%
📐 FIBO_LEVELS modifié: [0.1, 0.2, 0.4, 0.7, 1.2] → [0.3, 0.6, 1.2]
🛑 Arrêt demandé via /stop CONFIRM
```
