import { expect, test } from "@playwright/test";
import { watchErrors } from "./helpers";

test("one-click demo opens a private, handed-over copy; switching person works", async ({ page }) => {
  const noErrors = watchErrors(page);
  await page.goto("/");
  await page.getByRole("button", { name: /Try the demo/ }).click();
  await page.waitForURL(/\/p\/[^/]+$/);
  await expect(page.getByText("This is your private demo copy.")).toBeVisible();
  await expect(page.getByRole("heading", { name: /What needs your attention|All caught up/ })).toBeVisible();
  const select = page.locator('[data-guide="switch-person"]');
  await select.selectOption({ label: await select.locator("option", { hasText: "Karan" }).first().innerText() });
  await page.waitForURL("**/handover");
  await expect(page.getByText(/Approved · version 1/)).toBeVisible();
  noErrors();
});

test("published demo sign-in gives each browser its own copy", async ({ browser }) => {
  const a = await (await browser.newContext()).newPage();
  const b = await (await browser.newContext()).newPage();
  for (const p of [a, b]) {
    await p.goto("/signin");
    await p.getByRole("button", { name: "Sign in as Priya Nair" }).click();
    await p.waitForURL(/\/p\/[^/]+$/);
  }
  expect(a.url()).not.toEqual(b.url());
  // Judge B can't open judge A's copy.
  await b.goto(new URL(a.url()).pathname);
  await expect(b.getByText(/Project not found, or you don't have access/)).toBeVisible();
});
