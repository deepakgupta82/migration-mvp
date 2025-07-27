# =====================================================================================
# Stage 1: Build with Enhanced Caching
# =====================================================================================
FROM node:20-alpine as build

WORKDIR /app

# Copy package files first for better layer caching
COPY package.json package-lock.json ./

# Install dependencies with npm cache mount
RUN --mount=type=cache,target=/root/.npm \
    npm install --cache /root/.npm

# Copy source code after dependencies are installed
COPY ./public ./public
COPY ./src ./src
COPY tsconfig.json ./

# Build the application
RUN npm run build


# =====================================================================================
# Stage 2: Optimized Nginx Serving
# =====================================================================================
FROM nginx:1.25-alpine

# Copy custom nginx configuration if needed
# COPY nginx.conf /etc/nginx/nginx.conf

# Copy the build output from the build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy a custom Nginx configuration to handle single-page application routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Set proper permissions for nginx
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid



# Switch to nginx user
USER nginx

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Run as non-root user
USER nginx

# Start nginx
CMD ["nginx", "-g", "daemon off;"]