import { as, expect, test, vulnerableOnly } from "./helpers";

const stamp = Date.now().toString().slice(-6);

test("1. authentication: wrong password is rejected, valid login and logout work", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("support@northwind.test");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.getByLabel("Password").fill("Crm#Pass2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Welcome back")).toBeVisible();
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("2. customers: create, search and edit a customer", async ({ browser }) => {
  const { ctx, page } = await as(browser, "manager");
  await page.goto("/customers");
  await page.getByRole("button", { name: "New customer" }).click();
  await page.getByLabel("Name", { exact: true }).fill(`E2E Corp ${stamp}`);
  await page.getByLabel("Email").fill(`e2e${stamp}@example.test`);
  await page.getByRole("button", { name: "Save customer" }).click();
  await page.getByLabel("Search customers").fill(`E2E Corp ${stamp}`);
  await page.getByRole("cell", { name: new RegExp(`E2E Corp ${stamp}`) }).click();
  await expect(page.getByRole("heading", { name: `E2E Corp ${stamp}` })).toBeVisible();
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Industry").fill("Testing");
  await page.getByRole("button", { name: "Save customer" }).click();
  await expect(page.getByText("Testing").first()).toBeVisible();
  await ctx.close();
});

test("3. leads: qualify and convert a lead to a customer", async ({ browser }) => {
  const { ctx, page } = await as(browser, "rep");
  await page.goto("/leads");
  await page.getByRole("button", { name: "New lead" }).click();
  await page.getByLabel("Name", { exact: true }).fill(`Lead ${stamp}`);
  await page.getByLabel("Company").fill(`LeadCo ${stamp}`);
  await page.getByRole("button", { name: "Save lead" }).click();
  await page.getByLabel("Search leads").fill(`Lead ${stamp}`);
  await page.getByRole("cell", { name: new RegExp(`Lead ${stamp}`) }).click();
  await page.getByRole("button", { name: "Mark as qualified" }).click();
  await page.getByRole("button", { name: "Convert to customer" }).click();
  await expect(page).toHaveURL(/\/customers\/\d+/);
  await ctx.close();
});

test("4. pipeline: board shows stages and a deal advances one stage", async ({ browser }) => {
  const { ctx, page } = await as(browser, "rep");
  await page.goto("/pipeline");
  for (const s of ["prospecting", "qualification", "proposal", "negotiation"]) await expect(page.getByTestId(`stage-${s}`)).toBeVisible();
  const before = await page.getByTestId("stage-qualification").locator(".card").count();
  await page.getByTestId("stage-prospecting").getByRole("button", { name: /Move to Qualification/ }).first().click();
  await expect(page.getByTestId("stage-qualification").locator(".card")).toHaveCount(before + 1);
  await ctx.close();
});

test("5. approvals: a large deal needs manager approval before it can close", async ({ browser }) => {
  const rep = await as(browser, "rep");
  await rep.page.goto("/pipeline");
  await rep.page.getByRole("button", { name: "New deal" }).click();
  await rep.page.getByLabel("Deal name").fill(`Big deal ${stamp}`);
  await rep.page.getByLabel("Customer").selectOption({ index: 1 });
  await rep.page.getByLabel("Amount").fill("250000");
  await rep.page.getByRole("button", { name: "Save deal" }).click();
  await rep.page.getByText(`Big deal ${stamp}`).click();
  await expect(rep.page.getByText(/exceeds the approval threshold/)).toBeVisible();
  await rep.page.getByRole("button", { name: "Request approval" }).click();
  await expect(rep.page.getByText("Pending").first()).toBeVisible();
  const url = rep.page.url();
  const mgr = await as(browser, "manager");
  await mgr.page.goto(url);
  await mgr.page.getByLabel("Decision note").fill("Approved for e2e");
  await mgr.page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(mgr.page.getByText("Approved").first()).toBeVisible();
  await rep.ctx.close(); await mgr.ctx.close();
});

test("6. support: open a ticket, reply with an internal note, resolve it", async ({ browser }) => {
  const { ctx, page } = await as(browser, "support");
  await page.goto("/tickets");
  await page.getByRole("button", { name: "New ticket" }).click();
  await page.getByLabel("Subject").fill(`Ticket ${stamp}`);
  await page.getByLabel("Customer").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Create ticket" }).click();
  await expect(page.getByRole("heading", { name: `Ticket ${stamp}` })).toBeVisible();
  await page.getByLabel("Reply").fill("Investigating now");
  await page.getByLabel("Internal note").check();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Investigating now")).toBeVisible();
  await page.getByRole("button", { name: "resolved" }).click();
  await expect(page.getByText("Resolved").first()).toBeVisible();
  await ctx.close();
});

