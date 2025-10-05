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
├── README.md                   # 📖 Documentation
├── DEPLOYMENT_GUIDE.md         # 🚀 Guide déploiement
├── requirements.txt            # 📦 Dépendances
├── Procfile                    # ⚙️ Railway
├── runtime.txt                 # 🐍 Python
├── .env.example                # 🔐 Config template
├── .gitignore                  # 🚫 Git
├── bot/                        # 🤖 SCRIPT PRINCIPAL
│   └── eth_futures_telegram.py # Script avec alertes Telegram
├── docs/                       # 📚 Documentation
│   └── strategy1.md            # Stratégie crash buying
└── archive/                    # 📦 Anciens scripts
    ├── eth_futures_realtime.py # Monitoring simple
    ├── trading_bot.py          # Analyse paires
    └── key.py                  # Clés API (ne pas commit)
```

## ⚙️ Paramètres configurables

Dans `bot/eth_futures_telegram.py`, vous pouvez ajuster :

```python
CRASH_THRESHOLD = -2.0         # -2% = crash
CRASH_TIMEFRAME = 900          # 15 minutes
VARIATION_THRESHOLD = 0.5      # 0.5% variation importante
ALERT_COOLDOWN = 300           # 5 minutes entre alertes
```

## 🎯 Prochaines étapes

- [x] Détection de crash en temps réel
- [x] Alertes Telegram intelligentes
- [ ] Implémenter ordres automatiques (grid trading)
- [ ] Backtesting sur données historiques
- [ ] Multi-paires (BTC, SOL, etc.)
- [ ] Dashboard web

## Avertissement

⚠️ **Ce bot est à des fins éducatives et de test uniquement.**

- Ne tradez jamais avec de l'argent que vous ne pouvez pas perdre
- Testez toujours sur un compte de démonstration d'abord
- Le trading comporte des risques de perte en capital
