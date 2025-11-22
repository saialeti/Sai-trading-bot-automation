# 📋 Quick Start Guide

## Local Development (5 minutes)

### 1. Install Dependencies
```bash
cd ~/Sai-trading-bot-automation/trading-bot
pip install -r requirements.txt
```

### 2. Set Credentials
```bash
export ACCOUNTS_JSON='[{
  "name": "Aleti Sai",
  "environment": "https://demo.tradelocker.com",
  "username": "saialeti657@gmail.com",
  "password": "U!i7qYK)6|",
  "server": "HEROFX"
}]'
```

### 3. Run
```bash
python src/server.py
```

### 4. Test
```bash
curl http://localhost:3000
```

---

## Docker (10 minutes)

### 1. Build
```bash
docker build -t asaikale/trading-bot:latest .
```

### 2. Run
```bash
docker run -p 3000:3000 \
  -e ACCOUNTS_JSON='[{...}]' \
  asaikale/trading-bot:latest
```

### 3. Test
```bash
curl http://localhost:3000
```

---

## Kubernetes (15 minutes)

### 1. Update Secret
Edit `k8s/secret.yaml` and add all account credentials

### 2. Deploy
```bash
kubectl apply -f k8s/
```

### 3. Check
```bash
kubectl get pods -l app=trading-bot
kubectl logs -l app=trading-bot
```

### 4. Port Forward
```bash
kubectl port-forward svc/trading-bot 3000:3000
```

### 5. Test
```bash
curl http://localhost:3000
```

---

## Endpoints

### Health
- `GET /` - Server status

### Trades
- `POST /trade` - Send trade signal
- `GET /trades` - Get all trades
- `GET /trades/<id>` - Get specific trade

### Debug
- `GET /test` - Test connections
- `GET /debug/list` - List accounts
- `GET /debug/token/<account>` - Show token

---

Done! Read README.md for details.
