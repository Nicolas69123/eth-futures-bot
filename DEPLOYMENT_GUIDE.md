# 🚀 Guide de Déploiement - Bot Trading ETH Telegram

Guide complet pour déployer le bot de trading ETH sur Railway avec notifications Telegram 24/7.

---

## 📋 Vue d'ensemble

**Objectif :** Déployer un bot qui surveille le prix ETH/USDT perpetual futures sur MEXC et envoie les mises à jour sur Telegram toutes les 5-10 secondes.

**Technologies :**
- Python 3.11+
- WebSocket MEXC Futures
- Telegram Bot API
- Railway.app (hébergement gratuit)
- GitHub (stockage code)

**Coût :** 0€ (Railway offre 5$/mois gratuit)

---

## ✅ ÉTAPE 1 : Créer le bot Telegram

### 1.1 Créer le bot avec BotFather

1. Ouvrir Telegram
2. Chercher **@BotFather** (bot officiel avec badge vérifié)
3. Démarrer une conversation : `/start`
4. Créer un nouveau bot : `/newbot`
5. Suivre les instructions :
   - Choisir un nom pour votre bot (ex: "ETH Price Monitor")
   - Choisir un username (doit finir par "bot", ex: "eth_price_monitor_bot")

6. **IMPORTANT** : Copier et sauvegarder le **TOKEN** fourni
   - Format : `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
   - ⚠️ Ne JAMAIS partager ce token publiquement

### 1.2 Obtenir votre Chat ID

1. Chercher **@userinfobot** sur Telegram
2. Démarrer une conversation : `/start`
3. Le bot vous donnera votre **Chat ID** (ex: `123456789`)
4. Sauvegarder ce Chat ID

### 1.3 Démarrer votre bot

1. Chercher votre bot sur Telegram (username choisi)
2. Cliquer sur `/start` pour l'activer
3. Envoyer un message de test

**✅ Validation :** Vous avez maintenant :
- [ ] Token du bot (format: `1234567890:ABC...`)
- [ ] Votre Chat ID (format: `123456789`)
- [ ] Bot démarré

---

## ✅ ÉTAPE 2 : Modifier le script Python

### 2.1 Créer le nouveau script avec Telegram

Le script `eth_futures_telegram.py` sera créé avec :
- Connexion WebSocket MEXC
- Envoi messages Telegram toutes les X secondes
- Gestion des erreurs
- Variables d'environnement pour sécurité

**Configuration :**
- Fréquence d'envoi : Toutes les **10 secondes** (recommandé)
- Alternative : Uniquement si variation > 0.1%

### 2.2 Installer les dépendances

Dépendances nécessaires (dans `requirements.txt`) :
```
websocket-client>=1.6.0
requests>=2.31.0
python-telegram-bot>=20.0
```

**✅ Validation :** Script créé et testé localement

---

## ✅ ÉTAPE 3 : Préparer les fichiers de déploiement

### 3.1 Fichiers nécessaires

Pour déployer sur Railway, nous aurons besoin de :

1. **`requirements.txt`** - Dépendances Python
2. **`runtime.txt`** - Version Python (optionnel)
3. **`Procfile`** - Commande de démarrage
4. **`.env.example`** - Template des variables d'environnement
5. **`.gitignore`** - Fichiers à ne pas commit

### 3.2 Structure du projet

```
trading/
├── .env.example              # Template variables
├── .gitignore               # Fichiers ignorés
├── Procfile                 # Commande Railway
├── README.md                # Documentation
├── DEPLOYMENT_GUIDE.md      # Ce fichier
├── requirements.txt         # Dépendances
├── strategy1.md            # Stratégie trading
├── eth_futures_telegram.py  # Script principal
└── trading_bot.py          # Ancien script (backup)
```

**✅ Validation :** Tous les fichiers créés

---

## ✅ ÉTAPE 4 : Créer le repo GitHub

### 4.1 Initialiser Git localement

```bash
cd "/Users/nicolas/Documents/Mes Projects/trading"
git init
git add .
git commit -m "Initial commit - ETH Futures Telegram Bot"
```

### 4.2 Créer le repo sur GitHub

1. Aller sur https://github.com
2. Cliquer sur **New repository**
3. Nom : `eth-futures-bot` (ou autre)
4. **IMPORTANT** : Laisser **Private** pour la sécurité
5. Ne pas initialiser avec README (déjà existant)
6. Créer le repository

### 4.3 Pusher le code

```bash
git remote add origin https://github.com/VOTRE_USERNAME/eth-futures-bot.git
git branch -M main
git push -u origin main
```

**✅ Validation :** Code sur GitHub (repo privé)

---

## ✅ ÉTAPE 5 : Déployer sur Railway

### 5.1 Créer un compte Railway

1. Aller sur https://railway.app
2. Cliquer sur **Start a New Project**
3. Se connecter avec **GitHub** (recommandé)
4. Autoriser Railway à accéder à GitHub

### 5.2 Créer un nouveau projet

1. Cliquer sur **New Project**
2. Sélectionner **Deploy from GitHub repo**
3. Choisir votre repo `eth-futures-bot`
4. Railway va détecter automatiquement que c'est du Python

### 5.3 Configurer les variables d'environnement

Dans Railway, aller dans l'onglet **Variables** et ajouter :

| Variable | Valeur | Exemple |
|----------|--------|---------|
| `TELEGRAM_BOT_TOKEN` | Votre token BotFather | `1234567890:ABC...` |
| `TELEGRAM_CHAT_ID` | Votre Chat ID | `123456789` |
| `UPDATE_INTERVAL` | Fréquence (secondes) | `10` |
| `PYTHON_VERSION` | Version Python | `3.11.0` |

**⚠️ IMPORTANT :** Ne JAMAIS commit ces valeurs dans GitHub

### 5.4 Vérifier le déploiement

1. Railway va automatiquement :
   - Installer les dépendances (`requirements.txt`)
   - Lancer le script (`Procfile`)

2. Vérifier les logs dans l'onglet **Deployments**
3. Le bot devrait se connecter et commencer à envoyer sur Telegram

**✅ Validation :** Bot actif sur Railway et messages reçus sur Telegram

---

## ✅ ÉTAPE 6 : Tester et Surveiller

### 6.1 Vérification

- [ ] Messages reçus sur Telegram toutes les 10 secondes
- [ ] Prix ETH/USDT affiché correctement
- [ ] Variation 24h affichée
- [ ] Aucune erreur dans les logs Railway

### 6.2 Surveillance

**Logs Railway :**
- Accéder aux logs en temps réel dans Railway
- Vérifier qu'il n'y a pas d'erreurs

**Telegram :**
- Vérifier la fréquence des messages
- Vérifier que les prix sont cohérents

### 6.3 Ajustements

Si besoin, ajuster dans Railway > Variables :
- `UPDATE_INTERVAL` : Changer la fréquence (5, 10, 30 secondes)

---

## 🔧 Maintenance

### Mettre à jour le code

1. Modifier le code localement
2. Commit et push :
```bash
git add .
git commit -m "Description des changements"
git push
```
3. Railway redéploie automatiquement

### Arrêter le bot

Dans Railway :
- Aller dans Settings
- Cliquer sur **Delete Service**

### Redémarrer le bot

Dans Railway :
- Aller dans Deployments
- Cliquer sur **Restart**

---

## ⚠️ Sécurité

### ✅ Bonnes pratiques

- ✅ Repo GitHub en **Private**
- ✅ Token et Chat ID dans **variables d'environnement** uniquement
- ✅ Fichier `.env` dans `.gitignore`
- ✅ Ne JAMAIS commit de secrets dans Git

### ❌ À éviter

- ❌ Partager le token du bot
- ❌ Commit du fichier `.env`
- ❌ Repo public avec des secrets
- ❌ Token dans le code source

---

## 🐛 Résolution de problèmes

### Le bot ne démarre pas sur Railway

1. Vérifier les logs dans Railway
2. Vérifier que `Procfile` existe
3. Vérifier que `requirements.txt` est à jour

### Pas de messages sur Telegram

1. Vérifier que `TELEGRAM_BOT_TOKEN` est correct
2. Vérifier que `TELEGRAM_CHAT_ID` est correct
3. Vérifier que vous avez démarré le bot (`/start`)
4. Vérifier les logs pour erreurs

### WebSocket se déconnecte

- Normal : le script reconnecte automatiquement
- Vérifier les logs pour erreurs répétées

### Railway dit "Out of credits"

- Vous avez dépassé les 5$/mois gratuit
- Vérifier votre consommation
- Optimiser le code ou passer à un plan payant

---

## 📊 Consommation Railway estimée

Pour ce bot :
- **CPU** : Très faible (~5-10% utilisation)
- **RAM** : ~50-100 MB
- **Réseau** : Très faible (WebSocket + Telegram)

**Coût estimé :** ~0.50-1.50$/mois

✅ Largement dans les 5$/mois gratuit !

---

## 🎯 Prochaines étapes possibles

Après avoir le bot qui tourne :

1. **Implémenter la stratégie** (crash buying + grid trading)
2. **Ajouter alertes** (crash détecté, opportunité)
3. **Multi-paires** (ETH, BTC, SOL, etc.)
4. **Dashboard web** (visualisation graphique)
5. **Backtesting** (tester stratégie sur historique)

---

## 📚 Ressources

- [Railway Documentation](https://docs.railway.app)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [MEXC Futures API](https://www.mexc.com/api-docs/futures/websocket-api)
- [WebSocket Python](https://websocket-client.readthedocs.io/)

---

## ✅ Checklist complète

- [ ] Étape 1 : Bot Telegram créé (Token + Chat ID)
- [ ] Étape 2 : Script Python modifié avec Telegram
- [ ] Étape 3 : Fichiers de déploiement créés
- [ ] Étape 4 : Repo GitHub créé (privé)
- [ ] Étape 5 : Déployé sur Railway
- [ ] Étape 6 : Bot actif et messages reçus

**Une fois toutes les étapes validées : Bot actif 24/7 ! 🎉**
