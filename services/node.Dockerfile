# Shared image definition for the Node.js services (api-gateway, notification-service).
#   docker build -f services/node.Dockerfile --build-arg SERVICE=api-gateway \
#                --build-arg PORT=3000 -t novasurge/api-gateway:local services
FROM node:22-alpine

# iproute2 provides `tc` for the latency_injection chaos experiment.
RUN apk add --no-cache iproute2

WORKDIR /app
ARG SERVICE
ARG PORT=3000
ENV PORT=${PORT} NODE_ENV=production

COPY ${SERVICE}/package.json ${SERVICE}/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY ${SERVICE}/src/ ./src/

EXPOSE ${PORT}
CMD ["node", "src/index.js"]
