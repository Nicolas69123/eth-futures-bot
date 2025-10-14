# 📊 STRATÉGIE FIBONACCI HEDGE - DOCUMENTATION COMPLÈTE

**Version:** 2.0
**Date:** 2025-10-14
**Auteur:** Nicolas

---

## 🎯 OBJECTIF

Implémenter une stratégie de trading automatique **Fibonacci Hedge** avec :
- Hedge permanent (Long + Short simultanés)
- Take Profit fixe à **±0.3%**
- Doublement (martingale) basé sur niveaux Fibonacci
- Gestion automatique des ordres via API Bitget

---

## 📐 PARAMÈTRES GLOBAUX

```yaml
Capital Total: 1000 USDT
Marge Initiale: 1 USDT par position
Levier: x50
TP Fixe: 0.3% (0.003)
Paires: DOGE/USDT:USDT, PEPE/USDT:USDT, SHIB/USDT:USDT
```

### Niveaux Fibonacci (en %)
```yaml
Fib 0: 0.236%    # Niveau initial
Fib 1: 0.382%
Fib 2: 0.5%
Fib 3: 0.618%
Fib 4: 1.0%
Fib 5: 1.618%
Fib 6: 2.618%
Fib 7: 4.236%
Fib 8: 6.854%
Fib 9: 11.09%
Fib 10: 17.944%
```

---

## 🔄 CYCLE COMPLET DE LA STRATÉGIE

### **PHASE 1 : OUVERTURE HEDGE INITIAL**

#### État de départ
```
Positions: Aucune
Ordres: Aucun
Capital utilisé: 0 USDT
```

#### Actions
1. **Ouvrir position LONG au MARKET**
   - Type: `market`
   - Side: `buy`
   - Taille: `(1 USDT * 50) / prix_actuel`
   - Params: `tradeSide='open', holdSide='long'`

2. **Attendre 1 seconde**

3. **Ouvrir position SHORT au MARKET**
   - Type: `market`
   - Side: `sell`
   - Taille: `(1 USDT * 50) / prix_actuel`
   - Params: `tradeSide='open', holdSide='short'`

4. **Attendre 2 secondes**

5. **INTERROGER API : Récupérer positions réelles**
   ```
   GET /api/v2/mix/v1/position/allPosition
   ```
   - Extraire `entry_price_long`
   - Extraire `entry_price_short`
   - Extraire `size_long` (contrats)
   - Extraire `size_short` (contrats)

6. **Attendre 1 seconde**

7. **Placer TP LONG (ordre TP/SL plan)**
   - Type: `profit_plan`
   - Trigger: `entry_price_long * 1.003` (+0.3%)
   - Size: `size_long` (TOUS les contrats)

8. **Attendre 1 seconde**

9. **Placer TP SHORT (ordre TP/SL plan)**
   - Type: `profit_plan`
   - Trigger: `entry_price_short * 0.997` (-0.3%)
   - Size: `size_short` (TOUS les contrats)

10. **Attendre 1 seconde**

11. **Placer ordre DOUBLE LONG (ordre LIMIT)**
    - Type: `limit`
    - Side: `buy`
    - Prix: `entry_price_long * 0.99764` (-0.236%, Fib 0)
    - Taille: `size_long * 2` (DOUBLE)
    - Params: `tradeSide='open', holdSide='long'`

12. **Attendre 1 seconde**

13. **Placer ordre DOUBLE SHORT (ordre LIMIT)**
    - Type: `limit`
    - Side: `sell`
    - Prix: `entry_price_short * 1.00236` (+0.236%, Fib 0)
    - Taille: `size_short * 2` (DOUBLE)
    - Params: `tradeSide='open', holdSide='short'`

#### État final
```
Positions:
  - Long: ~250 contrats, 1 USDT marge
  - Short: ~250 contrats, 1 USDT marge

Ordres actifs:
  - TP Long @ entry +0.3%
  - TP Short @ entry -0.3%
  - Double Long @ entry -0.236%
  - Double Short @ entry +0.236%
```

---

### **PHASE 2 : SURVEILLANCE (Boucle infinie toutes les 1 seconde)**

#### Actions chaque itération
1. **INTERROGER API : Récupérer positions actuelles**
   ```
   GET /api/v2/mix/v1/position/allPosition
   ```

