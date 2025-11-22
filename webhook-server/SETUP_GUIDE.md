# 📖 Complete Setup Guide

## Prerequisites

- Node.js 18+ installed
- Docker installed (for containerization)
- Minikube or kubectl (for Kubernetes)
- Discord webhook URL
- Trading Bot endpoint URL

## Local Setup

### 1. Install Dependencies
```bash
cd ~/Sai-trading-bot-automation/webhook-server
npm install
```

### 2. Create Environment File (optional)
```bash
cat > .env << 'ENVEOF'
PORT=3001
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
TRADING_BOT_URL=http://localhost:3000/trade
ENVEOF
```

### 3. Run Server
```bash
npm start
```

Expected output:
```
🚀 Webhook server running on port 3001
```

### 4. Verify It Works
```bash
curl http://localhost:3001
# Response: Webhook server is running!
```

---

## Docker Setup

### 1. Build Image
```bash
docker build -t webhook-server:latest .
```

### 2. Run Container
```bash
docker run \
  -p 3001:3001 \
  -e DISCORD_WEBHOOK_URL="your-discord-webhook" \
  -e TRADING_BOT_URL="http://host.docker.internal:3000/trade" \
  webhook-server:latest
```

### 3. Test
```bash
curl http://localhost:3001
```

### 4. Stop Container
```bash
docker ps                    # Get container ID
docker stop <container-id>
```

---

## Kubernetes Setup

### 1. Start Minikube
```bash
minikube start
```

### 2. Update Secrets
Edit `k8s/secret.yaml`:
```yaml
stringData:
  DISCORD_WEBHOOK_URL: "your-discord-webhook"
  TRADING_BOT_URL: "http://trading-bot-service:3000/trade"
```

### 3. Deploy
```bash
kubectl apply -f k8s/
```

### 4. Verify Deployment
```bash
kubectl get pods -l app=webhook-server
# Should show 2 pods running

kubectl logs -l app=webhook-server
# Should show startup logs
```

### 5. Port Forward
```bash
kubectl port-forward svc/webhook-server 3001:3001
```

### 6. Test
```bash
curl http://localhost:3001
```

### 7. Check Service
```bash
kubectl get svc webhook-server
kubectl describe svc webhook-server
```

---

## Monitoring

### Local
```bash
npm start   # See logs in terminal
```

### Docker
```bash
docker logs <container-id>
docker logs -f <container-id>     # Follow logs
```

### Kubernetes
```bash
kubectl logs <pod-name>
kubectl logs -l app=webhook-server -f    # Follow all pod logs
kubectl describe pod <pod-name>          # Pod details
```

---

## Testing Webhook

### 1. Health Checks
```bash
curl http://localhost:3001/health/live
# Response: {"status":"alive"}

curl http://localhost:3001/health/ready
# Response: {"status":"ready"}
```

### 2. Send Webhook
```bash
curl -X POST http://localhost:3001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "signal": "BUY",
    "symbol": "EURUSD",
    "price": 1.1050,
    "quantity": 1.5
  }'
```

Expected response:
```
Forwarded to all services!
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 3001
lsof -i :3001
# Kill it or use different port
PORT=3002 npm start
```

### Docker Connection Refused
Make sure Docker daemon is running:
```bash
docker ps     # Should work if daemon running
```

### Kubernetes Pod Not Starting
```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Cannot Connect to Webhook
1. Check server is running
2. Check firewall/ports
3. Check environment variables set correctly

---

## Cleanup

### Local
```bash
# Just press Ctrl+C to stop
```

### Docker
```bash
docker stop <container-id>
docker rm <container-id>
```

### Kubernetes
```bash
kubectl delete -f k8s/
minikube stop
```

---

## Next Steps

1. Read QUICKSTART.md
2. Test endpoints
3. Configure Discord & Trading Bot URLs
4. Deploy to your environment

