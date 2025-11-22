#!/usr/bin/env python3
"""
UPDATED Complete Multi-Account TradeLocker Trading Bot
Fixed with working order cancellation method from original code
Handles both entry and exit signals from Pine Script
- Entry signals: Places LIMIT orders
- Exit signals: Cancels pending orders (tl.delete_order) OR closes filled positions (DELETE API)
Saves all trade details to SQLite database
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import logging
import json
import os
from datetime import datetime
from contextlib import contextmanager
import requests
import time
import pandas as pd
from tradelocker import TLAPI
import base64
from typing import Optional, Tuple
import threading
import random


def _mask(tok: Optional[str], head: int = 6, tail: int = 4) -> str:
    if not tok:
        return ""
    if len(tok) <= head + tail:
        return tok
    return f"{tok[:head]}...{tok[-tail:]}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _jwt_expiry_info(token: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """
    Returns (exp_unix, seconds_left) from a JWT without verifying signature.
    If token missing/invalid, returns (None, None).
    """
    try:
        if not token or token.count(".") < 2:
            return (None, None)
        header_b64, payload_b64, _ = token.split(".", 2)
        # add padding for base64
        def _fixpad(s: str) -> bytes:
            return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        payload = json.loads(_fixpad(payload_b64))
        exp = payload.get("exp")
        if not isinstance(exp, int):
            return (None, None)
        now = int(time.time())
        return (exp, exp - now)
    except Exception:
        return (None, None)


# ---- Per-account lightweight rate limit + 429 backoff ----
_last_call_at = {}                 # key: (account_name, endpoint_key) -> last call epoch
_last_call_lock = threading.Lock()
MIN_GAP_SEC = 0.40                 # ~2.5 req/sec per endpoint/account; raise to 0.6–0.8 if needed


def _respect_rate_limit(account_name: str, endpoint_key: str, min_gap: float = MIN_GAP_SEC):
    now = time.time()
    with _last_call_lock:
        last = _last_call_at.get((account_name, endpoint_key), 0.0)
        wait = (last + min_gap) - now
        if wait > 0:
            time.sleep(wait)
        _last_call_at[(account_name, endpoint_key)] = time.time()


def _with_429_backoff(req_fn, account_name: str, endpoint_key: str, max_attempts: int = 4):
    """
    Execute req_fn() with per-account rate limiting and exponential backoff on HTTP 429.
    req_fn must be a zero-arg callable that performs ONE SDK call (e.g., tl.get_all_orders).
    """
    delay = MIN_GAP_SEC
    for attempt in range(1, max_attempts + 1):
        _respect_rate_limit(account_name, endpoint_key)
        try:
            return req_fn()
        except Exception as e:
            msg = str(e)
            is_429 = ("429" in msg) or ("Too Many Requests" in msg)
            if not is_429:
                # Not a rate-limit error: bubble up
                raise
            # Use Retry-After if present; else exponential + small jitter
            retry_after = None
            try:
                resp = getattr(e, "response", None)
                if resp is not None:
                    ra = resp.headers.get("Retry-After")
                    if ra is not None:
                        retry_after = float(ra)
            except Exception:
                pass
            sleep_s = retry_after if retry_after is not None else (delay + random.uniform(0.05, 0.25))
            logger.warning(f"[{account_name}] 429 on {endpoint_key}; sleeping {sleep_s:.2f}s (attempt {attempt}/{max_attempts})")
            time.sleep(sleep_s)
            delay *= 1.6
    raise RuntimeError(f"[{account_name}] Too Many Requests on {endpoint_key} after {max_attempts} attempts")


def _expired_jwt() -> str:
    """
    Makes a trivially expired JWT (alg=none style string) for testing client-side expiry logic.
    Not meant to be sent to server—only so TLAPI's time_to_token_expiry() sees it as expired.
    """
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"exp": 1}).encode())  # Jan 1, 1970 + 1s
    sig = ""  # no signature content
    return f"{header}.{payload}."


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration (from ConfigMap/Environment)
DB_FILE = os.getenv('DB_FILE', 'trades.db')
PORT = int(os.getenv('PORT', 3000))
ENVIRONMENT = os.getenv('ENVIRONMENT', 'https://demo.tradelocker.com')
SERVER = os.getenv('SERVER', 'HEROFX')

# Account Configuration - will be loaded from Kubernetes Secrets
ACCOUNTS = []

# Per-account instrument cache
instrument_cache = {}  # {account_name: DataFrame}

# Global variables
tl_accounts = {}  # Store TradeLocker API instances
active_accounts = []  # List of successfully connected accounts


def init_database():
    """Initialize SQLite database with trades table including exit fields"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    lot_size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    sl_price REAL DEFAULT 0,
                    order_id TEXT,
                    position_id TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    close_timestamp TIMESTAMP,
                    close_position_id TEXT,
                    close_order_id TEXT,
                    realized_pnl REAL DEFAULT 0,
                    close_method TEXT,
                    UNIQUE(trade_id, account_name)
                )
            ''')

            # Create indexes for faster queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_trade_id ON trades(trade_id)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_account_status ON trades(account_name, status)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_status ON trades(status)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_symbol_side_lot ON trades(symbol, side, lot_size, status)
            ''')

            conn.commit()
            logger.info("✅ Database initialized successfully")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    try:
        yield conn
    finally:
        conn.close()


