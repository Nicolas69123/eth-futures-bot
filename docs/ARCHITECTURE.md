# 🏗️ Architecture du Bot Trading

## 📁 Structure Modulaire (Nouvelle)

Le projet a été restructuré en modules pour meilleure organisation :

```
trading/
├── bot/
│   ├── bitget_hedge_fibonacci_v2.py    ← FICHIER ACTUEL (fonctionne)
│   │
│   ├── core/                            ← Classes principales
│   │   ├── __init__.py
│   │   └── position.py                  # HedgePosition
│   │
│   ├── api/                             ← Clients API
│   │   ├── __init__.py
│   │   └── telegram_client.py           # TelegramClient
│   │
│   ├── strategies/                      ← Stratégies
│   │   ├── __init__.py
│   │   └── fibonacci.py                 # FibonacciGrid
│   │
│   ├── monitoring/                      ← Surveillance
│   │   ├── __init__.py
│   │   └── auto_recovery.py             # AutoRecovery
│   │
│   └── utils/                           ← Utilitaires
│       ├── __init__.py
│       ├── logger.py                    # Configuration logging
│       └── formatters.py                # Format prix/messages
│
├── logs/                                ← Logs automatiques
├── scripts/                             ← Scripts de gestion
├── docs/                                ← Documentation
├── manage_local.sh                      ← Script serveur
└── start_bot.sh                         ← Démarrage bot
```

---

## 🎯 Modules Créés

### **core/position.py** - Gestion des positions

```python
class HedgePosition:
    - Gère une paire (Long + Short)
    - Tracking ordres (TP, doublement)
    - Grille Fibonacci
    - Stats position
```

**Utilisation :**
```python
from core.position import HedgePosition

position = HedgePosition('DOGE/USDT:USDT', 1.0, 0.21, 0.21)
next_trigger = position.get_next_trigger_pct()  # 0.2%
```

---

### **api/telegram_client.py** - Client Telegram

```python
class TelegramClient:
    - Envoi messages
    - Récupération commandes
    - Gestion updates
```

**Utilisation :**
```python
from api.telegram_client import TelegramClient

telegram = TelegramClient(token, chat_id)
telegram.send_message("🚀 Bot démarré!")
updates = telegram.get_updates(offset=123)
```

---

### **strategies/fibonacci.py** - Grille Fibonacci

```python
class FibonacciGrid:
    LEVELS = [0.2, 0.2, 0.4, 0.6, 1.0, ...]

    - get_trigger_percent(level)      # Cumul
    - get_next_level_percent(level)   # Prochain
    - calculate_tp_price(...)         # Prix TP
    - calculate_double_price(...)     # Prix doublement
```

**Utilisation :**
```python
from strategies.fibonacci import FibonacciGrid

tp_price = FibonacciGrid.calculate_tp_price(0.21, 'long', level=0)
# Retourne: 0.21042 (+0.2%)
```

---

### **monitoring/auto_recovery.py** - Auto-correction

```python
class AutoRecovery:
    - Vérifie ordres manquants
    - Sync état bot vs API
    - Replace TPs automatiquement
    - Nettoie ordres orphelins
```

**Utilisation :**
```python
from monitoring.auto_recovery import AutoRecovery

recovery = AutoRecovery(bot_instance)
recovery.run_check()  # Vérifie et corrige
```

**Ce qu'il fait :**
- ✅ Détecte TP manquant → Replace
- ✅ Position fermée pas sync → Sync
- ✅ Ordre orphelin → Annule
- S'exécute automatiquement toutes les 30s

---

### **utils/logger.py** - Logging centralisé

```python
def setup_logging() → logger
def get_recent_logs(count=20) → list
```

**Buffer circulaire** :
- Garde les 50 derniers logs en mémoire
- Accessible via `/logs` sur Telegram

---

### **utils/formatters.py** - Formatage

```python
def format_price(price, pair) → str
def round_price(price, pair) → float
```

Gère automatiquement :
- PEPE/SHIB : 8 décimales
- DOGE : 5 décimales

---

## 🔄 Migration Progressive

### **Phase 1 : Modules créés** ✅

Tous les modules sont créés et disponibles dans le repo.

### **Phase 2 : V2 reste fonctionnel** ✅

Le fichier `bitget_hedge_fibonacci_v2.py` continue de fonctionner normalement.

### **Phase 3 : V3 avec modules** (TODO)

Créer `bitget_hedge_fibonacci_v3.py` qui :
- Importe tous les modules
- Code principal allégé (<500 lignes au lieu de 2300)
- Même comportement exact

### **Phase 4 : Tests et validation** (TODO)

Tester V3 en parallèle de V2, puis migrer.

---

## 🛡️ Auto-Recovery : Stratégie Détaillée

### **Vérifications toutes les 30 secondes :**

| Problème | Détection | Correction |
|----------|-----------|------------|
| **TP Long manquant** | Long existe, orders['tp_long'] = None | Replace TP au bon prix |
| **TP Short manquant** | Short existe, orders['tp_short'] = None | Replace TP au bon prix |
| **Ordre fantôme** | ID dans bot mais n'existe plus sur API | Nettoie ID + Replace |
| **État désync** | Long fermé API mais long_open=True | Sync: long_open=False |
| **Ordre orphelin** | Ordre sur API mais pas dans bot | Annule (sécurité) |

### **Actions automatiques :**

```python
CHAQUE 30s:
  Pour chaque paire:
    1. Fetch positions réelles (API)
    2. Comparer avec état bot
    3. Si incohérence → CORRIGER
    4. Logger l'action
    5. Si >3 corrections → Alerte Telegram
```

### **Exemple concret :**

```
20:00:00 - Ouverture hedge DOGE
20:00:05 - Placement TP Long... ÉCHOUE ❌
20:00:30 - AUTO-RECOVERY détecte TP manquant
20:00:31 - Replace TP Long @ $0.21042
20:00:32 - ✅ Position sécurisée
20:00:33 - Logger: "AUTO-RECOVERY: TP Long replacé"
```

---

## 📊 Avantages

### **Code plus propre :**
- 2300 lignes → Réparties en modules de 50-200 lignes
- Facile à lire et comprendre
- Chaque module a une responsabilité unique

### **Maintenabilité :**
- Modifier Fibonacci : juste `strategies/fibonacci.py`
- Modifier Telegram : juste `api/telegram_client.py`
- Pas besoin de toucher au reste

### **Testabilité :**
- Chaque module peut être testé séparément
- Mock des API facile
- Tests unitaires possibles

### **Auto-healing :**
- Le bot se corrige tout seul
- Détecte et répare les problèmes
- Tourne en continu sans intervention

---

## 🚀 Utilisation Actuelle

**Pour l'instant, utilisez V2 (fichier actuel) :**

```bash
python3 bot/bitget_hedge_fibonacci_v2.py
```

**Les modules sont prêts mais pas encore intégrés dans V2.**

**Prochaine étape : Créer V3 qui utilise les modules** (à venir)

---

## 💡 Note Technique

Les modules utilisent des **imports relatifs** :

```python
from core.position import HedgePosition
from api.telegram_client import TelegramClient
```

Pour que ça fonctionne, il faut lancer depuis le dossier parent :

```bash
cd ~/eth-futures-bot
python3 bot/bitget_hedge_fibonacci_v3.py  # Quand V3 sera créé
```

---

**Structure propre, modulaire, professionnelle !** ✨
