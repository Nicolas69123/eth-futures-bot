# Changelog - Trading Bot

Toutes les modifications notables du projet sont documentées ici.

Format basé sur [Keep a Changelog](https://keepachangelog.com/)

---

## [Unreleased]

### À venir
- Backtesting système sur données historiques
- Dashboard analytics web
- Indicateurs supplémentaires (RSI, MACD)
- Auto-ajustement paramètres

---

## [1.0.1] - 2025-10-18

### Changed
- **Restructuration projet** : Migration vers ~/Dev/Trading/TelegramBot/
- **CLAUDE.md modulaire** : Split en fichiers .claude/ séparés
- **Scripts optimisés** : Correction chemins SSH
- **Environnement** : Nettoyage et sécurisation (clés SSH)

### Added
- `.claude/context.md` - Contexte projet détaillé
- `.claude/architecture.md` - Documentation technique
- `.claude/progress.md` - Suivi avancement
- `.claude/changelog.md` - Ce fichier

### Security
- Clés SSH déplacées ~/Downloads → ~/.ssh/ avec permissions 600
- Vérification .gitignore pour .env

---

## [1.0.0] - 2025-10-12

### Added
- **Release initiale en production**
- Bot trading automatisé ETH Futures sur Bitget
- Stratégie hedge avec niveaux Fibonacci
- Déploiement Oracle Cloud 24/7 (Marseille)
- Notifications Telegram temps réel
- Scripts de gestion `.command` :
  - 🚀 Update Trading Bot
  - 📊 Check Bot Status
  - ⏹️ Stop Trading Bot
  - 📜 View Bot Logs

### Technical
- Python 3.11
- GNU Screen pour process management
- Bitget API integration
- Telegram Bot API
- SSH access sécurisé

---

## [0.3.0] - 2025-10-09

### Added
- Implémentation stratégie Fibonacci complète
- Calcul dynamique niveaux support/résistance
- Logic hedge (long + short simultané)
- Gestion automatique TP/SL

### Fixed
- Problèmes de connexion API Bitget (timeout)
- Calcul incorrect Fibonacci sur certains timeframes

---

## [0.2.0] - 2025-10-05

### Added
- Integration Bitget API (REST)
- Authentication HMAC-SHA256
- Endpoints : ticker, placeOrder, allPosition
- Tests locaux sur testnet

### Changed
- Migration de Binance vers Bitget
→ Raison : Meilleurs spreads ETH Futures

---

## [0.1.0] - 2025-10-01

### Added
- Setup projet initial
- Structure dossiers
- Configuration environnement
- Tests connexion Telegram Bot
- Documentation initiale

---

## Architecture des Versions

**Format** : MAJOR.MINOR.PATCH

- **MAJOR** : Changements majeurs architecture/stratégie
- **MINOR** : Nouvelles features
- **PATCH** : Bug fixes, optimisations mineures

---

## Notes Techniques

### Performance Optimization
- **2025-10-12** : Passage à screen session (vs PM2) → -50% RAM
- **2025-10-09** : Optimisation calculs Fibonacci → -30% CPU

### Security Updates
- **2025-10-18** : Migration SSH keys, permissions 600
- **2025-10-12** : Validation .env non-commit (.gitignore)

### Infrastructure
- **2025-10-12** : Déploiement Oracle Cloud free tier (stable)
- **2025-10-01** : Tests locaux MacOS (dev)

---

## Decisions Log

### Choix Technologiques

**Python vs JavaScript** → Python
- Raison : Meilleures libs pour calculs numériques (NumPy)
- Ecosystem trading plus mature

**Exchange Bitget vs Binance** → Bitget
- Raison : Spreads plus serrés, API plus stable

**Cloud Oracle vs AWS** → Oracle
- Raison : Free tier permanent (vs 12 mois AWS)

**Process Manager Screen vs PM2** → Screen
- Raison : Plus léger, moins dépendances, suffisant pour 1 process

---

## Métriques Historiques

*À compléter avec données réelles*

| Date | Trades | Win Rate | Profit | Notes |
|------|--------|----------|--------|-------|
| 2025-10-18 | - | - | - | Restructuration |
| 2025-10-12 | ~15 | ~65% | +$X | Deploy prod |
| 2025-10-09 | 8 | 62.5% | +$X | Tests strategy |

---

## Roadmap Future

### V1.1 (Q4 2025)
- [ ] Backtesting historique complet
- [ ] Dashboard analytics web
- [ ] Métriques avancées (Sharpe, Sortino)
- [ ] Multi-timeframe analysis

### V1.2 (Q1 2026)
- [ ] Indicateurs supplémentaires (RSI, MACD, Bollinger)
- [ ] Auto-ajustement paramètres (ML)
- [ ] Multi-pairs trading (BTC, SOL)
- [ ] API webhooks (TradingView integration)

### V2.0 (Future)
- [ ] Stratégies multiples (Grid, DCA, Arbitrage)
- [ ] Portfolio management
- [ ] Risk management avancé
- [ ] Mobile app monitoring
