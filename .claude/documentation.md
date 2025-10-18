# 📚 Documentation - Trading Bot

> **Dernière mise à jour** : 2025-10-18

---

## 🎯 Principe

Ce fichier contient **toute la documentation technique** nécessaire pour travailler sur le projet.
Claude doit **TOUJOURS se référer à ces docs** au lieu de ses connaissances générales.

---

## 📡 BITGET API - Documentation Officielle

### **Base URL**
```
https://api.bitget.com
```

### **Authentication**

**Type** : HMAC-SHA256

**Headers requis** :
```
ACCESS-KEY: [Votre API key]
ACCESS-SIGN: [Signature HMAC]
ACCESS-TIMESTAMP: [Unix timestamp ms]
ACCESS-PASSPHRASE: [Votre passphrase]
```

**Génération signature** :
```python
import hmac
import base64
from datetime import datetime

timestamp = str(int(datetime.now().timestamp() * 1000))
message = timestamp + 'GET' + '/api/mix/v1/market/ticker?symbol=ETHUSDT_UMCBL'
signature = base64.b64encode(
    hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        digestmod='sha256'
    ).digest()
).decode()
```

---

### **Endpoints Utilisés**

#### **1. Ticker Price (Market Data)**

**Endpoint** : `GET /api/mix/v1/market/ticker`

**Params** :
- `symbol` : ETHUSDT_UMCBL (ETH Futures USDT)

**Response** :
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "symbol": "ETHUSDT_UMCBL",
    "last": "2500.5",
    "bestAsk": "2500.6",
    "bestBid": "2500.4",
    "high24h": "2550.0",
    "low24h": "2450.0"
  }
}
```

**Rate Limit** : 20 requests/2s

---

#### **2. Place Order**

**Endpoint** : `POST /api/mix/v1/order/placeOrder`

**Body** :
```json
{
  "symbol": "ETHUSDT_UMCBL",
  "marginCoin": "USDT",
  "side": "open_long",  // ou "open_short"
  "orderType": "limit",
  "price": "2500.5",
  "size": "0.1",
  "timeinForceValue": "normal"
}
```

**Response** :
```json
{
  "code": "00000",
  "msg": "success",
  "data": {
    "orderId": "123456789",
    "clientOid": "custom_id"
  }
}
```

**Rate Limit** : 10 orders/s

---

#### **3. Get Positions**

**Endpoint** : `GET /api/mix/v1/position/allPosition`

**Params** :
- `productType` : umcbl (USDT futures)
- `marginCoin` : USDT

**Response** :
```json
{
  "code": "00000",
  "data": [
    {
      "symbol": "ETHUSDT_UMCBL",
      "holdSide": "long",
      "openPriceAvg": "2500.0",
      "leverage": 10,
      "available": "0.1",
      "total": "0.1",
      "upl": "5.5",  // Unrealized P&L
      "uplRatio": "0.022"
    }
  ]
}
```

---

### **Error Codes Bitget**

| Code | Signification | Action |
|------|---------------|--------|
| 00000 | Success | ✅ Continue |
| 40001 | Invalid request | Vérifier params |
| 40002 | Invalid API key | Vérifier .env |
| 40006 | Rate limit exceeded | **Retry avec backoff** |
| 40014 | Invalid timestamp | Sync time serveur |
| 43025 | Insufficient balance | Vérifier capital |

**⚠️ IMPORTANT** : Toujours gérer error code 40006 (rate limit) !

---

### **Rate Limits**

**Limites par endpoint** :
- Market data : 20 req/2s
- Order placement : 10 req/s
- Position queries : 20 req/2s

**Stratégie** :
```python
import time

