# DÃ©ploiement automatique â€” RPi 5

Synchronisation automatique du code depuis GitHub vers le Raspberry Pi 5.

**PrÃ©requis :**
- RPi accessible sur le rÃ©seau local Ã  `<RPi-IP>`
- Docker et Git installÃ©s
- Le rÃ©pertoire `/opt/5hostachy` existe dÃ©jÃ  (propriÃ©taire `hostachy`)
- Votre compte (`<your-user>`) dispose des droits `sudo`

---

## Ã‰tape 1 â€” GÃ©nÃ©rer une clÃ© SSH deploy sur le RPi

Connectez-vous au RPi en SSH depuis votre PC Windows :

```powershell
ssh <your-user>@<RPi-IP>
```

GÃ©nÃ©rez une paire de clÃ©s dÃ©diÃ©e (sans passphrase) :

```bash
ssh-keygen -t ed25519 -C "hostachy-rpi5-deploy" -f ~/.ssh/hostachy_deploy -N ""
```

Affichez et copiez la clÃ© publique :

```bash
cat ~/.ssh/hostachy_deploy.pub
```

La ligne commence par `ssh-ed25519 AAAA...` â€” copiez-la en entier.

---

## Ã‰tape 2 â€” Configurer SSH pour GitHub

```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
    IdentityFile ~/.ssh/hostachy_deploy
    StrictHostKeyChecking no
EOF
```

---

## Ã‰tape 3 â€” Ajouter la deploy key sur GitHub

1. Ouvrir : https://github.com/<github-user>/5hostachy/settings/keys
2. Cliquer **Add deploy key**
3. Titre : `RPi5 deploy`
4. Coller la clÃ© publique copiÃ©e Ã  l'Ã©tape 1
5. Laisser **Allow write access** dÃ©cochÃ© (lecture seule suffisante)
6. Cliquer **Add key**

Tester la connexion :

```bash
ssh -T git@github.com
# RÃ©ponse attendue :
# Hi <github-user>/5hostachy! You've successfully authenticated, but GitHub does not provide shell access.
```

---

## Ã‰tape 4 â€” TransfÃ©rer la propriÃ©tÃ© du rÃ©pertoire et rejoindre le groupe docker

Le rÃ©pertoire appartient Ã  `hostachy`. On transfÃ¨re la propriÃ©tÃ© Ã  `<your-user>` :

```bash
sudo chown -R <your-user>:<your-user> /opt/5hostachy
```