2. **INTERROGER API : Récupérer tous les ordres actifs**
   ```
   GET /api/v2/mix/v1/order/allOpenOrders
   GET /api/v2/mix/v1/plan/currentPlan
   ```

3. **Analyser ce qui s'est passé :**
   - Comparer `positions actuelles` vs `positions attendues`
   - Comparer `ordres actuels` vs `ordres attendus`
   - Détecter les changements

4. **Détecter les événements :**
   - ✅ TP Long exécuté ?
   - ✅ TP Short exécuté ?
   - ✅ Double Long exécuté ?
   - ✅ Double Short exécuté ?

5. **Déclencher l'action correspondante** (voir Phase 3 ou 4)

---

### **PHASE 3 : SCÉNARIO "TP LONG EXÉCUTÉ"**

**Déclencheur :** Position Long n'existe plus (close par TP)

#### Ce qui s'est passé automatiquement par Bitget
1. ✅ TP Long déclenché → Position Long fermée
2. ✅ **Double Short exécuté EN MÊME TEMPS** (même prix trigger) → Position Short doublée

#### État actuel détecté
```
Positions:
  - Long: N'EXISTE PLUS
  - Short: ~750 contrats (250 initial + 500 doublé), ~3 USDT marge

Ordres actifs:
  - TP Long: N'EXISTE PLUS (exécuté)
  - TP Short: EXISTE ENCORE (ancien prix)
  - Double Long: EXISTE ENCORE
  - Double Short: N'EXISTE PLUS (exécuté)
```

#### Actions à effectuer

**Étape 1 : Nettoyer les anciens ordres**

1. **Annuler ancien TP Short**
   ```
   DELETE /api/v2/mix/v1/plan/cancelPlan
   ```

2. **Attendre 500ms**

3. **Annuler ordre Double Long**
   ```
   DELETE /api/v2/mix/v1/order/cancel-order
   ```

4. **Attendre 500ms**

**Étape 2 : Ré-ouvrir nouveau Long au MARKET**

5. **Ouvrir position LONG au MARKET**
   - Type: `market`
   - Side: `buy`
   - Taille: `(1 USDT * 50) / prix_actuel`
   - Params: `tradeSide='open', holdSide='long'`

6. **Attendre 2 secondes**

**Étape 3 : INTERROGER API positions réelles**

7. **OBLIGATOIRE : Récupérer positions via API**
   ```
   GET /api/v2/mix/v1/position/allPosition
   ```
   - Extraire `entry_price_long_nouveau`
   - Extraire `size_long_nouveau`
   - Extraire `entry_price_short_moyen` (après doublement!)
   - Extraire `size_short_total`

8. **Attendre 1 seconde**

**Étape 4 : Replacer TOUS les ordres avec NOUVEAUX prix**

9. **Placer TP Long (nouveau Long)**
   - Type: `profit_plan`
   - Trigger: `entry_price_long_nouveau * 1.003` (+0.3%)
   - Size: `size_long_nouveau`

10. **Attendre 1 seconde**

11. **Placer TP Short (SHORT DOUBLÉ avec prix MOYEN)**
    - Type: `profit_plan`
    - Trigger: `entry_price_short_moyen * 0.997` (-0.3%)
    - Size: `size_short_total` (TOUS les contrats)

12. **Attendre 1 seconde**

13. **Incrémenter niveau Fibonacci : `current_level += 1`**

14. **Calculer prochain niveau Fibonacci**
    - Si `current_level = 1` → utiliser Fib[1] = 0.382%

15. **Placer ordre Double Long (niveau Fib suivant)**
    - Type: `limit`
    - Side: `buy`
    - Prix: `entry_price_long_nouveau * (1 - Fib[1]/100)`
    - Taille: `size_long_nouveau * 2`
    - Params: `tradeSide='open', holdSide='long'`

16. **Attendre 1 seconde**

17. **Placer ordre Double Short (niveau Fib suivant)**
    - Type: `limit`
    - Side: `sell`
    - Prix: `entry_price_short_moyen * (1 + Fib[1]/100)`
    - Taille: `size_short_total * 2`
    - Params: `tradeSide='open', holdSide='short'`

18. **Attendre 1 seconde**

