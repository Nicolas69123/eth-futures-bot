# 🎯 Stratégie Hedge Multi-Paires avec Grille Fibonacci

Stratégie avancée de hedging rotatif sur memecoins volatiles avec réajustement en cascade utilisant la suite de Fibonacci.

---

## 📊 Concept de la Stratégie

### Principe de base : Hedging Neutre Delta

**Position Hedge** = Long + Short simultanément sur même paire

**Exemple initial :**
```
DOGE/USDT
- Long  100$ (acheter DOGE)
- Short 100$ (vendre DOGE)
= Position neutre (delta = 0)
```

Au départ, les profits et pertes s'annulent :
- Si prix monte +10% → Long +10$, Short -10$ = 0$
- Si prix descend -10% → Long -10$, Short +10$ = 0$

---

## 🚀 Déclenchement : Mouvement Violent

Lorsque le prix fait un **mouvement rapide de +1%** (configurable) :

### Étape 1 : Fermer le Long (Prendre Profit)
```
Prix initial: 0.10$
Prix actuel: 0.101$ (+1%)

Action: Vendre le Long
Profit: +1$ ✅
```

### Étape 2 : Réajuster le Short (Doubler la Marge)

Le Short est maintenant en perte de -1$.

**Action** : Ajouter **2x la marge totale** du Short

```
Short initial: 100$ (1000 DOGE @ 0.10$)
Nouveau short: 200$ (1980 DOGE @ 0.101$)

Total Short: 300$ (2980 DOGE)
Prix moyen: ~0.1003$
```

**Objectif** : Rapprocher le prix moyen du prix actuel pour réduire le break-even.

### Étape 3 : Ouvrir Nouveau Hedge sur Autre Paire

Immédiatement après, ouvrir un nouveau hedge sur une **autre paire volatile** :

```
PEPE/USDT
- Long  100$
- Short 100$
```

**Le processus se répète en cascade !**

---

## 📈 Grille Fibonacci : Espacement des Niveaux

Au lieu de réajuster tous les 1%, on utilise la **suite de Fibonacci** pour espacer les niveaux :

### Suite de Fibonacci
```
1, 1, 2, 3, 5, 8, 13, 21, 34, 55...
```

### Application aux Niveaux de Grille

**Espacements** (en %) :
```
Niveau 1:  1%  (premier espacement)
Niveau 2:  1%  (deuxième espacement)
Niveau 3:  2%
Niveau 4:  3%
Niveau 5:  5%
Niveau 6:  8%
Niveau 7: 13%
Niveau 8: 21%
```

**Niveaux cumulés** (déclencheurs) :
```
Niveau 1: +1%  (1)
Niveau 2: +2%  (1+1)
Niveau 3: +4%  (1+1+2)
Niveau 4: +7%  (1+1+2+3)
Niveau 5: +12% (1+1+2+3+5)
Niveau 6: +20% (1+1+2+3+5+8)
Niveau 7: +33% (1+1+2+3+5+8+13)
```

### Pourquoi Fibonacci ?

✅ **Protection contre tendances fortes** : Les espacements augmentent exponentiellement
✅ **Survie du capital** : Évite de brûler le capital trop vite
✅ **Mathématiquement équilibré** : Ratio d'or naturel

---

## 📋 Exemple Complet : Scénario Step-by-Step

### État Initial
```
Capital: 10,000 USDT
Paires disponibles: DOGE, PEPE, SHIB, WIF, BONK, FLOKI
```

### Étape 1 : Ouverture DOGE
```
DOGE @ 0.10$
- Long  100$ (1000 DOGE)
- Short 100$ (1000 DOGE)

Capital utilisé: 200$
```

### Étape 2 : DOGE +1% → Trigger Niveau 1
```
DOGE @ 0.101$

Actions:
1. Fermer Long → Profit +1$ ✅
2. Doubler Short → +200$ (Total: 300$)
3. Ouvrir PEPE Hedge → 200$

Capital utilisé: 500$ (300 DOGE + 200 PEPE)
```

### Étape 3 : PEPE +1% → Trigger Niveau 1
```
PEPE @ 0.000011$

Actions:
1. Fermer Long PEPE → +1$ ✅
2. Doubler Short PEPE → +200$ (Total: 300$)
3. Ouvrir SHIB Hedge → 200$

Capital utilisé: 800$
```

### Étape 4 : DOGE +2% (cumulé) → Trigger Niveau 2
```
DOGE @ 0.102$ (total +2% depuis début)

Actions:
1. Long déjà fermé
2. Doubler Short DOGE → +600$ (Total: 900$)
3. Ouvrir WIF Hedge → 200$

Capital utilisé: 1700$
```

**Et ainsi de suite...**

---

## ⚠️ Gestion du Risque

### Capital Maximum
```python
MAX_CAPITAL = 5000$  # Ne pas dépasser
```

Le bot s'arrête d'ouvrir de nouveaux hedges si le capital utilisé approche la limite.

### Nombre Maximum de Niveaux

Fibonacci niveau 10 = +89% cumulé

**Si le marché monte de +89% sans retournement → STOP**

