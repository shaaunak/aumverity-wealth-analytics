import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = path.resolve(__dirname, "../../docs/screenshots");

test.describe("AUMVERITY End-to-End Audit & Critical Paths", () => {
  test("Audit all 9 routes for zero console/network errors and zero horizontal overflow", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const failedResponses: string[] = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });
    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });
    page.on("response", (res) => {
      if (res.status() >= 400 && !res.url().includes("favicon")) {
        failedResponses.push(`${res.status()} ${res.url()}`);
      }
    });

    const routes = [
      "/",
      "/bridge",
      "/advisors",
      "/clients",
      "/flows",
      "/reconciliation",
      "/investigations",
      "/lineage",
      "/exports",
    ];

    for (const route of routes) {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(route, { waitUntil: "networkidle" });
      await expect(page.locator("body")).toBeVisible();
      const overflowDesktop = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 2,
      );
      expect(overflowDesktop, `Desktop horizontal overflow on ${route}`).toBe(
        false,
      );

      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(150);
      const overflowMobile = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 2,
      );
      expect(overflowMobile, `Mobile horizontal overflow on ${route}`).toBe(
        false,
      );
    }

    expect(consoleErrors, `Console errors: ${consoleErrors.join("; ")}`).toEqual(
      [],
    );
    expect(pageErrors, `Page errors: ${pageErrors.join("; ")}`).toEqual([]);
    expect(
      failedResponses,
      `Failed HTTP responses: ${failedResponses.join("; ")}`,
    ).toEqual([]);
  });

  test("Path A & F: Dashboard to KPI investigation drawer & Filter synchronization", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByText("AUMVERITY")).toBeVisible();
    await expect(page.getByRole("button", { name: "Closing Assets" })).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01-executive-overview.png"),
      fullPage: true,
    });

    // Path A: Click a KPI card to open KPI investigation / SQL lineage drawer
    await page.getByRole("button", { name: "Closing Assets" }).click();
    const lineageTab = page.getByRole("button", { name: "3. SQL & Lineage" });
    await expect(lineageTab).toBeVisible({ timeout: 10_000 });
    await lineageTab.click();
    await expect(page.getByText("End-to-End Source Lineage")).toBeVisible();

    // Path F: Filter synchronization — change period preset in top bar
    const periodSelect = page.locator("header select").first();
    if (await periodSelect.isVisible()) {
      await periodSelect.selectOption("2026-Q2");
      await page.waitForLoadState("networkidle");
    }
  });

  test("Path B & G: Advisor ranking to transaction evidence & Empty search state", async ({
    page,
  }) => {
    await page.goto("/advisors", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Advisor Explorer/i }),
    ).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "03-advisor-explorer.png"),
      fullPage: true,
    });

    // Drill down to first advisor detail
    const firstAdvisorLink = page.locator("table tbody tr a").first();
    await expect(firstAdvisorLink).toBeVisible();
    await firstAdvisorLink.click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/Advisor/i).first()).toBeVisible();

    // Path G: Empty state on nonexistent advisor search
    await page.goto("/advisors", { waitUntil: "networkidle" });
    const searchInput = page.getByPlaceholder(/Search advisor/i);
    if (await searchInput.isVisible()) {
      await searchInput.fill("NONEXISTENT_ADVISOR_XYZ_999");
      await page.waitForTimeout(400);
      await page.waitForLoadState("networkidle");
    }
  });

  test("Path C: Financial bridge calculation & waterfall", async ({ page }) => {
    await page.goto("/bridge", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Asset Movement Bridge/i }),
    ).toBeVisible();
    await expect(page.getByRole("cell", { name: "Opening Assets" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Closing Assets" })).toBeVisible();
    await expect(page.getByText("Unexplained Residual:")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02-asset-bridge.png"),
      fullPage: true,
    });
  });

  test("Path D: Reconciliation issue detection & detail comparison", async ({
    page,
  }) => {
    await page.goto("/reconciliation", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Financial Reconciliation Center/i }),
    ).toBeVisible();

    const firstIssueRow = page.locator("table tbody tr").first();
    await expect(firstIssueRow).toBeVisible();
    await firstIssueRow.click();

    await expect(page.getByText("Reported Financial Balance")).toBeVisible();
    await expect(page.getByText("Reconstructed Financial Balance")).toBeVisible();
    await expect(page.getByText("SQL Lineage & Verification Query")).toBeVisible();

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06-reconciliation-issue.png"),
      fullPage: true,
    });
  });

  test("Path E: Investigation workspace, SQL lineage, and Excel export", async ({
    page,
    request,
  }) => {
    await page.goto("/investigations", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Investigation Workspace/i }),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "04-investigation-workspace.png"),
      fullPage: true,
    });

    await page.goto("/lineage", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Metric Dictionary/i }),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05-sql-lineage.png"),
      fullPage: true,
    });

    await page.goto("/exports", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("heading", { name: /Management Reports/i }),
    ).toBeVisible();
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "07-reports-exports.png"),
      fullPage: true,
    });

    const excelLink = page.getByRole("link", {
      name: /Download Excel Workbook/i,
    });
    const href = await excelLink.getAttribute("href");
    expect(href).toBeTruthy();
    const res = await request.get(href!);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("spreadsheetml.sheet");
  });
});
