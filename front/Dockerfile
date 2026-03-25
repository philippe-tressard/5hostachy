FROM node:22-alpine AS builder

ARG GIT_HASH=dev
ENV VITE_GIT_HASH=$GIT_HASH

WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package.json .
COPY --from=builder /app/node_modules ./node_modules
RUN addgroup -S app && adduser -S app -G app

EXPOSE 3000
ENV PORT=3000
ENV NODE_ENV=production

CMD ["node", "build"]
