# 📊 STRATÉGIE FIBONACCI HEDGE

**Version:** 2.2
**Règle d'or:** TP et Double au MÊME niveau | Chaque position a SON niveau Fibonacci

---

## ⚙️ PARAMÈTRES

```yaml
Marge initiale: 1 USDT par position
Levier: x50

Niveaux Fibonacci:
  Fib 0: Prix MARKET (ouverture initiale)
  Fib 1: 0.3%
  Fib 2: 0.382%
  Fib 3: 0.5%
  Fib 4: 0.618%
  Fib 5: 1.0%
  Fib 6: 1.618%
  ...
```

---

## 🚀 OUVERTURE INITIALE

```
1. Ouvrir Long 250 contrats MARKET (Fib 0)
2. Ouvrir Short 250 contrats MARKET (Fib 0)
3. Placer TP Long @ +0.3% (250 contrats, Fib 1)
4. Placer TP Short @ -0.3% (250 contrats, Fib 1)
5. Placer Double Long @ -0.3% (500 contrats, Fib 1)
6. Placer Double Short @ +0.3% (500 contrats, Fib 1)

État: Long(Fib0), Short(Fib0)
```

---

## 📈 SCÉNARIO : PRIX MONTE

### Fib 0 → Fib 1 SHORT

**Prix monte +0.3% (Fib 1)**

**Bitget exécute automatiquement:**
- TP Long @ +0.3% (250 contrats fermés)
- Double Short @ +0.3% (500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 750 contrats @ prix_moyen (Fib 1 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short (obsolète)
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET (Fib 0)
4. **INTERROGER API: prix_moyen_short, size_short_total**
5. Placer TP Long @ +0.3% (250 contrats, Fib 1)
6. Placer TP Short @ prix_moyen_short -0.382% (**750 contrats = INTÉGRALITÉ**, Fib 2)
7. Placer Double Long @ -0.3% (500 contrats, Fib 1 LONG)
8. Placer Double Short @ prix_moyen_short +0.382% (1500 contrats, Fib 2 SHORT)

**État final:** Long(Fib0), Short(Fib1)

---

### Fib 1 SHORT → Fib 2 SHORT

**Prix monte encore +0.382% (Fib 2)**

**Bitget exécute:**
- TP Long @ +0.3% (250 contrats fermés)
- Double Short @ +0.382% (1500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 2250 contrats @ prix_moyen (Fib 2 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET (Fib 0)
4. **INTERROGER API: prix_moyen_short, size_short_total**
5. Placer TP Long @ +0.3% (250 contrats, Fib 1)
6. Placer TP Short @ prix_moyen_short -0.5% (**2250 contrats = INTÉGRALITÉ**, Fib 3)
7. Placer Double Long @ -0.3% (500 contrats, Fib 1)
8. Placer Double Short @ prix_moyen_short +0.5% (4500 contrats, Fib 3 SHORT)

**État final:** Long(Fib0), Short(Fib2)

---

### Fib 2 SHORT → Fib 3 SHORT

**Prix monte encore +0.5% (Fib 3)**

**Bitget exécute:**
- TP Long @ +0.3% (250 contrats fermés)
- Double Short @ +0.5% (4500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 6750 contrats @ prix_moyen (Fib 3 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET (Fib 0)
4. **INTERROGER API: prix_moyen_short, size_short_total**
5. Placer TP Long @ +0.3% (250 contrats, Fib 1)
6. Placer TP Short @ prix_moyen_short -0.618% (**6750 contrats = INTÉGRALITÉ**, Fib 4)
7. Placer Double Long @ -0.3% (500 contrats, Fib 1)
8. Placer Double Short @ prix_moyen_short +0.618% (13500 contrats, Fib 4 SHORT)

**État final:** Long(Fib0), Short(Fib3)

---

## 📉 SCÉNARIO : PRIX DESCEND

**Logique MIROIR (inverse) - même principe:**

### Fib 0 → Fib 1 LONG

**Prix descend -0.3% (Fib 1)**

**Bitget exécute:**
- TP Short @ -0.3% (250 contrats fermés)
- Double Long @ -0.3% (500 contrats ajoutés)

**État après:** Long: 750 contrats (Fib 1), Short: 0

**Bot:**
1. Annuler ancien TP Long
2. Annuler ordre Double Short
3. Ré-ouvrir Short 250 MARKET (Fib 0)
4. **INTERROGER API: prix_moyen_long, size_long_total**
5. Placer TP Short @ -0.3% (250 contrats, Fib 1)
6. Placer TP Long @ prix_moyen_long +0.382% (**750 contrats = INTÉGRALITÉ**, Fib 2)
7. Placer Double Short @ +0.3% (500 contrats, Fib 1 SHORT)
8. Placer Double Long @ prix_moyen_long -0.382% (1500 contrats, Fib 2 LONG)

**État final:** Long(Fib1), Short(Fib0)

---

## 🎯 RÈGLES CRITIQUES

1. **Fib 0 = Prix MARKET** (ouverture/réouverture)
2. **TP et Double = MÊME niveau Fibonacci** (se déclenchent ensemble)
3. **2 niveaux séparés:** `long_fib_level` et `short_fib_level` indépendants
4. **TP ferme TOUT:** Toujours placer TP avec `size_total` (100% position)
5. **INTERROGER API:** Après chaque doublement, récupérer `prix_moyen` et `size_total`
6. **Délais:** 500ms annulation, 1s ordre LIMIT, 2s ordre MARKET
7. **Position réouverte = toujours Fib 0** (retour au début)
8. **Position doublée = niveau suivant** (Fib 0→1→2→3...)

---

## 📊 CALCUL DISTANCES

**Pour une position à Fib X qui doit placer ordres à Fib X+1 :**

```python
distance_pct = FIBONACCI_LEVELS[fib_level + 1]  # Ex: Fib 1 = 0.3%
prix_double_long = entry_price * (1 - distance_pct / 100)
prix_tp_long = entry_price * (1 + distance_pct / 100)
```

**TOUJOURS depuis le prix_moyen de la position !**

---

**FIN - Document de référence stratégie**
