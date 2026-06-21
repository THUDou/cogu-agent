import fs, { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { join, dirname, resolve, relative, isAbsolute, parse, basename } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import express from "express";
import getPort from "get-port";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
const CDN_BASE_URL = "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets";
const __dirname$1 = dirname(fileURLToPath(import.meta.url));
function hasAssetsManifest(dirPath) {
  return existsSync(join(dirPath, "css", "fonts.css"));
}
function* walkAncestorDirs(startDir) {
  let currentDir = resolve(startDir);
  while (true) {
    yield currentDir;
    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) {
      return;
    }
    currentDir = parentDir;
  }
}
function resolveAssetsDirFrom(startDir) {
  for (const ancestorDir of walkAncestorDirs(startDir)) {
    const directAssetsDir = join(ancestorDir, "assets");
    if (hasAssetsManifest(directAssetsDir)) {
      return directAssetsDir;
    }
    const workspaceAssetsDir = join(ancestorDir, "packages", "core", "assets");
    if (hasAssetsManifest(workspaceAssetsDir)) {
      return workspaceAssetsDir;
    }
    const siblingCoreAssetsDir = join(ancestorDir, "core", "assets");
    if (hasAssetsManifest(siblingCoreAssetsDir)) {
      return siblingCoreAssetsDir;
    }
  }
  return null;
}
function resolveAssetsDir() {
  const candidates = [__dirname$1, process.cwd()];
  for (const startDir of candidates) {
    const resolvedDir = resolveAssetsDirFrom(startDir);
    if (resolvedDir) {
      return resolvedDir;
    }
  }
  return join(__dirname$1, "..", "..", "assets");
}
const ASSETS_DIR = resolveAssetsDir();
const KNOWN_ASSET_MAPPINGS = [
  {
    remotePrefix: `${CDN_BASE_URL}/`,
    localSubdir: ""
  },
  {
    remotePrefix: "https://npmmirror.com/mirrors/fonteditor-core@2.6.3/",
    localSubdir: "fonteditor-core@2.6.3"
  }
];
const MIME_MAP = {
  ".js": "application/javascript",
  ".mjs": "application/javascript",
  ".css": "text/css",
  ".wasm": "application/wasm",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".svg": "image/svg+xml"
};
function getMimeType(fileUrl) {
  const pathname = fileUrl.split("?")[0].toLowerCase();
  for (const [ext, mime] of Object.entries(MIME_MAP)) {
    if (pathname.endsWith(ext)) {
      return mime;
    }
  }
  return "application/octet-stream";
}
function getDefaultExportFromCjs(x) {
  return x && x.__esModule && Object.prototype.hasOwnProperty.call(x, "default") ? x["default"] : x;
}
var ms$1;
var hasRequiredMs;
function requireMs() {
  if (hasRequiredMs) return ms$1;
  hasRequiredMs = 1;
  var s = 1e3;
  var m = s * 60;
  var h = m * 60;
  var d = h * 24;
  var w = d * 7;
  var y = d * 365.25;
  ms$1 = function(val, options) {
    options = options || {};
    var type = typeof val;
    if (type === "string" && val.length > 0) {
      return parse2(val);
    } else if (type === "number" && isFinite(val)) {
      return options.long ? fmtLong(val) : fmtShort(val);
    }
    throw new Error(
      "val is not a non-empty string or a valid number. val=" + JSON.stringify(val)
    );
  };
  function parse2(str) {
    str = String(str);
    if (str.length > 100) {
      return;
    }
    var match = /^(-?(?:\d+)?\.?\d+) *(milliseconds?|msecs?|ms|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d|weeks?|w|years?|yrs?|y)?$/i.exec(
      str
    );
    if (!match) {
      return;
    }
    var n = parseFloat(match[1]);
    var type = (match[2] || "ms").toLowerCase();
    switch (type) {
      case "years":
      case "year":
      case "yrs":
      case "yr":
      case "y":
        return n * y;
      case "weeks":
      case "week":
      case "w":
        return n * w;
      case "days":
      case "day":
      case "d":
        return n * d;
      case "hours":
      case "hour":
      case "hrs":
      case "hr":
      case "h":
        return n * h;
      case "minutes":
      case "minute":
      case "mins":
      case "min":
      case "m":
        return n * m;
      case "seconds":
      case "second":
      case "secs":
      case "sec":
      case "s":
        return n * s;
      case "milliseconds":
      case "millisecond":
      case "msecs":
      case "msec":
      case "ms":
        return n;
      default:
        return void 0;
    }
  }
  function fmtShort(ms2) {
    var msAbs = Math.abs(ms2);
    if (msAbs >= d) {
      return Math.round(ms2 / d) + "d";
    }
    if (msAbs >= h) {
      return Math.round(ms2 / h) + "h";
    }
    if (msAbs >= m) {
      return Math.round(ms2 / m) + "m";
    }
    if (msAbs >= s) {
      return Math.round(ms2 / s) + "s";
    }
    return ms2 + "ms";
  }
  function fmtLong(ms2) {
    var msAbs = Math.abs(ms2);
    if (msAbs >= d) {
      return plural(ms2, msAbs, d, "day");
    }
    if (msAbs >= h) {
      return plural(ms2, msAbs, h, "hour");
    }
    if (msAbs >= m) {
      return plural(ms2, msAbs, m, "minute");
    }
    if (msAbs >= s) {
      return plural(ms2, msAbs, s, "second");
    }
    return ms2 + " ms";
  }
  function plural(ms2, msAbs, n, name) {
    var isPlural = msAbs >= n * 1.5;
    return Math.round(ms2 / n) + " " + name + (isPlural ? "s" : "");
  }
  return ms$1;
}
var msExports = requireMs();
const ms = /* @__PURE__ */ getDefaultExportFromCjs(msExports);
const DEFAULT_FONT_FAMILY = "Noto Sans SC";
const APPROVED_FONT_FAMILIES = [
  DEFAULT_FONT_FAMILY,
  "WenYuan Sans SC",
  "文源黑体",
  "NanxiXinyuanti",
  "南西新圆体",
  "Frex Sans GB",
  "Frex Sans GB VF",
  "械黑 GB",
  "械黑GB",
  "WenJin Mincho Plane 0",
  "WenJin Mincho Plane 2",
  "WenJin Mincho Plane 3",
  "WenJin Mincho C Plane 0",
  "WenJin Mincho C Plane 2",
  "WenJin Mincho C Plane 3",
  "WenJin Mincho W Plane 0",
  "WenJin Mincho W Plane 2",
  "WenJin Mincho W Plane 3",
  "文津宋体 第0平面",
  "文津宋体 第2平面",
  "文津宋体 第3平面",
  "文津宋體 第0平面",
  "文津宋體 第2平面",
  "文津宋體 第3平面"
];
const APPROVED_FONT_FAMILY_SET = new Set(APPROVED_FONT_FAMILIES.map((font) => font.toLowerCase()));
function parseFontFamilyList(fontFamilyValue = "") {
  return fontFamilyValue.split(",").map((part) => part.trim().replace(/^["']|["']$/g, "")).filter(Boolean);
}
function getApprovedFontFamily(fontFamilyValue = "") {
  const families = parseFontFamilyList(fontFamilyValue);
  return families.find((family) => APPROVED_FONT_FAMILY_SET.has(family.toLowerCase())) ?? null;
}
function containsApprovedFontReference(value = "") {
  const lowerValue = value.toLowerCase();
  return APPROVED_FONT_FAMILIES.some((font) => lowerValue.includes(font.toLowerCase()));
}
function isExactApprovedFontFamily(fontFamilyValue = "") {
  const families = parseFontFamilyList(fontFamilyValue);
  return families.length === 1 && APPROVED_FONT_FAMILY_SET.has(families[0]?.toLowerCase() ?? "");
}
function normalizeToApprovedFontFamily(fontFamilyValue = "") {
  return getApprovedFontFamily(fontFamilyValue) ?? DEFAULT_FONT_FAMILY;
}
const ASSETS_ROOT = ASSETS_DIR;
const PptxAsset = {
  tailwind: `${CDN_BASE_URL}/vendors/tailwind.js`,
  echarts: `${CDN_BASE_URL}/vendors/echarts.min.js`,
  fontawesome: `${CDN_BASE_URL}/vendors/fontawesome/css/all.min.css`,
  mathjax: `${CDN_BASE_URL}/vendors/mathjax/tex-svg.min.js`,
  fontsCss: `${CDN_BASE_URL}/css/fonts.css`
};
const LOCAL_ASSET_PLACEHOLDER_RE = /^__LOCAL_ASSET__:(tailwind|echarts|fontawesome|mathjax|fonts|fontsCss)__$/i;
const LOCAL_MAPPINGS = KNOWN_ASSET_MAPPINGS.map((m) => ({
  remotePrefix: m.remotePrefix,
  localDir: m.localSubdir ? join(ASSETS_ROOT, m.localSubdir) : ASSETS_ROOT
}));
function hasLocalAssets() {
  return existsSync(ASSETS_ROOT);
}
function getAssetsRoot() {
  return ASSETS_ROOT;
}
function toPosixPath(inputPath) {
  return String(inputPath).replace(/\\/g, "/");
}
function isWindowsAbsolutePath(inputPath) {
  return /^[A-Za-z]:[\\/]/.test(inputPath);
}
function resolvePortablePath(inputPath) {
  return isWindowsAbsolutePath(inputPath) ? inputPath : resolve(inputPath);
}
function getPlaceholderAssetUrl(input) {
  const match = LOCAL_ASSET_PLACEHOLDER_RE.exec(input);
  if (!match?.[1]) {
    return null;
  }
  const name = match[1].toLowerCase();
  if (name === "fonts" || name === "fontscss") {
    return PptxAsset.fontsCss;
  }
  return PptxAsset[name] ?? null;
}
function mapExternalResourceUrlToPptxAssetUrl(urlValue, serverOrigin) {
  if (!urlValue) {
    return urlValue;
  }
  const input = String(urlValue);
  const placeholderAssetUrl = getPlaceholderAssetUrl(input);
  if (placeholderAssetUrl) {
    return placeholderAssetUrl;
  }
  if (input.startsWith("file://") || serverOrigin && input.startsWith(serverOrigin)) {
    return input;
  }
  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    return urlValue;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return urlValue;
  }
  const host = parsed.hostname.toLowerCase();
  const pathname = parsed.pathname.toLowerCase();
  const urlText = parsed.toString().toLowerCase();
  if (host === "cdn.tailwindcss.com") {
    return PptxAsset.tailwind;
  }
  if ((host.includes("jsdelivr.net") || host.includes("unpkg.com") || host.includes("cdnjs.cloudflare.com")) && (pathname.includes("tailwindcss") || pathname.includes("/tailwind."))) {
    return PptxAsset.tailwind;
  }
  if (host.includes("echarts.apache.org") || (host.includes("jsdelivr.net") || host.includes("unpkg.com") || host.includes("cdnjs.cloudflare.com")) && (pathname.includes("echarts") || /\/echarts(?:\.min)?\.js$/.test(pathname))) {
    return PptxAsset.echarts;
  }
  if ((host.includes("jsdelivr.net") || host.includes("unpkg.com") || host.includes("cdnjs.cloudflare.com")) && (pathname.includes("fontawesome") || pathname.includes("@fortawesome") || pathname.includes("/font-awesome/") || pathname.endsWith("/all.min.css")) || urlText.includes("@fortawesome/fontawesome-free")) {
    return PptxAsset.fontawesome;
  }
  if ((host.includes("jsdelivr.net") || host.includes("unpkg.com") || host.includes("cdnjs.cloudflare.com")) && pathname.includes("mathjax")) {
    return PptxAsset.mathjax;
  }
  if (host === "fonts.googleapis.com" || host === "fonts.gstatic.com") {
    return PptxAsset.fontsCss;
  }
  return urlValue;
}
function rewriteHtmlExternalResourceUrlsToCdnAssets(html, serverOrigin) {
  return String(html).replace(
    /__LOCAL_ASSET__:(?:tailwind|echarts|fontawesome|mathjax|fonts|fontsCss)__/gi,
    (matchedUrl) => mapExternalResourceUrlToPptxAssetUrl(matchedUrl, serverOrigin)
  ).replace(
    /https?:\/\/[^\s"'()<>]+/gi,
    (matchedUrl) => mapExternalResourceUrlToPptxAssetUrl(matchedUrl, serverOrigin)
  );
}
function longestCommonDir(paths) {
  if (paths.length === 0) {
    throw new Error("无法从空输入中解析 htmlDir");
  }
  const normalizedDirs = paths.map((currentPath) => resolvePortablePath(dirname(currentPath)));
  if (normalizedDirs.every((currentDir) => currentDir.toLowerCase() === normalizedDirs[0]?.toLowerCase())) {
    return normalizedDirs[0];
  }
  let commonPrefix = normalizedDirs[0];
  for (let index = 1; index < normalizedDirs.length; index++) {
    const currentDir = normalizedDirs[index];
    let cursor = 0;
    const maxLength = Math.min(commonPrefix.length, currentDir.length);
    while (cursor < maxLength && commonPrefix[cursor]?.toLowerCase() === currentDir[cursor]?.toLowerCase()) {
      cursor++;
    }
    commonPrefix = commonPrefix.slice(0, cursor);
  }
  const root = parse(normalizedDirs[0]).root;
  const lastSeparatorIndex = Math.max(commonPrefix.lastIndexOf("\\"), commonPrefix.lastIndexOf("/"));
  if (commonPrefix.toLowerCase() === root.toLowerCase()) {
    return root;
  }
  if (lastSeparatorIndex < root.length - 1) {
    return root;
  }
  return commonPrefix.slice(0, lastSeparatorIndex);
}
function resolveHtmlDirFromInput(input) {
  if (Array.isArray(input)) {
    return longestCommonDir(input);
  }
  const resolvedInput = resolvePortablePath(input);
  if (/\.html?$/i.test(resolvedInput)) {
    return dirname(resolvedInput);
  }
  return resolvedInput;
}
function buildRenderPageUrl(serverOrigin, htmlDir, filePath) {
  const resolvedHtmlDir = resolvePortablePath(htmlDir);
  const resolvedFilePath = resolvePortablePath(filePath);
  const relativePath = relative(resolvedHtmlDir, resolvedFilePath);
  const isInsideHtmlDir = relativePath === "" || !relativePath.startsWith("..") && !isAbsolute(relativePath);
  if (!isInsideHtmlDir) {
    throw new Error(`HTML 文件不在服务目录下: ${resolvedFilePath}`);
  }
  const encodedPath = toPosixPath(relativePath).replace(/^\/+/, "").split("/").filter(Boolean).map((segment) => encodeURIComponent(segment)).join("/");
  return new URL(encodedPath || ".", `${serverOrigin.replace(/\/$/, "")}/`).toString();
}
function mapKnownAssetUrlToLocalUrl(urlValue, serverOrigin) {
  if (!urlValue) {
    return urlValue;
  }
  const input = String(urlValue);
  if (input.startsWith("file://") || serverOrigin && input.startsWith(serverOrigin)) {
    return input;
  }
  for (const mapping of LOCAL_MAPPINGS) {
    if (!input.startsWith(mapping.remotePrefix)) {
      continue;
    }
    const parsed = new URL(input);
    const pathnamePrefix = new URL(mapping.remotePrefix).pathname.replace(/\/$/, "");
    const relativePath = decodeURIComponent(parsed.pathname.slice(pathnamePrefix.length)).replace(/^\/+/, "");
    const localRoot = resolve(mapping.localDir);
    const localPath = resolve(localRoot, relativePath);
    const relativeToRoot = relative(localRoot, localPath);
    const isInsideRoot = relativeToRoot === "" || !relativeToRoot.startsWith("..") && !isAbsolute(relativeToRoot);
    if (!isInsideRoot) {
      return urlValue;
    }
    if (!existsSync(localPath)) {
      return urlValue;
    }
    if (!serverOrigin) {
      return `${pathToFileURL(localPath).toString()}${parsed.search}${parsed.hash}`;
    }
    const encodedRelativePath = relativePath.split("/").filter(Boolean).map((segment) => encodeURIComponent(segment)).join("/");
    return new URL(
      `${pathnamePrefix}/${encodedRelativePath}${parsed.search}${parsed.hash}`,
      `${serverOrigin}/`
    ).toString();
  }
  return urlValue;
}
function mapKnownAssetUrlToLocalFileUrl(urlValue) {
  return mapKnownAssetUrlToLocalUrl(urlValue);
}
function rewriteHtmlCdnUrlsToLocalAssets(html, serverOrigin) {
  let output = rewriteHtmlExternalResourceUrlsToCdnAssets(html, serverOrigin);
  for (const mapping of LOCAL_MAPPINGS) {
    const escapedPrefix = mapping.remotePrefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    output = output.replace(
      new RegExp(`${escapedPrefix}[^\\s"'()<>]*`, "g"),
      (matchedUrl) => mapKnownAssetUrlToLocalUrl(matchedUrl, serverOrigin)
    );
  }
  return output;
}
async function startRenderServer(htmlDir) {
  const resolvedHtmlDir = resolve(htmlDir);
  const imagesDir = resolve(resolvedHtmlDir, "..", "images");
  const port = await getPort();
  const app = express();
  const origin = `http://127.0.0.1:${port}`;
  app.get("/slidagent/pptx-craft/assets/css/:file", async (request, response, next) => {
    try {
      const cssFilePath = resolve(join(ASSETS_ROOT, "css", request.params.file));
      const cssRoot = resolve(join(ASSETS_ROOT, "css"));
      const relativeToRoot = relative(cssRoot, cssFilePath);
      const isInsideRoot = relativeToRoot === "" || !relativeToRoot.startsWith("..") && !isAbsolute(relativeToRoot);
      if (!isInsideRoot) {
        response.status(404).end();
        return;
      }
      const cssText = await readFile(cssFilePath, "utf-8");
      response.type("text/css").send(rewriteHtmlCdnUrlsToLocalAssets(cssText, origin));
    } catch (error) {
      next(error);
    }
  });
  app.use("/slidagent/pptx-craft/assets", express.static(ASSETS_ROOT));
  app.use("/images", express.static(imagesDir));
  app.use("/", express.static(resolvedHtmlDir));
  const server = await new Promise((resolveServer, rejectServer) => {
    const instance = app.listen(port, "127.0.0.1", () => resolveServer(instance));
    instance.on("error", rejectServer);
  });
  return {
    htmlDir: resolvedHtmlDir,
    origin,
    close: async () => await new Promise((resolveClose, rejectClose) => {
      server.close((error) => {
        if (error) {
          rejectClose(error);
          return;
        }
        resolveClose();
      });
    })
  };
}
async function routeLocalAssetRequests(page) {
  let interceptCount = 0;
  await page.route("**/*", async (route) => {
    const requestUrl = route.request().url();
    const localUrl = mapKnownAssetUrlToLocalFileUrl(requestUrl);
    if (localUrl === requestUrl) {
      await route.continue();
      return;
    }
    interceptCount++;
    const fileName = localUrl.split("/").pop() || localUrl;
    console.log(`    🔄 CDN → 本地 #${interceptCount}: ${fileName}`);
    try {
      const filePath = fileURLToPath(localUrl);
      const body = await readFile(filePath);
      await route.fulfill({
        status: 200,
        body,
        contentType: getMimeType(filePath)
      });
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      console.warn(`    ⚠️ 本地资源加载失败: ${requestUrl} -> ${localUrl} - ${msg}`);
      await route.abort();
    }
  });
}
async function createLocalizedHtmlCopy(htmlPath, serverOrigin) {
  const originalHtml = await readFile(htmlPath, "utf-8");
  const localizedHtml = rewriteHtmlCdnUrlsToLocalAssets(originalHtml, serverOrigin);
  if (localizedHtml === originalHtml) {
    return null;
  }
  const localizedHtmlPath = join(
    dirname(htmlPath),
    `__local_assets_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.html`
  );
  await writeFile(localizedHtmlPath, localizedHtml, "utf-8");
  return localizedHtmlPath;
}
const nodeRequire = createRequire(import.meta.url);
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
const ACCEPTABLE_BROWSERS = ["chromium", "chromium_headless_shell"];
const INSTALL_COMMAND = "npx playwright install chromium";
const INSTALL_TIMEOUT_ENV = "PPTX_CRAFT_CHROMIUM_INSTALL_TIMEOUT_MS";
const DEFAULT_INSTALL_TIMEOUT_MS = 5 * 60 * 1e3;
const CHROMIUM_DOWNLOAD_HOST_ENV = "PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST";
const DOWNLOAD_HOST_ENV = "PLAYWRIGHT_DOWNLOAD_HOST";
const DOWNLOAD_TIMEOUT_ENV = "PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT";
const CHINA_DOWNLOAD_HOST_EXAMPLE = "https://npmmirror.com/mirrors/playwright";
function getPlaywrightInstallEnv() {
  const env = { ...process.env };
  if (!env[CHROMIUM_DOWNLOAD_HOST_ENV] && !env[DOWNLOAD_HOST_ENV]) {
    env[DOWNLOAD_HOST_ENV] = CHINA_DOWNLOAD_HOST_EXAMPLE;
  }
  return env;
}
function getConfiguredDownloadHost(env) {
  const chromiumHost = env[CHROMIUM_DOWNLOAD_HOST_ENV];
  if (chromiumHost) {
    return { name: CHROMIUM_DOWNLOAD_HOST_ENV, value: chromiumHost };
  }
  const downloadHost = env[DOWNLOAD_HOST_ENV];
  if (downloadHost) {
    return { name: DOWNLOAD_HOST_ENV, value: downloadHost };
  }
  return null;
}
function getChinaDownloadHostHint() {
  return [
    "默认使用国内 Playwright Chromium 下载源；如需覆盖，可指定：",
    `  ${DOWNLOAD_HOST_ENV}=${CHINA_DOWNLOAD_HOST_EXAMPLE} ${INSTALL_COMMAND}`,
    `也可使用 ${CHROMIUM_DOWNLOAD_HOST_ENV} 或 ${DOWNLOAD_TIMEOUT_ENV} 配置自定义镜像/超时。`
  ].join("\n");
}
function getInstallTimeoutMs(env) {
  const raw = env[INSTALL_TIMEOUT_ENV];
  if (!raw) {
    return DEFAULT_INSTALL_TIMEOUT_MS;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_INSTALL_TIMEOUT_MS;
}
function getLocalPlaywrightCliPath() {
  const pkgPath = nodeRequire.resolve("playwright/package.json");
  return join(dirname(pkgPath), "cli.js");
}
function terminateProcessTree(child) {
  if (!child.pid) {
    return;
  }
  if (process.platform === "win32") {
    spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch {
    try {
      process.kill(child.pid, "SIGTERM");
    } catch {
    }
  }
  setTimeout(() => {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      try {
        process.kill(child.pid, "SIGKILL");
      } catch {
      }
    }
  }, 2e3).unref();
}
async function runPlaywrightInstall(cliPath, installEnv, timeout) {
  await new Promise((resolve2, reject) => {
    let timedOut = false;
    const child = spawn(process.execPath, [cliPath, "install", "chromium"], {
      cwd: dirname(nodeRequire.resolve("playwright/package.json")),
      env: installEnv,
      stdio: "inherit",
      detached: process.platform !== "win32"
    });
    const timer = setTimeout(() => {
      timedOut = true;
      terminateProcessTree(child);
    }, timeout);
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      if (timedOut) {
        reject(new Error(`Playwright Chromium install timed out after ${timeout}ms`));
        return;
      }
      if (code === 0) {
        resolve2();
        return;
      }
      reject(new Error(`Playwright Chromium install exited with code ${code ?? "null"} signal ${signal ?? "null"}`));
    });
  });
}
function getCacheDirs() {
  return [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, "ms-playwright"),
    process.env.HOME && join(process.env.HOME, ".cache", "ms-playwright"),
    process.env.HOME && join(process.env.HOME, "Library", "Caches", "ms-playwright")
  ].filter((p) => Boolean(p));
}
function getPlaywrightVersion() {
  try {
    const pkgPath = nodeRequire.resolve("playwright/package.json");
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
    return pkg.version ?? null;
  } catch {
    return null;
  }
}
function getExpectedRevisions() {
  const browsersJsonPaths = ["playwright-core/browsers.json", "playwright/browsers.json"];
  for (const subpath of browsersJsonPaths) {
    try {
      const jsonPath = nodeRequire.resolve(subpath);
      const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
      const revisions = {};
      for (const name of ACCEPTABLE_BROWSERS) {
        const entry = data.browsers?.find((b) => b.name === name.replace(/_/g, "-") || b.name === name);
        if (entry?.revision) {
          revisions[name] = entry.revision;
        }
      }
      if (Object.keys(revisions).length > 0) {
        return revisions;
      }
    } catch {
    }
  }
  const revision = PLAYWRIGHT_TO_CHROMIUM[getPlaywrightVersion() ?? ""];
  return { chromium: revision, chromium_headless_shell: revision };
}
function getInstalledBrowserPath(browserName, expectedRevision) {
  for (const cacheDir of getCacheDirs()) {
    try {
      if (!fs.existsSync(cacheDir)) {
        continue;
      }
      const entries = fs.readdirSync(cacheDir);
      const browserDir = `${browserName}-${expectedRevision}`;
      if (!entries.includes(browserDir)) {
        continue;
      }
      const browserPath = join(cacheDir, browserDir);
      if (!fs.statSync(browserPath).isDirectory()) {
        continue;
      }
      const marker = join(browserPath, "INSTALLATION_COMPLETE");
      if (!fs.existsSync(marker)) {
        continue;
      }
      const contents = fs.readdirSync(browserPath).filter((f) => !["INSTALLATION_COMPLETE", "DEPENDENCIES_VALIDATED", ".links"].includes(f));
      if (contents.length === 0) {
        continue;
      }
      return browserPath;
    } catch {
    }
  }
  return null;
}
function findBrowserExecutable(browserPath, browserName) {
  const executableNames = browserName === "chromium_headless_shell" ? /* @__PURE__ */ new Set(["chrome-headless-shell", "headless_shell", "chrome-headless-shell.exe", "headless_shell.exe"]) : /* @__PURE__ */ new Set(["Google Chrome for Testing", "Chromium", "chrome", "chrome.exe", "chromium", "chromium-browser"]);
  const visit = (currentPath, depth) => {
    if (executableNames.has(basename(currentPath))) {
      return currentPath;
    }
    if (depth > 8) {
      return null;
    }
    try {
      if (!fs.statSync(currentPath).isDirectory()) {
        return null;
      }
      for (const entry of fs.readdirSync(currentPath)) {
        const found = visit(join(currentPath, entry), depth + 1);
        if (found) {
          return found;
        }
      }
    } catch {
      return null;
    }
    return null;
  };
  return visit(browserPath, 0);
}
async function getExecutablePath(browserName, browserPath) {
  if (browserName === "chromium") {
    const { chromium } = await import("playwright");
    const executablePath = chromium.executablePath();
    if (!executablePath) {
      throw new Error("无法获取 Chromium 可执行路径，请检查 Playwright 安装");
    }
    if (fs.existsSync(executablePath)) {
      return executablePath;
    }
  }
  const discoveredPath = findBrowserExecutable(browserPath, browserName);
  if (discoveredPath) {
    return discoveredPath;
  }
  if (browserName === "chromium") {
    const { chromium } = await import("playwright");
    const executablePath = chromium.executablePath();
    if (executablePath) {
      return executablePath;
    }
  }
  throw new Error(`无法获取 ${browserName} 可执行路径，请检查 Playwright 安装`);
}
function getInstalledBrowser(revisions) {
  for (const name of ACCEPTABLE_BROWSERS) {
    const revision = revisions[name];
    if (!revision) {
      continue;
    }
    const installedPath = getInstalledBrowserPath(name, revision);
    if (installedPath) {
      return { name, path: installedPath };
    }
  }
  return null;
}
async function getDefaultExecutablePath() {
  const { chromium } = await import("playwright");
  const executablePath = chromium.executablePath();
  if (!executablePath) {
    throw new Error("无法获取 Chromium 可执行路径，请检查 Playwright 安装");
  }
  return executablePath;
}
async function ensureChromium() {
  const revisions = getExpectedRevisions();
  const hasExpectedRevision = ACCEPTABLE_BROWSERS.some((name) => revisions[name] !== void 0);
  if (hasExpectedRevision) {
    const installed2 = getInstalledBrowser(revisions);
    if (installed2) {
      return getExecutablePath(installed2.name, installed2.path);
    }
  }
  console.log("正在安装 Chromium 浏览器（首次运行需要，请稍候）...");
  const installEnv = getPlaywrightInstallEnv();
  const downloadHost = getConfiguredDownloadHost(installEnv);
  if (downloadHost) {
    console.log(`使用 Playwright 下载源：${downloadHost.name}=${downloadHost.value}`);
  } else {
    console.log(getChinaDownloadHostHint());
  }
  try {
    const cliPath = getLocalPlaywrightCliPath();
    const timeout = getInstallTimeoutMs(installEnv);
    console.log(`Chromium 安装超时保护：${Math.round(timeout / 1e3)}s`);
    await runPlaywrightInstall(cliPath, installEnv, timeout);
  } catch (error) {
    throw new Error(
      `Chromium 安装失败。请手动运行: ${INSTALL_COMMAND}
${getChinaDownloadHostHint()}
错误详情: ${error instanceof Error ? error.message : String(error)}`
    );
  }
  const installed = getInstalledBrowser(getExpectedRevisions());
  if (installed) {
    return getExecutablePath(installed.name, installed.path);
  }
  return getDefaultExecutablePath();
}
export {
  CDN_BASE_URL as C,
  resolveHtmlDirFromInput as a,
  routeLocalAssetRequests as b,
  createLocalizedHtmlCopy as c,
  buildRenderPageUrl as d,
  ensureChromium as e,
  containsApprovedFontReference as f,
  getAssetsRoot as g,
  hasLocalAssets as h,
  isExactApprovedFontFamily as i,
  ms as m,
  normalizeToApprovedFontFamily as n,
  rewriteHtmlCdnUrlsToLocalAssets as r,
  startRenderServer as s
};
