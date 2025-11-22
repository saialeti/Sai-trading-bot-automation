# Webhook Server

Express.js webhook server that forwards requests to Discord and Trading Bot.

## Features

✅ Receives webhooks
✅ Forwards to Discord
✅ Forwards to Trading Bot
✅ Health checks (liveness & readiness)
✅ Docker containerized
✅ Kubernetes ready
✅ Non-root user (security)
✅ Configurable via environment variables

## Installation

### Local
```bash
npm install
npm start
```

### Docker
```bash
docker build -t webhook-server:latest .
docker run -p 3001:3001 webhook-server:latest
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

## Environment Variables
```bash
PORT                    # Port to run on (default: 3001)
DISCORD_WEBHOOK_URL     # Discord webhook URL
TRADING_BOT_URL         # Trading bot endpoint
```

## API Endpoints

### Health Checks
- `GET /` - Server running
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe

### Webhook
- `POST /webhook` - Receive and forward webhook

### Request Example
```bash
curl -X POST http://localhost:3001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "signal": "BUY",
    "symbol": "EURUSD",
    "price": 1.1050
  }'
```

## Docker Details

- Base: `node:18-alpine`
- User: `nodejs` (non-root, UID 1001)
- Health Check: Every 30 seconds
- Port: 3001

## Kubernetes Resources

- Deployment (2 replicas)
- Service (LoadBalancer)
- ConfigMap (configuration)
- Secret (sensitive data)
- ServiceAccount (RBAC)

## Files
```
src/server.js               Express.js app
package.json               Dependencies
Dockerfile                 Docker config
.dockerignore              Docker exclusions
.gitignore                 Git exclusions
k8s/deployment.yaml        K8s deployment
k8s/service.yaml           K8s service
k8s/configmap.yaml         Configuration
k8s/secret.yaml            Secrets
k8s/serviceaccount.yaml    RBAC
```

## Development
```bash
# Install dependencies
npm install

# Start development server
npm start

# Build Docker image
docker build -t webhook-server:latest .
```

## Troubleshooting

### Port already in use
```bash
PORT=3002 npm start
```

### Docker permission denied
```bash
sudo docker run ...
# or add user to docker group
```

### Pod not starting
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

## References

- [Express.js](https://expressjs.com/)
- [Node.js](https://nodejs.org/)
- [Docker](https://docker.com/)
- [Kubernetes](https://kubernetes.io/)
