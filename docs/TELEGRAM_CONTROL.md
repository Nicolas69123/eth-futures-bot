# 🤖 Contrôle du Bot via Telegram

Guide pour contrôler votre bot de trading **directement depuis Telegram**, sans ordinateur !

---

## 📱 Renommer votre Bot Telegram

### Sur Telegram, parlez à @BotFather :

1. Envoyez `/mybots`
2. Sélectionnez votre bot (`ETH Trading Alert`)
3. Choisissez **"Edit Bot"**
4. Puis **"Edit Name"**
5. Nouveau nom suggéré : **"Crypto Hedge Control"** ou ce que vous voulez

---

## 🎮 Commandes de Contrôle à Distance

### 📊 Commandes Trading

| Commande | Action |
|----------|--------|
| `/pnl` | Voir le P&L total (réalisé + non réalisé) |
| `/positions` | Afficher les positions ouvertes |
| `/balance` | Balance et capital disponible |
| `/history` | Historique des 10 derniers trades |
| `/status` | État détaillé du système |

---

### 🔐 Commandes Admin (NOUVEAU !)

Tapez `/admin` pour voir les commandes de contrôle.

| Commande | Action | Effet |
|----------|--------|-------|
| `/update` | Met à jour depuis GitHub et redémarre | ✅ Le bot récupère vos dernières modifications |
| `/restart` | Redémarre le bot | ✅ Nettoie et relance proprement |
| `/stop` | Arrête le bot | ⚠️ Demande confirmation avec `/stop CONFIRM` |
| `/status` | État système complet | Mémoire, uptime, version |

---

## 🔄 Workflow Complet Sans Ordinateur

### Exemple : Vous êtes en vacances et voulez modifier le bot

1. **Sur GitHub (depuis téléphone) :**
   - Modifiez le code directement sur github.com
   - Commitez les changements

2. **Sur Telegram :**
   - Envoyez `/update`
   - Le bot :
     - ✅ Fait `git pull`
     - ✅ Se redémarre avec le nouveau code
     - ✅ Nettoie les anciennes positions
     - ✅ Repart proprement

3. **Vérifiez :**
   - `/status` pour voir l'état
   - `/positions` pour les positions actives

---

## 📋 Scénarios d'Usage

### 🌙 Le soir avant de dormir

```
/pnl         → Voir les gains de la journée
/positions   → Vérifier les positions ouvertes
```

### 🚨 En cas de problème

```
/status      → Voir si tout va bien
/restart     → Si le bot semble bloqué
```

### 🔄 Après modification du code

```
/update      → Applique les changements GitHub
```

### 🛑 Pour maintenance

```
/stop        → Arrête le bot
/stop CONFIRM → Confirme l'arrêt
```

Plus tard :
```
/restart     → Relance le bot
```

---

## 🔒 Sécurité

### Les commandes admin nécessitent :
- ✅ Être envoyées depuis votre Chat ID configuré
- ✅ Le bot ignore les commandes des autres utilisateurs

### Confirmation requise pour :
- `/stop` → Demande `/stop CONFIRM`

---

## 📲 Notifications Automatiques

Le bot envoie automatiquement :

- **Au démarrage** : Configuration et état
- **Chaque minute** : Status des positions
- **À chaque trade** : Ouverture/fermeture de positions
- **En cas d'erreur** : Alertes et problèmes

---

## 💡 Astuces

### 1. Créer des raccourcis Telegram

Sur mobile, maintenez appuyé sur un message de commande → "Ajouter aux favoris"

### 2. Monitoring rapide

Envoyez ces commandes rapidement :
```
/pnl
/status
```

### 3. Redémarrage propre

Au lieu d'arrêter puis redémarrer :
```
/restart
```

Fait tout automatiquement !

### 4. Mise à jour one-click

Après avoir modifié le code sur GitHub :
```
/update
```

C'est tout ! Plus besoin d'ordinateur !

---

## 🆘 Dépannage

### "Bot ne répond pas"

1. Vérifiez sur Oracle Cloud Console que la VM tourne
2. Utilisez le raccourci Bureau pour relancer

### "Commande non reconnue"

- Vérifiez l'orthographe (avec le `/`)
- Tapez `/help` pour la liste des commandes

### "Erreur git pull"

- Le repo doit rester public sur GitHub
- Ou configurez un token d'accès

---

## 🎉 C'est Tout !

Vous pouvez maintenant **contrôler entièrement votre bot depuis votre téléphone** !

Plus besoin d'ouvrir votre ordinateur pour :
- ✅ Voir les performances
- ✅ Mettre à jour le code
- ✅ Redémarrer le bot
- ✅ Gérer les positions

**Profitez de votre liberté !** 🚀