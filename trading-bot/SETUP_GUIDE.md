# 📖 Complete Setup Guide

## Prerequisites

- Python 3.11+
- Docker (for containerization)
- Minikube or kubectl (for Kubernetes)
- TradeLocker account credentials
- pip (Python package manager)

## Local Setup

### 1. Install Python Packages
```bash
cd ~/Sai-trading-bot-automation/trading-bot
pip install -r requirements.txt
```

Installs:
```
Flask==2.3.3          # Web framework
Flask-CORS==4.0.0     # Cross-origin requests
requests==2.31.0      # HTTP library
pandas==2.0.3         # Data processing
tradelocker           # TradeLocker API
Werkzeug==2.3.7       # WSGI utilities
```

### 2. Set Environment Variables

Option A: Temporary (this session only)
```bash
export ACCOUNTS_JSON='[{
  "name": "Aleti Sai",
  "environment": "https://demo.tradelocker.com",
  "username": "saialeti657@gmail.com",
  "password": "U!i7qYK)6|",
  "server": "HEROFX"
}]'

export PORT=3000
```

Option B: Permanent (save to .env)
```bash
cat > .env << 'EOF'
ACCOUNTS_JSON=[{...}]
PORT=3000
