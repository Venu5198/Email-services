# =============================================================================
# SyncRivo Email Service — Next.js Frontend
# Multi-Stage Dockerfile
#
# Stage 1 (deps):     Installs only production node_modules
# Stage 2 (builder):  Builds the Next.js production bundle
# Stage 3 (runtime):  Lean image with only the compiled output + standalone server
# =============================================================================

# ── Stage 1: Install dependencies ────────────────────────────────────────────
FROM node:20-alpine AS deps

LABEL stage="deps"
WORKDIR /app

# Install libc compat for Alpine (required by some native node packages)
RUN apk add --no-cache libc6-compat

# Copy package manifests only (cache bust only when packages change)
COPY package.json package-lock.json ./

# Install production + dev deps (dev needed for the build)
RUN npm ci --frozen-lockfile

# ── Stage 2: Build the Next.js app ───────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy installed node_modules from the deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy full source
COPY . .

# Build-time env: bake the public API URL into the static bundle
# NEXT_PUBLIC_ vars must be present during `npm run build`, not just at runtime
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Enable Next.js standalone output mode for minimal runtime image
# (next.config.mjs must have output: 'standalone')
RUN npm run build

# ── Stage 3: Lean production runtime ─────────────────────────────────────────
FROM node:20-alpine AS runtime

LABEL maintainer="SyncRivo Team"
LABEL description="SyncRivo Email Service — Next.js Frontend"
LABEL version="2.0"

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy the standalone server output (smallest possible runtime)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
