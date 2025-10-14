# 📊 STRATÉGIE FIBONACCI HEDGE

**Version:** 2.3
**Règle d'or:** TP TOUJOURS 0.3% fixe | Double suit Fibonacci | Chaque position a SON niveau

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
5. Placer TP Long @ +0.3% FIXE (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% FIXE (**750 contrats = INTÉGRALITÉ**)
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
5. Placer TP Long @ +0.3% FIXE (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% FIXE (**2250 contrats = INTÉGRALITÉ**)
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
5. Placer TP Long @ +0.3% FIXE (250 contrats)
6. Placer TP Short @ prix_moyen_short -0.3% FIXE (**6750 contrats = INTÉGRALITÉ**)
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
5. Placer TP Short @ -0.3% FIXE (250 contrats)
6. Placer TP Long @ prix_moyen_long +0.3% FIXE (**750 contrats = INTÉGRALITÉ**)
7. Placer Double Short @ +0.3% (500 contrats, Fib 1 SHORT)
8. Placer Double Long @ prix_moyen_long -0.382% (1500 contrats, Fib 2 LONG)

**État final:** Long(Fib1), Short(Fib0)

---

## 🔍 DÉTECTION DES ÉVÉNEMENTS

**INTERROGER API toutes les 1 seconde pour détecter 3 cas :**

### CAS 1 : TP Long exécuté
- **Détection :** Position Long disparue (exists → n'existe plus)
- **Actions :** Annuler ordres (TP Short, Double Long) + Ré-ouvrir Long + Replacer 4 ordres

### CAS 2 : TP Short exécuté
- **Détection :** Position Short disparue (exists → n'existe plus)
- **Actions :** Annuler ordres (TP Long, Double Short) + Ré-ouvrir Short + Replacer 4 ordres

### CAS 3 : Double exécuté SEUL (sans TP)
- **Détection :** Taille position augmente (ex: Short 750 → 2250) SANS que l'autre disparaisse
- **Actions :** Annuler ordres de CETTE position uniquement + Replacer 2 ordres (TP + Double)
- **Important :** NE PAS TOUCHER l'autre position !

**Exemples CAS 3 :**
- Short 750 → 2250 : Replacer TP Short + Double Short uniquement
- Long 750 → 2250 : Replacer TP Long + Double Long uniquement

---

## 🎯 RÈGLES CRITIQUES

1. **Fib 0 = Prix MARKET** (ouverture/réouverture)
2. **TP TOUJOURS 0.3% FIXE** (peu importe niveau Fibonacci)
3. **Double suit Fibonacci** (0.3%, 0.382%, 0.5%, 0.618%, 1.0%, etc.)
4. **2 niveaux séparés:** `long_fib_level` et `short_fib_level` indépendants
5. **TP ferme TOUT:** Toujours placer TP avec `size_total` (100% position)
6. **INTERROGER API:** Toutes les 1 seconde pour détecter changements
7. **Délais:** 500ms annulation, 1s ordre LIMIT, 2s ordre MARKET
8. **Position réouverte = toujours Fib 0** (retour au début)
9. **Position doublée = niveau suivant** (Fib 0→1→2→3...)
10. **Déséquilibre NORMAL** (pas d'alerte si L:250 S:6750)
11. **Double SANS TP** : Replacer ordres de cette position UNIQUEMENT

---

## 📊 CALCUL DISTANCES

**Pour placer ordres après un doublement :**

```python
# Exemple: Short à Fib 1, doit placer ordres pour Fib 2

TP_FIXE = 0.3  # Constant !
prix_tp_short = entry_short_moyen * (1 - TP_FIXE / 100)  # -0.3% FIXE

next_fib_pct = FIBONACCI_LEVELS[2]  # Fib 2 = 0.382%
prix_double_short = entry_short_moyen * (1 + next_fib_pct / 100)  # +0.382% Fib
```

**IMPORTANT:**
- TP = 0.3% fixe depuis prix_moyen
- Double = Niveau Fibonacci suivant depuis prix_moyen
- TP et Double NE SONT PAS au même prix !

---

**FIN - Document de référence stratégie**
