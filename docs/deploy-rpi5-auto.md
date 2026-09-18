# Déploiement automatique — RPi 5

Synchronisation automatique du code depuis GitHub vers le Raspberry Pi 5.

**Prérequis :**
- RPi accessible sur le réseau local à `<RPi-IP>`
- Docker et Git installés
- Le répertoire `/opt/5hostachy` existe déjà (propriétaire `hostachy`)
- Votre compte (`<your-user>`) dispose des droits `sudo`

---

## Étape 1 — Générer une clé SSH deploy sur le RPi

Connectez-vous au RPi en SSH depuis votre PC Windows :

```powershell
ssh <your-user>@<RPi-IP>
```

Générez une paire de clés dédiée (sans passphrase) :

```bash
ssh-keygen -t ed25519 -C "hostachy-rpi5-deploy" -f ~/.ssh/hostachy_deploy -N ""
```

Affichez et copiez la clé publique :

```bash
cat ~/.ssh/hostachy_deploy.pub
```

La ligne commence par `ssh-ed25519 AAAA...` — copiez-la en entier.

---

## Étape 2 — Configurer SSH pour GitHub

```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/hostachy_deploy
    StrictHostKeyChecking no
EOF
```

---

## Étape 3 — Ajouter la deploy key sur GitHub

1. Ouvrir : https://github.com/<github-user>/5hostachy/settings/keys
2. Cliquer **Add deploy key**
3. Titre : `RPi5 deploy`
4. Coller la clé publique copiée à l'étape 1
5. Laisser **Allow write access** décoché (lecture seule suffisante)
6. Cliquer **Add key**

Tester la connexion :

```bash
ssh -T git@github.com
# Réponse attendue :
# Hi <github-user>/5hostachy! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## Étape 4 — Transférer la propriété du répertoire et rejoindre le groupe docker

Le répertoire appartient à `hostachy`. On transfère la propriété à `<your-user>` :

```bash
sudo chown -R <your-user>:<your-user> /opt/5hostachy
```

Ajouter `<your-user>` au groupe `docker` (évite d'utiliser `sudo` pour toutes les commandes docker) :

```bash
sudo usermod -aG docker <your-user>
```

**Se déconnecter/reconnecter** pour que le changement de groupe prenne effet :

```bash
exit
# puis :
ssh <your-user>@<RPi-IP>
```

Vérifier :

```bash
ls -la /opt/
# /opt/5hostachy doit afficher <your-user> <your-user>
groups
# docker doit apparaître dans la liste
```

---

## Étape 5 — Initialiser git et synchroniser depuis GitHub

```bash
cd /opt/5hostachy

# Définir la branche par défaut à main (global)
git config --global init.defaultBranch main

# Initialiser git
git init

# Ajouter le remote GitHub en SSH (ou mettre à jour l'URL si origin existe déjà)
git remote add origin git@github.com:<github-user>/5hostachy.git 2>/dev/null || \
  git remote set-url origin git@github.com:<github-user>/5hostachy.git

# Récupérer les branches depuis GitHub
git fetch origin

# Créer la branche locale main en la liant à origin/main et récupérer les commits
# (DWIM : git déduit automatiquement le tracking depuis origin/main)
git checkout main

# Vérifications
git log --oneline -3
git remote -v
git branch -vv
```

---

## Étape 6 — Vérifier et restaurer le fichier .env

Le fichier `.env` est dans le `.gitignore` et ne doit pas avoir été écrasé.
Vérifiez qu'il est intact :

```bash
cat /opt/5hostachy/.env
```

S'il est vide ou manquant, restaurez-le depuis l'exemple :

```bash
cp /opt/5hostachy/.env.example /opt/5hostachy/.env
nano /opt/5hostachy/.env
# Remettre les valeurs : SECRET_KEY, DOMAIN, ORIGIN, etc.
```

---

## Étape 7 — Redémarrer Docker Compose

```bash
cd /opt/5hostachy

# Arrêter les conteneurs existants
docker compose down

# Relancer (rebuild complet pour prendre en compte les nouveaux fichiers)
docker compose up --build -d

