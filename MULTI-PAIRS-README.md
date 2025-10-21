# 🚀 Bot Multi-Paires - Guide d'utilisation

## 📊 Vue d'ensemble

Ce système lance **6 instances** du bot simultanément, chacune tradant une paire différente :

1. **DOGE/USDT:USDT**
2. **PEPE/USDT:USDT**
3. **SHIB/USDT:USDT**
4. **ETH/USDT:USDT**
5. **SOL/USDT:USDT**
6. **AVAX/USDT:USDT**

**Total capital initial** : 6 paires × $5 × 2 positions = **$60 USDT**

---

## ⚡ Quick Start

### Local (test)

```bash
# Lancer toutes les instances
python3 bot/launch_multi_pairs.py

# Arrêter : Ctrl+C
```

### Production (Oracle Cloud)

```bash
# SSH sur Oracle
ssh -i ~/.ssh/ssh-key-2025-10-12.key ubuntu@130.110.243.130

# Lancer avec screen
screen -dmS multi_trading python3 bot/launch_multi_pairs.py

# Voir les logs
screen -r multi_trading

# Détacher : Ctrl+A puis D
```

---

## 🧪 Tester une seule paire

```bash
# Test DOGE
python3 bot/bitget_hedge_multi_instance.py --pair DOGE/USDT:USDT

# Test ETH
python3 bot/bitget_hedge_multi_instance.py --pair ETH/USDT:USDT
```

---

## 📊 Monitoring

### Telegram
Chaque instance envoie ses propres notifications avec le nom de la paire.

### Logs
Les logs sont séparés par instance dans `logs/`

### Process
```bash
# Voir les process
ps aux | grep bitget_hedge_multi_instance

# Compter les instances
ps aux | grep bitget_hedge_multi_instance | wc -l
# Devrait afficher 6
```

---

## ⚠️ Important

### Rate Limits Bitget
- 6 paires = **6x plus de requêtes**
- Le bot a `enableRateLimit: True` pour gérer automatiquement
- Si rate limit atteint → Le bot attend automatiquement

### Capital requis
- **Minimum** : $60 USDT (6 paires × $5 × 2 positions)
- **Recommandé** : $100+ USDT (marge de sécurité)

### Performance attendue
- **6 paires volatiles** = plus d'opportunités
- **TP 0.5%** par trade
- **Fibo 0.3%** (doublements)
- Leverage 50x

---

## 🛠️ Troubleshooting

### Une instance crash
```bash
# Identifier quelle paire a crashé
ps aux | grep bitget_hedge_multi_instance

# Relancer manuellement
python3 bot/bitget_hedge_multi_instance.py --pair DOGE/USDT:USDT
```

### Trop de rate limits
→ Réduire le nombre de paires à 3-4

### Capital insuffisant
→ Réduire INITIAL_MARGIN dans le code (ligne 107)

---

## 🔧 Personnalisation

### Changer les paires

Éditer `bot/launch_multi_pairs.py` ligne 14 :

```python
PAIRS = [
    'DOGE/USDT:USDT',
    'BTC/USDT:USDT',  # Changer ici
    # ...
]
```

### Changer les paramètres

Éditer `bot/bitget_hedge_multi_instance.py` lignes 107-118 :

```python
self.INITIAL_MARGIN = 5  # Marge par position
self.TP_PERCENT = 0.5    # Take Profit %
self.FIBO_LEVELS = [0.3, 0.6, 1.0, 1.5, 2.0]
```

---

## 📈 Statistiques attendues

Avec 6 paires volatiles :
- **Trades/jour** : ~50-100 (toutes paires confondues)
- **Capital utilisé** : $60-120 USDT (avec doublements)
- **Profit potentiel** : 0.5% par TP × nombre de TP
- **Risque** : Limité par hedge (positions opposées)

---

## 🚨 RAPPELS

- ✅ **Toujours** tester en local d'abord
- ✅ **Vérifier** que cleanup fonctionne au démarrage
- ✅ **Monitorer** les notifications Telegram
- ❌ **Jamais** modifier pendant que le bot trade
- ❌ **Jamais** commit `.env` (secrets)
