const http = require("http");

const PORT = Number(process.env.PORT || 3100);
const TRAINING = process.env.CONNECTOR_TRAINING === "1";
const BLOCKED = new Set(["__proto__", "constructor", "prototype"]);

const RECORDS = [
  { org: "2", email: "info@acme.example", name: "Acme Industrial Supply", syncToken: "sync-nw-0001", tier: "platinum" },
  { org: "2", email: "ops@harbor.example", name: "Harbor Logistics", syncToken: "sync-nw-0002", tier: "gold" },
  { org: "3", email: "info@zenith.example", name: "Zenith Retail", syncToken: "sync-ct-0001", tier: "silver" },
  { org: "4", email: "hello@orbit.example", name: "Orbit Media", syncToken: "sync-gl-0001", tier: "gold" },
];

const configs = new Map();
const hookLog = [];

function isVulnerable(req) {
  return TRAINING && req.headers["x-mode"] === "vulnerable";
}

function unsafeMerge(target, source) {
  for (const key of Object.keys(source)) {
    if (source[key] && typeof source[key] === "object" && !Array.isArray(source[key])) {
      if (typeof target[key] !== "object" || target[key] === null) target[key] = {};
      unsafeMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

function safeMerge(target, source) {
  for (const key of Object.keys(source)) {
    if (BLOCKED.has(key)) continue;
    if (source[key] && typeof source[key] === "object" && !Array.isArray(source[key])) {
      if (!Object.prototype.hasOwnProperty.call(target, key) || typeof target[key] !== "object" || target[key] === null) target[key] = {};
      safeMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}

function matchValue(value, cond) {
  if (cond !== null && typeof cond === "object" && !Array.isArray(cond)) {
    return Object.entries(cond).every(([op, arg]) => {
      switch (op) {
        case "$ne": return value !== arg;
        case "$eq": return value === arg;
        case "$in": return Array.isArray(arg) && arg.includes(value);
        case "$gt": return value > arg;
        case "$lt": return value < arg;
        case "$regex": return new RegExp(String(arg)).test(String(value));
        case "$exists": return (value !== undefined) === Boolean(arg);
        default: return false;
      }
    });
  }
  return value === cond;
}

function matches(doc, query) {
  return Object.entries(query).every(([k, cond]) => matchValue(doc[k], cond));
}

function send(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) });
  res.end(data);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (c) => {
      raw += c;
      if (raw.length > 100000) { reject(new Error("too large")); req.destroy(); }
    });
    req.on("end", () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
  });
}

function orgConfig(org) {
  if (!configs.has(org)) configs.set(org, { mapping: { name: "company", email: "contact_email" }, sync: { enabled: false, intervalMinutes: 60 } });
  return configs.get(org);
}

const routes = {
  "POST /connector/config": (req, body, org) => {
    const cfg = orgConfig(org);
    if (isVulnerable(req)) unsafeMerge(cfg, body); else safeMerge(cfg, body);
    return [200, { ok: true, config: cfg }];
  },
  "POST /connector/settings": (req, body, org) => {
    const cfg = orgConfig(org);
    const auth = { org, role: "integration_dev" };
    const effective = { batchSize: cfg.sync.batchSize || 100, intervalMinutes: cfg.sync.intervalMinutes, mapping: cfg.mapping };
    if (body.exportAll) {
      if (!auth.isAdmin) return [403, { error: "Administrator privileges are required to export all connector data" }];
      return [200, { settings: effective, export: RECORDS }];
    }
    return [200, { settings: effective }];
  },
  "POST /connector/lookup": (req, body, org) => {
    let query;
    if (isVulnerable(req)) {
      query = { org, ...body };
    } else {
      query = { org };
      for (const [k, v] of Object.entries(body)) {
        if (!["email", "name", "tier"].includes(k) || typeof v !== "string") return [400, { error: "Invalid lookup criteria" }];
        query[k] = v;
      }
    }
    const rows = RECORDS.filter((r) => matches(r, query));
    return [200, { count: rows.length, records: rows.map((r) => ({ email: r.email, name: r.name, tier: r.tier, ...(isVulnerable(req) ? { syncToken: r.syncToken, org: r.org } : {}) })) }];
  },
  "POST /hooks": (req, body, org) => {
    hookLog.unshift({ at: new Date().toISOString(), org, event: body.event || null });
    hookLog.length = Math.min(hookLog.length, 50);
    return [202, { accepted: true }];
  },
};

const server = http.createServer(async (req, res) => {
  const path = req.url.split("?")[0];
  if (req.method === "GET" && path === "/health") return send(res, 200, { status: "ok", service: "connector", training: TRAINING });
  const handler = routes[`${req.method} ${path}`];
  if (!handler) return send(res, 404, { error: "Not found" });
  try {
    const body = await readJson(req);
    if (body === null || typeof body !== "object" || Array.isArray(body)) return send(res, 400, { error: "JSON object expected" });
    const org = String(req.headers["x-org-id"] || "");
    if (!org) return send(res, 400, { error: "Missing organization context" });
    const [status, payload] = handler(req, body, org);
    send(res, status, payload);
  } catch (e) {
    send(res, 400, { error: "Invalid request" });
  }
});

if (require.main === module) server.listen(PORT, () => console.log(`connector listening on ${PORT} training=${TRAINING}`));
module.exports = { server, unsafeMerge, safeMerge };
