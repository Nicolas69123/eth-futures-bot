# Stratégie 1 : Crash Buying avec Grid Trading

## Objectif
Profiter des mouvements de baisse brutaux sur des paires à faible volatilité pour ouvrir des positions d'achat avec une stratégie de grid trading (DCA - Dollar Cost Averaging).

## Paires cibles
- Cryptos à **faible volatilité** mais avec **volume élevé**
- Exemples : ETH, SOL, etc.
- Éviter les paires "mortes" avec très faible volume

## Principe de la stratégie

### 1. Détection du crash
- **Déclencheur** : Baisse significative du prix (ex: -2%) sur une période courte (5-15 minutes)
- La rapidité de la baisse est importante : peut être 30 secondes comme 15 minutes
- L'objectif est de repérer un mouvement de baisse brutal

### 2. Ouverture de position
- **Première entrée** : Achat automatique au moment de la détection du crash (-2%)
- Positionnement au "bottom" de la baisse initiale

### 3. Grid Trading (si la baisse continue)
- Si le prix continue de descendre après la première entrée
- **Rajouter des positions** à des paliers prédéfinis
- Exemple de grille :
  - Entrée 1 : -2% (crash initial)
  - Entrée 2 : -4% (si continue)
  - Entrée 3 : -6% (si continue)
  - etc.

### 4. Sortie
- **Take Profit** : Vendre lorsque le prix remonte (à définir : +1.5% ? +2% ?)
- **Stop Loss** : Limite de perte si crash majeur continue (à définir)

## Paramètres à configurer

### Déclencheur
- **Pourcentage de baisse** : -2%
- **Durée maximale** : 15 minutes (à affiner : 5min ? 10min ?)
- **Durée minimale** : 30 secondes (pour éviter faux signaux)

### Grid Trading
- **Espacement des niveaux** : Tous les -1% ou -2% ?
- **Nombre max d'ordres** : 3 ? 5 ? 10 ?
- **Montant par ordre** : Fixe ou progressif ?

### Gestion du risque
- **Budget maximum** : Montant total alloué à la stratégie
- **Take Profit** : % de gain visé (à définir)
- **Stop Loss** : % de perte maximale acceptée (à définir)

## Avantages
- ✅ Profite des sur-réactions du marché (panic selling)
- ✅ Moyenne le prix d'achat si baisse continue (DCA)
- ✅ Paires à faible volatilité = mouvements plus prévisibles
- ✅ Automatisation possible

## Risques
- ⚠️ Crash majeur qui continue (besoin de stop loss)
- ⚠️ Capitaux immobilisés si baisse prolongée
- ⚠️ Faux signaux sur mouvements normaux
- ⚠️ Nécessite liquidité suffisante pour la grille

## Améliorations futures possibles
- Intégration de news/événements pour filtrer
- Analyse du volume lors du crash
- Ajustement dynamique des paliers selon volatilité
- Backtesting sur données historiques
