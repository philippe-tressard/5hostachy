FROM node:22-alpine AS builder

ARG GIT_HASH=dev
ARG INSTANCE_ID=
ENV VITE_GIT_HASH=$GIT_HASH
ENV VITE_INSTANCE_ID=$INSTANCE_ID

WORKDIR /app
# Lockfile COPIÉ + `npm ci` : build DÉTERMINISTE (versions figées par package-lock.json).
# Avant : `COPY package.json` seul + `npm install` re-résolvait les `^` vers les dernières
# versions à chaque build → un build propre cassait (vite-plugin-pwa 1.3.0) alors qu'un cache
# ancien passait. Cause des échecs silencieux de build front (cf. 23/06/2026).
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --legacy-peer-deps

COPY . .
RUN npm run build

FROM node:22-alpine AS runner
RUN apk add --no-cache tzdata
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json .
COPY --from=builder /app/node_modules ./node_modules
RUN addgroup -S app && adduser -S app -G app

EXPOSE 3000
ENV PORT=3000
ENV NODE_ENV=production

CMD ["node", "build"]
