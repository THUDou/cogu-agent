import fs from "node:fs";
import path from "node:path";
import { e as error } from "./logger-fUeZK7K8.js";
const MAX_SEQ = 1e3;
function generateTimestampDir(baseDir) {
  if (!baseDir || typeof baseDir !== "string" || baseDir.trim() === "") {
    error("错误：输出目录路径不能为空");
    process.exit(1);
  }
  const now = /* @__PURE__ */ new Date();
  const timestampPrefix = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
    "_",
    String(now.getHours()).padStart(2, "0"),
    String(now.getMinutes()).padStart(2, "0"),
    String(now.getSeconds()).padStart(2, "0")
  ].join("");
  if (!fs.existsSync(baseDir)) {
    fs.mkdirSync(baseDir, { recursive: true });
  }
  let seq = 0;
  while (fs.existsSync(path.join(baseDir, `${timestampPrefix}_${String(seq).padStart(3, "0")}`))) {
    if (seq >= MAX_SEQ) {
      error(`错误：同前缀目录数已达上限 (${MAX_SEQ})`);
      process.exit(1);
    }
    seq++;
  }
  const timestampDir = path.join(baseDir, `${timestampPrefix}_${String(seq).padStart(3, "0")}`);
  fs.mkdirSync(timestampDir, { recursive: true });
  const pagesDir = path.join(timestampDir, "pages");
  fs.mkdirSync(pagesDir, { recursive: true });
  return timestampDir;
}
if (process.argv[1]?.endsWith("generate_timestamp_dir")) {
  const defaultBase = path.resolve(process.cwd(), "workspace");
  const result = generateTimestampDir(process.argv[2] || defaultBase);
  console.log(result);
}
export {
  generateTimestampDir
};
