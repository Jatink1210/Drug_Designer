# Stage 1: Build Frontend
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
# Install avoiding peer conflicts
RUN npm install --legacy-peer-deps
COPY . .
# Execute Vite build into /dist
RUN npm run build

# Stage 2: Serve via Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Copy custom Nginx configuration to support React Router SPA Fallback
RUN echo 'server { \
    listen       80; \
    server_name  localhost; \
    location / { \
        root   /usr/share/nginx/html; \
        index  index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
    # Proxy API requests to backend service \
    location /api/ { \
        proxy_pass http://api:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_http_version 1.1; \
        proxy_connect_timeout 60s; \
        proxy_send_timeout 600s; \
        proxy_read_timeout 600s; \
        send_timeout 600s; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
