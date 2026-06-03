# Build stage: compile Vue.js application
FROM node:22-alpine AS build

WORKDIR /app

# Copy dependency manifests first for better layer caching
COPY package.json package-lock.json* ./

# Install dependencies (cached unless package files change)
RUN npm ci --prefer-offline --no-audit

# Copy source code
COPY . .

# Build production bundle with TypeScript checking
RUN npm run build

# Production stage: serve with Nginx
FROM nginx:1.27-alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy optimized Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add healthcheck for container orchestration
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/index.html || exit 1

EXPOSE 80

# Run as non-root user for security
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

USER nginx
