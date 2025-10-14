# 📊 STRATÉGIE FIBONACCI HEDGE

**Version:** 2.1
**Règle d'or:** Chaque position (Long/Short) a SON propre niveau Fibonacci

---

## ⚙️ PARAMÈTRES

```yaml
Marge initiale: 1 USDT par position
Levier: x50
TP fixe: ±0.3% (ferme INTÉGRALITÉ position)

Niveaux Fibonacci:
  Fib 0: 0.236%
  Fib 1: 0.382%
  Fib 2: 0.5%
  Fib 3: 0.618%
  Fib 4: 1.0%
  ... (suite standard Fibonacci)
```

---

## 🚀 OUVERTURE INITIALE

```
1. Ouvrir Long 250 contrats (1 USDT)
2. Ouvrir Short 250 contrats (1 USDT)
3. Placer TP Long @ +0.3% (250 contrats)
4. Placer TP Short @ -0.3% (250 contrats)
5. Placer Double Long @ -0.236% (500 contrats)
6. Placer Double Short @ +0.236% (500 contrats)

État: Long(Fib0), Short(Fib0)
```

---

## 📈 SCÉNARIO : PRIX MONTE +0.3%

### Fib 0 → Fib 1 SHORT

**Bitget exécute automatiquement:**
- TP Long (250 contrats fermés)
- Double Short (500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 750 contrats @ prix_moyen (Fib 1 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short (obsolète)
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET
4. **INTERROGER API: Obtenir prix_moyen_short et size_short_total**
5. Placer TP Long @ +0.3% (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% (**750 contrats = INTÉGRALITÉ**)
7. Placer Double Long @ -0.382% (500 contrats, Fib 1 LONG)
8. Placer Double Short @ +0.5% (1500 contrats, Fib 2 SHORT)

**État final:** Long(Fib0), Short(Fib1)

---

### Fib 1 SHORT → Fib 2 SHORT

**Prix monte encore +0.3%**

**Bitget exécute:**
- TP Long (250 contrats fermés)
- Double Short Fib 2 (1500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 2250 contrats @ prix_moyen (Fib 2 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET
4. **INTERROGER API: prix_moyen_short, size_short_total**
5. Placer TP Long @ +0.3% (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% (**2250 contrats = INTÉGRALITÉ**)
7. Placer Double Long @ -0.382% (500 contrats, Fib 1 LONG)
8. Placer Double Short @ +0.618% (4500 contrats, Fib 3 SHORT)

**État final:** Long(Fib0), Short(Fib2)

---

### Fib 2 SHORT → Fib 3 SHORT

**Prix monte encore +0.3%**

**Bitget exécute:**
- TP Long (250 contrats fermés)
- Double Short Fib 3 (4500 contrats ajoutés)

**État après:**
```
Long: 0 contrats
Short: 6750 contrats @ prix_moyen (Fib 3 SHORT)
```

**Bot actions:**
1. Annuler ancien TP Short
2. Annuler ordre Double Long
3. Ré-ouvrir Long 250 contrats MARKET
4. **INTERROGER API: prix_moyen_short, size_short_total**
5. Placer TP Long @ +0.3% (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% (**6750 contrats = INTÉGRALITÉ**)
7. Placer Double Long @ -0.382% (500 contrats, Fib 1 LONG)
8. Placer Double Short @ +1.0% (13500 contrats, Fib 4 SHORT)

**État final:** Long(Fib0), Short(Fib3)

---

## 📉 SCÉNARIO : PRIX DESCEND -0.3%

**Logique MIROIR (inverse) - même principe:**

### Fib 0 → Fib 1 LONG

**Bitget exécute:**
- TP Short (250 contrats fermés)
- Double Long (500 contrats ajoutés)

**État après:** Long: 750 contrats (Fib 1), Short: 0

**Bot:**
1. Annuler ancien TP Long
2. Annuler ordre Double Short
3. Ré-ouvrir Short 250 MARKET
4. **INTERROGER API: prix_moyen_long, size_long_total**
5. TP Short @ -0.3% (250 contrats)
6. TP Long @ prix_moyen_long +0.3% (**750 contrats = INTÉGRALITÉ**)
7. Double Short @ +0.382% (500 contrats, Fib 1 SHORT)
8. Double Long @ -0.5% (1500 contrats, Fib 2 LONG)

**État final:** Long(Fib1), Short(Fib0)

---

## 🎯 RÈGLES CRITIQUES

1. **2 niveaux séparés:** `long_fib_level` et `short_fib_level` indépendants
2. **TP ferme TOUT:** Toujours placer TP avec `size_total` (100% position)
3. **INTERROGER API:** Après chaque doublement, récupérer `prix_moyen` et `size_total` via API
4. **Délais:** 500ms annulation, 1s ordre LIMIT, 2s ordre MARKET
5. **Après Fib 3:** Même logique se répète avec Fib 4, 5, 6, etc.

---

**FIN - Document de référence stratégie**
