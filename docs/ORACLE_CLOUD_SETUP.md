# 🚀 Déployer le Bot sur Oracle Cloud (Gratuit à vie)

Guide complet pour faire tourner le bot de trading 24/7 sur Oracle Cloud **gratuitement**.

---

## 📋 Prérequis

- Compte email
- Les clés API Bitget (testnet ou production)
- Token Telegram bot + Chat ID

---

## 1️⃣ Créer un Compte Oracle Cloud (5 min)

### Étapes :

1. **Aller sur** : https://oracle.com/cloud/free
2. **Cliquer** : "Start for free"
3. **Remplir** : Email, mot de passe, région (choisir Europe)
4. **Vérification** : Email + téléphone
5. **Carte bancaire** : Demandée mais **jamais facturée** sur le tier gratuit

⚠️ Oracle ne facture **JAMAIS** si tu restes sur les ressources "Always Free"

---

## 2️⃣ Créer une VM Gratuite (5 min)

### Étapes dans Oracle Cloud Console :

1. **Menu** (☰) → **Compute** → **Instances**

2. **Cliquer** : "Create Instance"

3. **Configuration** :

   | Paramètre | Valeur |
   |-----------|--------|
   | **Name** | `trading-bot` |
   | **Availability Domain** | Laisser par défaut |
   | **Image** | Ubuntu 22.04 (Latest) |
   | **Shape** | **VM.Standard.A1.Flex** (ARM - GRATUIT ✅) |
   | **OCPUs** | 1 (ou 2 si disponible) |
   | **Memory** | 6 GB (max gratuit) |
   | **Network** | Laisser par défaut (VCN créé automatiquement) |

4. **SSH Keys** :
   - ✅ Cocher "Generate SSH key pair"
   - ✅ **Télécharger** la clé privée (`ssh-key-*.key`)
   - ⚠️ **IMPORTANT** : Sauvegarder ce fichier !

5. **Cliquer** : "Create"

6. **Attendre** : 1-2 minutes (status : Running ✅)

7. **Noter l'IP publique** : Ex: `123.45.67.89`

---

## 3️⃣ Configurer les Règles Firewall (2 min)

Par défaut, Oracle bloque presque tout. On ouvre juste SSH :

1. Sur la page de ton instance → **Subnet** (cliquer le lien)
2. **Security Lists** → Cliquer sur la liste par défaut
3. **Ingress Rules** → **Add Ingress Rule**
   - Source CIDR : `0.0.0.0/0`
   - Destination Port : `22`
   - Description : `SSH`
4. **Save**

---

## 4️⃣ Se Connecter en SSH (1 min)

### Depuis ton Mac :

```bash
# Donner les permissions à la clé SSH
chmod 400 ~/Downloads/ssh-key-*.key

# Se connecter (remplace <IP> par ton IP publique)
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<IP>

# Exemple :
# ssh -i ~/Downloads/ssh-key-2025-10-09.key ubuntu@123.45.67.89
```

✅ Tu es maintenant connecté au serveur !

---

## 5️⃣ Installer les Dépendances (3 min)

### Sur le serveur Oracle :

```bash
# Mettre à jour le système
sudo apt update && sudo apt upgrade -y

# Installer Python, pip, git, screen
sudo apt install -y python3-pip git screen

# Vérifier Python
python3 --version  # Devrait afficher Python 3.10+
```

---

## 6️⃣ Installer le Bot (2 min)

```bash
# Cloner le repo
git clone https://github.com/Nicolas69123/eth-futures-bot.git
cd eth-futures-bot

# Installer les dépendances Python
pip3 install -r requirements.txt
```

---

## 7️⃣ Configurer les Variables d'Environnement (2 min)

```bash
# Créer le fichier .env
nano .env
```

### Copier-coller (avec TES valeurs) :

```bash
# Bitget API (Testnet ou Production)
BITGET_API_KEY=your_api_key_here
BITGET_SECRET=your_secret_here
BITGET_PASSPHRASE=your_passphrase_here

# Telegram
TELEGRAM_BOT_TOKEN=ton_token_ici
TELEGRAM_CHAT_ID=ton_chat_id_ici
```

**Sauvegarder** :
- `Ctrl + O` (save)
- `Enter`
- `Ctrl + X` (exit)