Ajouter `<your-user>` au groupe `docker` (Ã©vite d'utiliser `sudo` pour toutes les commandes docker) :

```bash
sudo usermod -aG docker <your-user>
```

**Se dÃ©connecter/reconnecter** pour que le changement de groupe prenne effet :

```bash
exit
# puis :
ssh <your-user>@<RPi-IP>
```

VÃ©rifier :

```bash
ls -la /opt/
# /opt/5hostachy doit afficher <your-user> <your-user>
groups
# docker doit apparaÃ®tre dans la liste
```

---

## Ã‰tape 5 â€” Initialiser git et synchroniser depuis GitHub

```bash
cd /opt/5hostachy

# DÃ©finir la branche par dÃ©faut Ã  main (global)
git config --global init.defaultBranch main

# Initialiser git
git init

# Ajouter le remote GitHub en SSH (ou mettre Ã  jour l'URL si origin existe dÃ©jÃ )
git remote add origin git@github.com:<github-user>/5hostachy.git 2>/dev/null || \
  git remote set-url origin git@github.com:<github-user>/5hostachy.git

# RÃ©cupÃ©rer les branches depuis GitHub
git fetch origin

# CrÃ©er la branche locale main en la liant Ã  origin/main et rÃ©cupÃ©rer les commits
# (DWIM : git dÃ©duit automatiquement le tracking depuis origin/main)
git checkout main

# VÃ©rifications
git log --oneline -3
git remote -v
git branch -vv
```

---

## Ã‰tape 6 â€” VÃ©rifier et restaurer le fichier .env

Le fichier `.env` est dans le `.gitignore` et ne doit pas avoir Ã©tÃ© Ã©crasÃ©.
VÃ©rifiez qu'il est intact :

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

## Ã‰tape 7 â€” RedÃ©marrer Docker Compose

```bash
cd /opt/5hostachy

# ArrÃªter les conteneurs existants
docker compose down

# Relancer (rebuild complet pour prendre en compte les nouveaux fichiers)
docker compose up --build -d

# VÃ©rifier que les 3 conteneurs tournent
docker compose ps
```

RÃ©sultat attendu :

```
NAME                STATUS
5hostachy-api-1     Up
5hostachy-front-1   Up
5hostachy-caddy-1   Up
```

VÃ©rifier les logs :

```bash
docker compose logs --tail=30 -f
```

L'application doit rÃ©pondre sur http://<RPi-IP>

---

## Ã‰tape 8 â€” CrÃ©er le script de dÃ©ploiement automatique

```bash
sudo tee /opt/hostachy-deploy.sh << 'EOF'
#!/bin/bash
set -e
REPO=/opt/5hostachy
LOG_DATE=$(date '+%Y-%m-%d %H:%M:%S')

cd "$REPO"

echo "[$LOG_DATE] VÃ©rification des mises Ã  jour..."

# RÃ©cupÃ©rer sans fusionner
git fetch origin main

# Comparer HEAD local et origin/main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$LOG_DATE] Aucun changement â€” rien Ã  faire."
    exit 0
fi

echo "[$LOG_DATE] Nouveaux commits dÃ©tectÃ©s â€” pull en cours..."
git pull origin main

# Rebuild uniquement si des fichiers applicatifs ont changÃ©
if git diff "$LOCAL" HEAD --quiet -- api/ front/ docker-compose.yml Caddyfile; then
    echo "[$LOG_DATE] Pas de changement dans le code applicatif."
else
    echo "[$LOG_DATE] Rebuild et redÃ©marrage des conteneurs..."
    docker compose -f "$REPO/docker-compose.yml" up --build -d
    echo "[$LOG_DATE] DÃ©ploiement terminÃ©."
fi
EOF

sudo chmod +x /opt/hostachy-deploy.sh
```

Tester manuellement :

```bash
/opt/hostachy-deploy.sh
```

RÃ©sultat attendu si tout est Ã  jour :

```
[2026-03-01 10:00:00] VÃ©rification des mises Ã  jour...
[2026-03-01 10:00:01] Aucun changement â€” rien Ã  faire.
```

---

## Ã‰tape 9 â€” Planifier avec cron

```bash
crontab -e
```

Ajoutez **une seule** des lignes suivantes :

```cron
# Synchronisation toutes les nuits Ã  3h00 (recommandÃ©)
0 3 * * * /opt/hostachy-deploy.sh >> /var/log/hostachy-deploy.log 2>&1

# OU : synchronisation toutes les 10 minutes
*/10 * * * * /opt/hostachy-deploy.sh >> /var/log/hostachy-deploy.log 2>&1
```

VÃ©rifier :

```bash
crontab -l
```

---

## Ã‰tape 10 â€” Consulter les logs de dÃ©ploiement

```bash
# DerniÃ¨res lignes
tail -50 /var/log/hostachy-deploy.log

# Suivi en temps rÃ©el
tail -f /var/log/hostachy-deploy.log
```

---

## DÃ©clenchement manuel depuis votre PC Windows

```powershell
ssh <your-user>@<RPi-IP> "/opt/hostachy-deploy.sh"
```

---

## Workflow complet

```
PC (VS Code)
    â”‚
    â”‚  git add .
    â”‚  git commit -m "feat: ..."
    â”‚  git push
    â–¼
GitHub (<github-user>/5hostachy)
    â”‚
    â”‚  cron (3h ou 10 min) â€” ou dÃ©clencher manuellement
    â–¼
RPi 5 (<RPi-IP>)
    â”‚  git fetch â†’ comparaison SHA
    â”‚  git pull origin main
    â”‚  docker compose up --build -d  (seulement si code modifiÃ©)
    â–¼
Application mise Ã  jour sur http://<RPi-IP>
```

---

## DÃ©pannage

| ProblÃ¨me | Cause probable | Solution |
|----------|---------------|----------|
| `Permission denied` sur git | RÃ©pertoire appartient Ã  `hostachy` | `sudo chown -R <your-user>:<your-user> /opt/5hostachy` |
| `Permission denied (publickey)` | ClÃ© SSH non ajoutÃ©e sur GitHub | VÃ©rifier Ã©tape 3 |
| `fatal: not a git repository` | `git init` non exÃ©cutÃ© | Reprendre Ã©tape 5 |
| `git pull` Ã©choue sur conflit | Fichiers modifiÃ©s localement | `git reset --hard origin/main` |
| Conteneurs ne dÃ©marrent pas | `.env` manquant ou incorrect | VÃ©rifier Ã©tape 6 |
| `unable to open database file` | `DATABASE_URL` pointe vers un mauvais chemin | VÃ©rifier que `.env` contient `DATABASE_URL=sqlite:////app/data/app.db` puis `docker compose up -d --force-recreate api` |
| `permission denied` sur docker.sock | `<your-user>` pas dans le groupe `docker` | `sudo usermod -aG docker <your-user>` puis reconnexion |
| Docker non relancÃ© | Aucun changement dans `api/` / `front/` | `docker compose up --build -d` |
| Log vide aprÃ¨s cron | Cron ne tourne pas | `systemctl status cron` et `crontab -l` |
| Script introuvable | Mauvais chemin | `ls -la /opt/hostachy-deploy.sh` |