### Surveillance des Positions Shorts

Les Shorts accumulés doivent être surveillés. Si le prix continue de monter sans s'arrêter, les pertes augmentent.

**Solution** :
- Stop Loss global sur capital
- Fermer tous les shorts si perte > X%

---

## 🎯 Paires Recommandées

### Memecoins Volatiles (Haute Liquidité)

```
DOGE/USDT  - Dogecoin
PEPE/USDT  - Pepe
SHIB/USDT  - Shiba Inu
WIF/USDT   - Dogwifhat
BONK/USDT  - Bonk
FLOKI/USDT - Floki
```

**Critères** :
- ✅ Forte volatilité (mouvements rapides)
- ✅ Haute liquidité (slippage faible)
- ✅ Disponible sur Bitget Futures

**Éviter** :
- ❌ BTC, ETH (trop stables pour cette stratégie)
- ❌ Paires à faible volume (risque de slippage)

---

## ⚙️ Paramètres Configurables

Dans `bot/bitget_hedge_fibonacci.py` :

```python
# Stratégie
INITIAL_MARGIN = 100        # Marge initiale par hedge
TRIGGER_PERCENT = 1.0       # % de mouvement pour trigger
MAX_CAPITAL = 5000          # Capital maximum

# Grille Fibonacci
fib_levels = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]

# Paires
volatile_pairs = [
    'DOGE/USDT:USDT',
    'PEPE/USDT:USDT',
    # ...
]
```

### Ajustements Possibles

**Plus Agressif** :
```python
TRIGGER_PERCENT = 0.5  # Trigger à +0.5%
INITIAL_MARGIN = 50    # Moins de capital par position
```

**Plus Conservateur** :
```python
TRIGGER_PERCENT = 2.0  # Trigger à +2%
MAX_CAPITAL = 3000     # Moins de capital total
```

---

## 📊 Calculs Importants

### Capital Requis par Niveau

Avec marge initiale = 100$ et doublement à chaque niveau :

```
Niveau 1: 200$  (hedge initial)
Niveau 2: 600$  (+400 de doublement short)
Niveau 3: 1400$ (+800)
Niveau 4: 3000$ (+1600)
Niveau 5: 6200$ (+3200) → Dépasse MAX_CAPITAL !
```

**Conclusion** : Avec 5000$ de capital max, on peut gérer environ 4-5 niveaux Fibonacci.

### Break-Even du Short après Réajustement

```
Short 1: 1000 DOGE @ 0.10$  = 100$
Short 2: 1980 DOGE @ 0.101$ = 200$

Total: 2980 DOGE pour 300$
Prix moyen = 300 / 2980 = 0.1007$

Break-even: 0.1007$ (au lieu de 0.10$ initial)
```

Le prix moyen monte, mais reste proche du prix actuel.

---

## 🚦 Conditions de Sortie

### Take Profit

Lorsque le prix **redescend** et que le Short devient profitable :

```
Prix actuel < Prix moyen Short
→ Fermer Short
→ Profit réalisé ✅
```

### Stop Loss Global

Si pertes totales > 20% du capital :
```
→ Fermer toutes les positions
→ Arrêter le bot
```

---

## 📈 Backtesting Recommandé

Avant de trader en réel, **backtester sur données historiques** :

1. Récupérer historique des prix (1 mois)
2. Simuler la stratégie
3. Calculer :
   - Profit total
   - Max drawdown
   - Taux de réussite
   - Capital max utilisé

---

## ⚠️ Risques de la Stratégie

### Risque Principal : Tendance Haussière Prolongée

Si le marché monte continuellement (+50%, +100%) :
- Les Shorts accumulent des pertes
- Le capital est rapidement épuisé
- Risque de liquidation

**Mitigation** :
- Fibonacci espace les niveaux → protège mieux
- Stop loss global
- Diversification sur plusieurs paires

### Risque Secondaire : Liquidité

Sur memecoins volatiles, le slippage peut être important lors de gros ordres.

**Mitigation** :
- Utiliser des paires à haute liquidité
- Limiter la taille des ordres

---

## 🎯 Avantages de la Stratégie

✅ **Profits sur mouvements rapides** : Capture les pumps courts
✅ **Rotation automatique** : Multiplie les opportunités
✅ **Protection Fibonacci** : Survit aux tendances fortes
✅ **Neutre au départ** : Pas de direction initiale nécessaire

---

## 📚 Ressources

- [Suite de Fibonacci](https://fr.wikipedia.org/wiki/Suite_de_Fibonacci)
- [Hedging en trading](https://www.investopedia.com/terms/h/hedge.asp)
- [Grid Trading](https://www.investopedia.com/terms/g/grid-trading.asp)
- [Bitget Futures API](https://www.bitget.com/api-doc/contract/intro)

---

## 🎯 Prochaines Améliorations

- [ ] Backtesting engine
- [ ] Take profit automatique sur shorts
- [ ] Multi-timeframes (1%, 5min, 15min)
- [ ] Machine learning pour sélection de paires
- [ ] Dashboard web de monitoring
