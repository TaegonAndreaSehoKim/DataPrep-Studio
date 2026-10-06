import { expect, Page, request as apiRequest, test } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { testPython } from "./python-runtime";

const apiBase = "http://127.0.0.1:8001";

async function download(page: Page, label: string, path: string) {
  const [artifact] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: label, exact: true }).click(),
  ]);
  await artifact.saveAs(path);
  return readFile(path, "utf8");
}

for (const scenario of ["single", "train_test", "unlabeled_test"] as const) {
  const mode = scenario === "single" ? "single" : "train_test";
  const unlabeled = scenario === "unlabeled_test";
  test(`real API: ${scenario} upload analysis recipe preview apply and replay`, async ({ page }, testInfo) => {
    const pageErrors: string[] = [];
    let chartRequests = 0;
    page.on("request", (request) => { if (request.url().endsWith("/preview/charts")) chartRequests += 1; });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    let projectId: number | null = null;
    const inputs: Record<string, string> = mode === "single" ? {
      single: "age,notes,target\n10,a,0\n ?,b,1\n30,c,0\n",
    } : {
      train: "age,notes,target\n10,a,0\n ?,b,1\n30,c,0\n",
      test: unlabeled ? "age,notes\n ?,d\n9000,e\n" : "age,notes,target\n ?,d,0\n9000,e,1\n",
    };
    try {
      await page.goto("/");
      await page.getByRole("button", { name: "New Project", exact: true }).click();
      await page.getByLabel("Name", { exact: true }).fill(`Integration ${mode}`);
      const createdResponse = page.waitForResponse((response) => response.url() === `${apiBase}/projects` && response.request().method() === "POST");
      await page.getByRole("button", { name: "Create Project", exact: true }).click();
      const created = await createdResponse;
      expect(created.status()).toBe(201);
      projectId = (await created.json()).id;
      await page.getByRole("button", { name: "Upload Dataset", exact: true }).click();
      if (mode === "single") {
        await page.getByLabel("CSV File").setInputFiles({ name: "broken.csv", mimeType: "text/csv", buffer: Buffer.from('age\n"unterminated\n') });
        await page.getByRole("button", { name: "Upload CSV", exact: true }).click();
        await expect(page.getByRole("alert")).toContainText("Could not parse CSV");
      }
      for (const [role, csv] of Object.entries(inputs)) {
        await page.getByLabel("Dataset Role").selectOption(role);
        await page.getByLabel("CSV File").setInputFiles({ name: `${role}.csv`, mimeType: "text/csv", buffer: Buffer.from(csv) });
        await page.getByRole("button", { name: "Upload CSV", exact: true }).click();
        await expect(page.getByText(`Upload complete: ${role}.csv`, { exact: true })).toBeVisible();
        if (role === "train") await page.getByRole("button", { name: "Upload Another", exact: true }).click();
      }
      await page.getByRole("button", { name: "Run Analysis", exact: true }).click();
      await page.getByRole("combobox", { name: "Mode", exact: true }).selectOption(mode);
      await expect(page.getByText("Suggested setup applied from the loaded dataset.")).toBeVisible();
      await page.getByRole("combobox", { name: "Target Column", exact: true }).selectOption("target");
      await page.getByRole("combobox", { name: "Problem Type", exact: true }).selectOption("classification");
      await page.getByRole("textbox", { name: /^Missing Value Tokens/ }).fill("?");
      await page.getByRole("textbox", { name: /^Ignored Columns/ }).fill("notes");
      await page.getByRole("combobox", { name: "age", exact: true }).selectOption("numeric");
      const analysisResponse = page.waitForResponse((response) => response.url().endsWith("/analysis/run") && response.request().method() === "POST");
      await page.getByRole("button", { name: "Run Analysis", exact: true }).click();
      const analyzed = await analysisResponse;
      expect(analyzed.status()).toBe(201);
      const analysis = await analyzed.json();
      if (unlabeled) await expect(page.locator(".analysis-detail-panel").getByText("Test has no target column. Feature drift is checked; target distribution comparison is unavailable.")).toBeVisible();
      await expect(page.getByLabel("Current workspace context")).toContainText(`Score ${analysis.readiness_score.toFixed(1)}`);
      await page.getByRole("button", { name: /^Build Pipeline/ }).click();
      await page.getByRole("combobox", { name: "Mode", exact: true }).selectOption(mode);
      const pipelineResponse = page.waitForResponse((response) => response.url() === `${apiBase}/projects/${projectId}/pipelines` && response.request().method() === "POST");
      await page.getByRole("button", { name: "Create Pipeline", exact: true }).click();
      const pipelineId = (await (await pipelineResponse).json()).id;
      await expect(page.getByRole("button", { name: "Add Analysis Setup Steps", exact: true })).toBeVisible();
      if (unlabeled) await expect(page.getByRole("checkbox", { name: /^target / })).toBeDisabled();
      for (const operation of ["add_missing_indicator", "numeric_imputation"]) {
        await page.getByRole("combobox", { name: "Choose Operation", exact: true }).selectOption(operation);
        await page.getByRole("checkbox", { name: /^age / }).check();
        if (operation === "numeric_imputation") await page.getByLabel(/^strategy/).selectOption("mean");
        const stepResponse = page.waitForResponse((response) => response.url() === `${apiBase}/pipelines/${pipelineId}/steps` && response.request().method() === "POST");
        await page.getByRole("button", { name: "Add Manual Step", exact: true }).click();
        expect((await stepResponse).status()).toBe(201);
      }
      await page.getByRole("button", { name: "Add Analysis Setup Steps", exact: true }).click();
      await expect(page.locator(".pipeline-recipe li")).toHaveCount(4);
      await page.getByRole("button", { name: "Validate", exact: true }).click();
      await expect(page.getByText("Pipeline is valid", { exact: true })).toBeVisible();
      await page.getByRole("main").getByRole("button", { name: "Preview", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Pipeline Preview", exact: true })).toBeVisible();
      if (unlabeled) await expect(page.getByText(/^Test has no target column target;/)).toBeVisible();
      const applyResponse = page.waitForResponse((response) => response.url() === `${apiBase}/pipelines/${pipelineId}/apply` && response.request().method() === "POST");
      await page.getByRole("button", { name: "Apply Pipeline", exact: true }).click();
      const applied = await applyResponse;
      expect(applied.status()).toBe(201);
      const run = await applied.json();
      await expect(page.getByRole("heading", { name: `Downloads for Run #${run.id}`, exact: true })).toBeVisible();
      const config = JSON.parse(await download(page, "Config", testInfo.outputPath("config.json")));
      expect(config.analysis_options).toEqual(analysis.options);
      expect(config.steps.at(-1).fitted.fill_values.age).toBe(20);
      expect(config.metadata.train_only_fit).toBe(mode === "train_test");
      expect(await download(page, "Report", testInfo.outputPath("report.md"))).toContain("Analysis Setup Snapshot");
      const codePath = testInfo.outputPath("pipeline_code.py");
      await download(page, "Code", codePath);
      for (const [role, csv] of Object.entries(inputs)) {
        const label = role === "single" ? "Cleaned CSV" : role === "train" ? "Clean Train" : "Clean Test";
        const cleanPath = testInfo.outputPath(`clean_${role}.csv`);
        const cleaned = await download(page, label, cleanPath);
        expect(cleaned.split(/\r?\n/)[0]).toBe(unlabeled && role === "test" ? "age,age_was_missing" : "age,target,age_was_missing");
        const missingRow = role === "test" ? 1 : 2;
        expect(cleaned.split(/\r?\n/)[missingRow]).toBe(unlabeled && role === "test" ? "20.0,1" : `20.0,${role === "test" ? 0 : 1},1`);
        const inputPath = testInfo.outputPath(`input_${role}.csv`);
        await writeFile(inputPath, csv);
        const replay = spawnSync(testPython, ["-c", "import sys,runpy,pandas as pd; ns=runpy.run_path(sys.argv[1]); actual=ns['apply_pipeline'](pd.read_csv(sys.argv[2])); expected=pd.read_csv(sys.argv[3]); pd.testing.assert_frame_equal(actual,expected,check_dtype=False)", codePath, inputPath, cleanPath], { encoding: "utf8", timeout: 30_000 });
        expect(replay.error?.message || replay.stderr).toBe("");
        expect(replay.status).toBe(0);
      }
      expect(pageErrors).toEqual([]);
      expect(chartRequests).toBe(0);
    } finally {
      if (projectId !== null) {
        const cleanup = await apiRequest.newContext();
        try {
          expect((await cleanup.delete(`${apiBase}/projects/${projectId}`)).status()).toBe(204);
        } finally {
          await cleanup.dispose();
        }
      }
    }
  });
}
