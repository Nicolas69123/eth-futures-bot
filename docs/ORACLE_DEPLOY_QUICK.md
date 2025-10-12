# 🚀 Guide Rapide - Déploiement Oracle Cloud

Guide condensé pour déployer le bot Bitget sur Oracle Cloud (gratuit à vie).

---

## ⚡ Déploiement en 15 minutes

### 1️⃣ Créer Compte Oracle Cloud (5 min)

1. Aller sur : https://oracle.com/cloud/free
2. Créer compte (email + carte bancaire pour vérification, **jamais facturé**)
3. Choisir région : **Europe** (Frankfurt ou Amsterdam)

---

### 2️⃣ Créer VM Gratuite (3 min)

1. Menu ☰ → **Compute** → **Instances** → **Create Instance**
2. Configuration :
   - Name: `trading-bot`
   - Image: **Ubuntu 22.04**
   - Shape: **VM.Standard.A1.Flex (ARM)** ✅ GRATUIT
   - OCPUs: 1-2
   - Memory: 6 GB
   - SSH Keys: **Télécharger la clé privée** (.key) ⚠️ IMPORTANT
3. Créer et noter l'**IP publique**

---

### 3️⃣ Configurer Firewall (1 min)

1. Sur page de l'instance → **Subnet** → **Security Lists** → **Default Security List**
2. **Ingress Rules** → **Add Ingress Rule**
   - Source CIDR: `0.0.0.0/0`
   - Port: `22`
3. Save

---

### 4️⃣ Connexion SSH depuis Mac (1 min)

```bash
# Donner permissions à la clé SSH
chmod 400 ~/Downloads/ssh-key-*.key

# Se connecter (remplacer <IP> par votre IP publique)
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<IP>
```

---

### 5️⃣ Installation sur le Serveur (3 min)

```bash
# 1. Installer dépendances
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip git screen

# 2. Cloner le projet
git clone https://github.com/Nicolas69123/eth-futures-bot.git
cd eth-futures-bot

# 3. Installer packages Python
pip3 install -r requirements.txt

# 4. Configurer les variables d'environnement
nano .env
```

### Copier dans .env (avec vos vraies valeurs) :

```bash
# Bitget API (Testnet)
BITGET_API_KEY=votre_api_key
BITGET_SECRET=votre_secret
BITGET_PASSPHRASE=votre_passphrase

# Telegram
TELEGRAM_BOT_TOKEN=votre_token
TELEGRAM_CHAT_ID=votre_chat_id
```

**Sauvegarder** : `Ctrl+O`, `Enter`, `Ctrl+X`

---

### 6️⃣ Démarrer le Bot 24/7 (2 min)

#### Option A : Script de démarrage automatique (Recommandé)

```bash
# Rendre le script exécutable
chmod +x start_bot.sh

# Créer session screen
screen -S trading

# Lancer avec le script
./start_bot.sh

# Détacher (bot continue en background)
# Appuyer : Ctrl+A puis D
```

#### Option B : Lancement manuel

```bash
# Créer session screen
screen -S trading

# Lancer le bot
python3 bot/bitget_hedge_fibonacci_v2.py

# Détacher
# Appuyer : Ctrl+A puis D
```

✅ **Le bot tourne maintenant 24/7 !**

---

## 🔄 Commandes Utiles

### Gérer la session screen

```bash
# Voir sessions actives
screen -ls

# Revenir à la session (voir les logs)
screen -r trading

# Détacher à nouveau
Ctrl+A puis D

# Arrêter le bot
screen -X -S trading quit
```

### Mettre à jour depuis GitHub

```bash
# 1. Se connecter au serveur
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<IP>

# 2. Aller dans le projet
cd eth-futures-bot

# 3. Arrêter le bot
screen -X -S trading quit

# 4. Récupérer les dernières modifications
git pull

# 5. Redémarrer
screen -S trading
./start_bot.sh
Ctrl+A puis D
```

---

## 📊 Monitoring

### Vérifier que le bot tourne

```bash
# Processus Python actifs
ps aux | grep bitget

# Sessions screen
screen -ls

# Voir les logs en direct
screen -r trading
```

### Logs du bot

Les logs sont automatiquement sauvegardés dans `logs/` (si vous utilisez `start_bot.sh`)

```bash
# Voir les derniers logs
tail -f logs/bot_*.log

# Chercher une erreur
grep "❌" logs/bot_*.log
```

### Sur Telegram

- 📊 Status automatique : **Toutes les 1 minute**
- Commandes disponibles :
  - `/pnl` - P&L total
  - `/positions` - Positions ouvertes
  - `/balance` - Balance disponible
  - `/history` - Historique trades

---

## 🔐 Sécurité

### Protéger la clé SSH

```bash
# Sur votre Mac
mkdir -p ~/.ssh
mv ~/Downloads/ssh-key-*.key ~/.ssh/oracle-trading.key
chmod 400 ~/.ssh/oracle-trading.key

# Créer alias pour connexion rapide
echo "alias oracle-bot='ssh -i ~/.ssh/oracle-trading.key ubuntu@<IP>'" >> ~/.zshrc
source ~/.zshrc

# Maintenant vous pouvez juste taper :
oracle-bot
```

---

## ⚠️ Problèmes Courants

### Le bot ne démarre pas

```bash
# Vérifier les logs
cd eth-futures-bot
python3 bot/bitget_hedge_fibonacci_v2.py

# Vérifier le .env
cat .env

# Réinstaller dépendances
pip3 install -r requirements.txt --upgrade
```

### Connexion SSH refusée

```bash
# Vérifier permissions clé
chmod 400 ~/.ssh/oracle-trading.key

# Vérifier firewall Oracle Cloud (port 22)
```

### Bot arrêté après déconnexion

→ Vous avez oublié `screen` ! Relancez avec `screen -S trading`

---

## 💰 Coûts

**GRATUIT À VIE** avec Oracle Cloud Free Tier :
- ✅ VM.Standard.A1.Flex (ARM)
- ✅ Max 4 OCPUs + 24 GB RAM
- ✅ 200 GB stockage

**Oracle ne facture JAMAIS** si vous restez sur ces ressources "Always Free"

---

## ✅ Checklist Finale

- [ ] Compte Oracle Cloud créé
- [ ] VM Ubuntu créée avec IP publique notée
- [ ] Firewall configuré (port 22)
- [ ] Clé SSH téléchargée et sécurisée
- [ ] Connexion SSH réussie
- [ ] Projet cloné depuis GitHub
- [ ] Dépendances Python installées
- [ ] Fichier `.env` configuré avec vos clés API
- [ ] Bot testé en mode direct
- [ ] Bot lancé en `screen` pour 24/7
- [ ] Telegram reçoit les messages
- [ ] Session `screen` détachée

---

## 🎉 C'est Tout !

Votre bot tourne maintenant **24/7 gratuitement** sur Oracle Cloud !

**Besoin d'aide ?** Consultez le guide complet : `ORACLE_CLOUD_SETUP.md`