#### État final
```
Positions:
  - Long: ~250 contrats, 1 USDT marge (NOUVEAU Fib 0)
  - Short: ~750 contrats, 3 USDT marge (DOUBLÉ Fib 1)

Ordres actifs:
  - TP Long @ nouveau_entry +0.3%
  - TP Short @ entry_moyen_short -0.3%
  - Double Long @ nouveau_entry -0.382% (Fib 1)
  - Double Short @ entry_moyen_short +0.382% (Fib 1)

Niveau Fibonacci: 1
```

---

### **PHASE 4 : SCÉNARIO "TP SHORT EXÉCUTÉ"**

**Déclencheur :** Position Short n'existe plus (close par TP)

#### Ce qui s'est passé automatiquement par Bitget
1. ✅ TP Short déclenché → Position Short fermée
2. ✅ **Double Long exécuté EN MÊME TEMPS** (même prix trigger) → Position Long doublée

#### État actuel détecté
```
Positions:
  - Long: ~750 contrats (250 initial + 500 doublé), ~3 USDT marge
  - Short: N'EXISTE PLUS

Ordres actifs:
  - TP Long: EXISTE ENCORE (ancien prix)
  - TP Short: N'EXISTE PLUS (exécuté)
  - Double Long: N'EXISTE PLUS (exécuté)
  - Double Short: EXISTE ENCORE
```

#### Actions à effectuer

**Étape 1 : Nettoyer les anciens ordres**

1. **Annuler ancien TP Long**
   ```
   DELETE /api/v2/mix/v1/plan/cancelPlan
   ```

2. **Attendre 500ms**

3. **Annuler ordre Double Short**
   ```
   DELETE /api/v2/mix/v1/order/cancel-order
   ```

4. **Attendre 500ms**

**Étape 2 : Ré-ouvrir nouveau Short au MARKET**

5. **Ouvrir position SHORT au MARKET**
   - Type: `market`
   - Side: `sell`
   - Taille: `(1 USDT * 50) / prix_actuel`
   - Params: `tradeSide='open', holdSide='short'`

6. **Attendre 2 secondes**

**Étape 3 : INTERROGER API positions réelles**

7. **OBLIGATOIRE : Récupérer positions via API**
   ```
   GET /api/v2/mix/v1/position/allPosition
   ```
   - Extraire `entry_price_long_moyen` (après doublement!)
   - Extraire `size_long_total`
   - Extraire `entry_price_short_nouveau`
   - Extraire `size_short_nouveau`

8. **Attendre 1 seconde**

**Étape 4 : Replacer TOUS les ordres avec NOUVEAUX prix**

9. **Placer TP Long (LONG DOUBLÉ avec prix MOYEN)**
   - Type: `profit_plan`
   - Trigger: `entry_price_long_moyen * 1.003` (+0.3%)
   - Size: `size_long_total` (TOUS les contrats)

10. **Attendre 1 seconde**

11. **Placer TP Short (nouveau Short)**
    - Type: `profit_plan`
    - Trigger: `entry_price_short_nouveau * 0.997` (-0.3%)
    - Size: `size_short_nouveau`

12. **Attendre 1 seconde**

13. **Incrémenter niveau Fibonacci : `current_level += 1`**

14. **Calculer prochain niveau Fibonacci**
    - Si `current_level = 1` → utiliser Fib[1] = 0.382%

15. **Placer ordre Double Long (niveau Fib suivant)**
    - Type: `limit`
    - Side: `buy`
    - Prix: `entry_price_long_moyen * (1 - Fib[1]/100)`
    - Taille: `size_long_total * 2`
    - Params: `tradeSide='open', holdSide='long'`

16. **Attendre 1 seconde**

17. **Placer ordre Double Short (niveau Fib suivant)**
    - Type: `limit`
    - Side: `sell`
    - Prix: `entry_price_short_nouveau * (1 + Fib[1]/100)`
    - Taille: `size_short_nouveau * 2`
    - Params: `tradeSide='open', holdSide='short'`

18. **Attendre 1 seconde**

#### État final
```
Positions:
  - Long: ~750 contrats, 3 USDT marge (DOUBLÉ Fib 1)
  - Short: ~250 contrats, 1 USDT marge (NOUVEAU Fib 0)

Ordres actifs:
  - TP Long @ entry_moyen_long +0.3%
  - TP Short @ nouveau_entry -0.3%
  - Double Long @ entry_moyen_long -0.382% (Fib 1)
  - Double Short @ nouveau_entry +0.382% (Fib 1)

Niveau Fibonacci: 1
```

