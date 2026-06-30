import { stat, mkdir, rm, writeFile, readdir, readFile, access } from "node:fs/promises";
import { dirname, resolve, join, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { C as CDN_BASE_URL$1, r as rewriteHtmlCdnUrlsToLocalAssets, a as resolveHtmlDirFromInput, s as startRenderServer, h as hasLocalAssets, g as getAssetsRoot, c as createLocalizedHtmlCopy, b as routeLocalAssetRequests, d as buildRenderPageUrl, m as ms, e as ensureChromium } from "./ensure-chromium-AFJLKYj1.js";
import { chromium } from "playwright";
const DEFAULT_FONT_CSS_URLS = [`${CDN_BASE_URL$1}/css/fonts.css`];
function collectMergedStylesheetHrefs(pageResults) {
  const hrefs = pageResults.flatMap((page) => page.externalLinks || []);
  return [.../* @__PURE__ */ new Set([...hrefs, ...DEFAULT_FONT_CSS_URLS])];
}
function resolveAssetUrl(urlValue, baseUrl) {
  if (!urlValue) {
    return urlValue;
  }
  const trimmed = String(urlValue).trim();
  if (!trimmed || trimmed.startsWith("data:") || trimmed.startsWith("blob:") || trimmed.startsWith("javascript:") || trimmed.startsWith("#")) {
    return urlValue;
  }
  try {
    return new URL(trimmed, baseUrl).toString();
  } catch {
    return urlValue;
  }
}
function absolutizeCssUrls(cssText, baseUrl) {
  return String(cssText).replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/gi, (match, quote, rawUrl) => {
    const resolved = resolveAssetUrl(rawUrl, baseUrl);
    if (resolved === rawUrl) {
      return match;
    }
    return `url(${quote}${resolved}${quote})`;
  });
}
function absolutizeSrcset(srcsetValue, baseUrl) {
  return String(srcsetValue).split(",").map((candidate) => {
    const trimmed = candidate.trim();
    if (!trimmed) {
      return trimmed;
    }
    const parts = trimmed.match(/^(\S+)(\s+.+)?$/);
    if (!parts) {
      return trimmed;
    }
    const resolvedUrl = resolveAssetUrl(parts[1], baseUrl);
    return `${resolvedUrl}${parts[2] || ""}`;
  }).join(", ");
}
function absolutizeHtmlAssetUrls(html, baseUrl) {
  let output = String(html);
  output = output.replace(/\b(src|poster)\s*=\s*(['"])(.*?)\2/gi, (match, attr, quote, value) => {
    const resolved = resolveAssetUrl(value, baseUrl);
    if (resolved === value) {
      return match;
    }
    return `${attr}=${quote}${resolved}${quote}`;
  });
  output = output.replace(/\bsrcset\s*=\s*(['"])(.*?)\1/gi, (match, quote, value) => {
    const resolved = absolutizeSrcset(value, baseUrl);
    if (resolved === value) {
      return match;
    }
    return `srcset=${quote}${resolved}${quote}`;
  });
  output = output.replace(/\bstyle\s*=\s*(['"])(.*?)\1/gi, (match, quote, value) => {
    const resolved = absolutizeCssUrls(value, baseUrl);
    if (resolved === value) {
      return match;
    }
    return `style=${quote}${resolved}${quote}`;
  });
  return output;
}
function absolutizeExtractedPageAssets(pageResult, baseUrl) {
  return {
    ...pageResult,
    scopedCss: absolutizeCssUrls(pageResult.scopedCss || "", baseUrl),
    slideHtmls: Array.isArray(pageResult.slideHtmls) ? pageResult.slideHtmls.map((html) => absolutizeHtmlAssetUrls(html, baseUrl)) : pageResult.slideHtmls
  };
}
const CDN_BASE_URL = "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets";
const FONTS_CSS_URL = "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/css/fonts.css";
const WOFF2_INDEX_URL = "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonteditor-core@2.6.3/woff2/index.js";
const FONTEDITOR_ESM_RELATIVE = "../../../assets/fonteditor-core@2.6.3/src/main.esm.js";
const FONTEDITOR_CJS_RELATIVE = "../../../assets/fonteditor-core@2.6.3/lib/main.js";
function localizeFontEditorUrl(relativePath, serverOrigin) {
  return new URL(
    `/slidagent/pptx-craft/assets/fonteditor-core@2.6.3/${relativePath}`.replace(/\/{2,}/g, "/"),
    `${serverOrigin.replace(/\/$/, "")}/`
  ).toString();
}
function localizeCdnBaseUrl(serverOrigin) {
  return new URL("/slidagent/pptx-craft/assets", `${serverOrigin.replace(/\/$/, "")}/`).toString().replace(/\/$/, "");
}
function patchBundleSourceForLocalAssets(bundleSource, serverOrigin) {
  const localCdnBaseUrl = localizeCdnBaseUrl(serverOrigin);
  const localFontsCssUrl = rewriteHtmlCdnUrlsToLocalAssets(FONTS_CSS_URL, serverOrigin);
  const localWoff2IndexUrl = rewriteHtmlCdnUrlsToLocalAssets(WOFF2_INDEX_URL, serverOrigin);
  const localFontEditorEsmUrl = localizeFontEditorUrl("src/main.esm.js", serverOrigin);
  const localFontEditorCjsUrl = localizeFontEditorUrl("lib/main.js", serverOrigin);
  return String(bundleSource).split(CDN_BASE_URL).join(localCdnBaseUrl).split(FONTS_CSS_URL).join(localFontsCssUrl).split(WOFF2_INDEX_URL).join(localWoff2IndexUrl).split(FONTEDITOR_ESM_RELATIVE).join(localFontEditorEsmUrl).split(FONTEDITOR_CJS_RELATIVE).join(localFontEditorCjsUrl);
}
async function waitForFontsReady(page, { selector = ".ppt-slide" } = {}) {
  const sel = JSON.stringify(selector);
  await page.evaluate(`
    (async function() {
      try {
        if (document.fonts && document.fonts.ready && typeof document.fonts.ready.then === 'function') {
          await document.fonts.ready;
        }
      } catch (e) {
      }

      var elements = Array.from(document.querySelectorAll(${sel}));
      for (var i = 0; i < elements.length; i++) {
        window.getComputedStyle(elements[i]).fontFamily;
      }

      if (typeof requestAnimationFrame === 'function') {
        await new Promise(function(resolve) {
          requestAnimationFrame(function() { requestAnimationFrame(resolve); });
        });
      }
    })()
  `);
}
const __filename$1 = fileURLToPath(import.meta.url);
const __dirname$1 = dirname(__filename$1);
const CONVERT_PAGE_CONCURRENCY = 4;
let sharedBrowser = null;
const EXPLICIT_EMBED_FONTS = [
  {
    name: "Noto Sans SC",
    url: "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonts/NotoSansSC/NotoSansSC-Regular.ttf"
  },
  {
    name: "WenYuan Sans SC",
    url: "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonts/WenYuanSansSC/WenYuanSansSC-Regular.ttf"
  },
  {
    name: "NanxiXinyuanti",
    url: "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonts/NanxiXinyuanti/NanxiXinyuanti-Regular.ttf"
  },
  {
    name: "WenJin Mincho Plane 0",
    url: "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonts/WenJinMincho/WenJinMinchoP0-Regular.ttf"
  },
  {
    name: "Frex Sans GB",
    url: "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonts/FrexSansGB/FrexSansGB-Regular.ttf"
  }
];
async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
async function removeTemporaryFile(filePath, rmImpl = rm, logger = console) {
  if (!filePath) {
    return;
  }
  try {
    await rmImpl(filePath, { force: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    logger.warn("临时文件清理失败:", message);
  }
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
function getCoreBundleCandidates(cliDir, cliFileName) {
  const preferDevBundle = /\.dev\.js$/i.test(cliFileName);
  const preferredNames = preferDevBundle ? ["core.dev.js", "core.js"] : ["core.js", "core.dev.js"];
  const candidates = /* @__PURE__ */ new Set();
  for (const startDir of [cliDir, process.cwd()]) {
    for (const ancestorDir of walkAncestorDirs(startDir)) {
      for (const bundleName of preferredNames) {
        candidates.add(join(ancestorDir, "packages", "core", "dist", bundleName));
        candidates.add(join(ancestorDir, "core", "dist", bundleName));
        candidates.add(join(ancestorDir, "scripts", bundleName));
      }
    }
  }
  return Array.from(candidates);
}
async function resolveCoreBundlePath() {
  const bundleCandidates = getCoreBundleCandidates(__dirname$1, basename(__filename$1));
  for (const candidatePath of bundleCandidates) {
    if (await fileExists(candidatePath)) {
      return candidatePath;
    }
  }
  throw new Error(`未找到 core bundle，可尝试候选路径: ${bundleCandidates.join(", ")}`);
}
function buildExportOptions({
  slideWidth,
  slideHeight,
  svgAsEditable,
  autoEmbedFonts,
  serverOrigin
}) {
  return {
    slideWidth,
    slideHeight,
    svgAsEditable,
    autoEmbedFonts,
    fonts: autoEmbedFonts ? EXPLICIT_EMBED_FONTS.map((font) => ({
      ...font,
      url: rewriteHtmlCdnUrlsToLocalAssets(font.url, serverOrigin)
    })) : [],
    skipDownload: true
  };
}
function buildEmbedFontsConfig(wasmUrl, mirrorUrl) {
  return {
    woff2: {
      wasmUrl,
      mirrorUrl,
      optional: true
    }
  };
}
async function convert({ input, output, options = {} }) {
  const resolvedOptions = {
    selector: options.selector ?? ".ppt-slide",
    slideWidth: options.slideWidth ?? 10,
    slideHeight: options.slideHeight ?? 5.625,
    svgAsEditable: options.svgAsEditable ?? true,
    autoEmbedFonts: options.autoEmbedFonts ?? true,
    timeout: options.timeout ?? 6e4,
    reuseBrowser: options.reuseBrowser ?? true,
    snapshot: options.snapshot ?? false,
    snapshotDir: options.snapshotDir || void 0,
    debug: options.debug ?? false
  };
  if (Array.isArray(input)) {
    return await convertPages(input, output ?? "", resolvedOptions);
  }
  const inputStat = await stat(input);
  if (inputStat.isDirectory()) {
    return await convertPages(input, output ?? "", resolvedOptions);
  } else {
    return await convertSingleFile(input, output ?? "", resolvedOptions);
  }
}
async function convertSingleFile(htmlPath, outputPath, options) {
  console.log(`📄 HTML 文件: ${htmlPath}`);
  return convertPages([htmlPath], outputPath, options);
}
async function getBrowser(reuseBrowser = true, debug = false) {
  let browser = sharedBrowser;
  let shouldCloseBrowser = false;
  if (browser) {
    console.log("♻️ 复用浏览器实例");
  } else {
    const tBrowser = Date.now();
    console.log("🚀 启动浏览器...");
    try {
      const executablePath = await ensureChromium();
      browser = await chromium.launch({
        executablePath,
        headless: true,
        args: ["--no-sandbox", "--disable-setuid-sandbox"]
      });
      if (debug) {
        console.log(`  ⏱️ 浏览器启动: ${ms(Date.now() - tBrowser)}`);
      }
      console.log("✅ 浏览器启动成功");
      if (reuseBrowser) {
        sharedBrowser = browser;
      } else {
        shouldCloseBrowser = true;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("❌ 浏览器启动失败:", message);
      throw error;
    }
  }
  return { browser, shouldCloseBrowser };
}
async function convertPages(input, outputPath, options) {
  const {
    selector = ".ppt-slide",
    slideWidth = 10,
    slideHeight = 5.625,
    svgAsEditable = true,
    autoEmbedFonts = true,
    timeout = 6e4,
    reuseBrowser = true,
    snapshot: enableSnapshot = false,
    snapshotDir: snapshotDirFromOpts,
    debug = false
  } = options;
  const tTotal = debug ? Date.now() : 0;
  let snapshot = enableSnapshot;
  let snapshotDir = snapshotDirFromOpts || null;
  if (snapshot && !snapshotDir) {
    let inputPath;
    if (Array.isArray(input)) {
      inputPath = input[0];
    } else {
      inputPath = input;
    }
    const parentDir = dirname(resolve(inputPath));
    const now = /* @__PURE__ */ new Date();
    const yyyyMMdd = now.toISOString().slice(0, 10).replace(/-/g, "");
    const hhmmss = now.toTimeString().slice(0, 8).replace(/:/g, "");
    snapshotDir = join(parentDir, "e2e", `${yyyyMMdd}_${hhmmss}`, "convert-snapshot");
    try {
      await mkdir(snapshotDir, { recursive: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.warn(`⚠️ 无法创建截图目录: ${message}`);
      snapshot = false;
    }
  }
  let files;
  if (Array.isArray(input)) {
    console.log(`📄 将合并 ${input.length} 个 HTML 文件`);
    for (const filePath of input) {
      try {
        await stat(filePath);
      } catch {
        throw new Error(`文件不存在: ${filePath}`);
      }
    }
    files = input;
  } else {
    files = await findPageFiles(input);
    if (files.length === 0) {
      throw new Error(`目录 ${input} 中未找到 page-N.pptx.html 文件`);
    }
    console.log(`📂 找到 ${files.length} 个页面文件`);
  }
  const htmlDir = resolveHtmlDirFromInput(input);
  const renderServer = await startRenderServer(htmlDir);
  const { browser } = await getBrowser(reuseBrowser, debug);
  const pageResults = [];
  const scopeSelectorFn = `function scopeSelector(selectorText, attr) {
    return selectorText.split(',').map(function(s) {
      var t = s.trim();
      if (!t) return t;
      if (t === 'body') return '[' + attr + '] > *';
      if (t === ':root' || t === 'html' || t === ':host') return '[' + attr + ']';
      if (t === '*' || t === '::before' || t === '::after' || t === '*, ::before, ::after') return '[' + attr + '] ' + t;
      return '[' + attr + '] ' + t;
    }).join(', ');
  }`;
  try {
    const processPage = async (i) => {
      const file = files[i];
      const pageIndex = i + 1;
      console.log(`📄 渲染页面 ${pageIndex}/${files.length}: ${basename(file)}`);
      const page = await browser.newPage();
      page.setDefaultTimeout(timeout);
      let localizedHtmlPath = null;
      try {
        if (hasLocalAssets()) {
          console.log(`  📦 检测到本地 assets 目录: ${getAssetsRoot()}`);
          localizedHtmlPath = await createLocalizedHtmlCopy(file, renderServer.origin);
          if (localizedHtmlPath) {
            console.log(`  📝 创建本地化 HTML 副本: ${basename(localizedHtmlPath)}`);
          } else {
            console.log(`  ℹ️ HTML 无 CDN URL，无需本地化副本`);
          }
        } else {
          await routeLocalAssetRequests(page);
        }
        console.log(`  📝 加载 HTML 页面...`);
        const renderPath = localizedHtmlPath ?? file;
        const pageUrl = buildRenderPageUrl(renderServer.origin, renderServer.htmlDir, renderPath);
        const t0 = Date.now();
        await page.goto(pageUrl, { waitUntil: "load" });
        if (debug) {
          console.log(`  ⏱️ goto load: ${ms(Date.now() - t0)}`);
        }
        const t1 = Date.now();
        try {
          if (debug) {
            console.log(`  ⏳ 等待网络空闲...`);
          }
          await page.waitForLoadState("networkidle", { timeout: 15e3 });
          if (debug) {
            console.log(`  ⏱️ networkidle: ${ms(Date.now() - t1)}`);
          }
          if (debug) {
            console.log(`  ✅ 网络空闲完成`);
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          if (debug) {
            console.log(`  ⏱️ networkidle 超时: ${ms(Date.now() - t1)}`);
          }
          if (debug) {
            console.log(`  ⏳ 页面 ${pageIndex} networkidle 超时，继续处理...`, message);
          }
        }
        if (debug) {
          console.log(`  ⏳ 等待图表渲染...`);
        }
        const t2 = Date.now();
        await page.waitForTimeout(1e3);
        if (debug) {
          console.log(`  ⏱️ 图表渲染等待: ${ms(Date.now() - t2)}`);
        }
        if (debug) {
          console.log(`  ✅ 图表渲染完成`);
        }
        if (debug) {
          console.log(`  🔤 等待页面字体加载完成...`);
        }
        const tFonts = Date.now();
        await waitForFontsReady(page, { selector });
        if (debug) {
          console.log(`  ⏱️ 页面字体加载等待: ${ms(Date.now() - tFonts)}`);
        }
        if (debug) {
          console.log(`  ✅ 页面字体加载完成`);
        }
        if (debug) {
          console.log(`  🔄 提取 CSS 和幻灯片内容...`);
        }
        const t3 = Date.now();
        const scopeAttr = `data-page-${pageIndex}`;
        const result = await page.evaluate(`
          (function() {
            ${scopeSelectorFn}
            try {
              var cssTexts = [];
              var externalLinks = [];
              var bodyBgColor = '';
              var scopeAttr = ${JSON.stringify(scopeAttr)};

              for (var si = 0; si < document.styleSheets.length; si++) {
                var sheet = document.styleSheets[si];
                try {
                  var rules = sheet.cssRules || sheet.rules;
                  if (!rules) continue;
                  for (var ri = 0; ri < rules.length; ri++) {
                    cssTexts.push(rules[ri].cssText);
                  }
                } catch (e) {
                  if (sheet.href) {
                    externalLinks.push(sheet.href);
                  }
                }
              }

              function extractBgFromRule(rule) {
                var match = rule.match(/background-color\\s*:\\s*([^;]+);/i)
                  || rule.match(/background\\s*:\\s*([^;]+);/i);
                if (match) return match[1].trim();
                return null;
              }

              var scopedRules = [];

              cssTexts.forEach(function(rule) {
                if (rule.startsWith('@keyframes') || rule.startsWith('@font-face')) {
                  scopedRules.push(rule);
                  return;
                }
                if (rule.startsWith('@media') || rule.startsWith('@supports') || rule.startsWith('@layer')) {
                  scopedRules.push(rule.replace(/([^{}]+)\\{/g, function(match, selectorPart, offset) {
                    if (offset === rule.indexOf('{')) return match;
                    return scopeSelector(selectorPart, scopeAttr) + '{';
                  }));
                  if (!bodyBgColor && /body|html|:root/.test(rule)) {
                    var bg = extractBgFromRule(rule);
                    if (bg) bodyBgColor = bg;
                  }
                  return;
                }
                var braceIdx = rule.indexOf('{');
                if (braceIdx === -1) { scopedRules.push(rule); return; }
                var selectorPart = rule.substring(0, braceIdx);
                var rest = rule.substring(braceIdx);

                var selectors = selectorPart.split(',').map(function(s) { return s.trim(); });
                var isBodyRule = selectors.some(function(s) { return s === 'body' || s === 'html' || s === ':root'; });
                if (isBodyRule && !bodyBgColor) {
                  var bg = extractBgFromRule(rule);
                  if (bg) bodyBgColor = bg;
                }
                scopedRules.push(scopeSelector(selectorPart, scopeAttr) + rest);
              });

              function convertCanvasToImage(container) {
                var canvases = container.querySelectorAll('canvas');
                canvases.forEach(function(canvas) {
                  try {
                    var dataUrl = canvas.toDataURL('image/png');
                    var img = document.createElement('img');
                    img.src = dataUrl;
                    var rect = canvas.getBoundingClientRect();
                    img.style.width = rect.width + 'px';
                    img.style.height = rect.height + 'px';
                    img.style.display = 'block';
                    canvas.parentNode.replaceChild(img, canvas);
                  } catch (e) {
                    console.warn('Canvas 转图片失败:', e.message);
                  }
                });
              }

              var slides = document.querySelectorAll(${JSON.stringify(selector)});
              var slideHtmls;
              if (slides.length > 0) {
                slideHtmls = Array.from(slides).map(function(slide) {
                  convertCanvasToImage(slide);
                  return slide.outerHTML;
                });
              } else {
                console.warn('⚠️ 未找到 ' + ${JSON.stringify(selector)} + ' 元素，尝试兜底策略');
                var invisibleTags = new Set(['script', 'style', 'link', 'meta', 'noscript']);
                var visibleChildren = Array.from(document.body.children).filter(function(el) {
                  return !invisibleTags.has(el.tagName.toLowerCase());
                });
                if (visibleChildren.length === 1) {
                  var el = visibleChildren[0];
                  if (!el.classList.contains('ppt-slide')) {
                    el.classList.add('ppt-slide');
                  }
                  convertCanvasToImage(el);
                  slideHtmls = [el.outerHTML];
                } else {
                  convertCanvasToImage(document.body);
                  slideHtmls = ['<div class="ppt-slide">' + document.body.innerHTML + '</div>'];
                }
              }

              if (!bodyBgColor) {
                var csBg = window.getComputedStyle(document.body).backgroundColor;
                if (csBg && csBg !== 'transparent' && csBg !== 'rgba(0, 0, 0, 0)') {
                  bodyBgColor = csBg;
                }
              }

              return {
                scopedCss: scopedRules.join('\\n'),
                slideHtmls: slideHtmls,
                externalLinks: externalLinks,
                bodyBgColor: bodyBgColor
              };
            } catch (err) {
              console.error('页面处理失败:', err.message);
              return {
                scopedCss: '',
                slideHtmls: [],
                externalLinks: [],
                bodyBgColor: ''
              };
            }
          })()
        `);
        if (result.slideHtmls.length === 0) {
          console.warn(`⚠️ 文件 ${basename(file)} 中未找到 ${selector} 元素`);
        } else {
          const baseUrl = buildRenderPageUrl(renderServer.origin, renderServer.htmlDir, file);
          const normalizedResult = absolutizeExtractedPageAssets(result, baseUrl);
          const localizedResult = {
            ...normalizedResult,
            scopedCss: rewriteHtmlCdnUrlsToLocalAssets(normalizedResult.scopedCss || "", renderServer.origin),
            slideHtmls: Array.isArray(normalizedResult.slideHtmls) ? normalizedResult.slideHtmls.map((html) => rewriteHtmlCdnUrlsToLocalAssets(html, renderServer.origin)) : normalizedResult.slideHtmls,
            externalLinks: Array.isArray(normalizedResult.externalLinks) ? normalizedResult.externalLinks.map((href) => rewriteHtmlCdnUrlsToLocalAssets(href, renderServer.origin)) : normalizedResult.externalLinks
          };
          console.log(
            `  ✓ 提取 ${localizedResult.slideHtmls.length} 个幻灯片，CSS ${(localizedResult.scopedCss.length / 1024).toFixed(1)}KB`
          );
          if (debug) {
            console.log(`  ⏱️ CSS 提取 + 内联: ${ms(Date.now() - t3)}`);
          }
          pageResults.push({
            pageIndex,
            scopedCss: localizedResult.scopedCss,
            slideHtmls: localizedResult.slideHtmls,
            externalLinks: localizedResult.externalLinks,
            bodyBgColor: localizedResult.bodyBgColor
          });
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`❌ 处理页面 ${pageIndex} 失败:`, message);
        pageResults.push({
          pageIndex,
          error: message,
          scopedCss: "",
          slideHtmls: [],
          externalLinks: [],
          bodyBgColor: ""
        });
      } finally {
        if (snapshot && snapshotDir) {
          await takeScreenshot(page, snapshotDir, pageIndex, `page-${pageIndex}`);
        }
        console.log(`  🔒 关闭页面...`);
        await page.close();
        console.log(`  ✅ 页面已关闭`);
        if (localizedHtmlPath) {
          await rm(localizedHtmlPath, { force: true }).catch(() => {
          });
        }
      }
    };
    const pageConcurrency = Math.max(1, Math.min(CONVERT_PAGE_CONCURRENCY, files.length));
    let nextPageIdx = 0;
    const runPageWorker = async () => {
      for (let i = nextPageIdx++; i < files.length; i = nextPageIdx++) {
        await processPage(i);
      }
    };
    await Promise.all(Array.from({ length: pageConcurrency }, () => runPageWorker()));
    pageResults.sort((a, b) => a.pageIndex - b.pageIndex);
    const totalSlides = pageResults.reduce((sum, p) => sum + p.slideHtmls.length, 0);
    const failedPages = pageResults.filter((p) => p.error !== void 0);
    if (failedPages.length > 0) {
      throw new Error(
        `${failedPages.length} 个页面处理失败: ${failedPages.map((p) => `page ${p.pageIndex}`).join(", ")}`
      );
    }
    console.log(`🎨 共收集 ${totalSlides} 个幻灯片，开始合并转换...`);
    const mergedHtml = await buildMergedHtml(pageResults, renderServer.origin);
    console.log("📄 创建合并页...");
    const mergePage = await browser.newPage();
    mergePage.setDefaultTimeout(timeout);
    mergePage.on("response", (response) => {
      if (!debug) {
        return;
      }
      const status = response.status();
      if (status >= 400) {
        console.warn(`[browser:response] ${status} ${response.url()}`);
      }
    });
    mergePage.on("console", (message) => {
      const messageType = message.type();
      if (messageType === "warning" || messageType === "error") {
        console.warn(`[browser:${messageType}] ${message.text()}`);
      }
    });
    mergePage.on("pageerror", (error) => {
      console.warn(`[browser:pageerror] ${error.message}`);
    });
    let mergedHtmlPath = null;
    try {
      const t0 = Date.now();
      if (debug) {
        console.log("📝 加载合并 HTML...");
      }
      mergedHtmlPath = await loadMergedHtmlPage(mergePage, mergedHtml, files, renderServer);
      if (debug) {
        console.log(`  ⏱️ 加载合并 HTML: ${ms(Date.now() - t0)}`);
      }
      const t1 = Date.now();
      if (debug) {
        console.log("📦 注入依赖...");
      }
      await injectDependencies(mergePage, renderServer.origin);
      if (debug) {
        console.log(`  ⏱️ 注入依赖: ${ms(Date.now() - t1)}`);
      }
      const t2 = Date.now();
      if (debug) {
        console.log("🔤 等待合并页字体加载完成...");
      }
      await waitForFontsReady(mergePage, { selector });
      if (debug) {
        console.log(`  ⏱️ 字体加载等待: ${Date.now() - t2}ms`);
      }
      if (debug) {
        console.log("✅ 合并页字体加载完成");
      }
      if (snapshot && snapshotDir) {
        console.log("📸 截取合并页截图...");
        await takeScreenshot(mergePage, snapshotDir, files.length + 1, "merged");
      }
      console.log(`🔧 开始生成 PPTX...`);
      const t4 = Date.now();
      const base64Data = await mergePage.evaluate(`
        (async function() {
          var exportToPptx = window.domToPptx.exportToPptx;
          var elements = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
          var opts = ${JSON.stringify(
        buildExportOptions({
          slideWidth,
          slideHeight,
          svgAsEditable,
          autoEmbedFonts,
          serverOrigin: renderServer.origin
        })
      )};
          var blob = await exportToPptx(elements, opts);
          return new Promise(function(resolve) {
            var reader = new FileReader();
            reader.onloadend = function() {
              var result = reader.result;
              resolve(result.split(',')[1]);
            };
            reader.readAsDataURL(blob);
          });
        })()
      `);
      console.log(`  ⏱️ PPTX 生成: ${Date.now() - t4}ms`);
      const pptxBuffer = Buffer.from(base64Data, "base64");
      console.log(`💾 保存 PPTX: ${outputPath}`);
      await writeFile(outputPath, pptxBuffer);
      if (await fileExists(outputPath)) {
        const stats = await stat(outputPath);
        console.log(`✅ 转换成功！文件大小: ${(stats.size / 1024).toFixed(2)} KB`);
        if (debug && tTotal) {
          console.log(`⏱️ 总耗时: ${ms(Date.now() - tTotal)}`);
        }
        return { success: true, outputPath, size: stats.size };
      }
      throw new Error("文件保存失败：文件未创建");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("❌ 目录转换失败:", message);
      throw error;
    } finally {
      if (mergedHtmlPath) {
        await removeTemporaryFile(mergedHtmlPath);
      }
      await mergePage.close();
      await closeBrowser();
    }
  } finally {
    await renderServer.close();
  }
}
async function findPageFiles(dirPath) {
  const entries = await readdir(dirPath, { withFileTypes: true });
  const files = entries.filter((e) => e.isFile() && /^page-(\d+)\.pptx\.html$/.test(e.name)).map((e) => ({
    path: join(dirPath, e.name),
    num: parseInt(e.name.match(/^page-(\d+)/)[1], 10)
  })).sort((a, b) => a.num - b.num).map((f) => f.path);
  return files;
}
function buildTempHtmlPath(targetDir, label, seed = `${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`) {
  return join(resolve(targetDir), `${label}_${seed}.html`);
}
async function loadMergedHtmlPage(page, mergedHtml, files, renderServer) {
  const mergedHtmlPath = buildTempHtmlPath(dirname(files[0]), "merged");
  await writeFile(mergedHtmlPath, mergedHtml, "utf-8");
  const mergedHtmlUrl = buildRenderPageUrl(renderServer.origin, renderServer.htmlDir, mergedHtmlPath);
  await page.goto(mergedHtmlUrl, { waitUntil: "load" });
  try {
    await page.waitForLoadState("networkidle", { timeout: 15e3 });
  } catch {
  }
  return mergedHtmlPath;
}
async function buildMergedHtml(pageResults, serverOrigin) {
  const allCss = pageResults.map((p) => `/* === Page ${p.pageIndex} === */
${p.scopedCss}`).join("\n\n");
  const allExternalLinks = collectMergedStylesheetHrefs(pageResults);
  const localizedExternalLinks = allExternalLinks.map(
    (href) => rewriteHtmlCdnUrlsToLocalAssets(href, serverOrigin)
  );
  const linkTags = localizedExternalLinks.filter((href) => href.startsWith("http://") || href.startsWith("https://")).map((href) => `  <link href="${href}" rel="stylesheet" />`).join("\n");
  const allSlides = pageResults.map((p) => {
    const attr = `data-page-${p.pageIndex}`;
    const bgStyle = p.bodyBgColor && p.bodyBgColor !== "transparent" ? ` style="background-color:${p.bodyBgColor}"` : "";
    return p.slideHtmls.map((html) => `<div ${attr}${bgStyle}>
${html}
</div>`).join("\n");
  }).join("\n");
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
${linkTags}
  <style>
    body { margin: 0; padding: 40px; }
${allCss}
  </style>
</head>
<body>
${allSlides}
</body>
</html>`;
}
async function injectDependencies(page, serverOrigin) {
  const wasmUrl = rewriteHtmlCdnUrlsToLocalAssets(
    "https://cdn.digitalhumanai.top/slidagent/pptx-craft/assets/fonteditor-core@2.6.3/woff2/woff2.wasm",
    serverOrigin
  );
  const mirrorUrl = rewriteHtmlCdnUrlsToLocalAssets(
    "https://npmmirror.com/mirrors/fonteditor-core@2.6.3/woff2/woff2.wasm",
    serverOrigin
  );
  await page.addInitScript(
    (config) => {
      window.EMBED_FONTS_CONFIG = config;
    },
    buildEmbedFontsConfig(wasmUrl, mirrorUrl)
  );
  console.log("✅ 字体嵌入配置设置成功（本地 assets WASM）");
  const bundlePath = await resolveCoreBundlePath();
  console.log(`📦 读取打包文件: ${bundlePath}`);
  const bundleSource = await readFile(bundlePath, "utf-8");
  const patchedBundleSource = patchBundleSourceForLocalAssets(bundleSource, serverOrigin);
  console.log("📄 注入脚本...");
  await page.addScriptTag({ content: patchedBundleSource, type: "module" });
  console.log("✅ 脚本注入成功");
  try {
    console.log("⏳ 等待模块加载完成...");
    await page.waitForFunction(`typeof window.domToPptx?.exportToPptx === 'function'`, { timeout: 1e4 });
    console.log("✅ 模块加载完成");
  } catch (e) {
    const domToPptxExists = await page.evaluate(`typeof window.domToPptx !== 'undefined'`);
    const exportToPptxExists = await page.evaluate(`typeof window.domToPptx?.exportToPptx !== 'undefined'`);
    console.log("Debug: window.domToPptx exists:", domToPptxExists);
    console.log("Debug: window.domToPptx.exportToPptx exists:", exportToPptxExists);
    throw e;
  }
}
async function closeBrowser() {
  if (sharedBrowser) {
    await sharedBrowser.close();
    sharedBrowser = null;
  }
}
async function takeScreenshot(page, snapshotDir, counter, label) {
  const filename = `${counter}.${label}.png`;
  const filePath = join(snapshotDir, filename);
  try {
    await page.screenshot({ path: filePath, fullPage: false });
    console.log(`  📸 ${filename}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn(`  ⚠️ 截图失败 (${filename}): ${message}`);
  }
}
export {
  closeBrowser,
  convert
};
