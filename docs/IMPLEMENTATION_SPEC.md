# 🔧 SPÉCIFICATIONS D'IMPLÉMENTATION

**Version:** 1.0
**Objectif:** Code propre et fonctionnel selon STRATEGY.md

---

## 📊 DÉTECTION (Toutes les 1 seconde)

```python
# État actuel depuis API
current_state = {
    'long_exists': bool,
    'long_size': float,
    'short_exists': bool,
    'short_size': float
}

# Comparer avec previous_state

# 4 ÉVÉNEMENTS POSSIBLES:
if previous.long_exists and not current.long_exists:
    → handle_tp_long_executed()

if previous.short_exists and not current.short_exists:
    → handle_tp_short_executed()

if current.long_size > previous.long_size * 1.3:
    → handle_fib_long_executed()

if current.short_size > previous.short_size * 1.3:
    → handle_fib_short_executed()
```

---

## 🔴 ÉVÉNEMENT 1 : TP LONG TOUCHÉ

**Ordre actions :**
1. Annuler TP Short
2. Annuler Double Long
3. **Ré-ouvrir Long MARKET**
4. Attendre 2s
5. **API : Récupérer entry_long, size_long**
6. **Placer Double Long** @ -0.3% (Fib 1) - LIMIT - size * 2
7. Attendre 1s
8. **Placer TP Long** @ +0.3% - TP - size
9. **Message Telegram TP LONG**
10. Update: long_fib_level = 0

---

## 🔵 ÉVÉNEMENT 2 : TP SHORT TOUCHÉ

**Ordre actions :**
1. Annuler TP Long
2. Annuler Double Short
3. **Ré-ouvrir Short MARKET**
4. Attendre 2s
5. **API : Récupérer entry_short, size_short**
6. **Placer Double Short** @ +0.3% (Fib 1) - LIMIT - size * 2
7. Attendre 1s
8. **Placer TP Short** @ -0.3% - TP - size
9. **Message Telegram TP SHORT**
10. Update: short_fib_level = 0

---

## ⚡ ÉVÉNEMENT 3 : FIBONACCI LONG TOUCHÉ

**Ordre actions :**
1. Annuler TP Long
2. Annuler Double Long
3. **API : Récupérer entry_long_moyen, size_long_total**
4. **Incrémenter long_fib_level += 1**
5. **Placer Double Long** @ -Fib[next]% - LIMIT - size_total * 2
6. Attendre 1s
7. **Placer TP Long** @ +0.3% - TP - size_total
8. **Message Telegram FIBONACCI LONG**
9. Update size_previous

---

## ⚡ ÉVÉNEMENT 4 : FIBONACCI SHORT TOUCHÉ

**Ordre actions :**
1. Annuler TP Short
2. Annuler Double Short
3. **API : Récupérer entry_short_moyen, size_short_total**
4. **Incrémenter short_fib_level += 1**
5. **Placer Double Short** @ +Fib[next]% - LIMIT - size_total * 2
6. Attendre 1s
7. **Placer TP Short** @ -0.3% - TP - size_total
8. **Message Telegram FIBONACCI SHORT**
9. Update size_previous

---

## 📱 MESSAGES TELEGRAM

### Message TP touché
```
🔔 TP LONG EXÉCUTÉ

💰 Prix exécution: $0.20300
💵 Profit réalisé: +$0.50

🟢 LONG (réouvert Fib 0)
📊 Contrats: 250
📍 Entrée: $0.20305
💼 Marge: 1.02 USDT
💰 P&L: -$0.05
📈 ROE: -4.9%

⏰ 15:30:45
```

### Message Fibonacci touché
```
⚡ FIBONACCI 2 LONG TOUCHÉ

📈 Position doublée

🟢 LONG (Fib 2)
📊 Contrats: 2250 (+1500)
📍 Entrée moyenne: $0.20150
💼 Marge: 9.03 USDT
💰 P&L: +$0.35
📈 ROE: +3.8%

⏰ 15:31:12
```

---

## ✅ CHECKLIST AVANT COMMIT

- [ ] 4 fonctions handle_X_executed() créées
- [ ] check_orders_status() refait avec détection correcte
- [ ] Messages Telegram séparés et clairs
- [ ] Syntaxe Python valide
- [ ] Pas de suppositions (toujours vérifier API)
- [ ] Ordre placement respecté : MARKET → LIMIT → TP
- [ ] Logs détaillés à chaque étape

---

**Document de référence pour implémentation**
