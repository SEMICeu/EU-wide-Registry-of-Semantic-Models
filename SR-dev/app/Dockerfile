# Build React frontend
FROM node:18-alpine AS frontend-build
WORKDIR /frontend
COPY sr-frontend/package*.json ./
RUN npm ci
COPY sr-frontend/ ./
RUN npm run build

# Production stage
FROM node:18-alpine AS production
WORKDIR /app

# Install backend dependencies
COPY sr-backend/package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

# Copy backend source
COPY sr-backend/backend.js ./

# Copy built frontend from build stage
COPY --from=frontend-build /frontend/build ./public

# Create non-root user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup
USER appuser

# Expose port
EXPOSE 4000

# Start the application
CMD ["node", "backend.js"]