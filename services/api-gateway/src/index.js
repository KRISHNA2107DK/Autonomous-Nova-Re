'use strict';

/**
 * api-gateway — single entry point for ShopFusion (behind nginx).
 *
 * Proxies /products, /orders, /payments, /notifications to the owning
 * service, preserving the full path. Upstream calls use undici's fetch with
 * pooled keep-alive connections and a hard per-request deadline that also
 * covers a stuck TCP connect, so an unreachable upstream fails fast with 504
 * instead of hanging until the client gives up.
 *
 * Kubernetes Services balance per *connection*; long-lived keep-alive
 * connections would pin all traffic to whichever pods they first reached.
 * Each upstream connection is therefore recycled after MAX_REQUESTS_PER_CONN
 * requests so load keeps spreading across replicas (as Envoy's
 * max_requests_per_connection does).
 *
 * Emits the same metric names as the Python services so AutoHeal can query
 * every service uniformly:
 *   http_requests_total{method,route,status_code}
 *   http_request_duration_seconds{method,route}
 *   http_requests_in_flight
 *   http_client_requests_total{target,status_code}     (gateway -> upstream)
 *   http_client_request_duration_seconds{target}
 */

const path = require('path');
const express = require('express');
const client = require('prom-client');
const { Agent, fetch } = require('undici');

const PORT = Number(process.env.PORT || 3000);
const SERVICE = 'api-gateway';
const UPSTREAM_TIMEOUT_MS = Number(process.env.UPSTREAM_TIMEOUT_MS || 5000);
const MAX_BODY_BYTES = 1024 * 1024;
const MAX_REQUESTS_PER_CONN = Number(process.env.MAX_REQUESTS_PER_CONN || 25);

const dispatcher = new Agent({
  keepAliveTimeout: 4000,
  maxRequestsPerClient: MAX_REQUESTS_PER_CONN,
  connect: { timeout: UPSTREAM_TIMEOUT_MS },
});

