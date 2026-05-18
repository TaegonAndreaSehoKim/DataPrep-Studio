import { expect, Page, test } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000";

const project = {
  id: 101,
  name: "Browser Smoke Project",
  description: "Created from Playwright",
  created_at: "2026-05-17T00:00:00Z",
  updated_at: "2026-05-17T00:00:00Z"
};

const analysis = {
  id: 301,
  project_id: project.id,
  target_column: "target",
  problem_type: "classification",
  readiness_score: 91.5,
  score_breakdown: {},
  status: "completed",
  created_at: "2026-05-17T00:00:00Z"
};

async function mockApi(page: Page) {
  await page.route(`${apiBase}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();

    if (method === "GET" && url.pathname === "/dashboard") {
      await route.fulfill({
        json: {
          project_count: 0,
          dataset_count: 0,
          analysis_count: 0,
          pipeline_count: 0,
          recent_projects: [],
          recent_analysis_runs: [],
          recent_pipeline_runs: []
        }
      });
      return;
    }

    if (method === "GET" && url.pathname === "/projects") {
      await route.fulfill({ json: [project] });
      return;
    }

    if (method === "POST" && url.pathname === "/projects") {
      await route.fulfill({ status: 201, json: project });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}`) {
      await route.fulfill({ json: project });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/datasets`) {
      await route.fulfill({ json: [] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/analysis`) {
      await route.fulfill({ json: [analysis] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/pipelines`) {
      await route.fulfill({ json: [] });
      return;
    }

    if (method === "GET" && url.pathname === "/pipeline/operations") {
      await route.fulfill({
        json: [
          {
            operation_type: "drop_columns",
            label: "Drop Columns",
            description: "Remove selected columns.",
            supported_column_types: ["any"],
            params: []
          }
        ]
      });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: `Unhandled mock route: ${method} ${url.pathname}` } });
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test("renders dashboard and creates a project shell", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Configurable preprocessing for tabular ML" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "DataPrep Studio" })).toBeVisible();

  await page.getByRole("button", { name: "New Project" }).click();
  await page.getByLabel("Name").fill(project.name);
  await page.getByLabel("Description").fill(project.description);
  await page.getByRole("button", { name: "Create Project" }).click();

  await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
  await expect(page.getByText("No datasets")).toBeVisible();
  await expect(page.getByText("No single dataset")).toBeVisible();
});

test("opens pipeline builder and shows config import affordance", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Pipeline" }).click();

  await expect(page.getByRole("heading", { name: "Pipeline Builder" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Import Config" })).toBeVisible();
  await expect(page.getByLabel("preprocessing_config.json")).toBeVisible();
  await expect(page.getByRole("button", { name: "Import Config" })).toBeDisabled();
});
