# 🎯 Guide Configuration Bitget Testnet

Guide complet pour configurer et utiliser le bot de trading sur Bitget en mode démo (testnet).

---

## 📋 Prérequis

- Compte Bitget (gratuit)
- Python 3.11+
- Bibliothèque `ccxt` installée

---

## ✅ ÉTAPE 1 : Créer un compte Bitget

1. Allez sur https://www.bitget.com
2. Cliquez sur **S'inscrire**
3. Créez votre compte (email + mot de passe)
4. **Complétez la vérification KYC** (obligatoire pour demo trading)

---

## ✅ ÉTAPE 2 : Activer le mode Demo Trading

### Sur Web :

1. Connectez-vous à Bitget
2. En haut de la page, passez la souris sur **Futures**
3. Cliquez sur **Demo Trading**
4. Vous êtes maintenant en mode démo !
5. Vous recevrez automatiquement **50,000 USDT virtuels** 💰

### Sur App Mobile :

1. Ouvrez l'app Bitget
2. Tapez sur l'onglet **Futures**
3. Tapez sur **"..."** en haut à droite
4. Sélectionnez **Demo Trading**

---

## ✅ ÉTAPE 3 : Créer des clés API Demo

**IMPORTANT** : Les clés API demo sont différentes des clés de production !

1. En mode Demo Trading, cliquez sur votre profil (en haut à droite)
2. Allez dans **Personal Center** → **API Management**
3. Cliquez sur **Create a Demo API Key**
4. Remplissez :
   - **API Key Name** : "Trading Bot" (ou autre)
   - **API Passphrase** : Créez un mot de passe (8-32 caractères)
   - **Permissions** : Cochez **Read** et **Trade**
   - **IP Whitelist** : Laissez vide (ou ajoutez votre IP)
5. Cliquez sur **Confirm**
6. **IMPORTANT** : Sauvegardez immédiatement :
   - ✅ **API Key** (commence par "bg_...")
   - ✅ **Secret Key**
   - ✅ **Passphrase** (celui que vous avez créé)

⚠️ **La Secret Key ne sera affichée qu'une seule fois !**

---

## ✅ ÉTAPE 4 : Configurer le fichier .env

Ajoutez vos clés API dans le fichier `.env` :

```bash
# Bitget Demo Trading API
BITGET_API_KEY=votre_api_key_ici
BITGET_SECRET=votre_secret_key_ici
BITGET_PASSPHRASE=votre_passphrase_ici

# Telegram (déjà configuré)
TELEGRAM_BOT_TOKEN=8425963884:AAG_dcQSwORYf0rOPVO04mKIhj8BUPUIPsM
TELEGRAM_CHAT_ID=858901949
```

---

## ✅ ÉTAPE 5 : Lancer le bot

```bash
cd "/Users/nicolas/Documents/Mes Projects/trading"
python bot/bitget_testnet_trading.py
```

---

## 📊 Fonctionnement du Bot

### Stratégie implémentée : Crash Buying + Grid Trading

**Phase 1 : Détection du crash**
- Le bot surveille le prix ETH/USDT en temps réel
- Quand il détecte une chute de **-2% en moins de 15 minutes** → crash détecté

**Phase 2 : Entrée en position**
- Achat immédiat de **0.01 ETH** au marché (première entrée)

**Phase 3 : Grid Trading (achats échelonnés)**
- Placement de 5 ordres limites :
  - Niveau 1 : -1% du prix d'entrée
  - Niveau 2 : -2% du prix d'entrée
  - Niveau 3 : -3% du prix d'entrée
  - Niveau 4 : -4% du prix d'entrée
  - Niveau 5 : -5% du prix d'entrée

**Phase 4 : Take Profit**
- Quand le prix remonte à **+2%** du prix d'entrée → vente de toutes les positions
- Profit réalisé !

---

## ⚙️ Paramètres configurables

Dans `bot/bitget_testnet_trading.py`, vous pouvez modifier :

```python
self.CRASH_THRESHOLD = -2.0      # Seuil de crash (%)
self.CRASH_TIMEFRAME = 900        # Période de détection (secondes)
self.GRID_SPACING = 1.0           # Espacement grille (%)
self.GRID_LEVELS = 5              # Nombre de niveaux
self.ORDER_SIZE = 0.01            # Taille de chaque ordre (ETH)
```

**Exemples :**
- Crash plus agressif : `CRASH_THRESHOLD = -1.5` (détecte à -1.5%)
- Grille plus serrée : `GRID_SPACING = 0.5` (tous les 0.5%)
- Plus d'ordres : `GRID_LEVELS = 10` (10 niveaux)

---

## 📱 Alertes Telegram

Le bot envoie des notifications sur Telegram :

