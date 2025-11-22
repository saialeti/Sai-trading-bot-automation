# 🚀 Trading Bot - START HERE

Welcome! This is your Python trading bot connected to TradeLocker.

## 📍 Location
```
~/Sai-trading-bot-automation/trading-bot/
```

## 📁 What You Have
```
trading-bot/
├── src/server.py              (Python Flask app)
├── requirements.txt           (Dependencies)
├── Dockerfile                 (Docker config)
├── k8s/                       (Kubernetes files)
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── deployment.yaml
│   └── service.yaml
└── [docs]                     (Documentation)
```

## ⚡ Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Set Credentials
```bash
export ACCOUNTS_JSON='[
  {
    "name": "Aleti Sai",
    "environment": "https://demo.tradelocker.com",
    "username": "saialeti657@gmail.com",
    "password": "U!i7qYK)6|",
    "server": "HEROFX"
  }
]'
```

### Step 3: Run
```bash
python src/server.py
```

✅ Bot running on http://localhost:3000

## 🐳 Docker

Build:
```bash
docker build -t asaikale/trading-bot:latest .
```

Run:
```bash
docker run -p 3000:3000 \
  -e ACCOUNTS_JSON='[...]' \
  asaikale/trading-bot:latest
```

## ☸️ Kubernetes

Deploy:
```bash
kubectl apply -f k8s/
```

Check:
```bash
kubectl get pods -l app=trading-bot
kubectl logs -l app=trading-bot
```

## 🔑 Key Files

- **src/server.py** - Main trading logic
- **requirements.txt** - Python packages
- **k8s/secret.yaml** - Account credentials
- **k8s/deployment.yaml** - Pod configuration

## 📚 Documentation
- **QUICKSTART.md** - 3-step deployment
- **README.md** - Full documentation
- **SETUP_GUIDE.md** - Detailed setup
- **QUICK_REFERENCE.txt** - Commands
- **FILES_SUMMARY.txt** - File descriptions

## 🧪 Test It

### Health Check
```bash
curl http://localhost:3000
```

### Test Connections
```bash
curl http://localhost:3000/test
```

### Send Trade Signal
```bash
curl -X POST http://localhost:3000/trade \
  -H "Content-Type: application/json" \
  -d '{
    "embeds": [{
      "title": "EURUSD",
      "description": "buy signal",
      "fields": [
        {"name": "Trade ID", "value": "TEST_001"},
        {"name": "Lot Size", "value": "1.5"},
        {"name": "Entry Price", "value": "1.1050"},
        {"name": "SL Price", "value": "1.1000"}
      ]
    }]
  }'
```

## 🔐 Important

⚠️ **Never commit k8s/secret.yaml!**
- Add to `.gitignore`
- Contains real credentials
- Only for K8s deployment

## 🚀 Next Steps

1. Read QUICKSTART.md
2. Test locally with `python src/server.py`
3. Build Docker image
4. Deploy to Kubernetes

Good luck! 🎯
