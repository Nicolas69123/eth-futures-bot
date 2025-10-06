# 🤖 ETH Futures Trading Bot - MEXC + Telegram

Bot de trading automatisé qui surveille ETH/USDT perpetual futures sur MEXC et envoie des alertes intelligentes sur Telegram.

## 🎯 Fonctionnalités

- ✅ Analyse du prix ETH en **temps réel** (WebSocket MEXC)
- ✅ Alertes Telegram **intelligentes** :
  - 🔴 **Crash détecté** : -2% en moins de 15 minutes
  - ⚡ **Variation importante** : ±0.5% en 1 minute
  - 💰 **Opportunité de trading** : Pattern crash buying
- ✅ Prêt pour déploiement 24/7 sur Railway
- ✅ Aucune clé API MEXC nécessaire (lecture publique)

## 📦 Installation

### 1. Installer les dépendances

```bash
cd "/Users/nicolas/Documents/Mes Projects/trading"
pip install -r requirements.txt
```

### 2. Configuration (Test local)

Créer un fichier `.env` avec vos identifiants Telegram :

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

**Comment obtenir ces informations :**
- Voir le guide complet dans `DEPLOYMENT_GUIDE.md` (Étape 1)

## 🚀 Utilisation

### Test local

```bash
# Définir les variables d'environnement
export TELEGRAM_BOT_TOKEN="votre_token"
export TELEGRAM_CHAT_ID="votre_chat_id"

# Lancer le bot
python bot/eth_futures_telegram.py
```

### Déploiement sur Railway (24/7)

Suivre le guide complet : **`DEPLOYMENT_GUIDE.md`**

## 📊 Alertes configurées

| Type | Condition | Cooldown |
|------|-----------|----------|
| 🔴 Crash | -2% en 15 min | 5 min |
| ⚡ Variation | ±0.5% en 1 min | 5 min |
| 💰 Opportunité | Pattern rebond | 5 min |

## 📁 Structure du projet

```
trading/
├── README.md                       # 📖 Documentation
├── DEPLOYMENT_GUIDE.md             # 🚀 Guide déploiement Railway
├── requirements.txt                # 📦 Dépendances
├── Procfile                        # ⚙️ Railway
├── runtime.txt                     # 🐍 Python
├── .env.example                    # 🔐 Config template
├── .gitignore                      # 🚫 Git
├── bot/                            # 🤖 SCRIPTS
│   ├── eth_futures_telegram.py     # 📊 Alertes MEXC → Telegram
│   ├── bitget_testnet_trading.py   # 🎯 Trading crash buying (DEMO)
│   └── bitget_hedge_fibonacci.py   # 🔥 Hedge Fibonacci multi-paires
├── docs/                           # 📚 Documentation
│   ├── strategy1.md                # Stratégie crash buying
│   ├── BITGET_SETUP.md             # 🎯 Guide Bitget testnet
│   └── STRATEGY_HEDGE_FIBONACCI.md # 📖 Stratégie hedge Fibonacci
└── archive/                        # 📦 Anciens scripts
    ├── eth_futures_realtime.py     # Monitoring simple
    ├── trading_bot.py              # Analyse paires
    └── key.py                      # Clés API (ne pas commit)
```

## ⚙️ Paramètres configurables

Dans `bot/eth_futures_telegram.py`, vous pouvez ajuster :

```python
CRASH_THRESHOLD = -2.0         # -2% = crash
CRASH_TIMEFRAME = 900          # 15 minutes
VARIATION_THRESHOLD = 0.5      # 0.5% variation importante
ALERT_COOLDOWN = 300           # 5 minutes entre alertes
```

## 🎯 Bots disponibles

### 1️⃣ **Bot MEXC → Telegram** (`eth_futures_telegram.py`)
- ✅ Surveillance temps réel ETH/USDT
- ✅ Alertes intelligentes sur Telegram
- ✅ Déployé 24/7 sur Railway
- ❌ Pas de trading automatique (alertes uniquement)

### 2️⃣ **Bot Bitget Crash Buying** (`bitget_testnet_trading.py`)
- ✅ Trading automatique en mode DEMO
- ✅ Stratégie crash buying + grid trading
- ✅ Fonds virtuels (10k USDT)
- ✅ Ordres automatiques
- 📖 Voir `docs/BITGET_SETUP.md` pour configuration

### 3️⃣ **Bot Hedge Fibonacci** (`bitget_hedge_fibonacci.py`) 🔥 **NOUVEAU**
- ✅ Stratégie hedge multi-paires avancée
- ✅ Grille Fibonacci pour espacement des niveaux
- ✅ Rotation automatique sur memecoins volatiles
- ✅ Protection contre tendances fortes
- 📖 Voir `docs/STRATEGY_HEDGE_FIBONACCI.md` pour détails

## 🚀 Lancer les bots Bitget

```bash
# 1. Configurer les clés API dans .env (voir docs/BITGET_SETUP.md)

# 2. Lancer bot Crash Buying
python bot/bitget_testnet_trading.py

# OU Lancer bot Hedge Fibonacci
python bot/bitget_hedge_fibonacci.py
```

## 🎯 Fonctionnalités implémentées

- [x] Détection de crash en temps réel
- [x] Alertes Telegram intelligentes
- [x] Ordres automatiques (grid trading)
- [x] Test sur Bitget testnet
- [x] Stratégie hedge multi-paires
- [x] Grille Fibonacci
- [ ] Backtesting sur données historiques
- [ ] Dashboard web de monitoring

## Avertissement

⚠️ **Ce bot est à des fins éducatives et de test uniquement.**

- Ne tradez jamais avec de l'argent que vous ne pouvez pas perdre
- Testez toujours sur un compte de démonstration d'abord
- Le trading comporte des risques de perte en capital