# Vérifier que les 3 conteneurs tournent
docker compose ps
```

Résultat attendu :

```
NAME                STATUS
5hostachy-api-1     Up
5hostachy-front-1   Up
5hostachy-caddy-1   Up
```

Vérifier les logs :

```bash
docker compose logs --tail=30 -f
```

L'application doit répondre sur http://<RPi-IP>

---

## Étape 8 — Créer le script de déploiement automatique

```bash
sudo tee /opt/hostachy-deploy.sh << 'EOF'
#!/bin/bash
set -e
REPO=/opt/5hostachy
LOG_DATE=$(date '+%Y-%m-%d %H:%M:%S')

cd "$REPO"

echo "[$LOG_DATE] Vérification des mises à jour..."

# Récupérer sans fusionner
git fetch origin main

# Comparer HEAD local et origin/main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$LOG_DATE] Aucun changement — rien à faire."
    exit 0
fi

echo "[$LOG_DATE] Nouveaux commits détectés — pull en cours..."
git pull origin main

# Rebuild uniquement si des fichiers applicatifs ont changé
if git diff "$LOCAL" HEAD --quiet -- api/ front/ docker-compose.yml Caddyfile; then
    echo "[$LOG_DATE] Pas de changement dans le code applicatif."
else
    echo "[$LOG_DATE] Rebuild et redémarrage des conteneurs..."
    docker compose -f "$REPO/docker-compose.yml" up --build -d
    echo "[$LOG_DATE] Déploiement terminé."
fi
EOF

sudo chmod +x /opt/hostachy-deploy.sh
```

Tester manuellement :

```bash
/opt/hostachy-deploy.sh
```

Résultat attendu si tout est à jour :

```
[2026-03-01 10:00:00] Vérification des mises à jour...
[2026-03-01 10:00:01] Aucun changement — rien à faire.
```

---

## Étape 9 — Planifier avec cron

```bash
crontab -e
```

Ajoutez **une seule** des lignes suivantes :

```cron
# Synchronisation toutes les nuits à 3h00 (recommandé)
0 3 * * * /opt/hostachy-deploy.sh >> /var/log/hostachy-deploy.log 2>&1

# OU : synchronisation toutes les 10 minutes
*/10 * * * * /opt/hostachy-deploy.sh >> /var/log/hostachy-deploy.log 2>&1
```

Vérifier :

```bash
crontab -l
```

---

## Étape 10 — Consulter les logs de déploiement

```bash
# Dernières lignes
tail -50 /var/log/hostachy-deploy.log

# Suivi en temps réel
tail -f /var/log/hostachy-deploy.log
```

---

## Déclenchement manuel depuis votre PC Windows

```powershell
ssh <your-user>@<RPi-IP> "/opt/hostachy-deploy.sh"
```

---

## Workflow complet

```
PC (VS Code)
    │
    │  git add .
    │  git commit -m "feat: ..."
    │  git push
    â–¼
GitHub (<github-user>/5hostachy)
    │
    │  cron (3h ou 10 min) — ou déclencher manuellement
    â–¼
RPi 5 (<RPi-IP>)
    │  git fetch → comparaison SHA
    │  git pull origin main
    │  docker compose up --build -d  (seulement si code modifié)
    â–¼
Application mise à jour sur http://<RPi-IP>
```

---

## Dépannage

| Problème | Cause probable | Solution |
|----------|---------------|----------|
| `Permission denied` sur git | Répertoire appartient à `hostachy` | `sudo chown -R <your-user>:<your-user> /opt/5hostachy` |
| `Permission denied (publickey)` | Clé SSH non ajoutée sur GitHub | Vérifier étape 3 |
| `fatal: not a git repository` | `git init` non exécuté | Reprendre étape 5 |
| `git pull` échoue sur conflit | Fichiers modifiés localement | `git reset --hard origin/main` |
| Conteneurs ne démarrent pas | `.env` manquant ou incorrect | Vérifier étape 6 |
| `unable to open database file` | `DATABASE_URL` pointe vers un mauvais chemin | Vérifier que `.env` contient `DATABASE_URL=sqlite:////app/data/app.db` puis `docker compose up -d --force-recreate api` |
| `permission denied` sur docker.sock | `<your-user>` pas dans le groupe `docker` | `sudo usermod -aG docker <your-user>` puis reconnexion |
| Docker non relancé | Aucun changement dans `api/` / `front/` | `docker compose up --build -d` |
| Log vide après cron | Cron ne tourne pas | `systemctl status cron` et `crontab -l` |
| Script introuvable | Mauvais chemin | `ls -la /opt/hostachy-deploy.sh` |
