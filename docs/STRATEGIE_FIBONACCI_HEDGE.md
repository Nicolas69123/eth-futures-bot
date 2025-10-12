# 🎯 STRATÉGIE FIBONACCI HEDGE - Guide Complet

**Stratégie de trading automatique avec hedge permanent et grille Fibonacci**

Date: 12 Octobre 2025
Version: 2.0 (Hedge permanent avec réouverture)

---

## 📊 PRINCIPE GÉNÉRAL

**Hedge permanent** : Toujours maintenir Long + Short sur chaque paire active.

**Grille Fibonacci** : 0.3%, 0.3%, 0.6%, 0.9%, 1.5%, 2.4%...

**Paires** : DOGE/USDT (mode test), puis PEPE et SHIB

**Capitale** : $1000 max

**Levier** : x50

---

## 🔄 LOGIQUE COMPLÈTE (DOGE exemple)

### **📍 SITUATION INITIALE**

```
Prix DOGE: $0.21000

POSITIONS:
  🟢 LONG:  237 contrats @ $0.21000
     Marge: 1.0000000 USDT (Fibonacci 0)

  🔴 SHORT: 237 contrats @ $0.21000
     Marge: 1.0000000 USDT (Fibonacci 0)

ORDRES ACTIFS (4):
  🟢 TP Long      @ $0.21063 (+0.3%)  [TP/SL - ferme Long]
  🟢 Fib 1 Long   @ $0.20937 (-0.3%)  [LIMIT - double Long]
  🔴 TP Short     @ $0.20937 (-0.3%)  [TP/SL - ferme Short]
  🔴 Fib 1 Short  @ $0.21063 (+0.3%)  [LIMIT - double Short]
```

---

## ⬆️ SCÉNARIO : Le marché MONTE de +0.3%

### **Prix passe de $0.21000 → $0.21063**

---

### **ÉTAPE 1 : DÉCLENCHEMENTS SIMULTANÉS**

```
✅ TP Long @ $0.21063 s'exécute
   → Position Long FERMÉE
   → Profit réalisé: +0.0063000 USDT

✅ Fib 1 Short @ $0.21063 s'exécute
   → Ajoute 474 contrats au Short (2x marge initiale)
   → Short: 237 → 711 contrats
   → Marge: 1.00 → 3.00 USDT (triplé!)
   → Prix moyen Short: $0.21042 (recalculé par API)
```

---

### **ÉTAPE 2 : ANNULATIONS** ⚠️ CRITIQUE

**Le bot DOIT annuler ces ordres (plus valides) :**

```
🗑️ TP Short @ $0.20937
   ❓ Pourquoi ? Prix moyen Short a changé ($0.21000 → $0.21042)
   ✅ API: cancel_order() ou cancel_tpsl_order()

🗑️ Fib 1 Long @ $0.20937
   ❓ Pourquoi ? Long fermé, cet ordre n'a plus de sens
   ✅ API: cancel_order()
```

**⚠️ SI LES ORDRES NE S'ANNULENT PAS → PROBLÈME !**

---

### **ÉTAPE 3 : RÉOUVERTURE LONG (Fibonacci 0)**

```
📊 OUVRIR nouveau Long en MARKET
   → 237 contrats @ $0.21063 (prix actuel)
   → Marge: 1.0000000 USDT (Fibonacci 0)

✅ API: create_order(
    side='buy',
    type='market',
    amount=237,
    params={'tradeSide': 'open', 'holdSide': 'long'}
)
```

---

### **ÉTAPE 4 : REPLACEMENT DES 4 ORDRES**

#### **Pour le LONG (réouvert à Fib 0) :**

```
🟢 TP Long @ $0.21126
   📐 Calcul: $0.21063 × (1 + 0.3%) = $0.21126
   📝 Type: TP/SL plan (place_tpsl_order)

🟢 Fib 1 Long @ $0.21000
   📐 Calcul: $0.21063 × (1 - 0.3%) = $0.21000
   📝 Type: LIMIT (create_order type='limit')
   🎯 Action si atteint: Double Long (x2 marge)
```

#### **Pour le SHORT (doublé à Fib 1) :**

```
🔴 TP Short @ $0.20979
   📐 Calcul: $0.21042 (prix moyen) × (1 - 0.3%) = $0.20979
   📝 Type: TP/SL plan
   💰 Objectif: Profit global quand prix redescend

🔴 Fib 2 Short @ $0.21168
   📐 Calcul: $0.21042 × (1 + 0.6%) = $0.21168
   📝 Type: LIMIT
   🎯 Action si atteint: Double Short encore (Fib 2)
```

