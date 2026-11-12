const test = require("node:test");
const assert = require("node:assert");
process.env.CONNECTOR_TRAINING = "1";
const { server } = require("../server");

let base;
test.before(() => new Promise((r) => server.listen(0, () => { base = `http://127.0.0.1:${server.address().port}`; r(); })));
test.after(() => server.close());

const call = async (path, body, mode = "secure", org = "2") => {
  const r = await fetch(base + path, { method: "POST", headers: { "Content-Type": "application/json", "X-Org-Id": org, "X-Mode": mode }, body: JSON.stringify(body) });
  return { status: r.status, body: await r.json() };
};

test("secure: lookup rejects operator objects", async () => {
  const r = await call("/connector/lookup", { email: { $ne: null } });
  assert.strictEqual(r.status, 400);
});

test("secure: lookup is tenant scoped", async () => {
  const r = await call("/connector/lookup", { email: "info@zenith.example" });
  assert.strictEqual(r.body.count, 0);
});

test("vulnerable: operator injection returns org records with tokens", async () => {
  const r = await call("/connector/lookup", { email: { $ne: null } }, "vulnerable");
  assert.ok(r.body.count >= 2 && r.body.records[0].syncToken);
});

test("secure: prototype keys ignored", async () => {
  await call("/connector/config", JSON.parse('{"__proto__":{"isAdmin":true}}'));
  const r = await call("/connector/settings", { exportAll: true });
  assert.strictEqual(r.status, 403);
});

test("vulnerable: prototype pollution changes authorization outcome", async () => {
  const before = await call("/connector/settings", { exportAll: true }, "vulnerable");
  assert.strictEqual(before.status, 403);
  await call("/connector/config", JSON.parse('{"__proto__":{"isAdmin":true}}'), "vulnerable");
  const after = await call("/connector/settings", { exportAll: true }, "vulnerable");
  assert.strictEqual(after.status, 200);
  delete Object.prototype.isAdmin;
});
