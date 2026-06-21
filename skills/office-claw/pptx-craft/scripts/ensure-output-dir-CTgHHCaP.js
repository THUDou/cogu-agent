import fs from "node:fs";
import path from "node:path";
import { e as error } from "./logger-fUeZK7K8.js";
function ensureOutputDir(outputDir) {
  const resolvedPath = path.resolve(outputDir);
  if (path.basename(resolvedPath) === "pages") {
    error("Error: Do not pass a path ending in 'pages' to this script");
    process.exit(1);
  }
  const pagesDir = path.join(outputDir, "pages");
  fs.mkdirSync(pagesDir, { recursive: true });
  if (!fs.existsSync(pagesDir) || !fs.statSync(pagesDir).isDirectory()) {
    error(`Error: Failed to create directory ${pagesDir}`);
    process.exit(1);
  }
  return path.resolve(pagesDir);
}
if (process.argv[1]?.endsWith("ensure_output_dir")) {
  const target = process.argv[2];
  if (!target) {
    console.error("Usage: node ensure_output_dir.ts <directory>");
    process.exit(1);
  }
  const result = ensureOutputDir(target);
  console.log(result);
}
export {
  ensureOutputDir
};