---

### **📊 SITUATION FINALE**

```
Prix: $0.21063

POSITIONS:
  🟢 LONG:  237 @ $0.21063 (Marge: 1.0000000 USDT) ← Fib 0 (réouvert)
  🔴 SHORT: 711 @ $0.21042 (Marge: 3.0000000 USDT) ← Fib 1 (doublé)

RATIO: 1:3 ✅ NORMAL (marché a monté 1 fois)

ORDRES (4):
  🟢 TP Long      @ $0.21126 (+0.3% du nouveau Long)
  🟢 Fib 1 Long   @ $0.21000 (-0.3% du nouveau Long)
  🔴 TP Short     @ $0.20979 (-0.3% du prix moyen Short)
  🔴 Fib 2 Short  @ $0.21168 (+0.6% du prix moyen Short)

P&L SESSION:
  Réalisé: +0.0063000 USDT (Long fermé)
  Non réalisé: ~-0.0100000 USDT (Short en perte)
  Net: ~-0.0037000 USDT (temporaire)
```

---

## ⬇️ SCÉNARIO INVERSE : Le marché DESCEND de -0.3%

**C'est EXACTEMENT LA MÊME LOGIQUE mais inversée :**

1. TP Short s'exécute → Short fermé (+profit)
2. Fib 1 Long s'exécute → Long doublé (x3)
3. Annule TP Long + Fib 1 Short
4. Ré-ouvre nouveau Short MARKET (Fib 0)
5. Replace 4 ordres

---

## 🎯 POINTS CRITIQUES À VÉRIFIER

### **✅ CHOSES QUI DOIVENT MARCHER :**

| Fonctionnalité | API utilisée | Vérification |
|----------------|--------------|--------------|
| **Fermer position complète** | Flash Close `/api/v2/mix/order/close-positions` | fetch_positions après |
| **Annuler ordre LIMIT** | `exchange.cancel_order()` | fetch_open_orders après |
| **Annuler ordre TP/SL** | `cancel_tpsl_order()` HTTP direct | get_tpsl_orders après |
| **Ouvrir position MARKET** | `create_order(type='market')` | fetch_positions après |
| **Placer ordre LIMIT** | `create_order(type='limit')` | verify_order_placed() |
| **Placer TP/SL** | `place_tpsl_order()` HTTP direct | get_tpsl_orders après |

---

## 💰 CALCUL DES P&L ET FRAIS

### **P&L affiché = unrealized_pnl de l'API Bitget**
- ✅ Avant frais de fermeture
- ✅ 7 décimales de précision

### **Frais RÉELS = fetch_my_trades()**
- ✅ Récupère jusqu'à 500 trades par paire
- ✅ Additionne les fee.cost de chaque trade
- ❌ PAS d'estimation

### **P&L Net = Réalisé + Non Réalisé - Frais**

**Exemple :**
```
P&L Réalisé: +5.1234567 USDT
P&L Non Réalisé: +3.4556789 USDT
Frais payés (API): 0.9876543 USDT
────────────────────────────────
P&L Net: +7.5914813 USDT
```

---

## 🔧 PARAMÈTRES ACTUELS

| Paramètre | Valeur | Note |
|-----------|--------|------|
| **Fibonacci 0** | 0.3% | TP initial + Marge initiale |
| **Fibonacci 1** | 0.3% | Premier doublement |
| **Fibonacci 2** | 0.6% | Deuxième doublement |
| **Fibonacci 3** | 0.9% | Troisième doublement |
| **Mode test** | DOGE uniquement | Activer PEPE/SHIB plus tard |
| **Marge initiale** | 1 USDT | Par position (Long ou Short) |
| **Levier** | x50 | Maximum testnet Bitget |

---

## ⚠️ POINTS D'ATTENTION

### **1. Annulation des ordres**
- **CRUCIAL** : Vérifier que cancel_order() fonctionne vraiment
- Si ordres pas annulés → Risque d'exécutions indésirables
- Logs détaillés ajoutés pour tracer chaque annulation

### **2. Prix moyen après doublement**
- Le prix moyen se recalcule automatiquement (API Bitget)
- Le TP doit être placé à 0.3% de CE prix moyen
- Utiliser `real_pos['short']['entry_price']` après doublement

### **3. Ratio Long:Short**
- Ratio 1:3 après 1 mouvement = ✅ NORMAL
- Ratio 1:7 après 2 mouvements = ✅ NORMAL
- Ratio 1:21 après 4 mouvements = ✅ NORMAL
- **Ce n'est PAS un bug ! C'est la martingale !**

