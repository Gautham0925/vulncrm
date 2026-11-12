import { chromium, FullConfig } from "@playwright/test";
import fs from "fs";

export const ACCOUNTS: Record<string, string> = {
  rep: "rep1@northwind.test",
  rep2: "rep2@northwind.test",
  manager: "manager@northwind.test",
  support: "support@northwind.test",
  auditor: "auditor@northwind.test",
  dev: "dev@northwind.test",
  admin: "admin@contoso.test",
  contosoRep: "rep1@contoso.test",
  superadmin: "superadmin@vulncrm.test",
};

export default async function setup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL!;
  fs.mkdirSync(".auth", { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
  for (const [key, email] of Object.entries(ACCOUNTS)) {
    const ctx = await browser.newContext({ baseURL });
    const page = await ctx.newPage();
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("Crm#Pass2026");
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL(baseURL + "/");
    await ctx.storageState({ path: `.auth/${key}.json` });
    await ctx.close();
  }
  await browser.close();
}
