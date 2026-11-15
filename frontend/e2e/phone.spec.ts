import { expect, test } from "@playwright/test";
import { watchErrors } from "./helpers";

// Phone size in Chromium (iPhone 13 dimensions).
test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });

test("menu, review and no sideways scrolling", async ({ page }) => {
  const noErrors = watchErrors(page);
  await page.goto("/");
  await page.getByRole("button", { name: /Try the demo/ }).click();
  await page.waitForURL(/\/p\/[^/]+$/);
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Review" }).click();
  await page.waitForURL("**/review");
  await expect(page.getByRole("heading", { name: "Review" })).toBeVisible();
  const [scroll, width] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(scroll).toBeLessThanOrEqual(width);
  noErrors();
});
