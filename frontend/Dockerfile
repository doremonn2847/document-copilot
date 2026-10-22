# Production image for the Railway frontend service: build the SPA, then serve
# it with Caddy. VITE_* values are public and baked in at build time from the
# service's Railway variables.
FROM node:24.18.0-slim AS build
RUN npm install -g pnpm@11.20.0
WORKDIR /app
COPY package.json pnpm-lock.yaml .npmrc ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
RUN pnpm build

FROM caddy:2.10.0-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
