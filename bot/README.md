# 🤖 Bot Trading - Structure Modulaire

## 📁 Organisation du code

```
bot/
├── bitget_hedge_fibonacci_v2.py    # Fichier principal (version actuelle)
├── bitget_hedge_fibonacci_v3.py    # Version modulaire (WIP)
│
├── core/                            # Composants principaux
│   └── position.py                  # Classe HedgePosition
│
├── api/                             # Clients API
│   └── telegram_client.py           # Client Telegram
│
├── strategies/                      # Stratégies de trading
│   └── fibonacci.py                 # Grille Fibonacci
│
├── monitoring/                      # Surveillance et correction
│   ├── health_check.py              # Vérifications santé
│   └── auto_recovery.py             # Auto-correction
│
└── utils/                           # Utilitaires
    ├── logger.py                    # Configuration logging
    └── formatters.py                # Formatage prix/messages
```

---

## 🎯 Modules

### **core/position.py**
- Classe `HedgePosition` : Gère une paire avec Long + Short
- Tracking des ordres actifs (TP, doublement)
- Grille Fibonacci (niveaux)
- Stats de la position

### **api/telegram_client.py**
- Classe `TelegramClient` : Envoi messages + récupération commandes
- Gère l'authentification
- Timeout et retry automatique

### **strategies/fibonacci.py**
- Classe `FibonacciGrid` : Calculs de niveaux
- `get_trigger_percent()` : Cumul des niveaux
- `calculate_tp_price()` : Prix de TP
- `calculate_double_price()` : Prix de doublement

### **monitoring/auto_recovery.py**
- Classe `AutoRecovery` : Détection et correction automatique
- Vérifie ordres manquants (TP, doublement)
- Sync état bot vs réalité API
- Replace ordres automatiquement

### **utils/logger.py**
- Configuration du logging (fichier + console + Telegram buffer)
- Buffer circulaire pour `/logs`
- Setup centralisé

### **utils/formatters.py**
- `format_price()` : Format selon la paire (PEPE 8 décimales, DOGE 5)
- `round_price()` : Arrondi compatible Bitget

---

## 🔧 Utilisation

### **Version actuelle (V2) :**
```bash
python3 bot/bitget_hedge_fibonacci_v2.py
```

Monolithique, tout dans un fichier.

### **Version modulaire (V3) - WIP :**
```bash
python3 bot/bitget_hedge_fibonacci_v3.py
```

Utilise les modules, plus propre, plus maintenable.

---

## 🚀 Migration

1. ✅ Créer modules (position, telegram, fibonacci, auto_recovery)
2. ⏳ Créer V3 qui importe ces modules
3. ⏳ Tester V3 en parallèle de V2
4. ⏳ Une fois V3 validé, migrer définitivement

**V2 reste fonctionnel pendant toute la migration !**

---

## 📊 Avantages de la structure modulaire

| Avantage | Description |
|----------|-------------|
| **Maintenabilité** | Facile de trouver et modifier une partie |
| **Testabilité** | Chaque module peut être testé indépendamment |
| **Réutilisabilité** | Modules utilisables dans d'autres bots |
| **Clarté** | Code organisé logiquement |
| **Collaboration** | Plusieurs personnes peuvent travailler en parallèle |

---

## 🔍 Auto-Recovery

Le système d'auto-recovery détecte et corrige automatiquement :

✅ **TPs manquants** → Replace automatiquement
✅ **Ordres fantômes** → Nettoie
✅ **État désynchronisé** → Sync avec API
✅ **Ordres orphelins** → Annule ou intègre

S'exécute toutes les 30 secondes en arrière-plan.

---

## 📝 TODO

- [ ] Finaliser bitget_hedge_fibonacci_v3.py
- [ ] Extraire logique API Bitget dans api/bitget_client.py
- [ ] Implémenter replace_tp_long() et replace_tp_short()
- [ ] Créer health_check.py complet
- [ ] Tests unitaires pour chaque module
- [ ] Migration complète vers V3
