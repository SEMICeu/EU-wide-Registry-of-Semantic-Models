# Build React frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app
# Copy package files
COPY package*.json ./
RUN npm ci
# Copy all source files except node_modules
COPY . .
# Build the React app for production
RUN npm run build

# Production stage
FROM node:18-alpine AS production
WORKDIR /app

# Install backend dependencies
COPY package*.json ./
RUN npm ci --only=production && npm cache clean --force

# Copy backend source
COPY backend.js ./

# Copy built frontend from build stage
COPY --from=frontend-build /app/build ./public

# Create non-root user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup
USER appuser

# Expose port
EXPOSE 4000

# Start the application
CMD ["node", "backend.js"]