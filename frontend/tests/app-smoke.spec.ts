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

const uploadedDataset = {
  ...dataset,
  id: 202,
  filename: "uploaded-smoke.csv",
  storage_path: "uploads/uploaded-smoke.csv",
  file_size_bytes: 160
};

const uploadedAnalysis = {
  ...analysis,
  id: 302,
  readiness_score: 88.25
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

const pipelineRun = {
  id: 701,
  pipeline_id: pipeline.id,
  project_id: project.id,
  status: "completed",
  before_summary: { row_count: 5, column_count: 4 },
  after_summary: { row_count: 5, column_count: 4 },
  output_paths: {
    cleaned_single: "exports/project_101/pipeline_run_701/cleaned_dataset.csv",
    config: "exports/project_101/pipeline_run_701/preprocessing_config.json",
    report: "exports/project_101/pipeline_run_701/preprocessing_report.md",
    code: "exports/project_101/pipeline_run_701/pipeline_code.py"
  },
  report_path: "exports/project_101/pipeline_run_701/preprocessing_report.md",
  config_path: "exports/project_101/pipeline_run_701/preprocessing_config.json",
  code_path: "exports/project_101/pipeline_run_701/pipeline_code.py",
  created_at: "2026-05-17T00:00:00Z"
};

const missingIncomeIssue = {
  id: 501,
  analysis_run_id: analysis.id,
  severity: "warning",
  category: "missingness",
  title: "Missing values in income",
  explanation: "income has missing values that should be handled before modeling.",
  affected_columns: ["income"],
  suggested_actions: ["Impute missing values"],
  created_at: "2026-05-17T00:00:00Z"
};

const missingIncomeSuggestedStep = {
  operation_type: "numeric_imputation",
  columns: ["income"],
  params: { strategy: "median" },
  reason: "Median imputation is a conservative default for numeric missing values."
};

async function mockApi(page: Page) {
  let currentDataset = dataset;
  let currentAnalysis = analysis;
  let createdPipeline: typeof pipeline | null = null;
  let appliedRun: typeof pipelineRun | null = null;

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
      await route.fulfill({ json: currentDataset.id === dataset.id ? [dataset] : [currentDataset, dataset] });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/analysis`) {
      await route.fulfill({ json: currentAnalysis.id === analysis.id ? [analysis] : [currentAnalysis, analysis] });
      return;
    }

    if (method === "POST" && url.pathname === `/projects/${project.id}/datasets/upload`) {
      if (request.postData()?.includes("broken.csv")) {
        await route.fulfill({ status: 400, body: "Invalid CSV file" });
        return;
      }
      currentDataset = uploadedDataset;
      await route.fulfill({ status: 201, json: { dataset: currentDataset } });
      return;
    }

    if (method === "GET" && url.pathname === `/datasets/${currentDataset.id}/preview`) {
      await route.fulfill({
        json: {
          dataset_file_id: currentDataset.id,
          columns: currentDataset.columns,
          rows: [
            { age: 34, income: 72000, city: "Austin", target: "yes" },
            { age: 41, income: null, city: "Seattle", target: "no" }
          ],
          row_count: currentDataset.row_count,
          limit: Number(url.searchParams.get("limit") ?? 5)
        }
      });
      return;
    }

    if (method === "POST" && url.pathname === `/projects/${project.id}/analysis/run`) {
      currentAnalysis = uploadedAnalysis;
      await route.fulfill({ status: 201, json: currentAnalysis });
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

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/steps/from-issue/${missingIncomeIssue.id}` && createdPipeline) {
      const step = {
        id: 602,
        pipeline_id: pipeline.id,
        order_index: createdPipeline.steps.length,
        enabled: true,
        operation_type: missingIncomeSuggestedStep.operation_type,
        columns: missingIncomeSuggestedStep.columns,
        params: missingIncomeSuggestedStep.params,
        created_at: "2026-05-17T00:00:00Z",
        updated_at: "2026-05-17T00:00:00Z"
      };
      createdPipeline = { ...createdPipeline, steps: [...createdPipeline.steps, step] };
      await route.fulfill({ status: 201, json: step });
      return;
    }

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/validate`) {
      await route.fulfill({
        json: {
          valid: true,
          issues: [
            {
              severity: "warning",
              step_id: 601,
              operation_type: "numeric_imputation",
              message: "Review median imputation before applying."
            }
          ]
        }
      });
      return;
    }

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/preview`) {
      await route.fulfill({
        json: {
          before_summary: { row_count: 5, column_count: 4, missing_cells: 1 },
          after_summary: { row_count: 5, column_count: 4, missing_cells: 0 },
          affected_columns: ["income"],
          before_sample_rows: [{ age: 41, income: null, city: "Seattle", target: "no" }],
          sample_rows: [{ age: 41, income: 72000, city: "Seattle", target: "no" }],
          column_diffs: [
            {
              column_name: "income",
              status: "changed",
              before_missing_count: 1,
              after_missing_count: 0,
              before_non_null_count: 4,
              after_non_null_count: 5,
              changed_sample_count: 1,
              before_dtype: "float64",
              after_dtype: "float64"
            }
          ],
          step_effects: [
            {
              operation_type: "numeric_imputation",
              summary: "Filled missing income values."
            }
          ],
          warnings: [],
          fitted_params: []
        }
      });
      return;
    }

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/preview/charts`) {
      await route.fulfill({ json: { analysis_id: currentAnalysis.id, charts: {} } });
      return;
    }

    if (method === "POST" && url.pathname === `/pipelines/${pipeline.id}/apply`) {
      appliedRun = pipelineRun;
      await route.fulfill({ status: 201, json: appliedRun });
      return;
    }

    if (method === "GET" && url.pathname === `/pipeline-runs/${pipelineRun.id}` && appliedRun) {
      await route.fulfill({ json: appliedRun });
      return;
    }

    if (method === "GET" && url.pathname === `/projects/${project.id}/pipeline-runs`) {
      await route.fulfill({ json: appliedRun ? [appliedRun] : [] });
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

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/overview` || url.pathname === `/analysis/${uploadedAnalysis.id}/overview`)) {
      await route.fulfill({
        json: {
          analysis_run: currentAnalysis,
          row_count: 5,
          column_count: 4,
          issue_counts: { warning: 1 },
          column_type_counts: { numeric: 2, categorical: 2 },
          target_summary: null
        }
      });
      return;
    }

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/preprocessing-recommendations` || url.pathname === `/analysis/${uploadedAnalysis.id}/preprocessing-recommendations`)) {
      await route.fulfill({
        json: {
          analysis_id: currentAnalysis.id,
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

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/train-test-comparison` || url.pathname === `/analysis/${uploadedAnalysis.id}/train-test-comparison`)) {
      await route.fulfill({ status: 404, json: { detail: "Train/test comparison not found" } });
      return;
    }

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/charts` || url.pathname === `/analysis/${uploadedAnalysis.id}/charts`)) {
      await route.fulfill({ json: { analysis_id: currentAnalysis.id, charts: {} } });
      return;
    }

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/columns` || url.pathname === `/analysis/${uploadedAnalysis.id}/columns`)) {
      await route.fulfill({
        json: [
          {
            id: 1,
            analysis_run_id: currentAnalysis.id,
            dataset_role: "single",
            column_name: "income",
            inferred_type: "numeric",
            missing_count: 1,
            missing_rate: 0.2,
            unique_count: 4,
            cardinality_ratio: 0.8,
            summary: { mean: 68000, median: 72000 },
            warnings: []
          }
        ]
      });
      return;
    }

    if (
      method === "GET" &&
      (url.pathname === `/analysis/${analysis.id}/columns/income/charts` || url.pathname === `/analysis/${uploadedAnalysis.id}/columns/income/charts`)
    ) {
      await route.fulfill({
        json: {
          analysis_id: currentAnalysis.id,
          charts: {
            numeric_summary: {
              chart_type: "bar",
              title: "Income Numeric Summary",
              description: "Distribution summary for the selected income column.",
              data: [
                { label: "mean", value: 68000 },
                { label: "median", value: 72000 }
              ]
            }
          }
        }
      });
      return;
    }

    if (method === "GET" && (url.pathname === `/analysis/${analysis.id}/issues` || url.pathname === `/analysis/${uploadedAnalysis.id}/issues`)) {
      await route.fulfill({ json: [{ ...missingIncomeIssue, analysis_run_id: currentAnalysis.id }] });
      return;
    }

    if (method === "GET" && url.pathname === `/issues/${missingIncomeIssue.id}/suggested-step`) {
      await route.fulfill({ json: missingIncomeSuggestedStep });
      return;
    }

    if (method === "GET" && (url.pathname === `/datasets/${dataset.id}/setup-suggestions` || url.pathname === `/datasets/${uploadedDataset.id}/setup-suggestions`)) {
      await route.fulfill({
        json: {
          dataset_file_id: currentDataset.id,
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

  await expect(page.getByRole("heading", { name: "Pipeline Overview" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Import Config" })).toBeVisible();
  await expect(page.getByLabel("preprocessing_config.json")).toBeVisible();
  await expect(page.getByRole("button", { name: "Import Config" })).toBeDisabled();
});

test("uploads a CSV and runs analysis from the upload completion state", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Upload Dataset" }).click();

  await page.getByLabel("CSV File").setInputFiles({
    name: uploadedDataset.filename,
    mimeType: "text/csv",
    buffer: Buffer.from("age,income,city,target\n34,72000,Austin,yes\n41,,Seattle,no\n")
  });
  await page.getByRole("button", { name: "Upload CSV" }).click();

  await expect(page.getByText(`Upload complete: ${uploadedDataset.filename}`)).toBeVisible();
  await expect(page.getByText("Austin")).toBeVisible();
  await expect(page.getByText(uploadedDataset.filename).first()).toBeVisible();

  await page.getByRole("button", { name: "Run Analysis" }).click();
  await expect(page.getByRole("heading", { name: "Run Analysis" })).toBeVisible();
  await expect(page.getByText("Suggested setup applied from the loaded dataset.")).toBeVisible();

  await page.getByRole("button", { name: "Run Analysis" }).click();
  await expect(page.getByText("88.3").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Download Report" })).toBeVisible();
  await expect(page.getByText("Impute numeric missing values")).toBeVisible();
});

test("shows a readable upload error when the backend rejects a CSV", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Upload Dataset" }).click();

  await page.getByLabel("CSV File").setInputFiles({
    name: "broken.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("not,a,valid,csv\n\"unterminated\n")
  });
  await page.getByRole("button", { name: "Upload CSV" }).click();

  await expect(page.getByText("Invalid CSV file")).toBeVisible();
  await expect(page.getByText("Upload complete:")).not.toBeVisible();
});

test("loads a recommendation into pipeline step parameters", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Analysis" }).click();
  await page.getByRole("button", { name: "Add to Pipeline" }).click();

  await expect(page.getByRole("heading", { name: "Pipeline Overview" })).toBeVisible();
  await expect(page.getByText("Added recommendation to pipeline: numeric_imputation")).toBeVisible();
  await expect(page.getByText("Next: validate the pipeline, preview changes, or add another manual step.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Added From Recommendations" })).toBeVisible();
  await expect(page.getByText("Impute numeric missing values").first()).toBeVisible();
  await expect(page.getByText("Analysis recommendation / numeric_imputation / income")).toBeVisible();
  const addedStep = page.locator(".pipeline-step").filter({ hasText: "numeric_imputation" });
  await expect(addedStep).toBeVisible();
  await expect(addedStep).toContainText("Numeric Imputation");
  await expect(addedStep).toContainText("Recommended");
  await expect(addedStep).toContainText("strategy: median");
  await expect(addedStep).toContainText("Preview impact");
  await expect(addedStep).toContainText("income");

  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(page.getByText("Pipeline is valid")).toBeVisible();
  await expect(addedStep).toContainText("1 validation issue");
  await expect(addedStep).toContainText("Review median imputation before applying.");
  await expect(addedStep).toContainText("Fix:");

  await page.getByRole("main").getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Pipeline Preview" })).toBeVisible();
  await expect(page.getByText("Filled missing income values.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "income" })).toBeVisible();

  await page.getByRole("button", { name: "Apply Pipeline" }).click();
  await expect(page.getByRole("heading", { name: `Downloads for Run #${pipelineRun.id}` })).toBeVisible();
  await expect(page.getByRole("link", { name: "Config" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Report" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Code" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Cleaned CSV" })).toBeVisible();
});

test("adds an issue suggestion to the selected pipeline", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Analysis" }).click();
  await page.getByRole("button", { name: "Add to Pipeline" }).click();
  await expect(page.getByText("Added recommendation to pipeline: numeric_imputation")).toBeVisible();

  await page.getByRole("navigation").getByRole("button", { name: "Issues" }).click();
  await expect(page.getByRole("heading", { name: "Issues" })).toBeVisible();
  await expect(page.getByText(missingIncomeIssue.title)).toBeVisible();

  await page.getByRole("button", { name: "Suggest Step" }).click();
  await expect(page.getByText(missingIncomeSuggestedStep.reason)).toBeVisible();
  await expect(page.getByText("numeric_imputation").first()).toBeVisible();

  await page.getByRole("button", { name: "Add to Pipeline" }).click();
  await expect(page.getByText("Suggested step added.")).toBeVisible();
});

test("opens column profiles and renders selected column charts", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Projects" }).click();
  await page.getByRole("button", { name: project.name }).click();
  await page.getByRole("button", { name: "Analysis" }).click();
  await page.getByRole("main").getByRole("button", { name: "Columns" }).click();

  await expect(page.getByRole("heading", { name: "Columns" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "income" })).toBeVisible();
  await expect(page.getByText('"median": 72000')).toBeVisible();
  await expect(page.getByRole("heading", { name: "Charts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Income Numeric Summary" })).toBeVisible();
  await expect(page.getByText("Distribution summary for the selected income column.")).toBeVisible();
});
