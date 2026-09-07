# EconPilot frontend — static build served by nginx, which also reverse-proxies
# the API so the browser talks to a single origin (no CORS wrangling).
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The API is reached at /api/* and nginx strips the prefix when proxying to the
# backend, so all browser requests are same-origin.
ENV VITE_API_BASE_URL=/api
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
