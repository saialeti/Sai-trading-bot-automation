const express = require('express');
const cors = require('cors');
const axios = require('axios');
const app = express();
const PORT = process.env.PORT || 3001;

// Get sensitive URLs from environment variables (Kubernetes secrets)
const DISCORD_WEBHOOK_URL = process.env.DISCORD_WEBHOOK_URL;
const TRADING_BOT_URL = process.env.TRADING_BOT_URL;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Webhook endpoint
app.post('/webhook', async (req, res) => {
  console.log('✅ Webhook received!');
  console.log('📩 Headers:', req.headers);
  console.log('📦 Body:', JSON.stringify(req.body, null, 2));
  console.log('🔗 Using Trading Bot URL:', TRADING_BOT_URL);
  
  try {
    // Send to trading bot
    const tradingBot_Response = await axios.post(TRADING_BOT_URL, req.body);
    console.log('✅ Order Placed');
    
    // Send to Discord
    const response = await axios.post(DISCORD_WEBHOOK_URL, req.body);
    console.log('✅ Sent to Discord!');
    
    res.status(200).send('Forwarded to all services!');
  } catch (error) {
    console.error('❌ Error sending to services:', error.response?.data || error.message);
    res.status(500).send('Error forwarding to services');
  }
});

// Health check endpoint
app.get('/', (req, res) => {
  res.status(200).send('Webhook server is running!');
});

// Liveness probe endpoint for Kubernetes
app.get('/health/live', (req, res) => {
  res.status(200).json({ status: 'alive' });
});

// Readiness probe endpoint for Kubernetes
app.get('/health/ready', (req, res) => {
  res.status(200).json({ status: 'ready' });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Webhook server running on port ${PORT}`);
});
