import { expect, test } from "@playwright/test";
import path from "node:path";
import { nav, SEED, SEED_FILES, signUp, upload, UPDATE_NOTE, uniqueEmail, watchErrors } from "./helpers";

test("reviewer hands over a project; the new member joins, asks, and sees version 2", async ({ page, browser }) => {
  const noErrors = watchErrors(page);
  await signUp(page, "Dr. Mehra", uniqueEmail("mehra"), "reviewer-pass-1");

  // Create the project with the person leaving and the person taking over.
  await page.getByPlaceholder("Project name").fill("Library app");
  const full = page.getByPlaceholder("Full name");
  await full.nth(0).fill("Riya Sharma");
  await full.nth(1).fill("Karan Mehta");
  const handles = page.getByPlaceholder("Username in the files");
  await handles.nth(0).fill("riya-dev");
  await handles.nth(1).fill("karan-m");
  await page.getByRole("button", { name: "Create and add files" }).click();
  await page.waitForURL("**/sources");
  for (const [f, label] of SEED_FILES) await upload(page, path.join(SEED, f), label);

  // Analyse, then settle disagreements and review every finding.
  await page.locator('[data-guide="run-analysis"]').click();
  await page.waitForURL(/\/p\/[^/]+$/);
  await expect(page.getByText("Last analysis finished")).toBeVisible();
  await expect(page.getByTestId("attention")).toContainText("files disagree");
  const pid = page.url().split("/p/")[1];

  await nav(page, "gaps");
  await page.locator('[data-guide="resolve"]').first().waitFor();
  for (let i = 0; i < 4; i++) {
    const choose = page.locator('[data-guide="resolve"] button').nth(1);
    if (!(await choose.count())) break;
    await choose.click();
    await page.waitForTimeout(500);
  }
  await nav(page, "review");
  for (let i = 0; i < 40; i++) {
    const actions = page.locator('[data-guide="review-actions"]');
    await actions.waitFor({ timeout: 5_000 }).catch(() => undefined);
    if (!(await actions.count())) break;
    const approve = actions.getByRole("button", { name: /^Approve$/ });
    if ((await approve.count()) && (await approve.isEnabled())) await approve.click();
    else {
      await actions.getByRole("button", { name: "Reject" }).click();
      await page.locator('[data-guide="review-form"] input').fill("Not backed by the file");
      await page.getByRole("button", { name: "Save" }).click();
    }
    await page.waitForTimeout(300);
  }
  await expect(page.getByText("Nothing left to review")).toBeVisible();

  await nav(page, "handover");
  await page.locator('[data-guide="generate"]').click();
  await page.locator('[data-guide="approve-handover"]').click();
  await expect(page.getByText(/Approved · version 1/)).toBeVisible();

  // Invite Karan; he joins from a second browser with his own account.
  await nav(page, "overview");
  await page.locator('[data-guide="invite-incoming"] button').first().click();
  await page.getByRole("button", { name: "Create invite link" }).click();
  const link = await page.getByLabel("Invite link").inputValue();
  await page.keyboard.press("Escape");

  const karanCtx = await browser.newContext();
  const k = await karanCtx.newPage();
  const karanNoErrors = watchErrors(k);
  await k.goto(link);
  await k.getByPlaceholder("Email").fill(uniqueEmail("karan"));
  await k.getByPlaceholder(/Password/).fill("karan-pass-12");
  await k.getByRole("button", { name: "Create account" }).last().click();
  await k.getByRole("button", { name: /^Join/ }).click();
  await k.waitForURL("**/handover");
  await expect(k.getByText(/Approved · version 1/)).toBeVisible();

  // Ask Baton: one answer from the files, one sent to the leaver.
  await nav(k, "ask");
  await k.getByLabel("Your question").fill("Why are online payments switched off?");
  await k.getByRole("button", { name: "Ask" }).click();
  await expect(k.locator("mark").first()).toBeVisible();
  await k.getByLabel("Your question").fill("Where is visitor parking for the fest?");
  await k.getByRole("button", { name: "Ask" }).click();
  await k
    .getByRole("button", { name: /Ask Riya Sharma instead/ })
    .first()
    .click();
  await expect(k.getByText(/Sent to/).first()).toBeVisible();

  // Living handover: newer evidence flags approved lines, then version 2 with a diff.
  await nav(page, "sources");
  await upload(page, UPDATE_NOTE, "Team");
  await nav(page, "overview");
  await page.locator('[data-guide="run-analysis-top"]').click();
  await expect(page.getByText(/out of date/)).toBeVisible();
  await nav(page, "gaps");
  await page.locator('[data-guide="resolve"]').first().waitFor();
  for (let i = 0; i < 3; i++) {
    const choose = page.locator('[data-guide="resolve"] button').nth(0);
    if (!(await choose.count())) break;
    await choose.click();
    await page.waitForTimeout(500);
  }
  await nav(page, "review");
  for (let i = 0; i < 6; i++) {
    await page
      .locator('[data-guide="review-actions"]')
      .waitFor({ timeout: 5_000 })
      .catch(() => undefined);
    const approve = page.locator('[data-guide="review-actions"]').getByRole("button", { name: /^Approve$/ });
    if (!(await approve.count()) || !(await approve.isEnabled())) break;
    await approve.click();
    await page.waitForTimeout(300);
  }
  await nav(page, "handover");
  await page.locator('[data-guide="generate"]').click();
  await expect(page.getByText(/What changed since version 1/)).toBeVisible();
  await page.locator('[data-guide="approve-handover"]').click();

  await k.goto(`/p/${pid}/handover`);
  await expect(k.getByText(/Approved · version 2/)).toBeVisible();
  await k.reload();
  await expect(k.getByText(/Approved · version 2/)).toBeVisible(); // still signed in after a refresh
  noErrors();
  karanNoErrors();
});
