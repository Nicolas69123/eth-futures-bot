# Contexte du Projet - Trading Bot

## 🎯 Mission & Objectifs

**Problème résolu** : Trading manuel 24/7 impossible → Bot automatisé pour capturer opportunités marchés crypto

**Objectifs** :
- Trading automatique ETH Futures sur Bitget
- Stratégie hedge (long + short simultané)
- Niveaux Fibonacci pour entrée/sortie
- Notifications Telegram temps réel
- Disponibilité 24/7 sur cloud

**Users** : Nicolas (trader personnel)

---

## 🛠️ Stack Technique Complète

- **Langage** : Python 3.11
- **Exchange** : Bitget (API REST)
- **Serveur** : Oracle Cloud (Ubuntu 22.04, Marseille)
- **IP** : 130.110.243.130
- **Process Manager** : GNU Screen (session `trading`)
- **Notifications** : Telegram Bot API
- **Monitoring** : Logs locaux + Telegram alerts

---

## 🏢 Environnements

| Env | Serveur | Status |
|-----|---------|--------|
| **Dev** | MacOS local | Tests |
| **Prod** | Oracle Cloud | 24/7 live |

---

## 👤 Propriétaire

- **Nicolas** : Développeur + trader
- Projet personnel

---

## 🔑 Secrets & Configuration

**Variables d'environnement** (`.env`) :
```
BITGET_API_KEY=...
BITGET_SECRET_KEY=...
BITGET_PASSPHRASE=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

**⚠️ JAMAIS commit `.env` !**

**SSH Key** : `~/.ssh/ssh-key-2025-10-12.key`

---

## 📅 Timeline

- **Début projet** : Septembre 2025
- **V1 deploy** : Octobre 2025
- **Status actuel** : Production active
