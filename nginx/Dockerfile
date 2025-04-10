# syntax=docker/dockerfile:1
FROM nginx:stable-alpine

# Add metadata labels for enterprise-grade image management.
LABEL org.opencontainers.image.authors="aurelien.izoulet@epita.fr" \
      org.opencontainers.image.title="Yocto Mirror Nginx Proxy" \
      org.opencontainers.image.description="Enterprise-grade Nginx container serving as a reverse proxy and static file server for Yocto mirror data" \
      org.opencontainers.image.version="1.0"

# Remove default configuration to avoid conflicts.
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy the custom Nginx configuration file into the container.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Ensure configuration file has appropriate permissions.
RUN chmod 644 /etc/nginx/conf.d/default.conf

# Define a health check to ensure Nginx is running.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1

# Expose port 80 which is used by Nginx.
EXPOSE 80

# Launch Nginx in the foreground.
CMD ["nginx", "-g", "daemon off;"]