---

## 🔍 DÉTECTION DES ÉVÉNEMENTS

### Comment détecter qu'un TP a été exécuté ?

**Méthode : Comparaison avant/après**

```python
# État précédent (stocké en mémoire)
previous_state = {
    'long_exists': True,
    'short_exists': True,
    'long_size': 250,
    'short_size': 250
}

# État actuel (depuis API)
current_state = get_positions_from_api()

# Détection
if previous_state['long_exists'] and not current_state['long_exists']:
    → TP LONG EXÉCUTÉ !

if previous_state['short_exists'] and not current_state['short_exists']:
    → TP SHORT EXÉCUTÉ !

if current_state['long_size'] > previous_state['long_size']:
    → DOUBLE LONG EXÉCUTÉ !

if current_state['short_size'] > previous_state['short_size']:
    → DOUBLE SHORT EXÉCUTÉ !
```

---

## 📊 STRUCTURES DE DONNÉES

### Position State (en mémoire)
```python
class PositionState:
    pair: str                    # "DOGE/USDT:USDT"
    current_level: int           # 0, 1, 2, ... 10

    # Long
    long_exists: bool
    long_size: float            # contrats
    long_entry: float           # prix moyen
    long_margin: float          # marge utilisée

    # Short
    short_exists: bool
    short_size: float
    short_entry: float
    short_margin: float

    # Ordres actifs
    tp_long_id: str | None
    tp_short_id: str | None
    double_long_id: str | None
    double_short_id: str | None
```

### API Response Structure

**GET positions :**
```json
{
  "data": [
    {
      "symbol": "DOGEUSDT",
      "holdSide": "long",
      "contracts": "250.00",
      "entryPrice": "0.20022",
      "markPrice": "0.19970",
      "margin": "0.9948546",
      "unrealizedPnl": "-0.1120500",
      "percentage": "-11.26"
    }
  ]
}
```

**GET ordres LIMIT :**
```json
{
  "data": [
    {
      "orderId": "123456",
      "symbol": "DOGEUSDT",
      "side": "buy",
      "price": "0.19975",
      "size": "500",
      "orderType": "limit"
    }
  ]
}
```

**GET ordres TP/SL plan :**
```json
{
  "data": [
    {
      "planId": "789012",
      "symbol": "DOGEUSDT",
      "holdSide": "long",
      "triggerPrice": "0.20082",
      "size": "250",
      "planType": "profit_plan"
    }
  ]
}
```

---

## ⏱️ TIMING ET DÉLAIS

### Délais obligatoires entre appels API

```yaml
Après ordre MARKET: 2 secondes (attendre exécution)
Après ordre LIMIT: 1 seconde
Après ordre TP/SL: 1 seconde
Après annulation: 500ms
Entre 2 GET: 500ms minimum
```

### Rate Limits Bitget

```yaml
Ordres: 20 requêtes / 2 secondes
Positions: 20 requêtes / 2 secondes
Annulations: 20 requêtes / 2 secondes
```

**⚠️ NE JAMAIS dépasser ces limites sous peine de ban IP !**

---

## 🚨 VALIDATIONS ET SÉCURITÉS

### Avant de placer un ordre

1. ✅ **Vérifier que le prix n'est PAS déjà atteint**
   - TP Long @ +0.3% : Prix actuel doit être < prix TP
   - TP Short @ -0.3% : Prix actuel doit être > prix TP
   - Si déjà atteint → **NE PAS PLACER** (skip)

2. ✅ **Vérifier distance minimale : > 0.2%**
   - Si distance < 0.2% → **SKIP** (trop proche)
   - Logger warning

3. ✅ **Vérifier que l'ordre n'existe pas déjà**
   - Pas de doublon !

### Après placement ordre

1. ✅ **Vérifier que l'ordre est bien créé**
   ```python
   GET /api/v2/mix/v1/order/detail?orderId={id}
   ```
   - Si statut = "live" → OK
   - Si erreur → Retry 1 fois

2. ✅ **Stocker l'ID de l'ordre**
   - Pour pouvoir l'annuler plus tard

### Gestion des erreurs API