**1. Démarrage**
```
🤖 BOT BITGET TESTNET DÉMARRÉ
Balance: $50,000 USDT
Stratégie: Crash buying + Grid
```

**2. Crash détecté**
```
🔴 CRASH DÉTECTÉ - STRATÉGIE ACTIVÉE
Chute: -2.34% en 5 minutes
Position ouverte: 0.01 ETH
Grille activée: 5 niveaux
```

**3. Niveau de grille atteint**
```
📊 GRILLE - Niveau 2 atteint
Prix: $2,450.00
Baisse totale: -2.0%
```

**4. Take Profit**
```
💰 TAKE PROFIT EXÉCUTÉ
Profit: +2.15%
Positions fermées
```

---

## 🔧 Dépannage

### Erreur "API Key invalid"
- Vérifiez que vous êtes bien en **mode Demo**
- Vérifiez que les clés sont des **Demo API Keys** (pas production)
- Vérifiez le passphrase

### Erreur "Insufficient balance"
- Connectez-vous sur Bitget mode demo
- Vérifiez que vous avez des fonds virtuels (50k USDT)
- Si besoin, contactez le support Bitget pour réinitialiser

### Erreur "Exchange environment is incorrect"
- C'est un bug connu de ccxt avec Bitget
- Solution : Utiliser la dernière version de ccxt (`pip install --upgrade ccxt`)

### Le bot ne détecte pas de crash
- Normal ! Attendez qu'un vrai crash se produise
- Ou modifiez `CRASH_THRESHOLD` à `-0.5%` pour tester plus facilement

---

## 📊 Exemple de session de trading

```
🚀 BITGET TESTNET TRADING BOT - STRATÉGIE CRASH BUYING
💬 Telegram: ✅
🔑 API Bitget: ✅
📡 Connexion à Bitget Testnet...
💰 Balance USDT: $50,000.00

✅ Bot démarré - Surveillance active...
🔍 En attente d'un crash pour entrer en position...

🔍 EN ATTENTE | Prix: $2,500.00 | Historique: 60s | Ordres: 0
🔍 EN ATTENTE | Prix: $2,498.50 | Historique: 120s | Ordres: 0
🔍 EN ATTENTE | Prix: $2,485.00 | Historique: 180s | Ordres: 0

================================================================================
🔴 CRASH DÉTECTÉ - EXÉCUTION STRATÉGIE
================================================================================
✅ Ordre buy exécuté: 0.01 ETH @ $2,450.00

📊 Configuration de la grille de trading...
📝 Ordre limite buy placé: 0.01 ETH @ $2,425.50
📝 Ordre limite buy placé: 0.01 ETH @ $2,401.00
📝 Ordre limite buy placé: 0.01 ETH @ $2,376.50
📝 Ordre limite buy placé: 0.01 ETH @ $2,352.00
📝 Ordre limite buy placé: 0.01 ETH @ $2,327.50
✅ Grille configurée: 5 ordres placés

📊 GRILLE ACTIVE | Prix: $2,455.00 | Historique: 240s | Ordres: 1
✅ Niveau 1 atteint: $2,425.50
📊 GRILLE ACTIVE | Prix: $2,420.00 | Historique: 300s | Ordres: 2

💰 TAKE PROFIT ATTEINT - FERMETURE POSITIONS
✅ Ordre sell exécuté: 0.02 ETH @ $2,499.00
🗑️  Tous les ordres annulés
🔄 Stratégie réinitialisée - En attente du prochain crash
```

---

## 📚 Ressources

- [Documentation API Bitget](https://www.bitget.com/api-doc/contract/intro)
- [Guide Demo Trading Bitget](https://www.bitget.com/support/articles/12560603790031)
- [Documentation CCXT](https://docs.ccxt.com/)
- [Stratégie Grid Trading](https://www.investopedia.com/terms/g/grid-trading.asp)

---

## ⚠️ Avertissements

- ✅ Mode DEMO = **Fonds virtuels** (aucun risque réel)
- ⚠️ Testez TOUJOURS en demo avant de passer en production
- 📊 Les résultats en demo peuvent différer de la production
- 💰 Ne tradez JAMAIS avec de l'argent que vous ne pouvez pas perdre
- 📖 Continuez à apprendre et à améliorer votre stratégie

---

## 🎯 Prochaines étapes

Une fois la stratégie testée et validée sur le testnet :

1. ✅ Analyser les performances (profit/loss, taux de réussite)
2. ✅ Ajuster les paramètres si nécessaire
3. ✅ Tester sur différentes conditions de marché
4. ✅ Documenter les résultats
5. ⚠️ Si satisfait → Passer en production avec **petites sommes** d'abord
