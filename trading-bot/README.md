# Trading Bot

Python Flask trading bot that integrates with TradeLocker API.
Receives trade signals, manages multiple accounts, and stores all trades in SQLite.

## Features

✅ Multi-account support (11 accounts)
✅ Receives trade signals from webhook-server
✅ Places LIMIT orders on entry signals
✅ Cancels orders or closes positions on exit signals
✅ SQLite database for trade history
✅ Health check endpoints
✅ Docker containerized
✅ Kubernetes ready
✅ Non-root user (security)
✅ Auto token refresh (JWT)

## Installation

### Local
```bash
pip install -r requirements.txt
python src/server.py
```

### Docker
```bash
docker build -t asaikale/trading-bot:latest .
docker run -p 3000:3000 \
  -e ACCOUNTS_JSON='[...]' \
  asaikale/trading-bot:latest
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

## Environment Variables
```bash
ACCOUNTS_JSON          # JSON array with account credentials (from Secret)
PORT                   # Server port (default: 3000)
DB_FILE               # SQLite database file (default: trades.db)
LOG_LEVEL             # Logging level (default: INFO)
FLASK_ENV             # Flask environment (default: production)
```

## API Endpoints

### Health
- `GET /` - Health check & statistics

### Trade Management
- `POST /trade` - Receive and process trade signals
- `GET /trades` - Get all trades from database
- `GET /trades/<trade_id>` - Get specific trade

### Testing
- `GET /test` - Test account connections
- `GET /debug/list` - List active accounts
- `GET /debug/token/<account_name>` - Show token info
- `POST /debug/invalidate/<account_name>` - Force token refresh

## Trade Signal Format

### Entry Signal (BUY/SELL)
```json
{
  "embeds": [{
    "title": "EURUSD",
    "description": "🔵 buy signal",
    "fields": [
      {"name": "Trade ID", "value": "SIGNAL_001"},
      {"name": "Lot Size", "value": "1.5"},
      {"name": "Entry Price", "value": "1.1050"},
      {"name": "SL Price", "value": "1.1000"}
    ]
  }]
}
```

### Exit Signal (CLOSE)
```json
{
  "embeds": [{
    "title": "EURUSD",
    "description": "close signal",
    "fields": [
      {"name": "Side", "value": "buy"},
      {"name": "Lot Size", "value": "1.5"}
    ]
  }]
}
```

## Database

SQLite database (`trades.db`) stores:
- Trade ID, account name, symbol
- Entry price, lot size, stop loss
- Order ID, position ID, status
- Close timestamp, realized P&L
- Close method (ORDER_CANCELLED or POSITION_CLOSED)

## Architecture
```
Pine Script Signal
    ↓
Webhook Server (port 3001)
    ↓
Trading Bot (port 3000)
    ↓
TradeLocker API (11 accounts)
    ↓
Database (trades.db)
```

## Troubleshooting

### Account connection failed
- Check ACCOUNTS_JSON format
- Verify TradeLocker credentials
- Check internet connection

### Order placement failed
- Verify symbol exists on TradeLocker
- Check account balance
- Verify order parameters (lot size, price)

### Token expiration
- Bot auto-refreshes JWT tokens
- Use `/debug/reauth/<account>` endpoint to force refresh

## Files
```
src/server.py              # Main Flask app
requirements.txt          # Python dependencies
Dockerfile               # Docker build
k8s/                     # Kubernetes manifests
  configmap.yaml         # Configuration
  secret.yaml           # Secrets (credentials)
  deployment.yaml       # Pod deployment
  service.yaml          # Network service
```

## License

MIT
