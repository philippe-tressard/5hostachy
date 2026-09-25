FROM node:20-alpine

RUN apk add --no-cache git tzdata

WORKDIR /app

# `npm ci` et le lockfile (#1050, 25/09/2026) : `npm install` résolvait les
# plages `^` au moment du build — deux nœuds construits à deux dates pouvaient
# embarquer deux Baileys différents, sans que rien ne le dise. C'est le défaut
# corrigé le 23/06/2026 sur `front/Dockerfile`, resté ici.
# ⚠️ `libsignal` est une dépendance git (verrouillée en `git+ssh`) : npm la
# récupère en HTTPS sans clé SSH — vérifié par `npm ci` sans clé avant la PR.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY index.js ./

VOLUME /app/auth_state

EXPOSE 8090

CMD ["node", "index.js"]