const UPSTREAMS = [
  { prefix: '/products', name: 'product-service', url: process.env.PRODUCT_SERVICE_URL || 'http://product-service:8001' },
  { prefix: '/orders', name: 'order-service', url: process.env.ORDER_SERVICE_URL || 'http://order-service:8002' },
  { prefix: '/payments', name: 'payment-service', url: process.env.PAYMENT_SERVICE_URL || 'http://payment-service:8003' },
  { prefix: '/notifications', name: 'notification-service', url: process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:3001' },
];

// Hop-by-hop headers must not be forwarded (RFC 7230 §6.1).
const HOP_BY_HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade', 'host', 'content-length']);

// ── Metrics ──────────────────────────────────────────────────────────────────
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
const clientRequests = new client.Counter({
  name: 'http_client_requests_total', help: 'Proxied calls to upstream services',
  labelNames: ['target', 'status_code'], registers: [register],
});
const clientDuration = new client.Histogram({
  name: 'http_client_request_duration_seconds', help: 'Upstream call latency',
  labelNames: ['target'], buckets: BUCKETS, registers: [register],
});

function log(level, message, fields = {}) {
  console.log(JSON.stringify({ timestamp: new Date().toISOString(), service: SERVICE, level, message, ...fields }));
}

const UNINSTRUMENTED = new Set(['/health', '/ready', '/metrics', '/health/dependencies']);

function upstreamFor(path) {
  return UPSTREAMS.find((u) => path === u.prefix || path.startsWith(`${u.prefix}/`));
}

const app = express();
app.disable('x-powered-by');

app.use((req, res, next) => {
  // Static storefront page loads are not API traffic: keep them out of the RED metrics.
  if (UNINSTRUMENTED.has(req.path) || req.path === '/' || req.path.startsWith('/shop')) return next();
  const upstream = upstreamFor(req.path);
  const route = upstream ? upstream.prefix : 'unmatched';
  const start = process.hrtime.bigint();
  inFlight.inc();
  res.on('close', () => {
    inFlight.dec();
    const seconds = Number(process.hrtime.bigint() - start) / 1e9;
    const status = res.headersSent ? res.statusCode : 499;
    httpRequests.inc({ method: req.method, route, status_code: String(status) });
    httpDuration.observe({ method: req.method, route }, seconds);
    if (status >= 500) {
      log('ERROR', 'request failed', { method: req.method, path: req.originalUrl, status_code: status, duration_ms: Math.round(seconds * 1000) });
    }
  });
  next();
});

// ── Probes & metrics ─────────────────────────────────────────────────────────
app.get('/health', (_req, res) => res.json({ status: 'ok', service: SERVICE }));

// ShopFusion storefront (single static page calling the APIs above through this gateway).
app.use('/shop', express.static(path.join(__dirname, 'public'), { maxAge: '1m' }));
app.get('/', (_req, res) => res.redirect('/shop/'));
app.get('/ready', (_req, res) => res.json({ status: 'ready', service: SERVICE }));

app.get('/health/dependencies', async (_req, res) => {
  const results = await Promise.all(UPSTREAMS.map(async (u) => {
    const started = Date.now();
    try {
      const r = await fetch(`${u.url}/ready`, { dispatcher, signal: AbortSignal.timeout(1500) });
      await r.arrayBuffer();
      return { service: u.name, healthy: r.ok, status_code: r.status, latency_ms: Date.now() - started };
    } catch (err) {
      return { service: u.name, healthy: false, error: err.name === 'TimeoutError' ? 'timeout' : err.message, latency_ms: Date.now() - started };
    }
  }));
  const healthy = results.every((r) => r.healthy);
  res.status(healthy ? 200 : 503).json({ status: healthy ? 'ok' : 'degraded', dependencies: results });
});

app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// ── Proxy ────────────────────────────────────────────────────────────────────
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY_BYTES) {
        reject(Object.assign(new Error('payload too large'), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

async function proxy(upstream, req, res) {
  const started = process.hrtime.bigint();
  const elapsed = () => Number(process.hrtime.bigint() - started) / 1e9;
  let body;
  try {
    body = ['GET', 'HEAD'].includes(req.method) ? undefined : await readBody(req);
  } catch (err) {
    res.status(err.status || 400).json({ error: err.message });
    return;
  }
  const headers = {};
  for (const [k, v] of Object.entries(req.headers)) {
    if (!HOP_BY_HOP.has(k)) headers[k] = v;
  }
  try {
    const upstreamRes = await fetch(`${upstream.url}${req.originalUrl}`, {
      method: req.method, headers, body, redirect: 'manual', dispatcher,
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
    const payload = Buffer.from(await upstreamRes.arrayBuffer());
    clientRequests.inc({ target: upstream.name, status_code: String(upstreamRes.status) });
    clientDuration.observe({ target: upstream.name }, elapsed());
    res.status(upstreamRes.status);
    upstreamRes.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key) && key !== 'content-encoding') res.setHeader(key, value);
    });
    res.end(payload);
  } catch (err) {
    const timedOut = err.name === 'TimeoutError' || err.name === 'AbortError';
    clientRequests.inc({ target: upstream.name, status_code: 'transport_error' });
    clientDuration.observe({ target: upstream.name }, elapsed());
    log('ERROR', 'upstream error', { target: upstream.name, error: timedOut ? 'timeout' : (err.cause?.code || err.message) });
    if (!res.headersSent) {
      res.status(timedOut ? 504 : 502).json({
        error: timedOut ? 'Gateway Timeout' : 'Bad Gateway', upstream: upstream.name,
      });
    }
  }
}

app.use((req, res, next) => {
  const upstream = upstreamFor(req.path);
  if (!upstream) return next();
  proxy(upstream, req, res).catch(next);
});

app.use((_req, res) => res.status(404).json({ error: 'not found' }));

const server = app.listen(PORT, () => log('INFO', `${SERVICE} listening`, { port: PORT, upstream_timeout_ms: UPSTREAM_TIMEOUT_MS }));
server.keepAliveTimeout = 65000;   // longer than nginx's upstream keepalive

function shutdown() {
  log('INFO', 'shutting down');
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 5000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
