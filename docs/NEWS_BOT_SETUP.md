# Configuration du Bot Telegram News

Ce guide explique comment configurer le bot Telegram qui envoie automatiquement les dernières actualités (finance, trading, politique) toutes les 5 minutes.

## 📋 Prérequis

### 1. Créer un Bot Telegram

1. Ouvrez Telegram et cherchez **@BotFather**
2. Envoyez `/newbot`
3. Suivez les instructions pour choisir un nom et un username
4. **Copiez le token** fourni (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Obtenir votre Chat ID

**Option A - Via @userinfobot:**
1. Cherchez **@userinfobot** sur Telegram
2. Démarrez une conversation
3. Il vous donnera votre Chat ID

**Option B - Via votre bot:**
1. Démarrez une conversation avec votre nouveau bot
2. Envoyez n'importe quel message
3. Visitez: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Cherchez `"chat":{"id":123456789}` dans la réponse

### 3. Obtenir une clé API Finnhub (Gratuit)

1. Allez sur **https://finnhub.io/**
2. Cliquez "Get free API key"
3. Créez un compte (gratuit)
4. Copiez votre API key

**Plan gratuit:** 60 appels/minute, parfait pour ce bot

### 4. Obtenir une clé API Marketaux (Optionnel)

1. Allez sur **https://www.marketaux.com/**
2. Créez un compte gratuit
3. Copiez votre API token

**Plan gratuit:** 100% gratuit, pas besoin de carte bancaire

### 5. Clé API Anthropic

Vous avez déjà votre clé API Claude: `sk-ant-api03-kzcDP9hQ...`

## ⚙️ Configuration

### 1. Modifier le fichier `.env`

Éditez `/Users/nicolas/Documents/Mes Projects/trading/.env` et ajoutez:

```bash
# Configuration Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Claude API
ANTHROPIC_API_KEY=sk-ant-api03-votre-clé-ici

# News APIs
FINNHUB_API_KEY=votre-clé-finnhub
MARKETAUX_API_KEY=votre-clé-marketaux  # Optionnel
```

### 2. Installer les dépendances

```bash
cd "/Users/nicolas/Documents/Mes Projects/trading"
pip install -r requirements.txt
```

## 🚀 Lancement

### Lancer le bot localement

```bash
python bot/news_bot.py
```

Le bot va:
- ✅ Récupérer les dernières news toutes les 5 minutes
- ✅ Les analyser avec Claude API
- ✅ Envoyer un résumé sur votre Telegram

### Déployer sur Railway

1. **Créer un nouveau service sur Railway**
   - Connectez votre repo GitHub
   - Sélectionnez le projet `trading`

2. **Configurer les variables d'environnement**
   Ajoutez dans Railway:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
   - `FINNHUB_API_KEY`
   - `MARKETAUX_API_KEY` (optionnel)

3. **Modifier le Procfile**

   Créez ou modifiez le fichier pour lancer le news bot:
   ```
   worker: python bot/news_bot.py
   ```

4. **Déployer**
   - Railway déploiera automatiquement
   - Le bot tournera 24/7 et enverra des news toutes les 5 minutes

## 📊 Fonctionnalités

- **Sources multiples**: Finnhub (finance/trading) + Marketaux (politique/économie)
- **Analyse IA**: Claude résume et met en avant les points importants
- **Temps réel**: News fraîches, pas de délai de 24h
- **Automatique**: Envoie toutes les 5 minutes sans intervention
- **Émojis**: Messages formatés avec émojis pour meilleure lisibilité

## 🔧 Personnalisation

### Modifier la fréquence d'envoi

Dans `bot/news_bot.py`, ligne 148:
```python
time.sleep(300)  # 300 = 5 minutes
```

Changez `300` par:
- `60` = 1 minute
- `600` = 10 minutes
- `1800` = 30 minutes

### Modifier le format du résumé

Dans `bot/news_bot.py`, ligne 71-82, modifiez le prompt Claude pour ajuster le style et le contenu.

## 🐛 Dépannage

**Le bot ne démarre pas:**
- Vérifiez que toutes les variables d'environnement sont définies
- Installez les dépendances: `pip install -r requirements.txt`

**Pas de messages reçus:**
- Vérifiez que vous avez démarré une conversation avec votre bot sur Telegram
- Vérifiez le `TELEGRAM_CHAT_ID` (c'est VOTRE ID, pas celui du bot)

**Erreur API:**
- Vérifiez que vos clés API sont valides
- Vérifiez les limites de votre plan gratuit

## 📝 Notes

- Le bot utilise les crédits API Claude (même abonnement que Claude Code)
- Les APIs de news (Finnhub/Marketaux) sont 100% gratuites
- Sur Railway, le bot tourne en continu (worker)