test("7. documents: upload, preview metadata, add a version", async ({ browser }) => {
  const { ctx, page } = await as(browser, "rep");
  await page.goto("/documents");
  await page.getByRole("button", { name: "Upload document" }).click();
  await page.getByLabel("File").setInputFiles({ name: `notes-${stamp}.txt`, mimeType: "text/plain", buffer: Buffer.from("synthetic notes") });
  await page.getByLabel("Display name").fill(`Notes ${stamp}`);
  await page.getByRole("dialog").getByRole("button", { name: "Upload" }).click();
  await expect(page.getByRole("heading", { name: `Notes ${stamp}` })).toBeVisible();
  await page.getByLabel("New version file").setInputFiles({ name: `notes-${stamp}-v2.txt`, mimeType: "text/plain", buffer: Buffer.from("second revision") });
  await expect(page.getByRole("cell", { name: "v2", exact: true })).toBeVisible();
  await ctx.close();
});

test("8. reports: view a report and export CSV", async ({ browser }) => {
  const { ctx, page } = await as(browser, "manager");
  await page.goto("/reports");
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  const dl = page.waitForEvent("download");
  await page.getByRole("link", { name: "CSV" }).click();
  expect((await dl).suggestedFilename()).toMatch(/\.csv$/);
  await ctx.close();
});

test("9. RBAC: navigation and routes follow the role", async ({ browser }) => {
  const rep = await as(browser, "rep");
  await rep.page.goto("/");
  await expect(rep.page.getByRole("link", { name: "Audit logs" })).toHaveCount(0);
  await rep.page.goto("/audit");
  await expect(rep.page.getByText("Access denied")).toBeVisible();
  const aud = await as(browser, "auditor");
  await aud.page.goto("/audit");
  await expect(aud.page.getByRole("heading", { name: "Audit logs" })).toBeVisible();
  await aud.page.goto("/customers");
  await expect(aud.page.getByRole("button", { name: "New customer" })).toHaveCount(0);
  await rep.ctx.close(); await aud.ctx.close();
});

test("10. tenancy: switching organization changes the data in scope", async ({ browser }) => {
  const { ctx, page } = await as(browser, "superadmin");
  await page.goto("/");
  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("button", { name: "Globex Logistics" }).click();
  await expect(page.getByText("Globex Logistics").first()).toBeVisible();
  await ctx.close();
});

test("11. SSO: SAML sign-in through the synthetic identity provider", async ({ browser }) => {
  const ctx = await browser.newContext({ baseURL: process.env.BASE_URL || "http://localhost:8000" });
  const page = await ctx.newPage();
  await page.goto("/login");
  await page.getByRole("link", { name: "SAML" }).click();
  await page.waitForURL(/localhost:9000\/saml\/sso/);
  await page.locator("select[name=email]").selectOption("rep1@northwind.test");
  await page.locator("input[name=password]").fill("Idp#Pass2026");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL((u) => u.port === (new URL(process.env.BASE_URL || "http://localhost:8000")).port && u.pathname === "/");
  await expect(page.getByText("Welcome back")).toBeVisible();
  await ctx.close();
});

test("12. security library: filter and open a test case", async ({ browser }) => {
  const { ctx, page } = await as(browser, "auditor");
  await page.goto("/test-library");
  await expect(page.getByText("70 documented test cases")).toBeVisible();
  await page.getByLabel("Category").selectOption("SAML 2.0");
  await page.getByRole("cell", { name: /Missing signature handling/ }).click();
  await expect(page.getByRole("dialog").getByText("Manual test procedure")).toBeVisible();
  await expect(page.getByText(/flag/i)).toHaveCount(0);
  await ctx.close();
});

test("13. configuration banner matches the active mode", async ({ browser }) => {
  const { ctx, page } = await as(browser, "rep");
  await page.goto("/");
  if (vulnerableOnly) await expect(page.getByRole("note")).toContainText(/intentionally vulnerable/i);
  else await expect(page.getByRole("note")).toHaveCount(0);
  await ctx.close();
});
