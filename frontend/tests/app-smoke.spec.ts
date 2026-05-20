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

const dataset = {
  id: 201,
  project_id: project.id,
  role: "single",
  filename: "smoke.csv",
  storage_path: "uploads/smoke.csv",
  row_count: 5,
  column_count: 4,
  columns: ["age", "income", "city", "target"],
  file_size_bytes: 128,
  created_at: "2026-05-17T00:00:00Z"
};

const pipeline = {
  id: 401,
  project_id: project.id,
  analysis_run_id: analysis.id,
  name: `Recommended preprocessing #${analysis.id}`,
  description: null,
  mode: "single",
  status: "draft",
  steps: [],
  created_at: "2026-05-17T00:00:00Z",
  updated_at: "2026-05-17T00:00:00Z"
};

async function mockApi(page: Page) {
  let createdPipeline: typeof pipeline | null = null;

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
      await route.fulfill({ json: [dataset] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/analysis`) {
      await route.fulfill({ json: [analysis] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/dataset-configs`) {
      await route.fulfill({ json: [] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/pipelines`) {
      await route.fulfill({ json: createdPipeline ? [createdPipeline] : [] });
      return;
    }

    if (method === "POST" && url.pathname === `/projects/${project.id}/pipelines`) {
      createdPipeline = { ...pipeline, steps: [] };
      await route.fulfill({ status: 201, json: createdPipeline });
      return;
    }

    if (method === "GET" && url.pathname === `/pipelines/${pipeline.id}` && createdPipeline) {
      await route.fulfill({ json: createdPipeline });
      return;
    }

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/steps` && createdPipeline) {
      const body = request.postDataJSON() as { operation_type: string; columns: string[]; params: Record<string, unknown> };
      const step = {
        id: 601,
        pipeline_id: pipeline.id,
        order_index: 0,
        enabled: true,
        operation_type: body.operation_type,
        columns: body.columns,
        params: body.params,
        created_at: "2026-05-17T00:00:00Z",
        updated_at: "2026-05-17T00:00:00Z"
      };
      createdPipeline = { ...createdPipeline, steps: [step] };
      await route.fulfill({ status: 201, json: step });
      return;
    }

    if (method === "GET" && url.pathname === "/pipeline/operations") {
      await route.fulfill({
        json: [
          {
            operation_type: "numeric_imputation",
            label: "Numeric Imputation",
            description: "Fill missing numeric values.",
            supported_column_types: ["numeric"],
            params: [
              {
                name: "strategy",
                type: "select",
                required: false,
                default: "median",
                options: ["mean", "median", "constant"],
                description: "Imputation strategy."
              }
            ]
          },
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

    if (method === "GET" && url.pathname === `/analysis/${analysis.id}/overview`) {
      await route.fulfill({
        json: {
          analysis_run: analysis,
          row_count: 5,
          column_count: 4,
          issue_counts: { warning: 1 },
          column_type_counts: { numeric: 2, categorical: 2 },
          target_summary: null
        }
      });
      return;
    }

    if (method === "GET" && url.pathname === `/analysis/${analysis.id}/preprocessing-recommendations`) {
      await route.fulfill({
        json: {
          analysis_id: analysis.id,
          recommendations: [
            {
              priority: "high",
              category: "missingness",
              title: "Impute numeric missing values",
              rationale: "Median imputation is a conservative numeric default that is robust to outliers.",
              affected_columns: ["income"],
              issue_ids: [501],
              suggested_step: {
                operation_type: "numeric_imputation",
                columns: ["income"],
                params: { strategy: "median" },
                reason: "Median imputation is a conservative numeric default that is robust to outliers."
              }
            }
          ],
          notes: ["Recommendations are advisory and should be reviewed before applying."]
        }
      });
      return;
    }

    if (method === "GET" && url.pathname === `/analysis/${analysis.id}/train-test-comparison`) {
      await route.fulfill({ status: 404, json: { detail: "Train/test comparison not found" } });
      return;
    }

    if (method === "GET" && url.pathname === `/analysis/${analysis.id}/charts`) {
      await route.fulfill({ json: { analysis_id: analysis.id, charts: {} } });
      return;
    }

    if (method === "GET" && url.pathname === `/analysis/${analysis.id}/columns`) {
      await route.fulfill({
        json: [
          {
            id: 1,
            analysis_run_id: analysis.id,
            dataset_role: "single",
            column_name: "income",
            inferred_type: "numeric",
            missing_count: 1,
            missing_rate: 0.2,
            unique_count: 4,
            cardinality_ratio: 0.8,
            summary: {},
            warnings: []
          }
        ]
      });
      return;
    }

    if (method === "GET" && url.pathname === `/datasets/${dataset.id}/setup-suggestions`) {
      await route.fulfill({
        json: {
          dataset_file_id: dataset.id,
          recommended_target_column: "target",
          recommended_problem_type: "classification",
          target_candidates: [
            {
              column_name: "target",
              score: 0.92,
              inferred_type: "categorical",
              unique_count: 2,
              reason: "Likely label column."
            }
          ],
          missing_value_tokens: ["?", "NA"],
          column_type_overrides: {},
          ignored_columns: [],
          notes: []
        }
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
  await expect(page.getByText(dataset.filename).first()).toBeVisible();
  await expect(page.getByText("5 rows / 4 columns").first()).toBeVisible();
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

test("loads a recommendation into pipeline step parameters", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Analysis" }).click();
  await page.getByRole("button", { name: "Use in Pipeline" }).click();

  await expect(page.getByRole("heading", { name: "Pipeline Builder" })).toBeVisible();
  await expect(page.getByText("Created a pipeline draft and loaded recommendation: numeric_imputation")).toBeVisible();
  await expect(page.locator(".recommendation-focus")).toBeVisible();
  await expect(page.getByLabel("income")).toBeChecked();
  await expect(page.getByLabel("strategy")).toHaveValue("median");
  await expect(page.getByRole("button", { name: "Add Step" })).toBeEnabled();

  await page.getByRole("button", { name: "Add Step" }).click();
  const addedStep = page.locator(".pipeline-step").filter({ hasText: "numeric_imputation" });
  await expect(addedStep).toBeVisible();
  await expect(addedStep).toContainText("income");
});
