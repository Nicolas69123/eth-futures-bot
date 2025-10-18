# Architecture du Projet - Trading Bot

## 📂 Structure des Dossiers

```
TelegramBot/
├── bot/
│   └── bitget_hedge_fibonacci_v2.py  # 🎯 Script principal bot
├── scripts/                           # Scripts de gestion
│   └── manage_local.sh               # Gestion locale
├── docs/                              # Documentation
│   ├── DEPLOYMENT_GUIDE.md           # Guide déploiement
│   └── README.md                     # Doc principale
├── logs/                              # Logs d'exécution
├── archive/                           # Anciennes versions
├── .env                               # ⚠️ Secrets (JAMAIS commit)
├── .env.example                       # Template .env
├── .gitignore                         # Git ignore
├── requirements.txt                   # Dépendances Python
├── runtime.txt                        # Version Python
├── Procfile                           # Config Railway (backup)
├── nixpacks.toml                      # Config Nixpacks
├── .claude/                           # 📁 Config Claude
│   ├── context.md
│   ├── architecture.md (ce fichier)
│   ├── progress.md
│   └── changelog.md
└── CLAUDE.md                          # Point d'entrée Claude
```

---

## 🔄 Flow d'Exécution

```
Bot Start
    ↓
Load Config (.env)
    ↓
Connect Bitget API
    ↓
Connect Telegram Bot
    ↓
Main Loop (infinite)
    ↓
├→ Fetch Market Data
├→ Calculate Fibonacci Levels
├→ Check Entry Conditions
├→ Execute Trades (Long + Short hedge)
├→ Monitor Positions
├→ Send Telegram Notifications
└→ Sleep (interval)
```

---

## 🤖 Logique Trading

### Stratégie : Hedge Fibonacci

**Principe** :
1. Calculer niveaux Fibonacci sur timeframe
2. Ouvrir **LONG** au niveau 0.618 (support)
3. Ouvrir **SHORT** au niveau 0.382 (résistance)
4. TP/SL basés sur niveaux Fibonacci suivants
5. Hedge = risque limité, profit sur volatilité

**Paramètres** :
- **Timeframe** : 15min / 1h
- **Levier** : 5x-10x
- **Size** : Variable selon capital

---

## 📡 APIs Utilisées

### **1. Bitget API**

**Endpoints principaux** :
```
GET  /api/mix/v1/market/ticker        # Prix actuel
POST /api/mix/v1/order/placeOrder     # Passer ordre
GET  /api/mix/v1/position/allPosition # Positions ouvertes
```

**Authentication** : HMAC-SHA256

### **2. Telegram Bot API**

**Endpoints** :
```
POST sendMessage         # Envoyer notification
POST sendPhoto           # Envoyer screenshot charts
```

---

## 🖥️ Serveur Oracle Cloud

**Specs** :
- **OS** : Ubuntu 22.04 LTS
- **RAM** : 1 GB
- **CPU** : 1 core
- **Stockage** : 50 GB
- **IP** : 130.110.243.130
- **Région** : Marseille (EU)

**Process Management** :
```bash
# Session screen nommée "trading"
screen -dmS trading python3 bot/bitget_hedge_fibonacci_v2.py

# Attacher
screen -r trading

# Détacher
Ctrl+A puis D
```

---

## 📊 Gestion des Logs

**Localisation** : `logs/`

**Format** :
```
[2025-10-18 14:30:15] INFO - Bot started
[2025-10-18 14:30:20] INFO - Connected to Bitget
[2025-10-18 14:35:00] TRADE - LONG ETH-USDT @$2500 (5x)
[2025-10-18 14:35:05] TRADE - SHORT ETH-USDT @$2550 (5x)
[2025-10-18 15:00:00] PROFIT - +$25.50 (hedge closed)
```

**Rotation** : Logs archivés quotidiennement

---

## 🚀 Déploiement

### **Process Production**

1. **Code local** → Commit GitHub
2. **SSH Oracle Cloud**
```bash
ssh -i ~/.ssh/ssh-key-2025-10-12.key ubuntu@130.110.243.130
```
3. **Update code**
```bash
cd eth-futures-bot
git pull
```
4. **Restart bot**
```bash
screen -X -S trading quit
screen -dmS trading python3 bot/bitget_hedge_fibonacci_v2.py
```

### **Scripts de Gestion**

Situés dans `~/Tools/Scripts/` :

- `🚀 Update Trading Bot.command` - Update + redeploy
- `📊 Check Bot Status.command` - Vérifier status
- `⏹️ Stop Trading Bot.command` - Arrêter bot
- `📜 View Bot Logs.command` - Logs temps réel

---

## 🔐 Sécurité

- ✅ Clés API stockées dans `.env` (non commit)
- ✅ SSH key protégée (permissions 600)
- ✅ Firewall Oracle (port 22 seulement)
- ✅ Logs ne contiennent PAS de secrets
- ⚠️ Pas d'exposition publique (pas d'API endpoint)

---

## 📈 Monitoring

**Métriques suivies** :
- Nombre de trades / jour
- Win rate %
- Profit/Loss total
- Drawdown max
- Uptime bot

**Alertes Telegram** :
- ✅ Trade executed
- ✅ Profit target hit
- ✅ Stop loss hit
- ❌ Error / Exception
- ❌ Bot offline

---

## 🛠️ Dépendances Principales

```
ccxt==4.x          # Exchange API wrapper
python-telegram-bot
requests
pandas             # Data analysis
numpy              # Calculs Fibonacci
python-dotenv      # Load .env
```

Voir `requirements.txt` pour version exactes.
