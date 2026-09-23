# Build stage
ARG VITE_API_URL=/api
ARG VITE_ORCHESTRATOR_DASHBOARD_URL=http://10.0.0.92:8005/dashboard/
FROM node:22-alpine AS builder

WORKDIR /app

# Make build arg available during build for Vite
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
ARG VITE_ORCHESTRATOR_DASHBOARD_URL
ENV VITE_ORCHESTRATOR_DASHBOARD_URL=${VITE_ORCHESTRATOR_DASHBOARD_URL}

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy project files
COPY . .

# Build the application (Vite will read VITE_API_URL at build time)
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

WORKDIR /app

# Copy built files from builder
COPY --from=builder /app/dist ./dist

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O- http://localhost:3000/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
