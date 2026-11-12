import { as, expect, test, vulnerableOnly } from "./helpers";

test("search term in the URL is rendered as text only in the secure configuration", async ({ browser }) => {
  const { ctx, page } = await as(browser, "rep");
  await page.goto("/customers?q=" + encodeURIComponent("<i id='probe'>acme</i>"));
  await expect(page.getByTestId("search-echo")).toBeVisible();
  const injected = await page.locator("#probe").count();
  expect(injected).toBe(vulnerableOnly ? 1 : 0);
  await ctx.close();
});

test("customer records of another organization are reachable only in the vulnerable configuration", async ({ browser }) => {
  const other = await as(browser, "contosoRep");
  const list = await other.page.request.get("/api/customers?size=1");
  const foreignId = (await list.json()).items[0].id;
  const mine = await as(browser, "rep");
  const res = await mine.page.request.get(`/api/customers/${foreignId}`);
  expect(res.status()).toBe(vulnerableOnly ? 200 : 404);
  await other.ctx.close(); await mine.ctx.close();
});

test("function-level permissions: a representative cannot delete customers in the secure configuration", async ({ browser }) => {
  test.skip(vulnerableOnly, "destructive call is only exercised against the secure configuration");
  const { ctx, page } = await as(browser, "rep");
  const list = await page.request.get("/api/customers?size=1");
  const id = (await list.json()).items[0].id;
  const csrf = (await ctx.cookies()).find((c) => c.name === "vc_csrf")?.value ?? "";
  const res = await page.request.delete(`/api/customers/${id}`, { headers: { "X-CSRF-Token": csrf }, failOnStatusCode: false });
  expect(res.status()).toBe(403);
  await ctx.close();
});

test("link-local metadata addresses are blocked in every configuration", async ({ browser }) => {
  const { ctx, page } = await as(browser, "dev");
  const csrf = (await ctx.cookies()).find((c) => c.name === "vc_csrf")?.value ?? "";
  const res = await page.request.post("/api/integrations/import-url", { data: { url: "http://169.254.169.254/latest/meta-data/" }, headers: { "X-CSRF-Token": csrf }, failOnStatusCode: false });
  const body = await res.text();
  expect(body).not.toContain("ami-id");
  await ctx.close();
});
