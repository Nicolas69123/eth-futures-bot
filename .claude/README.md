# 📁 Dossier .claude/ - Documentation

Ce dossier contient la configuration modulaire de Claude Code pour ce projet.

---

## 📋 Fichiers

| Fichier | Description | Mise à jour |
|---------|-------------|-------------|
| `context.md` | Contexte projet, stack, objectifs | Rarement |
| `architecture.md` | Structure technique détaillée | Occasionnellement |
| `progress.md` | 🔥 **Avancement actuel**, dernières sessions | **Chaque session** |
| `changelog.md` | Historique complet des versions | À chaque release |
| `update-progress.sh` | Script pour mettre à jour `progress.md` | - |
| `README.md` | Ce fichier | - |

---

## 🎯 Workflow Recommandé

### Début de session

1. Lancer Claude dans le projet :
   ```bash
   cd ~/Dev/Trading/TelegramBot/
   claude
   ```

2. Claude charge automatiquement `CLAUDE.md`
3. Claude lit `progress.md` → sait **exactement** où vous en êtes
4. Vous continuez directement !

### Fin de session

**Mettre à jour progress.md** :

```bash
# Méthode 1 : Script interactif (recommandé)
./.claude/update-progress.sh

# Méthode 2 : Édition manuelle
code .claude/progress.md
```

**Pensez à commit** :
```bash
git add .claude/progress.md
git commit -m "docs: update progress session $(date +%Y-%m-%d)"
```

---

## 📏 Taille des Fichiers

**Limite contexte Claude** : 200 000 tokens

**Recommandations** :
- `context.md` : < 300 lignes
- `architecture.md` : < 500 lignes
- `progress.md` : < 500 lignes (archiver ancien si trop gros)
- `changelog.md` : Illimité (archiver par année)

---

## 🔄 Maintenance

### Archiver ancien progress

Quand `progress.md` devient trop gros (> 500 lignes) :

```bash
# Créer archive
mkdir -p .claude/archive
mv .claude/progress.md .claude/archive/progress-2025.md

# Créer nouveau progress.md
cp .claude/progress.md.template .claude/progress.md
```

### Nettoyer changelog

```bash
# Archiver changelogs anciens
mv .claude/changelog.md .claude/archive/changelog-2025.md
# Garder seulement 6 derniers mois dans changelog.md
```

---

## 💡 Astuces

### Référencer fichiers depuis CLAUDE.md

```markdown
@.claude/context.md           # Import automatique
@.claude/architecture.md      # Claude charge si besoin
```

### Garder progress.md à jour

**Habitude recommandée** :
- Mettre à jour **à chaque session**
- Même si petits changements
- Aide Claude à comprendre progression

### Structure progress.md

```markdown
## 🎯 Session Actuelle
[Ce qui se passe MAINTENANT]

## 🗓️ Dernières Sessions
[Historique récent 7 derniers jours]

## 💡 Décisions Récentes
[Choix techniques importants]

## 📝 Notes pour Prochaine Session
[Ce qu'il ne faut pas oublier]
```

---

## 🚀 Avantages Système Modulaire

✅ **CLAUDE.md reste léger** (< 150 lignes)
✅ **Contexte optimisé** (charge seulement ce qui est nécessaire)
✅ **Historique complet** (changelog archivé)
✅ **Avancement clair** (progress.md détaillé)
✅ **Facile à maintenir** (fichiers séparés par sujet)
✅ **Claude toujours à jour** (lit progress.md automatiquement)

---

## 📞 Questions ?

Si Claude ne comprend pas le contexte :
1. Vérifier que `progress.md` est à jour
2. Vérifier les `@imports` dans `CLAUDE.md`
3. Demander explicitement : "Lis .claude/progress.md"

Si trop de contexte :
1. Archiver ancien progress/changelog
2. Réduire verbosité dans architecture.md
3. Utiliser tableaux au lieu de longs paragraphes