def save_trade_to_db(trade_id, account_name, symbol, side, lot_size, entry_price, sl_price=0, order_id=None, metadata=None):
    """Save trade information to database"""
    try:
        with get_db_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO trades
                (trade_id, account_name, symbol, side, lot_size, entry_price, sl_price,
                 order_id, status, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, CURRENT_TIMESTAMP)
            ''', (trade_id, account_name, symbol, side, lot_size, entry_price, sl_price,
                  order_id, json.dumps(metadata) if metadata else None))

            conn.commit()
            logger.info(f"💾 Saved trade {trade_id} to database for {account_name}")

    except Exception as e:
        logger.error(f"❌ Error saving trade to database: {e}")
        raise


def update_trade_status(trade_id, account_name, status, position_id=None, metadata=None):
    """Update trade status in database"""
    try:
        with get_db_connection() as conn:
            if position_id:
                conn.execute('''
                    UPDATE trades
                    SET status = ?, position_id = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE trade_id = ? AND account_name = ?
                ''', (status, position_id, json.dumps(metadata) if metadata else None, trade_id, account_name))
            else:
                conn.execute('''
                    UPDATE trades
                    SET status = ?, metadata = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE trade_id = ? AND account_name = ?
                ''', (status, json.dumps(metadata) if metadata else None, trade_id, account_name))

            conn.commit()
            logger.info(f"💾 Updated trade {trade_id} status to {status} for {account_name}")

    except Exception as e:
        logger.error(f"❌ Error updating trade status: {e}")


def close_trade_in_db(account_name, symbol, side, lot_size, close_method, position_id=None, order_id=None, realized_pnl=0):
    """Update database when a trade is closed"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('''
                UPDATE trades
                SET status = 'CLOSED',
                    close_timestamp = CURRENT_TIMESTAMP,
                    close_position_id = ?,
                    close_order_id = ?,
                    realized_pnl = ?,
                    close_method = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE account_name = ? AND symbol = ? AND side = ? AND lot_size = ?
                  AND status IN ('PENDING', 'FILLED')
                  AND close_timestamp IS NULL
                ORDER BY created_at DESC
                LIMIT 1
            ''', (position_id, order_id, realized_pnl, close_method, account_name, symbol, side, lot_size))

            if cursor.rowcount and cursor.rowcount > 0:
                conn.commit()
                logger.info(f"💾 Closed trade in database: {account_name} {symbol} {side} {lot_size}")
                return True
            else:
                logger.warning(f"⚠️ No matching trade found to close: {account_name} {symbol} {side} {lot_size}")
                return False
    except Exception as e:
        logger.error(f"❌ Error closing trade in database: {e}")
        return False


def load_accounts_from_env():
    """Load accounts from environment variables (from Kubernetes Secrets)"""
    global ACCOUNTS
    try:
        accounts_json = os.getenv('ACCOUNTS_JSON', '[]')
        ACCOUNTS = json.loads(accounts_json)
        logger.info(f"✅ Loaded {len(ACCOUNTS)} accounts from environment")
    except Exception as e:
        logger.error(f"❌ Error loading accounts from environment: {e}")
        ACCOUNTS = []


def initialize_accounts():
    """Initialize all TradeLocker accounts"""
    global tl_accounts, active_accounts

    logger.info("🔐 Initializing TradeLocker Accounts...")
    connection_results = {}

    for account_config in ACCOUNTS:
        account_name = account_config.get("name", "Unknown")
        try:
            logger.info(f"Connecting to {account_name}...")

            # Initialize TradeLocker API
            tl_instance = TLAPI(
                environment=account_config.get("environment", ENVIRONMENT),
                username=account_config.get("username"),
                password=account_config.get("password"),
                server=account_config.get("server", SERVER)
            )
            # tag client with its account name (for instrument_cache scoping)
            tl_instance.account_name = account_name

            # Test connection
            try:
                accounts_info = tl_instance.get_all_accounts()
                if accounts_info is not None:
                    tl_accounts[account_name] = tl_instance
                    active_accounts.append(account_name)
                    connection_results[account_name] = "✅ CONNECTED"
                    logger.info(f"✅ {account_name} connected successfully")
                else:
                    connection_results[account_name] = "❌ FAILED - No account data"
                    logger.error(f"❌ {account_name} failed - No account data received")

            except Exception as conn_error:
                connection_results[account_name] = f"❌ FAILED - {str(conn_error)}"
                logger.error(f"❌ {account_name} connection test failed: {conn_error}")

        except Exception as e:
            connection_results[account_name] = f"❌ FAILED - {str(e)}"
            logger.error(f"❌ {account_name} initialization failed: {e}")

    # Display connection summary
    print("\n" + "="*60)
    print("📊 ACCOUNT CONNECTION SUMMARY")
    print("="*60)
    for account_config in ACCOUNTS:
        account_name = account_config.get("name", "Unknown")
        status = connection_results.get(account_name, "❌ FAILED")
        server = account_config.get("server", SERVER)
        print(f"{account_name:<20} ({server:<15}) - {status}")
    print("="*60)
    print(f"📈 RESULT: {len(active_accounts)}/{len(ACCOUNTS)} accounts connected")
    print("")

    return len(active_accounts) > 0


def determine_signal_type(description):
    """Determine signal type from description"""
    description = description.lower()
    if "buy signal" in description or "🔵 buy signal" in description:
        return "BUY"
    elif "sell signal" in description or "🔴 sell signal" in description:
        return "SELL"
    elif "close signal" in description or "exit signal" in description or "close" in description:
        return "CLOSE"
    else:
        return "UNKNOWN"


def validate_trade_parameters(lot_size, entry_price, trade_id):
    """Validate trade parameters"""
    errors = []

    if not trade_id or trade_id.strip() == "":
        errors.append("Trade ID is required")

    if lot_size <= 0:
        errors.append(f"Invalid lot size: {lot_size}")

    if entry_price <= 0:
        errors.append(f"Invalid entry price: {entry_price}")

    return errors


def validate_exit_parameters(symbol, side, lot_size):
    """Validate exit signal parameters"""
    errors = []

    if not symbol or symbol.strip() == "":
        errors.append("Symbol is required")

    if side not in ["buy", "sell", "BUY", "SELL"]:
        errors.append(f"Invalid side: {side}")

    if lot_size <= 0:
        errors.append(f"Invalid lot size: {lot_size}")

    return errors


def get_symbol_from_instrument_id(tl_instance, instrument_id):
    """
    Map instrument_id -> symbol using per-account instrument_cache only.
    Caller is responsible for prefetching instruments into instrument_cache[account_name].
    """
    try:
        name = getattr(tl_instance, "account_name", None) or "default"
        df = instrument_cache.get(name)
        if df is None:
            # Do NOT trigger a network call here; just report miss.
            logger.debug(f"No instrument cache for {name}; returning None for id={instrument_id}")
            return None
        if isinstance(df, pd.DataFrame):
            m = df[df['tradableInstrumentId'] == instrument_id]
            if not m.empty:
                return m.iloc[0]['name']
        return None
    except Exception as e:
        logger.error(f"Error mapping instrument ID: {e}")
        return None


def place_limit_order(tl_instance, symbol, side, lot_size, entry_price, sl_price=0):
    """Place a LIMIT order via TradeLocker API"""
    try:
        # Get instrument ID from symbol
        instrument_id = tl_instance.get_instrument_id_from_symbol_name(symbol)
        if not instrument_id:
            raise Exception(f"Symbol {symbol} not found")

        # Prepare order parameters
        order_params = {
            "instrument_id": instrument_id,
            "quantity": lot_size,
            "side": side,
            "price": entry_price,  # This makes it a LIMIT order
            "type_": "limit",      # Explicitly set as limit order
            "validity": "GTC"      # Good Till Cancelled
        }

        # Add stop loss if provided
        if sl_price > 0:
            order_params["stop_loss"] = sl_price
            order_params["stop_loss_type"] = "absolute"

        # Place the order
        order_id = tl_instance.create_order(**order_params)

        if order_id:
            logger.info(f"📤 LIMIT order placed: ID {order_id}")
            return order_id
        else:
            raise Exception("Order placement returned None")

    except Exception as e:
        logger.error(f"❌ Error placing LIMIT order: {e}")
        raise


def cancel_pending_order(tl_instance, order_id, account_name=None):
    try:
        name = account_name or getattr(tl_instance, "account_name", "unknown")
        logger.info(f"🚫 Cancelling pending order: ID {order_id}")
        success = _with_429_backoff(lambda: tl_instance.delete_order(order_id),
                                    name, "delete_order")
        if success:
            logger.info(f"✅ Order cancelled successfully: ID {order_id}")
            return True
        logger.error(f"❌ Order cancellation failed: ID {order_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Error cancelling order: {e}")
        return False


def _position_absent(tl: TLAPI, position_id: str) -> bool:
    """Return True if position is no longer present."""
    try:
        pos_df = tl.get_all_positions()
        if pos_df is None or pos_df.empty:
            return True
        return str(position_id) not in set(map(str, pos_df['id']))
    except Exception:
        # If we can't fetch positions, don't claim it's absent
        return False


def close_filled_position_safe(tl: TLAPI, position_id: str, *, base_url: str = None, max_retries: int = 2, poll_seconds: float = 0.75) -> bool:
    """
    Robust close:
      - Always fetch fresh token via tl.get_access_token()
      - Use correct accNum header from tl.acc_num
      - Retry on 401/403 (auth), 409 (in-progress), 429/5xx (backoff)
      - 404 is OK if the position is actually gone
    """
    if not base_url:
        base_url = getattr(tl, "environment", None) or "https://demo.tradelocker.com"

    url = f"{base_url.rstrip('/')}/backend-api/trade/positions/{position_id}"

    def _headers() -> dict:
        token = tl.get_access_token()  # <-- uses your TLAPI auth/refresh
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {token}",
            "accNum": str(getattr(tl, "acc_num", ""))  # <-- real account number, NOT hardcoded
        }

    backoff = 0.8
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.delete(url, headers=_headers(), timeout=30)
            code = resp.status_code

            if code in (200, 204):
                return True

            if code == 404:
                if _position_absent(tl, position_id):
                    return True
                # else retry below

            if code in (401, 403):  # auth/token issue
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 1.5
                    continue
                return False

            if code == 409:  # conflict/in-progress
                time.sleep(poll_seconds)
                if _position_absent(tl, position_id):
                    return True
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 1.5
                    continue
                return False

            if code in (429, 500, 502, 503, 504):  # rate/server
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 1.5
                    continue
                return False

            # Unexpected → one more try if available
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 1.5
                continue
            return False

        except requests.RequestException:
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 1.5
                continue
            return False


@app.route('/', methods=['GET'])
def health():
    """Health check endpoint"""
    try:
        # Get active trade counts from database
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT account_name, status, COUNT(*) as count
                FROM trades
                GROUP BY account_name, status
            ''')
            trade_stats = {}
            for row in cursor.fetchall():
                account = row['account_name']
                if account not in trade_stats:
                    trade_stats[account] = {}
                trade_stats[account][row['status']] = row['count']

        return jsonify({
            "status": "🟢 TradeLocker Trading Bot - ACTIVE",
            "version": "2.1 - FIXED Entry & Exit Signals",
            "timestamp": datetime.now().isoformat(),
            "active_accounts": len(active_accounts),
            "configured_accounts": len(ACCOUNTS),
            "account_names": active_accounts,
            "database_file": DB_FILE,
            "trade_statistics": trade_stats
        }), 200

    except Exception as e:
        return jsonify({
            "status": "🔴 Error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/trade', methods=['POST'])
def handle_trade_signal():
    """Main endpoint to handle Pine Script signals - both entry and exit"""
    try:
        data = request.json
        logger.info(f"📥 Received signal: {json.dumps(data, indent=2)}")

        if not active_accounts:
            return jsonify({"error": "No active accounts available"}), 500

        # Validate data structure
        if not data or "embeds" not in data or not data["embeds"]:
            return jsonify({"error": "Invalid data structure - missing embeds"}), 400

        embed = data["embeds"][0]
        symbol = embed.get("title", "").strip()
        description = embed.get("description", "").lower()

        if not symbol:
            return jsonify({"error": "Missing symbol in title"}), 400

        # Parse fields
        fields = {}
        if "fields" in embed:
            for field in embed["fields"]:
                fields[field["name"]] = field["value"]

        # Determine signal type
        signal_type = determine_signal_type(description)
        logger.info(f"🎯 Signal Type: {signal_type} for {symbol}")

        # Handle different signal types
        if signal_type in ["BUY", "SELL"]:
            return handle_entry_signal(symbol, signal_type, fields, description)
        elif signal_type == "CLOSE":
            return handle_exit_signal(symbol, fields, description)
        else:
            return jsonify({
                "error": f"Signal type '{signal_type}' not supported",
                "message": "Supported: BUY, SELL, CLOSE signals"
            }), 400

    except Exception as e:
        logger.error(f"❌ Error processing signal: {e}")
        return jsonify({"error": str(e)}), 500


def handle_entry_signal(symbol, signal_type, fields, description):
    """Handle BUY/SELL entry signals - Place LIMIT orders on all accounts"""
    try:
        logger.info(f"🚀 Processing {signal_type} ENTRY for {symbol}")

        # Extract parameters
        trade_id = fields.get("Trade ID", "")
        lot_size = float(fields.get("Lot Size", 0))
        entry_price = float(fields.get("Entry Price", 0))
        sl_price = float(fields.get("SL Price", 0))

        # Validate parameters
        validation_errors = validate_trade_parameters(lot_size, entry_price, trade_id)
        if validation_errors:
            return jsonify({
                "error": "Validation failed",
                "validation_errors": validation_errors
            }), 400

        # Determine order side
        side = "buy" if signal_type == "BUY" else "sell"

        logger.info("📊 Order Parameters:")
        logger.info(f"   Trade ID: {trade_id}")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Side: {side.upper()}")
        logger.info(f"   Lot Size: {lot_size}")
        logger.info(f"   Entry Price: {entry_price}")
        logger.info(f"   Stop Loss: {sl_price}")

        # Execute on all active accounts
        account_results = {}
        successful_count = 0
        failed_count = 0

        for account_name in active_accounts:
            try:
                # Optional stagger to avoid API bursts (prevents 429)
                time.sleep(0.1 + random.uniform(0.0, 0.15))

                logger.info(f"📤 Placing order on {account_name}...")
                tl = tl_accounts[account_name]

                # Place LIMIT order
                order_id = place_limit_order(tl, symbol, side, lot_size, entry_price, sl_price)

                # Save to database
                metadata = {
                    "signal_type": signal_type,
                    "description": description,
                    "entry_timestamp": datetime.now().isoformat()
                }

                save_trade_to_db(
                    trade_id=trade_id,
                    account_name=account_name,
                    symbol=symbol,
                    side=side,
                    lot_size=lot_size,
                    entry_price=entry_price,
                    sl_price=sl_price,
                    order_id=str(order_id),
                    metadata=metadata
                )

                account_results[account_name] = {
                    "status": "SUCCESS",
                    "order_id": order_id,
                    "trade_id": trade_id,
                    "message": "LIMIT order placed and saved to database"
                }

                successful_count += 1
                logger.info(f"✅ {account_name}: Order placed successfully (ID: {order_id})")

            except Exception as e:
                account_results[account_name] = {
                    "status": "FAILED",
                    "error": str(e),
                    "trade_id": trade_id
                }
                failed_count += 1
                logger.error(f"❌ {account_name}: Order failed - {e}")

        # Summary
        logger.info(f"📊 ENTRY Summary: {successful_count} successful, {failed_count} failed")

        return jsonify({
            "status": "COMPLETED",
            "message": f"{side.upper()} LIMIT orders execution completed",
            "trade_id": trade_id,
            "symbol": symbol,
            "order_type": "LIMIT",
            "side": side.upper(),
            "lot_size": lot_size,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "summary": {
                "total_accounts": len(active_accounts),
                "successful": successful_count,
                "failed": failed_count
            },
            "account_results": account_results,
            "timestamp": datetime.now().isoformat()
        }), 200

    except ValueError as e:
        logger.error(f"❌ Invalid numeric values: {e}")
        return jsonify({"error": f"Invalid numeric values: {e}"}), 400
    except Exception as e:
        logger.error(f"❌ Error in entry signal handling: {e}")
        return jsonify({"error": str(e)}), 500


def handle_exit_signal(symbol, fields, description):
    """Handle CLOSE/EXIT signals - Cancel pending orders OR close filled positions (token-safe, 429-aware)."""
    try:
        logger.info(f"🔚 Processing FIXED EXIT signal for {symbol}")

        # Extract parameters
        side = fields.get("Side", "").lower()
        lot_size = float(fields.get("Lot Size", 0))

        # Validate parameters
        validation_errors = validate_exit_parameters(symbol, side, lot_size)
        if validation_errors:
            return jsonify({
                "error": "Exit validation failed",
                "validation_errors": validation_errors
            }), 400

        logger.info("📊 Exit Parameters:")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Side: {side.upper()}")
        logger.info(f"   Lot Size: {lot_size}")

        # Execute on all active accounts
        account_results = {}
        successful_count = 0
        no_position_count = 0
        failed_count = 0

        for account_name in active_accounts:
            try:
                logger.info(f"🔍 Processing FIXED exit for {account_name}...")
                tl = tl_accounts[account_name]

                # --- Fetch once per account (rate-limited + 429 backoff) ---
                orders = None
                positions = None

                try:
                    orders = _with_429_backoff(lambda: tl.get_all_orders(), account_name, "orders")
                except Exception as order_pull_err:
                    logger.warning(f"⚠️ {account_name} orders pull failed: {order_pull_err}")

                try:
                    positions = _with_429_backoff(lambda: tl.get_all_positions(), account_name, "positions")
                except Exception as pos_pull_err:
                    logger.warning(f"⚠️ {account_name} positions pull failed: {pos_pull_err}")

                # Prefetch instruments if cache missing for this account
                if account_name not in instrument_cache or not isinstance(instrument_cache[account_name], pd.DataFrame):
                    try:
                        instruments_df = _with_429_backoff(lambda: tl.get_all_instruments(), account_name, "instruments")
                        instrument_cache[account_name] = instruments_df
                    except Exception as inst_err:
                        logger.warning(f"⚠️ {account_name} instruments pull failed: {inst_err}")

                # ---- Step 1: cancel pending orders if any ----
                order_cancelled = False
                try:
                    if orders is not None and not orders.empty:
                        for _, order in orders.iterrows():
                            order_instrument_id = order['tradableInstrumentId']
                            order_symbol = get_symbol_from_instrument_id(tl, order_instrument_id)
                            order_side = order['side']
                            order_qty = order['qty']

                            # Match: symbol + side + lot size
                            if (
                                order_symbol == symbol and
                                order_side == side and
                                abs(order_qty - lot_size) < 0.001  # float tolerance
                            ):
                                logger.info(f"📋 Found matching pending order: {order['id']}")
                                if cancel_pending_order(tl, order['id']):
                                    # Update DB
                                    close_trade_in_db(
                                        account_name, symbol, side, lot_size,
                                        "ORDER_CANCELLED", order_id=str(order['id'])
                                    )

                                    account_results[account_name] = {
                                        "status": "SUCCESS",
                                        "action": "ORDER_CANCELLED",
                                        "message": f"{symbol} {side.upper()} {lot_size} - Order ID {order['id']} cancelled",
                                        "order_id": str(order['id'])
                                    }
                                    order_cancelled = True
                                    successful_count += 1
                                    break
                                else:
                                    raise Exception(f"Failed to cancel order {order['id']}")
                except Exception as order_error:
                    logger.warning(f"⚠️ Order processing failed for {account_name}: {order_error}")

                # ---- Step 2: close position if nothing cancelled ----
                if not order_cancelled:
                    position_closed = False
                    try:
                        if positions is not None and not positions.empty:
                            for _, position in positions.iterrows():
                                pos_instrument_id = position['tradableInstrumentId']
                                pos_symbol = get_symbol_from_instrument_id(tl, pos_instrument_id)
                                pos_side = position['side']
                                pos_qty = position['qty']
                                pos_unrealized_pnl = position.get('unrealizedPl', 0)

                                if (
                                    pos_symbol == symbol and
                                    pos_side == side and
                                    abs(pos_qty - lot_size) < 0.001
                                ):
                                    logger.info(f"📍 Found matching position: {position['id']}")

                                    # ✅ Token-safe close
                                    if close_filled_position_safe(tl, str(position['id'])):
                                        close_trade_in_db(
                                            account_name, symbol, side, lot_size,
                                            "POSITION_CLOSED", position_id=str(position['id']),
                                            realized_pnl=pos_unrealized_pnl
                                        )
                                        account_results[account_name] = {
                                            "status": "SUCCESS",
                                            "action": "POSITION_CLOSED",
                                            "message": f"{symbol} {side.upper()} {lot_size} - Position ID {position['id']} closed",
                                            "position_id": str(position['id']),
                                            "realized_pnl": pos_unrealized_pnl
                                        }
                                        position_closed = True
                                        successful_count += 1
                                        break
                                    else:
                                        raise Exception(f"Failed to close position {position['id']}")

                        if not position_closed:
                            account_results[account_name] = {
                                "status": "NO_POSITION_FOUND",
                                "message": f"No {symbol} {side.upper()} position with lot size {lot_size} found"
                            }
                            no_position_count += 1
                    except Exception as position_error:
                        logger.error(f"❌ Position processing failed for {account_name}: {position_error}")
                        failed_count += 1

                # If nothing happened and no result set, record as not found
                if not order_cancelled and account_name not in account_results:
                    account_results[account_name] = {
                        "status": "NO_POSITION_FOUND",
                        "message": f"No {symbol} {side.upper()} order or position with lot size {lot_size} found"
                    }
                    no_position_count += 1

            except Exception as e:
                account_results[account_name] = {
                    "status": "FAILED",
                    "error": str(e)
                }
                failed_count += 1
                logger.error(f"❌ {account_name}: Exit processing failed - {e}")

        # Summary
        logger.info(
            f"📊 FIXED EXIT Summary: {successful_count} successful, "
            f"{no_position_count} no position, {failed_count} failed"
        )

        return jsonify({
            "status": "COMPLETED",
            "message": f"FIXED EXIT signals execution completed for {symbol}",
            "symbol": symbol,
            "side": side.upper(),
            "lot_size": lot_size,
            "summary": {
                "total_accounts": len(active_accounts),
                "successful_closes": successful_count,
                "no_position_found": no_position_count,
                "failed": failed_count
            },
            "account_results": account_results,
            "timestamp": datetime.now().isoformat()
        }), 200

    except ValueError as e:
        logger.error(f"❌ Invalid numeric values in exit signal: {e}")
        return jsonify({"error": f"Invalid numeric values: {e}"}), 400
    except Exception as e:
        logger.error(f"❌ Error in exit signal handling: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/trades', methods=['GET'])
def get_all_trades():
    """Get all trades from database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM trades
                ORDER BY created_at DESC
            ''')

            trades = [dict(row) for row in cursor.fetchall()]

            # Parse metadata JSON
            for trade in trades:
                if trade['metadata']:
                    try:
                        trade['metadata'] = json.loads(trade['metadata'])
                    except:
                        pass

            # Group by status for summary
            status_summary = {}
            for trade in trades:
                status = trade['status']
                status_summary[status] = status_summary.get(status, 0) + 1

        return jsonify({
            "status": "SUCCESS",
            "total_trades": len(trades),
            "status_summary": status_summary,
            "trades": trades,
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"❌ Error fetching trades: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/trades/<trade_id>', methods=['GET'])
def get_trade_by_id(trade_id):
    """Get specific trade by trade_id"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM trades WHERE trade_id = ?
                ORDER BY created_at DESC
            ''', (trade_id,))

            trades = [dict(row) for row in cursor.fetchall()]

            # Parse metadata
            for trade in trades:
                if trade['metadata']:
                    try:
                        trade['metadata'] = json.loads(trade['metadata'])
                    except:
                        pass

        if not trades:
            return jsonify({
                "status": "NOT_FOUND",
                "message": f"No trades found for trade_id: {trade_id}"
            }), 404

        return jsonify({
            "status": "SUCCESS",
            "trade_id": trade_id,
            "trades_found": len(trades),
            "trades": trades,
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"❌ Error fetching trade by ID: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/test', methods=['GET'])
def test_connections():
    """Test TradeLocker connections for all accounts"""
    try:
        test_results = {}

        for account_name in active_accounts:
            try:
                tl = tl_accounts[account_name]
                accounts = tl.get_all_accounts()
                test_results[account_name] = {
                    "status": "✅ CONNECTED",
                    "account_info": str(accounts) if accounts is not None else "No data"
                }
            except Exception as e:
                test_results[account_name] = {
                    "status": "❌ FAILED",
                    "error": str(e)
                }

        return jsonify({
            "status": "Connection Test Results",
            "active_accounts": len(active_accounts),
            "test_results": test_results,
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/debug/list', methods=['GET'])
def debug_list_accounts():
    """Lists active accounts and whether we can fetch an access token."""
    results = {}
    for name in active_accounts:
        tl = tl_accounts[name]
        try:
            tok = tl.get_access_token()
            exp, left = _jwt_expiry_info(tok)
            results[name] = {
                "environment": getattr(tl, "environment", None),
                "accNum": str(getattr(tl, "acc_num", "")),
                "access_token_mask": _mask(tok),
                "exp_unix": exp,
                "seconds_left": left
            }
        except Exception as e:
            results[name] = {"error": str(e)}
    return jsonify({"accounts": results, "timestamp": datetime.now().isoformat()}), 200


@app.route('/debug/token/<account_name>', methods=['GET'])
def debug_show_token(account_name):
    """Shows masked token + expiry info for a specific account."""
    if account_name not in tl_accounts:
        return jsonify({"error": f"Unknown account '{account_name}'"}), 404
    try:
        tl = tl_accounts[account_name]
        tok = tl.get_access_token()
        exp, left = _jwt_expiry_info(tok)
        return jsonify({
            "account": account_name,
            "environment": getattr(tl, "environment", None),
            "accNum": str(getattr(tl, "acc_num", "")),
            "access_token_mask": _mask(tok),
            "exp_unix": exp,
            "seconds_left": left,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/debug/invalidate/<account_name>', methods=['POST'])
def debug_invalidate_tokens(account_name):
    """Forces tokens to be 'expired' locally so next call reauths."""
    if account_name not in tl_accounts:
        return jsonify({"error": f"Unknown account '{account_name}'"}), 404
    tl = tl_accounts[account_name]
    try:
        expired = _expired_jwt()
        if hasattr(tl, "_auth_with_tokens"):
            tl._auth_with_tokens(expired, expired)
        else:
            setattr(tl, "_access_token", expired)
            setattr(tl, "_refresh_token", expired)
        tok = tl.get_access_token()
        exp, left = _jwt_expiry_info(tok)
        return jsonify({
            "account": account_name,
            "message": "Tokens invalidated & refreshed.",
            "new_access_token_mask": _mask(tok),
            "exp_unix": exp,
            "seconds_left": left,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/debug/reauth/<account_name>', methods=['POST'])
def debug_force_reauth(account_name):
    """Triggers a fresh access token retrieval."""
    if account_name not in tl_accounts:
        return jsonify({"error": f"Unknown account '{account_name}'"}), 404
    tl = tl_accounts[account_name]
    try:
        before = tl.get_access_token()
        b_mask = _mask(before)
        b_exp, b_left = _jwt_expiry_info(before)

        after = tl.get_access_token()
        a_mask = _mask(after)
        a_exp, a_left = _jwt_expiry_info(after)

        return jsonify({
            "account": account_name,
            "before": {"mask": b_mask, "exp_unix": b_exp, "seconds_left": b_left},
            "after":  {"mask": a_mask, "exp_unix": a_exp, "seconds_left": a_left},
            "token_changed": before != after,
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 STARTING FIXED COMPLETE TRADELOCKER TRADING BOT")
    print("="*70)

    # Initialize database
    try:
        init_database()
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        exit(1)

    # Load accounts from environment (Kubernetes Secrets)
    load_accounts_from_env()

    # Initialize accounts
    if initialize_accounts():
        logger.info(f"✅ Bot initialized with {len(active_accounts)} active accounts")
        logger.info("📡 Listening for Pine Script signals on port 3000...")
        logger.info("🎯 Supported Signals:")
        logger.info("   • BUY/SELL entry → LIMIT orders + database storage")
        logger.info("   • CLOSE/EXIT → FIXED: Cancel orders (tl.delete_order) OR close positions (DELETE API)")
        logger.info("\n📊 Available Endpoints:")
        logger.info("   POST /trade              - Handle Pine Script signals (entry & exit)")
        logger.info("   GET  /trades             - View all trades in database")
        logger.info("   GET  /trades/<trade_id>  - View specific trade")
        logger.info("   GET  /test               - Test account connections")
        logger.info("   GET  /                   - Health check")
        logger.info("   GET  /debug/list         - List all active accounts")
        logger.info("   GET  /debug/token/<account>  - Show token info")
        logger.info("   POST /debug/invalidate/<account> - Force token refresh")
        logger.info("   POST /debug/reauth/<account>   - Re-authenticate account")
        print("="*70)

        # Start Flask server
        app.run(host='0.0.0.0', port=PORT, debug=False)

    else:
        logger.error("❌ No accounts could be initialized. Please check your credentials.")
        logger.error("Update the ACCOUNTS_JSON environment variable with your TradeLocker credentials.")
        exit(1)
