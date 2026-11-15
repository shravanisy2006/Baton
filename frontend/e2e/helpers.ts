import { expect, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const SEED = path.resolve(here, "../../backend/seed/eventapp");
export const UPDATE_NOTE = path.resolve(here, "../../backend/seed/updates/standup-2026-11-12.md");
export const SEED_FILES: [string, string][] = [
  ["meeting-notes-2026-09-15.md", "Team"],
  ["tasks-export.csv", "Team"],
  ["github-export-eventapp.md", "Team"],
  ["deploy-runbook.pdf", "Team"],
  ["riya-handover-notes.docx", "Leads"],
  ["sponsor-notes.md", "Restricted"],
  ["club-whatsapp-export.txt", "Team"],
];

let n = 0;
export function uniqueEmail(prefix: string) {
  n += 1;
  return `${prefix}-${Date.now()}-${n}@example.com`;
}

/** Fail the test on any uncaught page error. */
export function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  return () => expect(errors, errors.join("\n")).toEqual([]);
}

export async function signUp(page: Page, name: string, email: string, password: string) {
  await page.goto("/signin");
  await page.getByPlaceholder("Your name").fill(name);
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder(/Password/).fill(password);
  await page.getByRole("button", { name: "Create account" }).last().click();
  await page.waitForURL("**/projects");
}

export async function upload(page: Page, file: string, label = "Team") {
  await page.locator("input[type=file]").setInputFiles(file);
  await page.locator("#label").selectOption(label);
  await page.getByRole("button", { name: /^Upload/ }).click();
  await expect(page.getByRole("cell", { name: new RegExp(path.basename(file).replace(/[.]/g, "\\.")) }).first()).toBeVisible();
}

const HEADINGS: Record<string, RegExp> = {
  gaps: /Questions & disagreements/,
  review: /^Review$/,
  handover: /^Handover$/,
  sources: /^Sources$/,
  ask: /Ask Baton/,
};

export async function nav(page: Page, key: string) {
  await page.locator(`[data-guide="nav-${key}"]`).click();
  if (HEADINGS[key]) await expect(page.getByRole("heading", { level: 1, name: HEADINGS[key] })).toBeVisible();
  await page.waitForLoadState("networkidle");
}
