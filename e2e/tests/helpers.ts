import { test as base, Browser, BrowserContext, Page } from "@playwright/test";

export const MODE = process.env.MODE || "vulnerable";
export const vulnerableOnly = MODE === "vulnerable";

export async function as(browser: Browser, role: string): Promise<{ ctx: BrowserContext; page: Page }> {
  const ctx = await browser.newContext({ storageState: `.auth/${role}.json`, baseURL: process.env.BASE_URL || "http://localhost:8000" });
  return { ctx, page: await ctx.newPage() };
}

export const test = base;
export { expect } from "@playwright/test";
