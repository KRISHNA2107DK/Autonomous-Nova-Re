'use strict';

/**
 * notification-service — consumes order/payment events from Redis pub/sub.
 *
 *   GET /notifications/stats   per-channel counters
 *   GET /health /ready /metrics
 */

const express = require('express');
const Redis = require('ioredis');
const client = require('prom-client');

const PORT = Number(process.env.PORT || 3001);
const SERVICE = 'notification-service';
const CHANNELS = ['order-events', 'payment-events'];

const register = new client.Registry();
client.collectDefaultMetrics({ register });
const BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];

const httpRequests = new client.Counter({
  name: 'http_requests_total', help: 'HTTP requests handled',
  labelNames: ['method', 'route', 'status_code'], registers: [register],
});
const httpDuration = new client.Histogram({
  name: 'http_request_duration_seconds', help: 'HTTP request latency',
  labelNames: ['method', 'route'], buckets: BUCKETS, registers: [register],
});
const inFlight = new client.Gauge({
  name: 'http_requests_in_flight', help: 'HTTP requests currently being served', registers: [register],
});
const received = new client.Counter({
  name: 'notifications_received_total', help: 'Events consumed from Redis',
  labelNames: ['channel', 'status'], registers: [register],
});
const processing = new client.Histogram({
  name: 'notification_processing_seconds', help: 'Event handling latency',
  labelNames: ['channel'], buckets: [0.0005, 0.001, 0.005, 0.01, 0.05, 0.1], registers: [register],
});

function log(level, message, fields = {}) {
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), service: SERVICE, level, message, ...fields }));
}

const counts = Object.fromEntries(CHANNELS.map((c) => [c, 0]));
const byStatus = {};

// ioredis reconnects automatically with backoff; re-subscription on
// reconnect is handled by the client (autoResubscribe defaults to true).
const subscriber = new Redis({
  host: process.env.REDIS_HOST || 'redis-service',
  port: Number(process.env.REDIS_PORT || 6379),
  retryStrategy: (times) => Math.min(times * 500, 5000),
  maxRetriesPerRequest: null,
});

subscriber.on('ready', () => log('INFO', 'redis subscriber ready'));
subscriber.on('error', (err) => log('ERROR', 'redis subscriber error', { error: err.message }));
subscriber.subscribe(...CHANNELS).then(
  () => log('INFO', 'subscribed', { channels: CHANNELS }),
  (err) => log('ERROR', 'subscribe failed', { error: err.message }),
);

subscriber.on('message', (channel, message) => {
  const end = processing.startTimer({ channel });
  try {
    const event = JSON.parse(message);
    const status = String(event.status || 'unknown');
    counts[channel] = (counts[channel] || 0) + 1;
    byStatus[`${channel}:${status}`] = (byStatus[`${channel}:${status}`] || 0) + 1;
    received.inc({ channel, status });
  } catch (err) {
    received.inc({ channel, status: 'malformed' });
    log('ERROR', 'malformed event', { channel, error: err.message });
  } finally {
    end();
  }
});

const app = express();
app.disable('x-powered-by');

app.use((req, res, next) => {
  if (['/health', '/ready', '/metrics'].includes(req.path)) return next();
  const start = process.hrtime.bigint();
  inFlight.inc();
  res.on('close', () => {
    inFlight.dec();
    const seconds = Number(process.hrtime.bigint() - start) / 1e9;
    const route = req.route ? req.route.path : 'unmatched';
    httpRequests.inc({ method: req.method, route, status_code: String(res.statusCode) });
    httpDuration.observe({ method: req.method, route }, seconds);
  });
  next();
});

app.get('/health', (_req, res) => res.json({ status: 'ok', service: SERVICE }));
app.get('/ready', (_req, res) => {
  const ok = subscriber.status === 'ready';
  res.status(ok ? 200 : 503).json({ status: ok ? 'ready' : 'redis unavailable', redis: subscriber.status });
});
app.get('/notifications/stats', (_req, res) => res.json({ service: SERVICE, received: counts, by_status: byStatus }));
app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});
app.use((_req, res) => res.status(404).json({ error: 'not found' }));

const server = app.listen(PORT, () => log('INFO', `${SERVICE} listening`, { port: PORT }));

function shutdown() {
  server.close(() => {
    subscriber.quit().finally(() => process.exit(0));
  });
  setTimeout(() => process.exit(0), 5000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
