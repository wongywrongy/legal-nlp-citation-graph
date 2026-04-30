# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all deps (including dev) — Next.js's build needs TypeScript and
# the rest of the dev tooling. Production-only install lands in the runner
# stage via the `next build --output=standalone` artifact.
RUN npm ci

# Copy source code
COPY . .

# NEXT_PUBLIC_* env vars are baked at build time, not read at runtime.
# Override via `docker compose build --build-arg NEXT_PUBLIC_API_URL=...`
# or set the build arg in compose.
ARG NEXT_PUBLIC_API_URL=http://localhost:8001/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Build the application
RUN npm run build

# Production stage
FROM node:18-alpine AS runner

WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Set ownership
RUN chown -R nextjs:nodejs /app
USER nextjs

# Expose port
EXPOSE 3000

# Set environment
ENV NODE_ENV=production
ENV PORT=3000

# Start the application
CMD ["node", "server.js"]