---

## 8️⃣ Tester le Bot (1 min)

```bash
# Lancer en mode test
python3 bot/bitget_hedge_fibonacci_v2.py
```

✅ Tu devrais voir :
```
🔑 API Key chargée: ✅ (longueur: 36)
🚀 BITGET HEDGE BOT V2 - ORDRES LIMITES AUTO
📡 Connexion Bitget Testnet...
🎯 OUVERTURE HEDGE: DOGE/USDT:USDT
```

✅ **Sur Telegram** : Message de démarrage

**Stopper** : `Ctrl + C`

---

## 9️⃣ Lancer en Background 24/7 (1 min)

### Utiliser `screen` pour que le bot continue même si tu te déconnectes :

```bash
# Créer une session screen
screen -S trading

# Lancer le bot
python3 bot/bitget_hedge_fibonacci_v2.py

# Détacher (bot continue en background)
# Appuyer : Ctrl+A puis D
```

✅ **Le bot tourne maintenant 24/7 !**

### Commandes utiles :

```bash
# Voir les sessions screen actives
screen -ls

# Revenir à la session (voir les logs)
screen -r trading

# Détacher à nouveau
Ctrl+A puis D

# Tuer la session (arrêter le bot)
screen -X -S trading quit
```

---

## 🔟 Mettre à Jour le Bot (quand tu push sur GitHub)

```bash
# Se connecter au serveur
ssh -i ~/Downloads/ssh-key-*.key ubuntu@<IP>

cd eth-futures-bot

# Arrêter le bot
screen -X -S trading quit

# Mettre à jour depuis GitHub
git pull

# Relancer
screen -S trading
python3 bot/bitget_hedge_fibonacci_v2.py
Ctrl+A puis D
```

---

## 📊 Monitoring

### Vérifier que le bot tourne :

```bash
# Voir les processus Python
ps aux | grep bitget

# Voir les sessions screen
screen -ls

# Revenir aux logs
screen -r trading
```

### Sur Telegram :

- Messages automatiques **toutes les minutes**
- Commandes :
  - `/pnl` - Voir le P&L
  - `/positions` - Positions actives
  - `/balance` - Balance disponible
  - `/history` - Historique trades

---

## ⚠️ Important

### Sécurité de la Clé SSH :

```bash
# Sauvegarder la clé dans un endroit sûr
mkdir -p ~/.ssh
mv ~/Downloads/ssh-key-*.key ~/.ssh/oracle-trading.key
chmod 400 ~/.ssh/oracle-trading.key

# Connexion simplifiée
ssh -i ~/.ssh/oracle-trading.key ubuntu@<IP>
```

### Créer un alias (optionnel) :

```bash
# Sur ton Mac
echo "alias oracle-bot='ssh -i ~/.ssh/oracle-trading.key ubuntu@<IP>'" >> ~/.zshrc
source ~/.zshrc

# Maintenant tu peux juste taper :
oracle-bot
```

---

## 🆘 Dépannage

### Le bot ne démarre pas :

```bash
# Vérifier les logs d'erreur
cd eth-futures-bot
python3 bot/bitget_hedge_fibonacci_v2.py

# Vérifier le .env
cat .env

# Vérifier les dépendances
pip3 install -r requirements.txt --upgrade
```

### Connexion SSH refuse :

```bash
# Vérifier que les permissions sont bonnes
chmod 400 ~/.ssh/oracle-trading.key

# Vérifier le firewall Oracle Cloud (règle port 22)
```

### Bot arrêté après déconnexion :

→ Tu as oublié d'utiliser `screen` ! Relance avec `screen -S trading`

---

## 💰 Coûts

**GRATUIT À VIE** si tu restes sur :
- ✅ VM.Standard.A1.Flex (ARM)
- ✅ Max 4 OCPUs + 24 GB RAM combinés (largement suffisant)
- ✅ 200 GB de stockage

Oracle **ne facturera jamais** tant que tu utilises ces ressources "Always Free".

---

## 🎉 C'est Tout !

Ton bot tourne maintenant **24/7 gratuitement** sur Oracle Cloud !

**Questions ?** Reviens ici si tu as besoin d'aide pour une étape. 🚀
