import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { l as log } from "./logger-fUeZK7K8.js";
const __dirname$1 = path.dirname(fileURLToPath(import.meta.url));
const skillRoot = path.resolve(__dirname$1, "..");
const PLAYWRIGHT_TO_CHROMIUM = {
  "1.57.0": "1200",
  "1.56.0": "1192",
  "1.55.0": "1185",
  "1.54.0": "1176",
  "1.53.0": "1166",
  "1.52.0": "1156",
  "1.51.0": "1147",
  "1.50.0": "1138",
  "1.49.0": "1129",
  "1.48.0": "1118",
  "1.47.0": "1108",
  "1.46.0": "1097",
  "1.45.0": "1083",
  "1.44.0": "1071",
  "1.43.0": "1061",
  "1.42.0": "1052",
  "1.41.0": "1042"
};
function checkNode() {
  try {
    const v = process.version;
    const major = parseInt(v.replace("v", "").split(".")[0], 10);
    return { ok: major >= 18, version: v };
  } catch {
    return { ok: false, version: null };
  }
}
function checkNodeModules() {
  const nm = path.join(skillRoot, "node_modules");
  if (!fs.existsSync(nm)) {
    return { ok: false };
  }
  try {
    const playwrightPath = path.join(nm, "playwright");
    if (fs.existsSync(playwrightPath)) {
      return { ok: true };
    }
    const entries = fs.readdirSync(nm);
    if (entries.length === 0) {
      return { ok: false, empty: true };
    }
    return { ok: false, missingPlaywright: true };
  } catch {
    return { ok: false };
  }
}
let cachedPlaywrightVersion;
function getPlaywrightVersion() {
  if (cachedPlaywrightVersion !== void 0) {
    return cachedPlaywrightVersion;
  }
  try {
    const pkgPath = path.join(skillRoot, "package.json");
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
    const dep = pkg.dependencies?.playwright;
    if (!dep) {
      cachedPlaywrightVersion = null;
      return null;
    }
    cachedPlaywrightVersion = dep.replace(/^[\^~]/, "");
    return cachedPlaywrightVersion;
  } catch {
    cachedPlaywrightVersion = null;
    return null;
  }
}
const ACCEPTABLE_BROWSERS = [
  { name: "chromium", displayName: "Chromium" },
  { name: "chromium_headless_shell", displayName: "Chromium Headless Shell" }
];
function getBrowserRevisions() {
  const nmCore = path.join(skillRoot, "node_modules", "playwright-core", "browsers.json");
  const nmPlaywright = path.join(skillRoot, "node_modules", "playwright", "browsers.json");
  for (const browsersJson of [nmCore, nmPlaywright]) {
    try {
      if (!fs.existsSync(browsersJson)) {
        continue;
      }
      const data = JSON.parse(fs.readFileSync(browsersJson, "utf-8"));
      const revisions = {};
      for (const browser of ACCEPTABLE_BROWSERS) {
        const entry = data.browsers?.find((b) => b.name === browser.name.replace(/_/g, "-") || b.name === browser.name);
        if (entry?.revision) {
          revisions[browser.name] = entry.revision;
        }
      }
      if (Object.keys(revisions).length > 0) {
        return revisions;
      }
    } catch {
    }
  }
  const pwVersion = getPlaywrightVersion();
  const revision = PLAYWRIGHT_TO_CHROMIUM[pwVersion || ""];
  return { chromium: revision, chromium_headless_shell: revision };
}
function checkBrowsers() {
  const caches = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, "ms-playwright"),
    process.env.HOME && path.join(process.env.HOME, ".cache", "ms-playwright"),
    process.env.HOME && path.join(process.env.HOME, "Library", "Caches", "ms-playwright")
  ].filter((p) => Boolean(p));
  const revisions = getBrowserRevisions();
  const playwrightVersion = getPlaywrightVersion();
  const results = {};
  for (const cacheDir of caches) {
    try {
      if (!fs.existsSync(cacheDir)) {
        continue;
      }
      const entries = fs.readdirSync(cacheDir);
      for (const browser of ACCEPTABLE_BROWSERS) {
        if (results[browser.name]) {
          continue;
        }
        let browserDir = null;
        if (revisions[browser.name]) {
          browserDir = `${browser.name}-${revisions[browser.name]}`;
          if (!entries.includes(browserDir)) {
            continue;
          }
        } else {
          browserDir = entries.find((e) => e.startsWith(`${browser.name}-`)) ?? null;
          if (!browserDir) {
            continue;
          }
        }
        const browserPath = path.join(cacheDir, browserDir);
        const stat = fs.statSync(browserPath);
        if (!stat.isDirectory()) {
          continue;
        }
        const installMarker = path.join(browserPath, "INSTALLATION_COMPLETE");
        if (!fs.existsSync(installMarker)) {
          continue;
        }
        const contents = fs.readdirSync(browserPath).filter((f) => !["INSTALLATION_COMPLETE", "DEPENDENCIES_VALIDATED", ".links"].includes(f));
        if (contents.length === 0) {
          continue;
        }
        results[browser.name] = {
          ok: true,
          path: browserPath,
          revision: browserDir.replace(`${browser.name}-`, ""),
          matched: revisions[browser.name] ? revisions[browser.name] === browserDir.replace(`${browser.name}-`, "") : null
        };
      }
    } catch {
    }
  }
  for (const browser of ACCEPTABLE_BROWSERS) {
    if (!results[browser.name]) {
      results[browser.name] = {
        ok: false,
        requiredRevision: revisions[browser.name]
      };
    }
  }
  return { results, revisions, playwrightVersion };
}
function main() {
  const node = checkNode();
  const nodeModules = checkNodeModules();
  const browsers = checkBrowsers();
  const lines = [];
  if (node.ok) {
    lines.push(`✅ Node.js ${node.version}`);
  } else {
    lines.push(`❌ Node.js 未安装或版本过低（需要 >=18）`);
    lines.push(`   → 安装: https://nodejs.org`);
  }
  if (nodeModules.ok) {
    lines.push(`✅ npm 依赖已安装`);
  } else {
    if (nodeModules.empty) {
      lines.push(`❌ node_modules 目录为空`);
    } else if (nodeModules.missingPlaywright) {
      lines.push(`❌ playwright 依赖缺失`);
    } else {
      lines.push(`❌ npm 依赖未安装`);
    }
    lines.push(`   → 安装: cd ${skillRoot} && npm install`);
  }
  const browsersOk = ACCEPTABLE_BROWSERS.some(
    (b) => browsers.results[b.name]?.ok && browsers.results[b.name]?.matched !== false
  );
  for (const browser of ACCEPTABLE_BROWSERS) {
    const result = browsers.results[browser.name];
    const label = browser.displayName;
    if (!result.ok) {
      if (browsersOk) {
        const revisionHint = result.requiredRevision ? `（可选，${browser.name}-${result.requiredRevision} 未安装）` : "（可选，未安装）";
        lines.push(`ℹ️ ${label} ${revisionHint}`);
      } else if (result.requiredRevision) {
        lines.push(`❌ ${label} 未安装（需要 ${browser.name}-${result.requiredRevision}）`);
        lines.push(`   → 安装: npx playwright install chromium`);
      } else {
        lines.push(`❌ ${label} 未安装`);
        lines.push(`   → 安装: npx playwright install chromium`);
      }
    } else if (result.matched === false) {
      lines.push(`⚠️ ${label} 版本不匹配（当前 revision-${result.revision}）`);
      lines.push(`   → 重装: npx playwright install chromium`);
    } else {
      lines.push(`✅ ${label} ${browser.name}-${result.revision} 已安装`);
    }
  }
  const coreOk = node.ok && nodeModules.ok;
  const allOk = coreOk && browsersOk;
  lines.push("");
  if (allOk) {
    lines.push(`✅ 环境就绪，可以开始制作 PPT`);
  } else {
    lines.push(`⚠️ 环境未就绪，请按上述 → 提示安装`);
    if (!browsersOk) {
      lines.push("");
      lines.push(`📌 浏览器安装必须尝试执行，超时失败后可继续后续 Stage`);
    }
  }
  log(lines.join("\n"));
  process.exit(allOk ? 0 : 1);
}
async function checkEnv() {
  main();
}
if (process.argv[1]?.endsWith("check-env")) {
  main();
}
export {
  checkEnv
};