```python
if erreur API:
    logger.error(f"Erreur API: {erreur}")

    if erreur == "rate limit":
        attendre 5 secondes
        retry

    if erreur == "insufficient margin":
        logger.critical("CAPITAL INSUFFISANT!")
        alert Telegram
        STOP

    if erreur == "invalid size":
        logger.error("Taille ordre invalide")
        skip cet ordre
        continuer

    # Autres erreurs
    retry 1 fois
    si échec: logger + continuer
```

---

## 📝 LOGS DÉTAILLÉS

### Chaque action doit être loggée

```python
logger.info(f"[{pair}] TP LONG EXÉCUTÉ détecté")
logger.info(f"[{pair}] Ancien Long: 250 contrats fermés")
logger.info(f"[{pair}] Short doublé: 250 → 750 contrats")
logger.info(f"[{pair}] Annulation ancien TP Short (id: 789012)")
logger.info(f"[{pair}] Annulation ordre Double Long (id: 123456)")
logger.info(f"[{pair}] Ouverture nouveau Long MARKET...")
logger.info(f"[{pair}] Nouveau Long ouvert: 250 contrats @ 0.19970")
logger.info(f"[{pair}] API check: entry_long=0.19970, size_long=250")
logger.info(f"[{pair}] API check: entry_short_moyen=0.19985, size_short=750")
logger.info(f"[{pair}] Placement TP Long @ 0.20030 (+0.3%)")
logger.info(f"[{pair}] Placement TP Short @ 0.19925 (-0.3%)")
logger.info(f"[{pair}] Niveau Fibonacci: 0 → 1")
logger.info(f"[{pair}] Placement Double Long @ 0.19894 (-0.382%)")
logger.info(f"[{pair}] Placement Double Short @ 0.20061 (+0.382%)")
logger.info(f"[{pair}] ✅ CYCLE COMPLET - État: L:250 (Fib0) S:750 (Fib1)")
```

---

## 🎯 ORDRE DES PRIORITÉS

### En cas de détection simultanée

1. **Priorité 1 : TP exécutés**
   - Traiter TP Long exécuté
   - Traiter TP Short exécuté

2. **Priorité 2 : Doublements détectés**
   - Vérifier cohérence avec TP

3. **Priorité 3 : Replacer ordres manquants**
   - Si un ordre disparaît sans raison

---

## ✅ CHECKLIST AVANT IMPLÉMENTATION

- [ ] Comprendre TOUTE la logique Phase 1 à 4
- [ ] Valider les niveaux Fibonacci
- [ ] Valider les délais (500ms, 1s, 2s)
- [ ] Comprendre la détection d'événements
- [ ] Valider les structures de données
- [ ] Comprendre les appels API
- [ ] Valider les sécurités
- [ ] Valider les logs
- [ ] Tester sur papier avec scénarios

---

## 🧪 SCÉNARIOS DE TEST

### Scénario 1 : Prix monte +0.3%
```
État initial: Long 250 (Fib 0), Short 250 (Fib 0)
Action Bitget: TP Long + Double Short exécutés
État attendu: Long 250 (Fib 0 NOUVEAU), Short 750 (Fib 1)
Ordres attendus: 4 ordres (TP L, TP S, Double L @ -0.382%, Double S @ +0.382%)
```

### Scénario 2 : Prix descend -0.3%
```
État initial: Long 250 (Fib 0), Short 250 (Fib 0)
Action Bitget: TP Short + Double Long exécutés
État attendu: Long 750 (Fib 1), Short 250 (Fib 0 NOUVEAU)
Ordres attendus: 4 ordres
```

### Scénario 3 : Prix monte +0.3% deux fois de suite
```
État initial: Long 250 (Fib 0), Short 750 (Fib 1)
Action 1: TP Long exécuté → Long 250 (nouveau), Short 2250 (Fib 2)
État après 1: Long 250 (Fib 0), Short 2250 (Fib 2), Level = 2
Action 2: TP Long exécuté ENCORE → Long 250 (nouveau), Short 6750 (Fib 3)
État après 2: Long 250 (Fib 0), Short 6750 (Fib 3), Level = 3
```

---

## 🔚 FIN DU DOCUMENT

**Ce document est la référence ABSOLUE.**
**Toute implémentation Python DOIT suivre EXACTEMENT cette logique.**
**Aucun raccourci. Aucune approximation.**

---

**Questions ? Modifications ? Validations ? → AVANT de coder !**
