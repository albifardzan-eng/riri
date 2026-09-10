FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup --system --gid 10001 riri && adduser --system --uid 10001 --ingroup riri riri
COPY --from=builder --chown=riri:riri /app/.next/standalone ./
COPY --from=builder --chown=riri:riri /app/.next/static ./.next/static
COPY --from=builder --chown=riri:riri /app/public ./public
USER riri
EXPOSE 3000
CMD ["node", "server.js"]