---

## 📱 COMMANDES TELEGRAM

| Commande | Usage |
|----------|-------|
| `/checkapi` | Voir positions RÉELLES API |
| `/forceclose` | Flash Close toutes positions |
| `/cleanup` | Nettoyage complet |
| `/logs` | Derniers logs |
| `/update` | Git pull + redémarrage |
| `/positions` | Positions actuelles |
| `/pnl` | P&L session avec frais réels |

---

## 🎯 OBJECTIF DE LA STRATÉGIE

**Générer des profits réguliers (+0.3% à chaque TP) :**
- Les positions gagnantes se ferment vite (+0.3%)
- Les positions perdantes accumulent (martingale)
- Pari que le prix va inverser et les grosses positions feront profit

**Risque** : Si le marché monte/descend indéfiniment sans inverser
- Protection : Capital max $1000
- Protection : Fibonacci limité à 10 niveaux

---

## 📋 CHECKLIST AVANT CHAQUE TEST

- [ ] Flash Close API fonctionne (positions fermées à 100%)
- [ ] Ordres LIMIT s'annulent correctement
- [ ] Ordres TP/SL s'annulent correctement
- [ ] Réouverture en MARKET fonctionne
- [ ] 4 nouveaux ordres placés après chaque TP
- [ ] Prix moyen lu depuis API (pas calculé)
- [ ] Frais récupérés depuis fetch_my_trades
- [ ] P&L avec 7 décimales
- [ ] Logs détaillés activés
- [ ] Health check toutes les 60s

---

## 🚀 WORKFLOW DE TEST

1. Démarrer bot (hedge DOGE ouvert)
2. Attendre mouvement de +0.3% ou -0.3%
3. Vérifier sur Telegram :
   - Message "TP LONG EXÉCUTÉ" ou "TP SHORT EXÉCUTÉ"
   - Positions actuelles avec `/checkapi`
   - Ordres actifs (doit y avoir 4 ordres)
4. Vérifier les logs avec `/logs`
5. Vérifier que les anciens ordres sont bien annulés

---

## 💡 RAPPELS IMPORTANTS

### **PAS d'estimation ! Que des appels API :**
- ✅ P&L = `unrealized_pnl` de l'API
- ✅ Marge = `initialMargin` de l'API
- ✅ Frais = `fetch_my_trades()` sommés
- ✅ Prix moyen = `entry_price` de l'API
- ❌ Jamais de calculs manuels

### **Précision :**
- 7 décimales pour P&L et Marge
- 5 décimales pour les prix

### **Couleurs Telegram :**
- 🟢 = Toutes les infos LONG
- 🔴 = Toutes les infos SHORT

---

## 🔥 EN CAS DE PROBLÈME

### **Positions ne se ferment pas :**
```
/forceclose
```
Utilise Flash Close API pour fermer 100%

### **Ordres pas annulés :**
Vérifier les logs :
```
/logs
```
Chercher : "Annulation ordre..."

### **Bot bloqué :**
```
/restart
```
Ou utiliser raccourci Bureau

### **Vérifier état réel :**
```
/checkapi
```
Compare avec interface Bitget

---

## 📈 EXEMPLE COMPLET SUR 3 MOUVEMENTS

### **Mouvement 1 : +0.3%**

```
Long fermé → Short doublé → Long réouvert
Ratio: 1:3 (NORMAL)
```

### **Mouvement 2 : +0.3% encore**

```
Long fermé → Short doublé → Long réouvert
Ratio: 1:7 (NORMAL)
```

### **Mouvement 3 : -0.3% (inversion)**

```
Short fermé avec PROFIT → Long doublé → Short réouvert
Ratio: 3:1 (inversé, NORMAL)
```

**À chaque TP = Profit de 0.3% sur la position fermée**

**C'est une martingale équilibrée !**

---

## 🎯 CETTE STRATÉGIE EN UNE PHRASE

**"À chaque mouvement de 0.3%, on ferme le côté gagnant (+profit), on double le côté perdant (martingale), et on ré-ouvre le côté fermé pour maintenir le hedge."**

---

## 📞 SI BESOIN DE RAPPEL

Donnez ce fichier à Claude avec :

> "Voici ma stratégie (fichier MD), respecte-la exactement."

Et Claude pourra coder en suivant cette logique précise.

---

**🚀 Stratégie testée et prête ! Fibonacci 0.3%, Flash Close API, Hedge permanent !**