def call_api_with_retry(endpoint, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = api.call(endpoint)
            if response['code'] == '40006':  # Rate limit
                wait_time = 2 ** attempt  # Backoff exponentiel
                time.sleep(wait_time)
                continue
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

---

### **Symboles Bitget**

**Format** : `{BASE}{QUOTE}_{PRODUCT_TYPE}`

**Exemples** :
- `ETHUSDT_UMCBL` : ETH Futures USDT (perpetual)
- `BTCUSDT_UMCBL` : BTC Futures USDT
- `SOLUSDT_UMCBL` : SOL Futures USDT

**Product Types** :
- `UMCBL` : USDT-based perpetual futures
- `DMCBL` : Coin-based perpetual futures
- `CMCBL` : USDT-based delivery futures

---

## 🤖 TELEGRAM BOT API - Documentation

### **Base URL**
```
https://api.telegram.org/bot{TOKEN}/
```

### **Send Message**

**Endpoint** : `POST /sendMessage`

**Params** :
```json
{
  "chat_id": "123456789",
  "text": "🚀 Trade executed: LONG ETH @$2500",
  "parse_mode": "Markdown"  // ou "HTML"
}
```

**Exemple** :
```python
import requests

def send_telegram_notification(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=data)
    return response.json()
```

---

## 📊 CALCUL FIBONACCI - Référence Technique

### **Niveaux Fibonacci**

**Support (retracement)** :
- 0.236 (23.6%)
- 0.382 (38.2%)
- 0.500 (50.0%)
- **0.618 (61.8%)** ← Niveau d'or (golden ratio)
- 0.786 (78.6%)

**Résistance (extension)** :
- 1.272 (127.2%)
- 1.414 (141.4%)
- **1.618 (161.8%)** ← Extension d'or
- 2.618 (261.8%)

### **Formule de Calcul**

```python
def calculate_fibonacci_levels(high, low):
    """
    Calcule les niveaux de Fibonacci entre un high et un low

    Args:
        high (float): Prix le plus haut de la période
        low (float): Prix le plus bas de la période

    Returns:
        dict: Niveaux Fibonacci calculés
    """
    diff = high - low

    levels = {
        # Retracements (support)
        'fib_0.236': high - (diff * 0.236),
        'fib_0.382': high - (diff * 0.382),
        'fib_0.500': high - (diff * 0.500),
        'fib_0.618': high - (diff * 0.618),  # Golden ratio
        'fib_0.786': high - (diff * 0.786),

        # Extensions (résistance)
        'fib_1.272': high + (diff * 0.272),
        'fib_1.618': high + (diff * 0.618),  # Extension d'or
        'fib_2.618': high + (diff * 1.618),
    }

    return levels
```

### **Stratégie Hedge**

**Principe** :
1. **Identifier trend** (uptrend/downtrend/range)
2. **Calculer Fibonacci** sur dernières 24h-48h
3. **Entry LONG** : Niveau 0.618 (support fort)
4. **Entry SHORT** : Niveau 0.382 (résistance)
5. **TP LONG** : Niveau 1.618 (extension)
6. **TP SHORT** : Niveau 0.236 (retracement)
7. **SL** : 2% du prix d'entrée

**Hedge = Long + Short simultané** :
- Profit si volatilité (oscillation)
- Risque limité (positions opposées)
- Fonctionne en range market

---

## 🐍 PYTHON - Libraries Utilisées

### **ccxt (Version 4.x)**

**Installation** :
```bash
pip install ccxt
```

**Bitget avec ccxt** :
```python
import ccxt

exchange = ccxt.bitget({
    'apiKey': API_KEY,
    'secret': SECRET_KEY,
    'password': PASSPHRASE,
})

# Fetch ticker
ticker = exchange.fetch_ticker('ETH/USDT:USDT')

# Place order
order = exchange.create_limit_buy_order(
    symbol='ETH/USDT:USDT',
    amount=0.1,
    price=2500
)
```

**⚠️ IMPORTANT** : Bitget nécessite `password` (passphrase) en plus de API key/secret

---

### **python-telegram-bot**

**Installation** :
```bash
pip install python-telegram-bot
```

**Usage** :
```python
from telegram import Bot

bot = Bot(token=TELEGRAM_TOKEN)
bot.send_message(
    chat_id=CHAT_ID,
    text="🚀 Trade executed"
)
```

---

## 📖 Ressources Officielles

### **Bitget API**

**Documentation officielle** :
- URL : https://bitgetlimited.github.io/apidoc/en/mix/
- Version : v1 (current)
- Dernière update connue : 2024

**Sections importantes** :
- Authentication : https://bitgetlimited.github.io/apidoc/en/mix/#authentication
- Market Data : https://bitgetlimited.github.io/apidoc/en/mix/#get-single-symbol-ticker
- Orders : https://bitgetlimited.github.io/apidoc/en/mix/#place-order

### **Telegram Bot API**

**Documentation officielle** :
- URL : https://core.telegram.org/bots/api
- Toujours à jour

---

## 🛠️ GNU Screen - Référence

**Commandes essentielles** :

```bash
# Créer session
screen -dmS nom-session commande

# Lister sessions
screen -ls

# Attacher session
screen -r nom-session

# Détacher (dans screen)
Ctrl+A puis D

# Tuer session
screen -X -S nom-session quit
```

---

## 📝 Notes de Version

**Bitget API** :
- Version actuelle : v1
- Endpoint base : /api/mix/v1/
- Dernière vérification : 2025-10-18

**CCXT** :
- Version utilisée : 4.x
- Support Bitget : ✅ Complet

**Python** :
- Version : 3.11+
- Requirements : Voir requirements.txt

---

## 🔄 Mise à Jour Documentation

**Quand mettre à jour ce fichier ?**

- ✅ Nouvelle version API Bitget
- ✅ Changement endpoints
- ✅ Nouveaux rate limits
- ✅ Nouvelles features utilisées
- ✅ Bugs découverts dans API

**Comment vérifier ?**
- Consulter changelog Bitget API
- Tester endpoints en cas de doute
- Vérifier doc officielle régulièrement

---

## ⚠️ ERREURS FRÉQUENTES À ÉVITER

### **Bitget**

❌ **Oublier le passphrase** (3ème clé requise)
❌ **Timestamp incorrect** (> 30s de différence = rejeté)
❌ **Symbol format** (doit être ETHUSDT_UMCBL, pas ETH-USDT)
❌ **Rate limit** (ne pas gérer le code 40006)

### **Stratégie**

❌ **Fibonacci sur timeframe trop court** (< 15min = bruit)
❌ **Hedge sans SL** (risque illimité si trend fort)
❌ **Positions trop grosses** (> 10% capital par trade)

---

## 💡 Quick Reference

**⚡ Pour Claude : Toujours vérifier cette doc avant de coder !**

**Endpoints principaux** :
```
GET  /api/mix/v1/market/ticker        → Prix
POST /api/mix/v1/order/placeOrder     → Ordre
GET  /api/mix/v1/position/allPosition → Positions
```

**Calcul Fibonacci** :
```python
levels = calculate_fibonacci_levels(high=2550, low=2450)
# Returns: {fib_0.618: 2488.2, ...}
```

**Send Telegram** :
```python
send_telegram_notification("🚀 Trade: LONG ETH @$2500")
```

---

**📌 Cette documentation est la SOURCE DE VÉRITÉ pour le projet.**
**Claude doit se référer ICI, pas à ses connaissances générales.**
