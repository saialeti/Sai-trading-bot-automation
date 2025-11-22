# 📋 Quick Start Guide

## Local Development (5 minutes)

### 1. Install Dependencies
```bash
npm install
```

### 2. Set Variables
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
export TRADING_BOT_URL="http://localhost:3000/trade"
```

### 3. Run
```bash
npm start
```

### 4. Test
```bash
curl http://localhost:3001
```

---

## Docker (10 minutes)

### 1. Build
```bash
docker build -t webhook-server:latest .
```

### 2. Run
```bash
docker run -p 3001:3001 \
  -e DISCORD_WEBHOOK_URL="your-webhook" \
  -e TRADING_BOT_URL="http://host.docker.internal:3000/trade" \
  webhook-server:latest
```

### 3. Test
```bash
curl http://localhost:3001
```

---

## Kubernetes (15 minutes)

### 1. Update Secret
Edit `k8s/secret.yaml`:
```yaml
DISCORD_WEBHOOK_URL: "your-webhook-url"
TRADING_BOT_URL: "http://trading-bot:3000/trade"
```

### 2. Deploy
```bash
kubectl apply -f k8s/
```

### 3. Check
```bash
kubectl get pods
kubectl logs -l app=webhook-server
```

### 4. Port Forward
```bash
kubectl port-forward svc/webhook-server 3001:3001
```

### 5. Test
```bash
curl http://localhost:3001
```

---

## Endpoints
```bash
# Health
GET /
GET /health/live
GET /health/ready

# Webhook
POST /webhook
```

---

Done! Read README.md for details.
