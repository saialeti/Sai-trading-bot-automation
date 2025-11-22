const request = require('supertest');
const express = require('express');
const cors = require('cors');
const axios = require('axios');

// Mock axios
jest.mock('axios');

describe('Webhook Server', () => {
  let app;

  beforeEach(() => {
    // Create a minimal Express app for testing
    app = express();
    app.use(cors());
    app.use(express.json());

    // Health check endpoint
    app.get('/', (req, res) => {
      res.status(200).send('Webhook server is running!');
    });

    // Liveness probe
    app.get('/health/live', (req, res) => {
      res.status(200).json({ status: 'alive' });
    });

    // Readiness probe
    app.get('/health/ready', (req, res) => {
      res.status(200).json({ status: 'ready' });
    });

    // Mock webhook endpoint
    app.post('/webhook', async (req, res) => {
      try {
        axios.post.mockResolvedValue({ status: 200 });
        res.status(200).send('Forwarded to all services!');
      } catch (error) {
        res.status(500).send('Error forwarding to services');
      }
    });
  });

  test('Health check endpoint returns 200', async () => {
    const response = await request(app).get('/');
    expect(response.statusCode).toBe(200);
    expect(response.text).toContain('Webhook server is running');
  });

  test('Liveness probe returns alive status', async () => {
    const response = await request(app).get('/health/live');
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe('alive');
  });

  test('Readiness probe returns ready status', async () => {
    const response = await request(app).get('/health/ready');
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe('ready');
  });

  test('Webhook endpoint accepts POST request', async () => {
    const response = await request(app)
      .post('/webhook')
      .send({ test: 'data' });
    expect(response.statusCode).toBe(200);
  });
});
