# 🤖 Trading Bot - Claude Configuration

## 🎯 Vue d'ensemble rapide

Bot trading automatisé ETH Futures sur Bitget avec stratégie hedge Fibonacci.
Déployé 24/7 sur Oracle Cloud (Marseille), notifications Telegram temps réel.

**Status actuel** : ✅ Production active
**Dernière session** : 2025-10-18

---

## 📚 Documentation Complète

@.claude/context.md           # Contexte détaillé du projet
@.claude/architecture.md      # Structure technique & APIs
@.claude/progress.md          # 🔥 Avancement & dernières actions
@.claude/changelog.md         # Historique complet des versions

---

## ⚡ Quick Start

### Gestion Locale (MacOS)

**Scripts disponibles** (dans `~/Tools/Scripts/`) :
```bash
# Double-clic sur :
🚀 Update Trading Bot.command      # Deploy sur Oracle
📊 Check Bot Status.command        # Vérifier status
⏹️ Stop Trading Bot.command         # Arrêter bot
📜 View Bot Logs.command            # Logs temps réel
```

### Accès SSH Oracle Cloud

```bash
ssh -i ~/.ssh/ssh-key-2025-10-12.key ubuntu@130.110.243.130
cd eth-futures-bot
screen -r trading  # Attacher session bot
```

---

## 🚨 Règles Critiques

- ❌ **NE JAMAIS** commit `.env` (contient API keys Bitget + Telegram)
- ⚠️ **TOUJOURS** tester localement avant deploy
- ✅ **VÉRIFIER** que bot tourne après update (Telegram notification)
- ✅ **BACKUP** logs avant rotation
- 🔒 **SSH key permissions** : 600 (déjà configuré)

---

## 📦 Fichiers Importants

| Fichier | Description |
|---------|-------------|
| `bot/bitget_hedge_fibonacci_v2.py` | 🎯 Script principal bot |
| `.env` | ⚠️ Secrets API (JAMAIS commit) |
| `.env.example` | Template configuration |
| `requirements.txt` | Dépendances Python |
| `logs/` | Logs d'exécution |
| `.claude/progress.md` | 📍 **Lire pour savoir où on en est** |

---

## 🎓 Conventions de Code

@/Users/nicolas/Documents/Notes/python-conventions.md

**Spécifiques trading bot** :
- Logging verbeux pour chaque trade
- Gestion exceptions API (timeout, rate limit)
- Validation données market avant trade
- Tests avec petits montants d'abord

---

## 💡 Aide Rapide

**Contexte projet** : `.claude/context.md`
**Architecture détaillée** : `.claude/architecture.md`
**Où on en est** : `.claude/progress.md` 👈 **LIRE EN PRIORITÉ**
**Historique** : `.claude/changelog.md`

**Serveur Oracle** : 130.110.243.130
**Process** : Screen session `trading`

---

## 🚀 Commandes Courantes

```bash
# Lancer bot (Oracle)
screen -dmS trading python3 bot/bitget_hedge_fibonacci_v2.py

# Vérifier status
screen -ls | grep trading

# Voir logs temps réel
screen -r trading  # Puis Ctrl+A puis D pour détacher

# Arrêter bot
screen -X -S trading quit
```

---

**🔗 Pour détails complets** : Voir fichiers `.claude/` ou demander à Claude !
