import { existsSync } from "node:fs";
import { resolve } from "node:path";

const executable = process.platform === "win32" ? "Scripts/python.exe" : "bin/python";
const candidates = [resolve("../backend/.venv", executable), resolve("../.venv", executable)];

export const testPython = process.env.DATAPREP_TEST_PYTHON || candidates.find(existsSync) || "python";
