# 🚀 Webhook Server - START HERE

Welcome! This is your webhook server for Discord & Trading Bot integration.

## 📍 Location
```
~/Sai-trading-bot-automation/webhook-server/
```

## 📁 What You Have
```
webhook-server/
├── src/server.js              (Node.js Express app)
├── package.json               (Dependencies)
├── Dockerfile                 (Docker config)
├── k8s/                       (Kubernetes files)
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── serviceaccount.yaml
└── [docs]                     (This folder)
```

## ⚡ Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
npm install
```

### Step 2: Set Environment Variables
```bash
export DISCORD_WEBHOOK_URL="your-discord-webhook"
export TRADING_BOT_URL="http://localhost:3000/trade"
export PORT=3001
```

### Step 3: Run Server
```bash
npm start
```

✅ Server running on http://localhost:3001

## 🧪 Test It
```bash
# Health check
curl http://localhost:3001

# Send webhook
curl -X POST http://localhost:3001/webhook \
  -H "Content-Type: application/json" \
  -d '{"signal": "BUY", "symbol": "EURUSD"}'
```

## 🐳 Docker

Build image:
```bash
docker build -t webhook-server:latest .
```

Run container:
```bash
docker run -p 3001:3001 \
  -e DISCORD_WEBHOOK_URL="your-url" \
  -e TRADING_BOT_URL="http://host.docker.internal:3000/trade" \
  webhook-server:latest
```

## ☸️ Kubernetes

Deploy:
```bash
kubectl apply -f k8s/
```

Check:
```bash
kubectl get pods
kubectl logs -l app=webhook-server
```

## 📚 Documentation
- **QUICKSTART.md** - 3-step Docker/K8s deployment
- **README.md** - Full documentation
- **SETUP_GUIDE.md** - Detailed setup
- **QUICK_REFERENCE.txt** - Commands reference
- **FILES_SUMMARY.txt** - File descriptions

## 🔑 Endpoints

- `GET /` - Server status
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `POST /webhook` - Forward webhook

## ⚠️ Important

Update these before deploying:
- `k8s/secret.yaml` - Add Discord & Trading Bot URLs
- `k8s/configmap.yaml` - Change PORT if needed

Good luck! 🚀
