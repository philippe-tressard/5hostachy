FROM node:20-alpine

RUN apk add --no-cache git

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY index.js ./

VOLUME /app/auth_state

EXPOSE 8090

CMD ["node", "index.js"]
