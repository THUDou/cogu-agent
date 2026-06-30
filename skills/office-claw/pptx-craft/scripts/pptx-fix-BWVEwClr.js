import { readdirSync, readFileSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { m as ms, f as containsApprovedFontReference, i as isExactApprovedFontFamily, n as normalizeToApprovedFontFamily, a as resolveHtmlDirFromInput, s as startRenderServer, r as rewriteHtmlCdnUrlsToLocalAssets, d as buildRenderPageUrl, e as ensureChromium } from "./ensure-chromium-AFJLKYj1.js";
import { l as log, w as warn, e as error } from "./logger-fUeZK7K8.js";
import { writeFile, rm } from "node:fs/promises";
const ECHART_INIT_NO_RENDERER_RE = /echarts\.init\(\s*document\.getElementById\s*\(\s*['"]([^'"]+)['"]\s*\)\s*(?:,\s*null\s*)?\)/g;
function fixChartInit(match, _domId) {
  if (/renderer\s*:/.test(match)) {
    return match;
  }
  return match.replace(/\)$/, `, null, { renderer: 'svg' })`);
}
function fixChartLayout(html, opts = {}) {
  const dryRun = opts.dryRun ?? false;
  ECHART_INIT_NO_RENDERER_RE.lastIndex = 0;
  const matches = html.match(ECHART_INIT_NO_RENDERER_RE);
  const issueCount = matches ? matches.length : 0;
  if (dryRun) {
    return { html, fixedCount: issueCount };
  }
  ECHART_INIT_NO_RENDERER_RE.lastIndex = 0;
  let fixedCount = 0;
  const newHtml = html.replace(ECHART_INIT_NO_RENDERER_RE, (match, domId) => {
    fixedCount++;
    return fixChartInit(match);
  });
  return { html: newHtml, fixedCount };
}
const CDN_BASE = "https://cdn.jsdelivr.net/npm/";
const DEPENDENCY_REGISTRY = [
  {
    name: "tailwind",
    patterns: [
      /\bclass\s*=\s*["'][^"']*tailwindcss[^"']*["']/i,
      /\bclass\s*=\s*["'][^"']*\b(?:bg|text|flex|grid|p[xy]?|m[xy]?)-\b[^"']*["']/i
    ],
    localPatterns: [/tailwind\.css/i, /tailwindcss/i],
    cdnReplacement: `${CDN_BASE}tailwindcss@3.4.1/lib/index.min.css`
  },
  {
    name: "fontawesome",
    patterns: [
      /\bfa-(?:solid|regular|brands|lg|xs|sm|lg|fw|ul|li|border|pull-left|pull-right|spin|pulse|rotate-90|rotate-180|rotate-270|flip-horizontal|flip-vertical)\b/i,
      /["']fa-["']/
    ],
    localPatterns: [/fontawesome/i, /@fortawesome/i],
    cdnReplacement: `${CDN_BASE}@fortawesome/fontawesome-free@6.5.1/css/all.min.css`
  },
  {
    name: "echarts",
    patterns: [/echarts\.(?:init|connect)/i, /["']echarts["']/],
    localPatterns: [/echarts/i],
    cdnReplacement: `${CDN_BASE}echarts@5.5.0/dist/echarts.min.js`
  },
  {
    name: "mathjax",
    patterns: [/mathjax/i, /["']mathjax["']/, /\$\$.*\$\$/],
    localPatterns: [/mathjax/i],
    cdnReplacement: `${CDN_BASE}mathjax@3.2.2/es5/tex-mml-chtml.js`
  }
];
function detectUsage(content) {
  const detected = /* @__PURE__ */ new Map();
  for (const dep of DEPENDENCY_REGISTRY) {
    const matched = dep.patterns.some((pattern) => pattern.test(content));
    if (matched) {
      detected.set(dep.name, dep);
    }
  }
  return detected;
}
function detectLocalPresent(headContent, dep) {
  return dep.localPatterns.some((pattern) => pattern.test(headContent));
}
function replaceCdnUrls(content, detected, headContent) {
  const injected = [];
  for (const [name, dep] of detected) {
    if (detectLocalPresent(headContent, dep)) {
      continue;
    }
    const replacement = dep.cdnReplacement;
    const ext = replacement.split(".").pop()?.toLowerCase() || "";
    let tag;
    if (["css"].includes(ext)) {
      tag = `<link rel="stylesheet" href="__LOCAL_ASSET__:${name}__" />`;
    } else {
      tag = `<script src="__LOCAL_ASSET__:${name}__"><\/script>`;
    }
    content = content.replace(/(<\/head>)/i, `${tag}
$1`);
    injected.push(name);
  }
  return { content, injected };
}
function fixHtmlDeps(html) {
  const headMatch = /<head[^>]*>([\s\S]*?)<\/head>/i.exec(html);
  const headContent = headMatch ? headMatch[1] : "";
  const detected = detectUsage(html);
  const detectedNames = Array.from(detected.keys());
  if (detectedNames.length === 0) {
    return { html, injected: [], detected: [] };
  }
  const result = replaceCdnUrls(html, detected, headContent);
  return {
    html: result.content,
    injected: result.injected,
    detected: detectedNames
  };
}
const ALL_OPERATIONS = ["tags", "fonts", "layout", "deps", "charts", "overflow", "whitespace"];
function noopDebug$4(_msg) {
  return void 0;
}
async function fixAll(executors, initialHtml, options = {}) {
  const { operations = ALL_OPERATIONS, dryRun = true, debug } = options;
  const dbg = debug ?? noopDebug$4;
  let html = initialHtml;
  const reportEntries = [];
  for (const op of operations) {
    const executor = executors[op];
    const tOp = Date.now();
    const result = await executor(html, { dryRun, debug: dbg });
    dbg(
      `  [fixAll] ${op}: ${ms(Date.now() - tOp)}, ${result.report.issueCount} 问题 / ${result.report.fixedCount} 修复`
    );
    html = result.html;
    reportEntries.push({ operation: op, ...result.report });
  }
  return {
    html,
    report: {
      operations: reportEntries,
      totalFixed: reportEntries.reduce((sum, e) => sum + e.fixedCount, 0),
      totalIssues: reportEntries.reduce((sum, e) => sum + e.issueCount, 0)
    }
  };
}
const TARGET_TW_FONT_FAMILY = `fontFamily: {
            sans: ['Noto Sans SC', 'sans-serif'],
          }`;
function getLineNumber$1(html, index) {
  return html.slice(0, index).split("\n").length;
}
function findMatchingBrace(html, start) {
  let depth = 0;
  let i = start;
  while (i < html.length && html[i] !== "{") {
    i++;
  }
  if (i >= html.length) {
    return -1;
  }
  for (; i < html.length; i++) {
    if (html[i] === "{") {
      depth++;
    } else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        return i;
      }
    }
  }
  return -1;
}
function analyzeFonts(html) {
  const fixes = [];
  const twMatch = html.match(/tailwind\.config\s*=\s*\{/);
  if (twMatch?.index !== void 0) {
    const configStart = twMatch.index + twMatch[0].length - 1;
    const configEnd = findMatchingBrace(html, configStart);
    if (configEnd !== -1) {
      const configBlock = html.slice(configStart, configEnd + 1);
      const ffMatch = configBlock.match(/fontFamily\s*:\s*\{/);
      if (ffMatch?.index === void 0) {
        const extendMatch = configBlock.match(/extend\s*:\s*\{/);
        if (extendMatch?.index !== void 0) {
          const insertPos = configStart + extendMatch.index + extendMatch[0].length;
          fixes.push({
            type: "tailwind-font",
            description: "tailwind.config 缺少 fontFamily 声明，需插入",
            line: getLineNumber$1(html, insertPos),
            start: insertPos,
            end: insertPos,
            replacement: `
            fontFamily: {
              sans: ['Noto Sans SC', 'sans-serif'],
            },`
          });
        }
      } else {
        const ffStart = configStart + ffMatch.index;
        const ffContentStart = ffStart + ffMatch[0].length - 1;
        const ffEnd = findMatchingBrace(html, ffContentStart);
        if (ffEnd !== -1) {
          const ffBlock = html.slice(ffStart, ffEnd + 1);
          if (!containsApprovedFontReference(ffBlock)) {
            fixes.push({
              type: "tailwind-font",
              description: `tailwind.config fontFamily 不合规：${ffBlock.replace(/\n/g, " ").trim()}`,
              line: getLineNumber$1(html, ffStart),
              start: ffStart,
              end: ffEnd + 1,
              replacement: TARGET_TW_FONT_FAMILY
            });
          }
        }
      }
    }
  }
  const styleRe = /style\s*=\s*"([^"]*)"/gi;
  for (let styleMatch = styleRe.exec(html); styleMatch !== null; styleMatch = styleRe.exec(html)) {
    const styleContent = styleMatch[1];
    const ffInlineMatch = styleContent.match(/font-family\s*:\s*([^;"]+)/i);
    if (!ffInlineMatch) {
      continue;
    }
    const fontValue = ffInlineMatch[1].trim();
    if (isExactApprovedFontFamily(fontValue)) {
      continue;
    }
    const replacementFont = normalizeToApprovedFontFamily(fontValue);
    const contentStart = styleMatch.index + styleMatch[0].indexOf('"') + 1;
    const matchIndex = ffInlineMatch.index ?? 0;
    const absValueStart = contentStart + matchIndex + "font-family".length;
    const colonPos = html.indexOf(":", absValueStart);
    const valueStartInHtml = colonPos + 1;
    let valueEndInHtml = valueStartInHtml;
    while (valueEndInHtml < html.length && html[valueEndInHtml] !== ";" && html[valueEndInHtml] !== '"') {
      valueEndInHtml++;
    }
    fixes.push({
      type: "inline-font",
      description: `inline style font-family 不合规：${fontValue}`,
      line: getLineNumber$1(html, valueStartInHtml),
      start: valueStartInHtml,
      end: valueEndInHtml,
      replacement: ` '${replacementFont}'`
    });
  }
  const styleTagRe = /<style(?![^>]*type\s*=\s*["']text\/tailwindcss["'])[^>]*>([\s\S]*?)<\/style>/gi;
  for (let styleTagMatch = styleTagRe.exec(html); styleTagMatch !== null; styleTagMatch = styleTagRe.exec(html)) {
    const cssContent = styleTagMatch[1];
    const cssContentStart = html.indexOf(">", styleTagMatch.index) + 1;
    const cssFFRe = /font-family\s*:\s*([^;}]+)/gi;
    for (let cssFFMatch = cssFFRe.exec(cssContent); cssFFMatch !== null; cssFFMatch = cssFFRe.exec(cssContent)) {
      const fontValue = cssFFMatch[1].trim();
      if (isExactApprovedFontFamily(fontValue)) {
        continue;
      }
      const replacementFont = normalizeToApprovedFontFamily(fontValue);
      const absValueStart = cssContentStart + cssFFMatch.index + "font-family".length;
      const colonPos = html.indexOf(":", absValueStart);
      const valueStartInHtml = colonPos + 1;
      let valueEndInHtml = valueStartInHtml;
      while (valueEndInHtml < html.length && html[valueEndInHtml] !== ";" && html[valueEndInHtml] !== "}") {
        valueEndInHtml++;
      }
      fixes.push({
        type: "css-font",
        description: `<style> 内 font-family 不合规：${fontValue}`,
        line: getLineNumber$1(html, valueStartInHtml),
        start: valueStartInHtml,
        end: valueEndInHtml,
        replacement: ` '${replacementFont}'`
      });
    }
  }
  return fixes;
}
function applyFontFixes(html, fixes) {
  return [...fixes].sort((a, b) => b.start - a.start).reduce((result, fix) => result.slice(0, fix.start) + fix.replacement + result.slice(fix.end), html);
}
function parseAttrs(attrStr) {
  const attrs = {};
  const re = /(\w[\w-]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|(\S+)))?/g;
  for (let m = re.exec(attrStr); m !== null; m = re.exec(attrStr)) {
    attrs[m[1]] = m[2] ?? m[3] ?? m[4] ?? "";
  }
  return attrs;
}
function rebuildTagTree(html) {
  const voidElements2 = /* @__PURE__ */ new Set([
    "br",
    "hr",
    "img",
    "input",
    "meta",
    "link",
    "area",
    "base",
    "col",
    "embed",
    "source",
    "track",
    "wbr"
  ]);
  const result = [];
  const stack = [];
  const OPEN_RE = /<(\w+)((?:\s[^>]*)?)>/g;
  const CLOSE_RE = /<\/(\w+)>/g;
  const events = [];
  OPEN_RE.lastIndex = 0;
  for (let m = OPEN_RE.exec(html); m !== null; m = OPEN_RE.exec(html)) {
    const tag = m[1].toLowerCase();
    if (tag === "script") {
      const endIdx = html.indexOf("<\/script>", m.index + m[0].length);
      if (endIdx !== -1) {
        OPEN_RE.lastIndex = endIdx + 9;
      }
      continue;
    }
    if (tag === "style") {
      const endIdx = html.indexOf("</style>", m.index + m[0].length);
      if (endIdx !== -1) {
        OPEN_RE.lastIndex = endIdx + 9;
      }
      continue;
    }
    events.push({ type: "open", tag, pos: m.index, attrStr: m[2] || "" });
  }
  CLOSE_RE.lastIndex = 0;
  for (let m = CLOSE_RE.exec(html); m !== null; m = CLOSE_RE.exec(html)) {
    events.push({ type: "close", tag: m[1].toLowerCase(), pos: m.index });
  }
  events.sort((a, b) => a.pos - b.pos);
  for (const evt of events) {
    if (evt.type === "open") {
      const attrs = parseAttrs(evt.attrStr || "");
      const idx = result.length;
      const parentIdx = stack.length > 0 ? stack[stack.length - 1].index : -1;
      result.push({
        tag: evt.tag,
        attrs,
        selfIndex: idx,
        parentIndex: parentIdx,
        classStr: attrs.class || "",
        pos: evt.pos
      });
      if (!voidElements2.has(evt.tag)) {
        stack.push({ tag: evt.tag, index: idx });
      }
    } else {
      for (let i = stack.length - 1; i >= 0; i--) {
        if (stack[i].tag === evt.tag) {
          stack.splice(i, 1);
          break;
        }
      }
    }
  }
  return result;
}
function getDirectChildren(tags, parentIdx) {
  return tags.filter((t) => t.parentIndex === parentIdx);
}
function hasClass(classStr, className) {
  return new RegExp(`(?:^|\\s)${className}(?:\\s|$)`).test(classStr);
}
function addClasses(classStr, ...classes) {
  let result = classStr;
  for (const cls of classes) {
    if (!hasClass(result, cls)) {
      result = result ? `${result} ${cls}` : cls;
    }
  }
  return result;
}
function getInlineFontFamily(styleStr = "") {
  const match = styleStr.match(/(?:^|;)\s*font-family\s*:\s*([^;]+)/i);
  return match ? match[1].trim() : "";
}
function isExactNotoSansSc(fontFamilyValue) {
  return isExactApprovedFontFamily(fontFamilyValue);
}
function ensureNotoSansSc(fontFamilyValue) {
  return normalizeToApprovedFontFamily(fontFamilyValue);
}
function checkGridChildren(tags, issues) {
  const gridParents = tags.filter((t) => /\bgrid-cols-\d+\b/.test(t.classStr));
  for (const parent of gridParents) {
    const children = getDirectChildren(tags, parent.selfIndex);
    for (const child of children) {
      if (hasClass(child.classStr, "h-full") && !hasClass(child.classStr, "min-h-0")) {
        issues.push({
          type: "grid-child-missing-min-h-0",
          node: child,
          severity: "error",
          fixable: true,
          fix: { addClasses: ["min-h-0"] },
          message: `Grid 子元素 <${child.tag}> 有 h-full 但缺少 min-h-0`
        });
      }
    }
  }
}
function checkMainChildren(tags, issues) {
  const mainNodes = tags.filter((t) => t.tag === "main");
  for (const main of mainNodes) {
    const children = getDirectChildren(tags, main.selfIndex);
    if (children.length < 2) {
      issues.push({
        type: "main-single-child",
        node: main,
        severity: "error",
        fixable: false,
        message: `main 仅有 ${children.length} 个子元素，需至少 2 个`
      });
    }
    for (const child of children) {
      if (hasClass(child.classStr, "h-full") && !hasClass(child.classStr, "flex-1")) {
        issues.push({
          type: "main-child-h-full",
          node: child,
          severity: "error",
          fixable: true,
          fix: { removeClass: "h-full", addClasses: ["flex-1", "min-h-0"] },
          message: `main 子元素 <${child.tag}> 使用 h-full，应改为 flex-1 min-h-0`
        });
      }
    }
  }
}
function checkHeaderFooter(tags, issues) {
  for (const node of tags) {
    if ((node.tag === "header" || node.tag === "footer") && !hasClass(node.classStr, "flex-shrink-0")) {
      issues.push({
        type: "header-footer-missing-shrink",
        node,
        severity: "warning",
        fixable: true,
        fix: { addClasses: ["flex-shrink-0"] },
        message: `<${node.tag}> 缺少 flex-shrink-0`
      });
    }
  }
}
function checkMainFlexClasses(tags, issues) {
  const requiredClasses = ["flex", "min-h-0", "overflow-hidden"];
  for (const main of tags) {
    if (main.tag !== "main") {
      continue;
    }
    const missing = requiredClasses.filter((cls) => !hasClass(main.classStr, cls));
    if (missing.length > 0) {
      issues.push({
        type: "main-missing-flex-classes",
        node: main,
        severity: "error",
        fixable: true,
        fix: { addClasses: missing },
        message: `main 缺少必要的 flex 类: ${missing.join(", ")}`
      });
    }
  }
}
function checkOverflowAuto(tags, issues) {
  const forbiddenClasses = ["overflow-auto", "overflow-y-auto", "overflow-x-auto"];
  for (const node of tags) {
    for (const forbidden of forbiddenClasses) {
      if (hasClass(node.classStr, forbidden)) {
        issues.push({
          type: "overflow-auto-forbidden",
          node,
          severity: "error",
          fixable: true,
          fix: { removeClass: forbidden, addClasses: [forbidden.replace("-auto", "-hidden")] },
          message: `<${node.tag}> 使用了禁止的 ${forbidden}，应改为 ${forbidden.replace("-auto", "-hidden")}`
        });
      }
    }
  }
}
function checkFontFamilyContainsNotoSansSc(tags, issues, html = "") {
  for (const node of tags) {
    const fontFamily = getInlineFontFamily(node.attrs.style);
    if (!fontFamily || isExactNotoSansSc(fontFamily)) {
      continue;
    }
    issues.push({
      type: "font-family-missing-noto-sans-sc",
      node,
      severity: "error",
      fixable: true,
      fix: { kind: "inline-font-family", from: fontFamily, to: ensureNotoSansSc(fontFamily) },
      message: `<${node.tag}> 的 font-family 未使用允许的字体`
    });
  }
  const styleBlockRe = /<style\b[^>]*>([\s\S]*?)<\/style>/gi;
  for (let styleBlockMatch = styleBlockRe.exec(html); styleBlockMatch !== null; styleBlockMatch = styleBlockRe.exec(html)) {
    const declarationRe = /font-family\s*:\s*([^;}{]+)\s*[;}]?/gi;
    for (let declarationMatch = declarationRe.exec(styleBlockMatch[1]); declarationMatch !== null; declarationMatch = declarationRe.exec(styleBlockMatch[1])) {
      const fontFamily = declarationMatch[1].trim();
      if (!isExactNotoSansSc(fontFamily)) {
        issues.push({
          type: "font-family-missing-noto-sans-sc",
          severity: "error",
          fixable: true,
          fix: { kind: "stylesheet-font-family", from: fontFamily, to: ensureNotoSansSc(fontFamily) },
          message: "检测到 font-family 未使用允许的字体"
        });
      }
    }
  }
}
function checkPptSlide(tags, issues) {
  for (const node of tags) {
    if (!hasClass(node.classStr, "ppt-slide")) {
      continue;
    }
    const has720px = /\bh-\[720px\]\b/.test(node.classStr);
    const hasOverflow = hasClass(node.classStr, "overflow-hidden");
    if (!has720px || !hasOverflow) {
      const missing = [];
      if (!has720px) {
        missing.push("h-[720px]");
      }
      if (!hasOverflow) {
        missing.push("overflow-hidden");
      }
      issues.push({
        type: "ppt-slide-missing-height",
        node,
        severity: "error",
        fixable: false,
        message: `.ppt-slide 缺少固定高度约束: ${missing.join(", ")}`
      });
    }
  }
}
function runAllChecks(tags, html = "") {
  const issues = [];
  checkGridChildren(tags, issues);
  checkMainChildren(tags, issues);
  checkHeaderFooter(tags, issues);
  checkMainFlexClasses(tags, issues);
  checkOverflowAuto(tags, issues);
  checkFontFamilyContainsNotoSansSc(tags, issues, html);
  checkPptSlide(tags, issues);
  return issues;
}
function escapeRegExp$1(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function patchClassAttr(html, node, fix) {
  let newClassStr = node.classStr;
  if (fix.removeClass) {
    newClassStr = newClassStr.replace(new RegExp(`(?:^|\\s)${escapeRegExp$1(fix.removeClass)}(?:\\s|$)`), " ").trim();
  }
  if (fix.addClasses?.length) {
    newClassStr = addClasses(newClassStr, ...fix.addClasses);
  }
  if (node.attrs.id) {
    const patterns = [
      new RegExp(
        `(<${node.tag}\\s[^>]*id\\s*=\\s*["']${escapeRegExp$1(node.attrs.id)}["'][^>]*class\\s*=\\s*["'])(${escapeRegExp$1(node.classStr)})(["'][^>]*>)`,
        "s"
      ),
      new RegExp(
        `(<${node.tag}\\s[^>]*class\\s*=\\s*["'])(${escapeRegExp$1(node.classStr)})(["'][^>]*id\\s*=\\s*["']${escapeRegExp$1(node.attrs.id)}["'][^>]*>)`,
        "s"
      )
    ];
    for (const re2 of patterns) {
      if (re2.test(html)) {
        return html.replace(re2, `$1${newClassStr}$3`);
      }
    }
  }
  const re = new RegExp(`(<${node.tag}\\s[^>]*class\\s*=\\s*["'])(${escapeRegExp$1(node.classStr)})(["'][^>]*>)`, "s");
  if (re.test(html)) {
    return html.replace(re, `$1${newClassStr}$3`);
  }
  return html;
}
function patchFontFamily(html, issue) {
  const fix = issue.fix;
  if (!fix?.kind || !fix.from || !fix.to || !issue.node?.attrs?.style) {
    return html;
  }
  const updatedStyle = issue.node.attrs.style.replace(/((?:^|;)\s*font-family\s*:\s*)([^;]+)/i, `$1${fix.to}`);
  if (updatedStyle === issue.node.attrs.style) {
    return html;
  }
  const patterns = [
    new RegExp(
      `(<${issue.node.tag}\\s[^>]*style\\s*=\\s*["'])(${escapeRegExp$1(issue.node.attrs.style)})(["'][^>]*>)`,
      "s"
    )
  ];
  if (issue.node.attrs.id) {
    patterns.unshift(
      new RegExp(
        `(<${issue.node.tag}\\s[^>]*id\\s*=\\s*["']${escapeRegExp$1(issue.node.attrs.id)}["'][^>]*style\\s*=\\s*["'])(${escapeRegExp$1(issue.node.attrs.style)})(["'][^>]*>)`,
        "s"
      )
    );
  }
  for (const re of patterns) {
    if (re.test(html)) {
      return html.replace(re, `$1${updatedStyle}$3`);
    }
  }
  return html;
}
function applyFixes$1(html, issues) {
  let newHtml = html;
  const fixableIssues = issues.filter((i) => i.fixable && i.fix);
  const fixedCount = { success: 0, failed: 0 };
  for (const issue of fixableIssues) {
    if (!issue.node || !issue.fix) {
      continue;
    }
    const newHtmlTry = issue.fix.kind ? patchFontFamily(newHtml, issue) : patchClassAttr(newHtml, issue.node, issue.fix);
    if (newHtmlTry === newHtml) {
      fixedCount.failed++;
    } else {
      newHtml = newHtmlTry;
      fixedCount.success++;
    }
  }
  return { html: newHtml, fixedCount };
}
const OVERFLOW_TAG = "y_axis_overflow_detected";
const DEFAULT_OVERFLOW_PX_THRESHOLD = 2;
function noopDebug$3(_msg) {
  return void 0;
}
async function detectOverflow(renderer, html, opts = {}) {
  const pct = opts.percentThreshold ?? 0;
  const px = opts.pxThreshold ?? DEFAULT_OVERFLOW_PX_THRESHOLD;
  const skipLoad = opts.skipLoad ?? false;
  const dbg = opts.debug ?? noopDebug$3;
  if (!skipLoad) {
    const t0 = Date.now();
    await renderer.load(html);
    dbg(`  [overflow] renderer.load: ${ms(Date.now() - t0)}`);
  }
  const t1 = Date.now();
  renderer.evaluate(
    `(doc, _win, args) => {
    const t = args ?? "y_axis_overflow_detected";
    doc.querySelectorAll("." + t).forEach((el) => {
      el.classList.remove(t);
    });
  }`,
    OVERFLOW_TAG
  );
  dbg(`  [overflow] 清除标记: ${ms(Date.now() - t1)}`);
  const t2 = Date.now();
  const results = await renderer.evaluate(
    `(doc, _win, args) => {
      const pct = args.pct;
      const px = args.px;
      const tag = args.tag;
      const overflowResults = [];
      const slides = doc.querySelectorAll(".ppt-slide");
      if (slides.length === 0) {
        return overflowResults;
      }

      for (const slide of slides) {
        const elements = slide.querySelectorAll("*");
        for (const el of elements) {
          const sH = el.scrollHeight;
          const cH = el.clientHeight;
          const overflow = sH - cH;
          if (overflow <= 0) {
            continue;
          }
          if (el.children.length === 0) {
            continue;
          }
          const ratio = overflow / cH;
          const tagName = el.tagName.toLowerCase();
          const className =
            typeof el.className === "string"
              ? el.className
              : (el.className && el.className.baseVal) || "";
          const style = (doc.defaultView ?? window).getComputedStyle(el);
          const lineHeight = parseFloat(style.lineHeight);
          const isSvgTextNoise =
            el.namespaceURI === "http://www.w3.org/2000/svg" &&
            (tagName === "text" || tagName === "tspan");
          const isFontAwesomeIconNoise =
            tagName === "i" &&
            /\\bfa[srb]?\\b|\\bfa-[\\w-]+\\b/.test(className) &&
            el.children.length === 0 &&
            el.getClientRects().length <= 1 &&
            overflow <= Math.max(px + 1, lineHeight * 0.14);
          const isSingleLineMetricNoise =
            /(^|\\s)leading-none(\\s|$)/.test(className) &&
            el.getClientRects().length <= 1 &&
            el.scrollWidth <= el.clientWidth + 1 &&
            Number.isFinite(lineHeight) &&
            overflow <= Math.max(px + 2, lineHeight * 0.16);
          const childElements = Array.from(el.children);
          const hasOnlyInlineChildren =
            childElements.length > 0 &&
            childElements.every((child) => {
              const childTag = child.tagName.toLowerCase();
              return childTag === "span" || childTag === "strong" || childTag === "em" || childTag === "b" || childTag === "i";
            });
          const isSingleLinePlainTextNoise =
            (tagName === "span" || tagName === "div" || tagName === "p") &&
            el.getClientRects().length <= 1 &&
            el.scrollWidth <= el.clientWidth + 1 &&
            Number.isFinite(lineHeight) &&
            (childElements.length === 0 || hasOnlyInlineChildren) &&
            overflow <= Math.max(px + 3, lineHeight * 0.25);
          const isSingleLineFlexNoise =
            /(^|\\s)flex(\\s|$)/.test(className) &&
            el.getClientRects().length <= 1 &&
            el.scrollWidth <= el.clientWidth + 1 &&
            Number.isFinite(lineHeight) &&
            overflow <= Math.max(px + 2, lineHeight * 0.16);
          const isBaselineMetricRowNoise =
            /(^|\\s)items-baseline(\\s|$)/.test(className) &&
            el.getClientRects().length <= 1 &&
            el.scrollWidth <= el.clientWidth + 1 &&
            Number.isFinite(lineHeight) &&
            overflow <= Math.max(px + 3, lineHeight * 0.22);
          const hasOnlyTextOrBreakChildren =
            el.children.length === 0 ||
            (el.children.length === 1 && el.children[0].tagName.toLowerCase() === "br");
          const shouldIgnoreHeadingNoise =
            /^h[1-6]$/.test(tagName) &&
            hasOnlyTextOrBreakChildren &&
            el.getClientRects().length <= 1 &&
            el.scrollWidth <= el.clientWidth + 1 &&
            Number.isFinite(lineHeight) &&
            overflow <= Math.max(px + 3, lineHeight * 0.2);
          if (
            ratio * 100 > pct &&
            overflow > px &&
            !shouldIgnoreHeadingNoise &&
            !isSvgTextNoise &&
            !isFontAwesomeIconNoise &&
            !isSingleLineMetricNoise &&
            !isSingleLinePlainTextNoise &&
            !isSingleLineFlexNoise &&
            !isBaselineMetricRowNoise
          ) {
            el.classList.add(tag);
            const id = el.id || "";
            const classParts = className.split(/\\s+/).filter(Boolean);
            const sigClass = classParts.slice(0, 3).join(" ");
            const pathParts = [];
            let current = el;
            while (current && current !== slide) {
              const t = current.tagName.toLowerCase();
              const cls =
                typeof current.className === "string" ? current.className.split(/\\s+/).filter(Boolean).join(".") : "";
              pathParts.unshift(cls ? t + "." + cls : t);
              current = current.parentElement;
            }
            overflowResults.push({
              domPath: pathParts.join(" → "),
              scrollHeight: sH,
              clientHeight: cH,
              overflow: Math.round(overflow * 10) / 10,
              ratio: Math.round(ratio * 1000) / 10,
              tagName: tagName,
              id: id,
              sigClass: sigClass,
            });
          }
        }
      }
      return overflowResults;
    }`,
    { pct, px, tag: OVERFLOW_TAG }
  );
  dbg(`  [overflow] 检测溢出元素: ${ms(Date.now() - t2)}, ${results.length} 个元素`);
  return results;
}
const SPACING_TYPES = {
  margin: {
    name: "margin",
    patterns: [
      "\\bm-(\\d+)\\b",
      "\\bmx-(\\d+)\\b",
      "\\bmy-(\\d+)\\b",
      "\\bmt-(\\d+)\\b",
      "\\bmb-(\\d+)\\b",
      "\\bml-(\\d+)\\b",
      "\\bmr-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bm-\\[([^\\]]+)\\]",
      "\\bmx-\\[([^\\]]+)\\]",
      "\\bmy-\\[([^\\]]+)\\]",
      "\\bmt-\\[([^\\]]+)\\]",
      "\\bmb-\\[([^\\]]+)\\]",
      "\\bml-\\[([^\\]]+)\\]",
      "\\bmr-\\[([^\\]]+)\\]"
    ]
  },
  padding: {
    name: "padding",
    patterns: [
      "\\bp-(\\d+)\\b",
      "\\bpx-(\\d+)\\b",
      "\\bpy-(\\d+)\\b",
      "\\bpt-(\\d+)\\b",
      "\\bpb-(\\d+)\\b",
      "\\bpl-(\\d+)\\b",
      "\\bpr-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bp-\\[([^\\]]+)\\]",
      "\\bpx-\\[([^\\]]+)\\]",
      "\\bpy-\\[([^\\]]+)\\]",
      "\\bpt-\\[([^\\]]+)\\]",
      "\\bpb-\\[([^\\]]+)\\]",
      "\\bpl-\\[([^\\]]+)\\]",
      "\\bpr-\\[([^\\]]+)\\]"
    ]
  },
  gap: {
    name: "gap/space",
    patterns: [
      "\\bgap-(\\d+)\\b",
      "\\bgap-x-(\\d+)\\b",
      "\\bgap-y-(\\d+)\\b",
      "\\bspace-y-(\\d+)\\b",
      "\\bspace-x-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bgap-\\[([^\\]]+)\\]",
      "\\bgap-x-\\[([^\\]]+)\\]",
      "\\bgap-y-\\[([^\\]]+)\\]",
      "\\bspace-y-\\[([^\\]]+)\\]",
      "\\bspace-x-\\[([^\\]]+)\\]"
    ]
  }
};
const TYPO_TYPES = {
  "font-size": {
    name: "font-size",
    label: "font-size",
    tierList: [
      "text-9xl",
      "text-8xl",
      "text-7xl",
      "text-6xl",
      "text-5xl",
      "text-4xl",
      "text-3xl",
      "text-2xl",
      "text-xl",
      "text-lg",
      "text-base",
      "text-sm"
    ],
    tierMap: {
      "text-9xl": 128,
      "text-8xl": 96,
      "text-7xl": 72,
      "text-6xl": 60,
      "text-5xl": 48,
      "text-4xl": 36,
      "text-3xl": 30,
      "text-2xl": 24,
      "text-xl": 20,
      "text-lg": 18,
      "text-base": 16,
      "text-sm": 14
    },
    arbitraryPatterns: ["\\btext-\\[([^\\]/]+)\\]"],
    slashPattern: "\\btext-\\[([^\\]]+)/([^\\]]+)\\]",
    minPx: 14,
    scaleFactor: 0.8,
    remToPx: 16,
    ptToPx: 96 / 72
  },
  "line-height": {
    name: "line-height",
    label: "line-height",
    tierList: ["leading-loose", "leading-relaxed", "leading-normal", "leading-snug", "leading-tight", "leading-none"],
    tierMap: {
      "leading-loose": 2,
      "leading-relaxed": 1.625,
      "leading-normal": 1.5,
      "leading-snug": 1.375,
      "leading-tight": 1.25,
      "leading-none": 1
    },
    fixedTierList: [
      "leading-10",
      "leading-9",
      "leading-8",
      "leading-7",
      "leading-6",
      "leading-5",
      "leading-4",
      "leading-3"
    ],
    fixedTierMap: {
      "leading-10": 40,
      "leading-9": 36,
      "leading-8": 32,
      "leading-7": 28,
      "leading-6": 24,
      "leading-5": 20,
      "leading-4": 16,
      "leading-3": 12
    },
    arbitraryPatterns: ["\\bleading-\\[([^\\]]+)\\]"],
    minMultiplier: 1,
    minPx: 10,
    scaleFactor: 0.8,
    remToPx: 16,
    ptToPx: 96 / 72
  }
};
function generateStrategySteps(maxDepth = 10) {
  const types = [
    { key: "margin", label: "margin" },
    { key: "padding", label: "padding" },
    { key: "gap", label: "gap/space" }
  ];
  const steps = [];
  for (let depth = 0; depth <= maxDepth; depth++) {
    for (const type of types) {
      steps.push({ depth, typeName: type.key, typeLabel: type.label });
    }
  }
  for (let depth = -1; depth >= -maxDepth; depth--) {
    for (const type of types) {
      steps.push({ depth, typeName: type.key, typeLabel: type.label });
    }
  }
  const TYPO_STEPS = [
    { key: "font-size", label: "font-size" },
    { key: "line-height", label: "line-height" }
  ];
  const maxTierSteps = Math.max(
    TYPO_TYPES["font-size"].tierList.length - 1,
    TYPO_TYPES["line-height"].tierList.length - 1,
    (TYPO_TYPES["line-height"].fixedTierList?.length ?? 0) - 1
  );
  for (let i = 0; i < maxTierSteps; i++) {
    for (const t of TYPO_STEPS) {
      steps.push({ depth: "typo", typeName: t.key, typeLabel: t.label });
    }
  }
  return steps;
}
function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function applyChangesToHtml$1(html, changes) {
  let result = html;
  for (const { from, to, targetTag, targetId, targetSigClass } of changes) {
    let replaced = false;
    if (targetTag && (targetId || targetSigClass)) {
      const tagPattern = escapeRegExp(targetTag);
      const scopedMatchers = [];
      if (targetId) {
        scopedMatchers.push(
          new RegExp(
            `(<${tagPattern}[^>]*\\bid\\s*=\\s*["']${escapeRegExp(targetId)}["'][^>]*?\\bclass\\s*=\\s*["'])([^"']*)(["'][^>]*>)`,
            "s"
          )
        );
      }
      if (targetSigClass) {
        const sigParts = targetSigClass.split(/\s+/).filter(Boolean);
        if (sigParts.length > 0) {
          const lookaheads = sigParts.map((part) => `(?=[^"']*${escapeRegExp(part)})`).join("");
          scopedMatchers.push(
            new RegExp(`(<${tagPattern}[^>]*?\\bclass\\s*=\\s*["'])(${lookaheads}[^"']*)(["'][^>]*>)`, "s")
          );
        }
      }
      for (const re2 of scopedMatchers) {
        result = result.replace(re2, (match, prefix, classValue, suffix) => {
          if (replaced || !classValue.split(/\s+/).includes(from)) {
            return match;
          }
          const parts = classValue.split(/(\s+)/);
          const newParts = parts.map((p) => p === from ? to : p);
          replaced = true;
          return `${prefix}${newParts.join("")}${suffix}`;
        });
        if (replaced) {
          break;
        }
      }
    }
    if (replaced) {
      continue;
    }
    const re = /(class\s*=\s*["'])([^"']*)(["'])/g;
    result = result.replace(re, (match, prefix, classValue, suffix) => {
      if (!classValue.split(/\s+/).includes(from)) {
        return match;
      }
      const parts = classValue.split(/(\s+)/);
      const newParts = parts.map((p) => p === from ? to : p);
      return `${prefix}${newParts.join("")}${suffix}`;
    });
  }
  return result;
}
function noopDebug$2(_msg) {
  return void 0;
}
async function fixOverflow(renderer, html, opts = {}) {
  const pct = opts.percentThreshold ?? 0;
  const px = opts.pxThreshold ?? DEFAULT_OVERFLOW_PX_THRESHOLD;
  const timeoutMs = (opts.timeoutSec ?? 300) * 1e3;
  const dbg = opts.debug ?? noopDebug$2;
  const startTime = Date.now();
  const t0 = Date.now();
  let overflows = await detectOverflow(renderer, html, { percentThreshold: pct, pxThreshold: px, debug: dbg });
  dbg(`  [overflow] 初始检测: ${ms(Date.now() - t0)}, ${overflows.length} 个溢出元素`);
  const issueCount = overflows.length;
  if (overflows.length === 0) {
    return { html, fixedCount: 0, issueCount: 0, remaining: 0 };
  }
  const strategySteps = generateStrategySteps();
  const allChanges = [];
  let totalSteps = 0;
  for (const step of strategySteps) {
    if (Date.now() - startTime > timeoutMs) {
      dbg(`  [overflow] 策略循环超时，已执行 ${totalSteps} 步`);
      break;
    }
    dbg(`  [overflow] 策略: ${step.typeLabel}`);
    const tStep = Date.now();
    let changes;
    if (step.depth === "typo") {
      changes = await executeTypographyStep(renderer, step.typeName);
    } else {
      changes = await executeSpacingStep(renderer, step);
    }
    dbg(`  [overflow] 策略执行: ${ms(Date.now() - tStep)}, ${changes.length} 个变更`);
    if (changes.length === 0) {
      continue;
    }
    totalSteps++;
    allChanges.push(...changes);
    await renderer.evaluate(
      `(doc, _win, args) => {
      doc.querySelectorAll("." + args).forEach((el) => {
        el.classList.remove(args);
      });
    }`,
      OVERFLOW_TAG
    );
    const updatedHtml = await renderer.getContent();
    const tRecheck = Date.now();
    overflows = await detectOverflow(renderer, updatedHtml, {
      percentThreshold: pct,
      pxThreshold: px,
      skipLoad: true,
      debug: dbg
    });
    dbg(`  [overflow] 重新检测: ${ms(Date.now() - tRecheck)}, 剩余 ${overflows.length} 个`);
    if (overflows.length === 0) {
      const fixedHtml2 = applyChangesToHtml$1(html, allChanges);
      return { html: fixedHtml2, fixedCount: issueCount, issueCount, remaining: 0 };
    }
  }
  const improvedCount = issueCount - overflows.length;
  const fixedHtml = allChanges.length > 0 && improvedCount > 0 ? applyChangesToHtml$1(html, allChanges) : html;
  return {
    html: fixedHtml,
    fixedCount: totalSteps > 0 ? improvedCount : 0,
    issueCount,
    remaining: overflows.length
  };
}
async function executeTypographyStep(renderer, typeName) {
  const config = TYPO_TYPES[typeName];
  if (!config) {
    return [];
  }
  return await renderer.evaluate(
    `(doc, _win, args) => {
      const tag = args.tag;
      const config = args.config;
      const changes = [];
      const overflowEls = doc.querySelectorAll("." + tag);

      function parseCssValue(valStr) {
        const numMatch = valStr.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(px|rem|em|pt)?$/);
        if (!numMatch) {
          return null;
        }
        return { value: parseFloat(numMatch[1]), unit: numMatch[2] || "" };
      }

      function toPx(parsed) {
        if (parsed.unit === "rem" || parsed.unit === "em") {
          return parsed.value * config.remToPx;
        }
        if (parsed.unit === "pt") {
          return parsed.value * config.ptToPx;
        }
        return parsed.value;
      }

      for (const overflowEl of overflowEls) {
        const targets = [overflowEl].concat(Array.from(overflowEl.querySelectorAll("*")));
        const processed = new Set();
        for (const el of targets) {
          if (processed.has(el)) {
            continue;
          }
          processed.add(el);
          const classList = Array.from(el.classList);
          const targetTag = el.tagName.toLowerCase();
          const targetId = el.id || "";
          const rawClassName =
            typeof el.className === "string"
              ? el.className
              : (el.className && el.className.baseVal) || "";
          const targetSigClass = rawClassName.split(/\\s+/).filter(Boolean).slice(0, 3).join(" ");
          const isProtectedHeading = /^h[1-3]$/.test(targetTag);
          const headingFontShrinkAttr = "data-pptx-craft-heading-font-shrink";

          if (config.name === "font-size") {
            if (isProtectedHeading && el.getAttribute(headingFontShrinkAttr) === "1") {
              continue;
            }

            let changedFontSize = false;
            for (const cls of classList) {
              const idx = config.tierList.indexOf(cls);
              if (idx >= 0 && idx < config.tierList.length - 1) {
                el.classList.remove(cls);
                el.classList.add(config.tierList[idx + 1]);
                changes.push({ from: cls, to: config.tierList[idx + 1], targetTag, targetId, targetSigClass });
                changedFontSize = true;
              }
            }

            const textArbitraryRe = new RegExp(config.arbitraryPatterns[0]);
            for (const cls of Array.from(el.classList)) {
              const m = cls.match(textArbitraryRe);
              if (!m || m[1].includes("/")) {
                continue;
              }
              const parsed = parseCssValue(m[1]);
              if (!parsed) {
                continue;
              }
              const pxVal = toPx(parsed);
              if (pxVal <= (config.minPx || 0)) {
                continue;
              }
              const newPx = Math.max(pxVal * config.scaleFactor, config.minPx || 0);
              if (newPx >= pxVal) {
                continue;
              }
              const newClass = "text-[" + Math.round(newPx * 10) / 10 + "px]";
              el.classList.remove(cls);
              el.classList.add(newClass);
              changes.push({ from: cls, to: newClass, targetTag, targetId, targetSigClass });
              changedFontSize = true;
            }

            if (isProtectedHeading && changedFontSize) {
              el.setAttribute(headingFontShrinkAttr, "1");
            }
          }

          if (config.name === "line-height") {
            for (const cls of classList) {
              const idx = config.tierList.indexOf(cls);
              if (idx >= 0 && idx < config.tierList.length - 1) {
                el.classList.remove(cls);
                el.classList.add(config.tierList[idx + 1]);
                changes.push({ from: cls, to: config.tierList[idx + 1], targetTag, targetId, targetSigClass });
              }
            }

            if (config.fixedTierList) {
              for (const cls of classList) {
                const idx = config.fixedTierList.indexOf(cls);
                if (idx >= 0 && idx < config.fixedTierList.length - 1) {
                  el.classList.remove(cls);
                  el.classList.add(config.fixedTierList[idx + 1]);
                  changes.push({ from: cls, to: config.fixedTierList[idx + 1], targetTag, targetId, targetSigClass });
                }
              }
            }

            const leadArbitraryRe = new RegExp(config.arbitraryPatterns[0]);
            for (const cls of Array.from(el.classList)) {
              const m = cls.match(leadArbitraryRe);
              if (!m) {
                continue;
              }
              const parsed = parseCssValue(m[1]);
              if (!parsed) {
                continue;
              }
              var newClass;
              if (parsed.unit) {
                const pxVal = toPx(parsed);
                if (pxVal <= (config.minPx || 0)) {
                  continue;
                }
                const newVal = Math.max(pxVal * config.scaleFactor, config.minPx || 0);
                if (newVal >= pxVal) {
                  continue;
                }
                newClass = "leading-[" + Math.round(newVal * 10) / 10 + parsed.unit + "]";
              } else {
                if (parsed.value < 3) {
                  if (parsed.value <= (config.minMultiplier || 0)) {
                    continue;
                  }
                  const newVal = Math.max(parsed.value * config.scaleFactor, config.minMultiplier || 0);
                  if (newVal >= parsed.value) {
                    continue;
                  }
                  newClass = "leading-[" + Math.round(newVal * 1000) / 1000 + "]";
                } else {
                  if (parsed.value <= (config.minPx || 0)) {
                    continue;
                  }
                  const newVal = Math.max(parsed.value * config.scaleFactor, config.minPx || 0);
                  if (newVal >= parsed.value) {
                    continue;
                  }
                  newClass = "leading-[" + Math.round(newVal * 10) / 10 + "px]";
                }
              }
              el.classList.remove(cls);
              el.classList.add(newClass);
              changes.push({ from: cls, to: newClass, targetTag, targetId, targetSigClass });
            }
          }
        }
      }
      return changes;
    }`,
    { tag: OVERFLOW_TAG, config }
  );
}
async function executeSpacingStep(renderer, step) {
  const typeDef = SPACING_TYPES[step.typeName];
  if (!typeDef || step.depth === "typo") {
    return [];
  }
  const depth = step.depth;
  const patternStrs = typeDef.patterns;
  const arbitraryPatternStrs = typeDef.arbitraryPatterns;
  return await renderer.evaluate(
    `(doc, _win, args) => {
      const patterns = args.patternStrs.map(function(s) { return new RegExp(s); });
      const arbitraryPatterns = args.arbitraryPatternStrs.map(function(s) { return new RegExp(s); });
      const depth = args.depth;
      const tag = args.tag;
      const changes = [];
      const overflowEls = doc.querySelectorAll("." + tag);

      for (const overflowEl of overflowEls) {
        var targetEls;
        if (depth === 0) {
          targetEls = [overflowEl];
        } else if (depth < 0) {
          targetEls = [];
          var current = overflowEl.parentElement;
          var parentLevel = 1;
          const slides = doc.querySelectorAll(".ppt-slide");
          const slideSet = new Set(slides);
          while (current) {
            if (slideSet.has(current)) {
              break;
            }
            if (parentLevel === -depth) {
              targetEls.push(current);
              break;
            }
            current = current.parentElement;
            parentLevel++;
          }
        } else {
          targetEls = [];
          function collectAtDepth(el, currentDepth) {
            if (currentDepth === depth) {
              targetEls.push(el);
              return;
            }
            for (const child of el.children) {
              collectAtDepth(child, currentDepth + 1);
            }
          }
          for (const child of overflowEl.children) {
            collectAtDepth(child, 1);
          }
        }

        for (const el of targetEls) {
          const classList = Array.from(el.classList);
          for (const pattern of patterns) {
            for (const cls of classList) {
              const m = cls.match(pattern);
              if (!m) {
                continue;
              }
              const value = parseInt(m[1], 10);
              const newValue = Math.floor(value * 0.8);
              if (newValue < 2) {
                continue;
              }
              const prefix = cls.replace(/-\\d+$/, "");
              const newClass = prefix + "-" + newValue;
              el.classList.remove(cls);
              el.classList.add(newClass);
              changes.push({ from: cls, to: newClass });
            }
          }

          for (const pattern of arbitraryPatterns) {
            for (const cls of classList) {
              const m = cls.match(pattern);
              if (!m) {
                continue;
              }
              const valStr = m[1];
              const numMatch = valStr.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(px|rem|em)?$/);
              if (!numMatch) {
                continue;
              }
              const num = parseFloat(numMatch[1]);
              const newVal = Math.floor(num * 0.8);
              const unit = numMatch[2] || "px";
              var pxValue = newVal;
              if (unit === "rem" || unit === "em") {
                pxValue = newVal * 16;
              }
              if (pxValue < 4) {
                continue;
              }
              const prefix = cls.replace(/-\\[([^\\]]+)\\]$/, "");
              const newClass = prefix + "-[" + newVal + unit + "]";
              el.classList.remove(cls);
              el.classList.add(newClass);
              changes.push({ from: cls, to: newClass });
            }
          }
        }
      }
      return changes;
    }`,
    { patternStrs, arbitraryPatternStrs, depth, tag: OVERFLOW_TAG }
  );
}
const WS_ID_ATTR = "data-ws-id";
const WS_TAG = "whitespace_detected";
const SELF_CLOSING_TAGS = /* @__PURE__ */ new Set([
  "br",
  "hr",
  "img",
  "input",
  "meta",
  "link",
  "area",
  "base",
  "col",
  "embed",
  "source",
  "track",
  "wbr"
]);
const SLIDE_SELECTOR = '.ppt-slide[type="content"]';
function injectWsIds(html) {
  let counter = 0;
  const result = html.replace(/<([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^>]*?)?)(\s*\/?)>/g, (match, tagName, attrs, closing) => {
    if (SELF_CLOSING_TAGS.has(tagName.toLowerCase())) {
      return match;
    }
    if (/\bdata-ws-id\s*=/.test(attrs)) {
      return match;
    }
    counter++;
    return `<${tagName}${attrs} ${WS_ID_ATTR}="${counter}"${closing}>`;
  });
  return { html: result, count: counter };
}
function removeWhitespaceClass(html) {
  let result = html;
  const tagRe = new RegExp(`\\b${WS_TAG}\\b\\s*`, "g");
  result = result.replace(/(\bclass=["'])([^"']*)(["'])/g, (_match, open, classes, close) => {
    const cleaned = classes.replace(tagRe, "").trim();
    if (cleaned.length === 0) {
      return "";
    }
    return `${open}${cleaned.replace(/\s+/g, " ")}${close}`;
  });
  result = result.replace(/\s+class=(["'])\1/g, "");
  return result;
}
function applyChangesToHtml(html, changes) {
  let result = html;
  for (const { from, to } of changes) {
    const re = /(class\s*=\s*["'])([^"']*)(["'])/g;
    result = result.replace(re, (match, prefix, classValue, suffix) => {
      if (!classValue.split(/\s+/).includes(from)) {
        return match;
      }
      const parts = classValue.split(/(\s+)/);
      const newParts = parts.map((p) => p === from ? to : p);
      return `${prefix}${newParts.join("")}${suffix}`;
    });
  }
  return result;
}
function applyJustifyAroundByWsId(html, wsIds) {
  const idSet = new Set(wsIds);
  return html.replace(/(<[a-zA-Z][a-zA-Z0-9]*)(\s[^>]*)?>/g, (match, _tag, attrs) => {
    const wsIdMatch = attrs?.match(/\bdata-ws-id=["']([^"']+)["']/);
    if (!wsIdMatch || !idSet.has(wsIdMatch[1])) {
      return match;
    }
    if (/\bclass=["']/.test(match)) {
      return match.replace(/(\bclass=["'])([^"']*)(["'])/, (m, open, cls, close) => {
        if (cls.split(/\s+/).includes("justify-around")) {
          return m;
        }
        return `${open}${cls} justify-around${close}`;
      });
    }
    return match.replace(">", ` class="justify-around">`);
  });
}
function removeWsIds(html) {
  return html.replace(new RegExp(`\\s+${WS_ID_ATTR}=["'][^"']*["']`, "g"), "");
}
function noopDebug$1(_msg) {
  return void 0;
}
async function detectWhitespace(renderer, html, opts = {}) {
  const pct = opts.percentThreshold ?? 70;
  const px = opts.pxThreshold ?? 40;
  const skipLoad = opts.skipLoad ?? false;
  const dbg = opts.debug ?? noopDebug$1;
  const t0 = Date.now();
  const { html: taggedHtml } = injectWsIds(html);
  dbg(`  [whitespace] 注入 WS ID: ${ms(Date.now() - t0)}`);
  if (!skipLoad) {
    const t1 = Date.now();
    await renderer.load(taggedHtml);
    dbg(`  [whitespace] renderer.load: ${ms(Date.now() - t1)}`);
  }
  const t2 = Date.now();
  const results = await renderer.evaluate(
    `(doc, _win, args) => {
      const pctThreshold = args.pct;
      const pxThreshold = args.px;
      const wsIdAttr = args.wsIdAttr;
      const slideSel = args.slideSel;
      const wsResults = [];

      function isColorTransparent(color) {
        if (!color) { return true; }
        const c = color.trim().toLowerCase();
        return c === "transparent" || c === "rgba(0, 0, 0, 0)" || c === "rgba(0,0,0,0)";
      }

      function getClassStr(el) {
        return typeof el.className === "string" ? el.className : (el.className && el.className.baseVal) || "";
      }

      function getTextNodeBounds(textNode, containerRect) {
        const text = (textNode.textContent || "").trim();
        if (text.length === 0) { return null; }
        const range = doc.createRange();
        range.selectNodeContents(textNode);
        const rect = range.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) { return null; }
        return { top: rect.top - containerRect.top, bottom: rect.bottom - containerRect.top };
      }

      function analyzeVisualContribution(el) {
        const style = (doc.defaultView ?? window).getComputedStyle(el);
        const result = { fullBounds: false, contributesTop: false, contributesBottom: false };
        if (!isColorTransparent(style.backgroundColor)) { result.fullBounds = true; return result; }
        const text = (el.textContent || "").trim();
        if (text.length > 0 && !isColorTransparent(style.color)) { result.fullBounds = true; return result; }
        const tag = el.tagName.toLowerCase();
        if (["img", "video", "canvas", "svg"].includes(tag)) { result.fullBounds = true; return result; }
        if (/\\bfa-[a-z]/.test(getClassStr(el))) { result.fullBounds = true; return result; }
        const hasLeftBorder = parseFloat(style.borderLeftWidth) > 0 && !isColorTransparent(style.borderLeftColor);
        const hasRightBorder = parseFloat(style.borderRightWidth) > 0 && !isColorTransparent(style.borderRightColor);
        if (hasLeftBorder || hasRightBorder) { result.fullBounds = true; return result; }
        if (parseFloat(style.borderTopWidth) > 0 && !isColorTransparent(style.borderTopColor)) { result.contributesTop = true; }
        if (parseFloat(style.borderBottomWidth) > 0 && !isColorTransparent(style.borderBottomColor)) { result.contributesBottom = true; }
        return result;
      }

      function getVisualBounds(el, containerRect) {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) { return null; }
        const contrib = analyzeVisualContribution(el);
        if (contrib.fullBounds) { return { top: rect.top - containerRect.top, bottom: rect.bottom - containerRect.top }; }

        var childMinTop = Infinity;
        var childMaxBottom = -Infinity;
        var hasVisibleChild = false;
        for (var i = 0; i < el.childNodes.length; i++) {
          const child = el.childNodes[i];
          if (child.nodeType === 1) {
            const bounds = getVisualBounds(child, containerRect);
            if (bounds) { childMinTop = Math.min(childMinTop, bounds.top); childMaxBottom = Math.max(childMaxBottom, bounds.bottom); hasVisibleChild = true; }
          } else if (child.nodeType === 3) {
            const bounds2 = getTextNodeBounds(child, containerRect);
            if (bounds2) { childMinTop = Math.min(childMinTop, bounds2.top); childMaxBottom = Math.max(childMaxBottom, bounds2.bottom); hasVisibleChild = true; }
          }
        }

        if (!contrib.contributesTop && !contrib.contributesBottom) {
          if (!hasVisibleChild) { return null; }
          return { top: childMinTop, bottom: childMaxBottom };
        }

        const relTop = rect.top - containerRect.top;
        const relBottom = rect.bottom - containerRect.top;
        if (!hasVisibleChild) {
          if (contrib.contributesTop && contrib.contributesBottom) { return { top: relTop, bottom: relBottom }; }
          if (contrib.contributesTop) { return { top: relTop, bottom: relTop + parseFloat((doc.defaultView ?? window).getComputedStyle(el).borderTopWidth) }; }
          return { top: relBottom - parseFloat((doc.defaultView ?? window).getComputedStyle(el).borderBottomWidth), bottom: relBottom };
        }

        return { top: contrib.contributesTop ? Math.min(relTop, childMinTop) : childMinTop, bottom: contrib.contributesBottom ? Math.max(relBottom, childMaxBottom) : childMaxBottom };
      }

      const slides = doc.querySelectorAll(slideSel);
      if (slides.length === 0) { return wsResults; }

      for (var si = 0; si < slides.length; si++) {
        const slide = slides[si];
        const elements = slide.querySelectorAll("*");
        for (var ei = 0; ei < elements.length; ei++) {
          const el = elements[ei];
          if (el.closest("svg") || el.tagName.toLowerCase() === "svg") { continue; }

          const containerRect = el.getBoundingClientRect();
          const containerHeight = el.clientHeight;
          if (containerHeight <= 0) { continue; }

          var minTop = Infinity;
          var maxBottom = -Infinity;
          var hasVisibleChild = false;
          for (var ci = 0; ci < el.childNodes.length; ci++) {
            const ch = el.childNodes[ci];
            if (ch.nodeType === 1) { const b = getVisualBounds(ch, containerRect); if (b) { minTop = Math.min(minTop, b.top); maxBottom = Math.max(maxBottom, b.bottom); hasVisibleChild = true; } }
            else if (ch.nodeType === 3) { const b2 = getTextNodeBounds(ch, containerRect); if (b2) { minTop = Math.min(minTop, b2.top); maxBottom = Math.max(maxBottom, b2.bottom); hasVisibleChild = true; } }
          }

          if (!hasVisibleChild) { continue; }
          const childrenSpan = maxBottom - minTop;
          if (childrenSpan <= 0) { continue; }

          const whitespace = containerHeight - childrenSpan;
          const spanRatio = (childrenSpan / containerHeight) * 100;
          if (spanRatio < pctThreshold && whitespace > pxThreshold) {
            const wsId = el.getAttribute(wsIdAttr) || "";
            const pathParts = [];
            var current = el;
            while (current && current !== slide) {
              const t = current.tagName.toLowerCase();
              const cls = typeof current.className === "string" ? current.className.split(/\\s+/).filter(Boolean).join(".") : "";
              pathParts.unshift(cls ? t + "." + cls : t);
              current = current.parentElement;
            }
            wsResults.push({
              domPath: pathParts.join(" → "),
              containerHeight: Math.round(containerHeight),
              childrenSpan: Math.round(childrenSpan * 10) / 10,
              whitespace: Math.round(whitespace * 10) / 10,
              spanRatio: Math.round(spanRatio * 10) / 10,
              whitespaceRatio: Math.round((whitespace / containerHeight) * 1000) / 10,
              wsId: wsId,
            });
          }
        }
      }
      return wsResults;
    }`,
    { pct, px, wsIdAttr: WS_ID_ATTR, slideSel: SLIDE_SELECTOR }
  );
  dbg(`  [whitespace] 检测空白元素: ${ms(Date.now() - t2)}, ${results.length} 个元素`);
  return results;
}
const TYPO_EXPANSION_TYPES = {
  "line-height": {
    name: "line-height",
    label: "line-height",
    tierList: ["leading-none", "leading-tight", "leading-snug", "leading-normal", "leading-relaxed", "leading-loose"],
    tierMap: {
      "leading-none": 1,
      "leading-tight": 1.25,
      "leading-snug": 1.375,
      "leading-normal": 1.5,
      "leading-relaxed": 1.625,
      "leading-loose": 2
    },
    fixedTierList: [
      "leading-3",
      "leading-4",
      "leading-5",
      "leading-6",
      "leading-7",
      "leading-8",
      "leading-9",
      "leading-10"
    ],
    fixedTierMap: {
      "leading-3": 12,
      "leading-4": 16,
      "leading-5": 20,
      "leading-6": 24,
      "leading-7": 28,
      "leading-8": 32,
      "leading-9": 36,
      "leading-10": 40
    },
    arbitraryPatterns: ["\\bleading-\\[([^\\]]+)\\]"],
    maxMultiplier: 2,
    maxPx: 40,
    scaleFactor: 1.25,
    remToPx: 16,
    ptToPx: 96 / 72
  }
};
const EXPANSION_TYPES = {
  padding: {
    name: "padding",
    label: "padding",
    patterns: [
      "\\bp-(\\d+)\\b",
      "\\bpx-(\\d+)\\b",
      "\\bpy-(\\d+)\\b",
      "\\bpt-(\\d+)\\b",
      "\\bpb-(\\d+)\\b",
      "\\bpl-(\\d+)\\b",
      "\\bpr-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bp-\\[([^\\]]+)\\]",
      "\\bpx-\\[([^\\]]+)\\]",
      "\\bpy-\\[([^\\]]+)\\]",
      "\\bpt-\\[([^\\]]+)\\]",
      "\\bpb-\\[([^\\]]+)\\]",
      "\\bpl-\\[([^\\]]+)\\]",
      "\\bpr-\\[([^\\]]+)\\]"
    ],
    maxPx: 64,
    scaleFactor: 1.25,
    remToPx: 16,
    ptToPx: 96 / 72
  },
  margin: {
    name: "margin",
    label: "margin",
    patterns: [
      "\\bm-(\\d+)\\b",
      "\\bmx-(\\d+)\\b",
      "\\bmy-(\\d+)\\b",
      "\\bmt-(\\d+)\\b",
      "\\bmb-(\\d+)\\b",
      "\\bml-(\\d+)\\b",
      "\\bmr-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bm-\\[([^\\]]+)\\]",
      "\\bmx-\\[([^\\]]+)\\]",
      "\\bmy-\\[([^\\]]+)\\]",
      "\\bmt-\\[([^\\]]+)\\]",
      "\\bmb-\\[([^\\]]+)\\]",
      "\\bml-\\[([^\\]]+)\\]",
      "\\bmr-\\[([^\\]]+)\\]"
    ],
    maxPx: 64,
    scaleFactor: 1.25,
    remToPx: 16,
    ptToPx: 96 / 72
  },
  gap: {
    name: "gap/space",
    label: "gap/space",
    patterns: [
      "\\bgap-(\\d+)\\b",
      "\\bgap-x-(\\d+)\\b",
      "\\bgap-y-(\\d+)\\b",
      "\\bspace-y-(\\d+)\\b",
      "\\bspace-x-(\\d+)\\b"
    ],
    arbitraryPatterns: [
      "\\bgap-\\[([^\\]]+)\\]",
      "\\bgap-x-\\[([^\\]]+)\\]",
      "\\bgap-y-\\[([^\\]]+)\\]",
      "\\bspace-y-\\[([^\\]]+)\\]",
      "\\bspace-x-\\[([^\\]]+)\\]"
    ],
    maxPx: 64,
    scaleFactor: 1.25,
    remToPx: 16,
    ptToPx: 96 / 72
  }
};
function generateExpansionStrategy(maxDepth = 2, maxCycles = 5) {
  const steps = [];
  const spacingTypes = [
    { key: "padding", label: "padding" },
    { key: "margin", label: "margin" },
    { key: "gap", label: "gap/space" }
  ];
  for (let cycle = 0; cycle < maxCycles; cycle++) {
    steps.push({
      stepType: "typo",
      depth: 0,
      typeName: "line-height",
      typeLabel: "line-height"
    });
    steps.push({
      stepType: "spacing",
      depth: 0,
      typeName: "gap",
      typeLabel: "gap/space"
    });
    for (let d = 1; d <= maxDepth; d++) {
      for (const type of spacingTypes) {
        if (type.key === "gap") {
          continue;
        }
        steps.push({
          stepType: "spacing",
          depth: d,
          typeName: type.key,
          typeLabel: type.label
        });
      }
    }
  }
  return steps;
}
function noopDebug(_msg) {
  return void 0;
}
function assembleFinalHtml(taggedHtml, allChanges, justifyWsIds) {
  let result = taggedHtml;
  if (allChanges.length > 0) {
    result = applyChangesToHtml(result, allChanges);
  }
  if (justifyWsIds.length > 0) {
    result = applyJustifyAroundByWsId(result, justifyWsIds);
  }
  result = removeWsIds(result);
  return result;
}
async function fixWhitespace(renderer, html, opts = {}) {
  const pct = opts.percentThreshold ?? 70;
  const px = opts.pxThreshold ?? 40;
  const isDryRun = opts.dryRun ?? false;
  const timeoutMs = (opts.timeoutSec ?? 300) * 1e3;
  const dbg = opts.debug ?? noopDebug;
  const startTime = Date.now();
  const cleanHtml = removeWhitespaceClass(html);
  const { html: taggedHtml } = injectWsIds(cleanHtml);
  const t0 = Date.now();
  let whitespaces = await detectWhitespace(renderer, cleanHtml, { percentThreshold: pct, pxThreshold: px, debug: dbg });
  dbg(`  [whitespace] 初始检测: ${ms(Date.now() - t0)}, ${whitespaces.length} 个空白元素`);
  const issueCount = whitespaces.length;
  if (whitespaces.length === 0) {
    return { html, fixedCount: 0, issueCount: 0, remaining: 0 };
  }
  const wsIdsForMarking = whitespaces.map((w) => w.wsId).filter(Boolean);
  await renderer.evaluate(
    `(doc, _win, args) => {
      const wsIdSet = new Set(args.wsIds);
      doc.querySelectorAll("[data-ws-id]").forEach((el) => {
        const wsId = el.getAttribute(args.wsIdAttr);
        if (wsId && wsIdSet.has(wsId)) {
          el.classList.add(args.wsTag);
        }
      });
    }`,
    { wsIds: wsIdsForMarking, wsIdAttr: WS_ID_ATTR, wsTag: WS_TAG }
  );
  const allChanges = [];
  const justifyWsIds = [];
  let totalSteps = 0;
  const tJustify = Date.now();
  const justifyResult = await renderer.evaluate(
    `(doc, _win, args) => {
      const ids = [];
      const whitespaceEls = doc.querySelectorAll("." + args.wsTag);
      for (const el of whitespaceEls) {
        const style = (doc.defaultView ?? window).getComputedStyle(el);
        if (style.display === "flex" && style.flexDirection === "column") {
          if (!el.classList.contains("justify-around")) {
            const wsId = el.getAttribute(args.wsIdAttr);
            if (wsId) {
              ids.push(wsId);
            }
            el.classList.add("justify-around");
          }
        }
      }
      return ids;
    }`,
    { wsIdAttr: WS_ID_ATTR, wsTag: WS_TAG }
  );
  dbg(`  [whitespace] justify-around: ${ms(Date.now() - tJustify)}, ${justifyResult.length} 个元素`);
  if (justifyResult.length > 0) {
    justifyWsIds.push(...justifyResult);
    totalSteps++;
    await renderer.evaluate(
      `(doc, _win, args) => {
      doc.querySelectorAll("." + args).forEach((el) => {
        el.classList.remove(args);
      });
    }`,
      WS_TAG
    );
    const reTaggedContent = await renderer.getContent();
    const { html: reTaggedHtml } = injectWsIds(removeWhitespaceClass(reTaggedContent));
    await renderer.load(reTaggedHtml);
    const tRecheck1 = Date.now();
    whitespaces = await detectWhitespace(renderer, removeWhitespaceClass(reTaggedHtml), {
      percentThreshold: pct,
      pxThreshold: px,
      skipLoad: true,
      debug: dbg
    });
    dbg(`  [whitespace] justify 后复验: ${ms(Date.now() - tRecheck1)}, 剩余 ${whitespaces.length} 个`);
    if (whitespaces.length === 0) {
      const result2 = assembleFinalHtml(taggedHtml, allChanges, justifyWsIds);
      if (!isDryRun) {
        return { html: result2, fixedCount: issueCount, issueCount, remaining: 0 };
      }
      return { html, fixedCount: issueCount, issueCount, remaining: 0 };
    }
    const reMarkWsIds = whitespaces.map((w) => w.wsId).filter(Boolean);
    await renderer.evaluate(
      `(doc, _win, args) => {
        const wsIdSet = new Set(args.wsIds);
        doc.querySelectorAll("." + args.wsTag).forEach((el) => {
          el.classList.remove(args.wsTag);
        });
        doc.querySelectorAll("[data-ws-id]").forEach((el) => {
          const wsId = el.getAttribute(args.wsIdAttr);
          if (wsId && wsIdSet.has(wsId)) {
            el.classList.add(args.wsTag);
          }
        });
      }`,
      { wsIds: reMarkWsIds, wsIdAttr: WS_ID_ATTR, wsTag: WS_TAG }
    );
  }
  const tPadding = Date.now();
  const paddingChanges = await executePaddingReduction(renderer);
  dbg(`  [whitespace] padding 缩减: ${ms(Date.now() - tPadding)}, ${paddingChanges.length} 个变更`);
  if (paddingChanges.length > 0) {
    totalSteps++;
    allChanges.push(...paddingChanges);
    await renderer.evaluate(
      `(doc, _win, args) => {
      doc.querySelectorAll("." + args).forEach((el) => {
        el.classList.remove(args);
      });
    }`,
      WS_TAG
    );
    const reTaggedContentPad = await renderer.getContent();
    const { html: reTaggedHtmlPad } = injectWsIds(removeWhitespaceClass(reTaggedContentPad));
    await renderer.load(reTaggedHtmlPad);
    const tRecheckPad = Date.now();
    whitespaces = await detectWhitespace(renderer, removeWhitespaceClass(reTaggedHtmlPad), {
      percentThreshold: pct,
      pxThreshold: px,
      skipLoad: true,
      debug: dbg
    });
    dbg(`  [whitespace] padding 后复验: ${ms(Date.now() - tRecheckPad)}, 剩余 ${whitespaces.length} 个`);
    if (whitespaces.length === 0) {
      const result2 = assembleFinalHtml(taggedHtml, allChanges, justifyWsIds);
      if (!isDryRun) {
        return { html: result2, fixedCount: issueCount, issueCount, remaining: 0 };
      }
      return { html, fixedCount: totalSteps > 0 ? issueCount - whitespaces.length : 0, issueCount, remaining: 0 };
    }
    const reMarkWsIdsPad = whitespaces.map((w) => w.wsId).filter(Boolean);
    await renderer.evaluate(
      `(doc, _win, args) => {
        const wsIdSet = new Set(args.wsIds);
        doc.querySelectorAll("[data-ws-id]").forEach((el) => {
          const wsId = el.getAttribute(args.wsIdAttr);
          if (wsId && wsIdSet.has(wsId)) {
            el.classList.add(args.wsTag);
          }
        });
      }`,
      { wsIds: reMarkWsIdsPad, wsIdAttr: WS_ID_ATTR, wsTag: WS_TAG }
    );
  }
  const strategySteps = generateExpansionStrategy();
  for (const step of strategySteps) {
    if (Date.now() - startTime > timeoutMs) {
      dbg(`  [whitespace] 策略循环超时，已执行 ${totalSteps} 步`);
      break;
    }
    dbg(`  [whitespace] 膨胀策略: ${step.typeLabel || step.typeName}`);
    const tStep = Date.now();
    let changes;
    if (step.stepType === "typo") {
      changes = await executeTypographyExpansion(renderer, step.typeName);
    } else {
      changes = await executeSpacingExpansion(renderer, step);
    }
    dbg(`  [whitespace] 策略执行: ${ms(Date.now() - tStep)}, ${changes.length} 个变更`);
    if (changes.length === 0) {
      continue;
    }
    totalSteps++;
    allChanges.push(...changes);
    await renderer.evaluate(
      `(doc, _win, args) => {
      doc.querySelectorAll("." + args).forEach((el) => {
        el.classList.remove(args);
      });
    }`,
      WS_TAG
    );
    const reTaggedContent = await renderer.getContent();
    const { html: reTaggedHtml } = injectWsIds(removeWhitespaceClass(reTaggedContent));
    await renderer.load(reTaggedHtml);
    const tRecheckExp = Date.now();
    whitespaces = await detectWhitespace(renderer, removeWhitespaceClass(reTaggedHtml), {
      percentThreshold: pct,
      pxThreshold: px,
      skipLoad: true,
      debug: dbg
    });
    dbg(`  [whitespace] 膨胀后复验: ${ms(Date.now() - tRecheckExp)}, 剩余 ${whitespaces.length} 个`);
    if (whitespaces.length === 0) {
      const result2 = assembleFinalHtml(taggedHtml, allChanges, justifyWsIds);
      if (!isDryRun) {
        return { html: result2, fixedCount: issueCount, issueCount, remaining: 0 };
      }
      return { html, fixedCount: totalSteps > 0 ? issueCount : 0, issueCount, remaining: 0 };
    }
    const reMarkWsIds = whitespaces.map((w) => w.wsId).filter(Boolean);
    await renderer.evaluate(
      `(doc, _win, args) => {
        const wsIdSet = new Set(args.wsIds);
        doc.querySelectorAll("[data-ws-id]").forEach((el) => {
          const wsId = el.getAttribute(args.wsIdAttr);
          if (wsId && wsIdSet.has(wsId)) {
            el.classList.add(args.wsTag);
          }
        });
      }`,
      { wsIds: reMarkWsIds, wsIdAttr: WS_ID_ATTR, wsTag: WS_TAG }
    );
  }
  const result = assembleFinalHtml(taggedHtml, allChanges, justifyWsIds);
  if (!isDryRun) {
    return {
      html: result,
      fixedCount: totalSteps > 0 ? issueCount - whitespaces.length : 0,
      issueCount,
      remaining: whitespaces.length
    };
  }
  return { html, fixedCount: 0, issueCount, remaining: whitespaces.length };
}
async function executePaddingReduction(renderer) {
  const typeDef = EXPANSION_TYPES.padding;
  return await renderer.evaluate(
    `(doc, _win, args) => {
      const typeDef = args.typeDef;
      const tag = args.tag;
      const patternStrs = typeDef.patterns;
      const arbitraryPatternStrs = typeDef.arbitraryPatterns;

      const changes = [];
      const whitespaceEls = doc.querySelectorAll("." + tag);
      const patterns = patternStrs.map(function(p) { return new RegExp(p); });
      const arbitraryPatterns = arbitraryPatternStrs.map(function(p) { return new RegExp(p); });

      function parseCssValueInner(valStr) {
        const numMatch = valStr.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(px|rem|em|pt)?$/);
        if (!numMatch) {
          return null;
        }
        return { value: parseFloat(numMatch[1]), unit: numMatch[2] || "" };
      }

      function toPxInner(parsed) {
        if (parsed.unit === "rem" || parsed.unit === "em") {
          return parsed.value * typeDef.remToPx;
        }
        if (parsed.unit === "pt") {
          return parsed.value * typeDef.ptToPx;
        }
        return parsed.value;
      }

      for (const el of whitespaceEls) {
        const classList = Array.from(el.classList);

        for (const pattern of patterns) {
          for (const cls of classList) {
            const m = cls.match(pattern);
            if (!m) {
              continue;
            }
            const value = parseFloat(m[1]);
            const newValue = Math.floor(value * 0.8);
            if (newValue < 2) {
              continue;
            }
            const prefix = cls.replace(/-\\d+(?:\\.\\d+)?$/, "");
            const newClass = prefix + "-" + newValue;
            el.classList.remove(cls);
            el.classList.add(newClass);
            changes.push({ from: cls, to: newClass });
          }
        }

        for (const pattern of arbitraryPatterns) {
          for (const cls of classList) {
            const m = cls.match(pattern);
            if (!m) {
              continue;
            }
            const valStr = m[1];
            const parsed = parseCssValueInner(valStr);
            if (!parsed) {
              continue;
            }
            const px = toPxInner(parsed);
            const newPx = Math.floor(px * 0.8);
            if (newPx < 4) {
              continue;
            }
            const prefix = cls.replace(/-\\[([^\\]]+)\\]$/, "");
            const unit = parsed.unit || "px";
            const newClass = prefix + "-[" + newPx + unit + "]";
            el.classList.remove(cls);
            el.classList.add(newClass);
            changes.push({ from: cls, to: newClass });
          }
        }
      }

      return changes;
    }`,
    { typeDef, tag: WS_TAG }
  );
}
async function executeTypographyExpansion(renderer, typeName) {
  const config = TYPO_EXPANSION_TYPES[typeName];
  if (!config) {
    return [];
  }
  return await renderer.evaluate(
    `(doc, _win, args) => {
      const config = args.config;
      const tag = args.tag;
      const changes = [];
      const whitespaceEls = doc.querySelectorAll("." + tag);

      for (const wsEl of whitespaceEls) {
        const targets = [wsEl].concat(Array.from(wsEl.querySelectorAll("*")));

        for (const el of targets) {
          const classList = Array.from(el.classList);

          if (config.name === "line-height") {
            for (const cls of classList) {
              const idx = config.tierList.indexOf(cls);
              if (idx >= 0 && idx < config.tierList.length - 1) {
                el.classList.remove(cls);
                el.classList.add(config.tierList[idx + 1]);
                changes.push({ from: cls, to: config.tierList[idx + 1] });
              }
            }

            for (const cls of classList) {
              const idx = config.fixedTierList.indexOf(cls);
              if (idx >= 0 && idx < config.fixedTierList.length - 1) {
                el.classList.remove(cls);
                el.classList.add(config.fixedTierList[idx + 1]);
                changes.push({ from: cls, to: config.fixedTierList[idx + 1] });
              }
            }

            const leadArbitraryRe = new RegExp(config.arbitraryPatterns[0]);
            for (const cls of Array.from(el.classList)) {
              const m = cls.match(leadArbitraryRe);
              if (!m) {
                continue;
              }
              const numMatch = m[1].match(/^(-?\\d+(?:\\.\\d+)?)\\s*(px|rem|em|pt)?$/);
              if (!numMatch) {
                continue;
              }
              const parsedVal = parseFloat(numMatch[1]);
              const parsedUnit = numMatch[2] || "";

              if (parsedUnit) {
                var px;
                if (parsedUnit === "rem" || parsedUnit === "em") {
                  px = parsedVal * config.remToPx;
                } else if (parsedUnit === "pt") {
                  px = parsedVal * config.ptToPx;
                } else {
                  px = parsedVal;
                }
                if (px >= config.maxPx) {
                  continue;
                }
                const newVal = Math.min(Math.ceil(px * config.scaleFactor), config.maxPx);
                if (newVal <= px) {
                  continue;
                }
                const newClass = "leading-[" + newVal + parsedUnit + "]";
                el.classList.remove(cls);
                el.classList.add(newClass);
                changes.push({ from: cls, to: newClass });
              } else {
                if (parsedVal < 3) {
                  if (parsedVal >= config.maxMultiplier) {
                    continue;
                  }
                  const newVal = Math.min(
                    Math.ceil(parsedVal * config.scaleFactor * 1000) / 1000,
                    config.maxMultiplier
                  );
                  if (newVal <= parsedVal) {
                    continue;
                  }
                  const newClass = "leading-[" + newVal + "]";
                  el.classList.remove(cls);
                  el.classList.add(newClass);
                  changes.push({ from: cls, to: newClass });
                } else {
                  if (parsedVal >= config.maxPx) {
                    continue;
                  }
                  const newVal = Math.min(Math.ceil(parsedVal * config.scaleFactor), config.maxPx);
                  if (newVal <= parsedVal) {
                    continue;
                  }
                  const newClass = "leading-[" + newVal + "px]";
                  el.classList.remove(cls);
                  el.classList.add(newClass);
                  changes.push({ from: cls, to: newClass });
                }
              }
            }
          }
        }
      }

      return changes;
    }`,
    { config, tag: WS_TAG }
  );
}
async function executeSpacingExpansion(renderer, step) {
  const typeDef = EXPANSION_TYPES[step.typeName];
  if (!typeDef) {
    return [];
  }
  return await renderer.evaluate(
    `(doc, _win, args) => {
      const typeDef = args.typeDef;
      const depth = args.depth;
      const tag = args.tag;
      const typeName = args.typeName;
      const patternStrs = typeDef.patterns;
      const arbitraryPatternStrs = typeDef.arbitraryPatterns;

      const changes = [];
      const whitespaceEls = doc.querySelectorAll("." + tag);
      const patterns = patternStrs.map(function(p) { return new RegExp(p); });
      const arbitraryPatterns = arbitraryPatternStrs.map(function(p) { return new RegExp(p); });

      function parseCssValueInner(valStr) {
        const numMatch = valStr.match(/^(-?\\d+(?:\\.\\d+)?)\\s*(px|rem|em|pt)?$/);
        if (!numMatch) {
          return null;
        }
        return { value: parseFloat(numMatch[1]), unit: numMatch[2] || "" };
      }

      function toPxInner(parsed) {
        if (parsed.unit === "rem" || parsed.unit === "em") {
          return parsed.value * typeDef.remToPx;
        }
        if (parsed.unit === "pt") {
          return parsed.value * typeDef.ptToPx;
        }
        return parsed.value;
      }

      const targetEls = [];
      for (const wsEl of whitespaceEls) {
        if (depth === 0) {
          if (typeName === "gap") {
            const style = (doc.defaultView ?? window).getComputedStyle(wsEl);
            if (style.display !== "flex" || style.flexDirection !== "column") {
              continue;
            }
          }
          targetEls.push(wsEl);
        } else {
          function collectAtDepth(el, currentDepth) {
            if (currentDepth === depth) {
              targetEls.push(el);
              return;
            }
            for (const child of el.children) {
              collectAtDepth(child, currentDepth + 1);
            }
          }
          for (const child of wsEl.children) {
            collectAtDepth(child, 1);
          }
        }
      }

      for (const el of targetEls) {
        const classList = Array.from(el.classList);

        for (const pattern of patterns) {
          for (const cls of classList) {
            const m = cls.match(pattern);
            if (!m) {
              continue;
            }
            const value = parseFloat(m[1]);
            const newValue = Math.ceil(value * typeDef.scaleFactor);
            if (newValue <= value || newValue > typeDef.maxPx) {
              continue;
            }
            const prefix = cls.replace(/-\\d+(?:\\.\\d+)?$/, "");
            const newClass = prefix + "-" + newValue;
            el.classList.remove(cls);
            el.classList.add(newClass);
            changes.push({ from: cls, to: newClass });
          }
        }

        for (const pattern of arbitraryPatterns) {
          for (const cls of classList) {
            const m = cls.match(pattern);
            if (!m) {
              continue;
            }
            const valStr = m[1];
            const parsed = parseCssValueInner(valStr);
            if (!parsed) {
              continue;
            }
            const px = toPxInner(parsed);
            const newPx = Math.ceil(px * typeDef.scaleFactor);
            if (newPx <= px || newPx > typeDef.maxPx) {
              continue;
            }
            const prefix = cls.replace(/-\\[([^\\]]+)\\]$/, "");
            const unit = parsed.unit || "px";
            const newClass = prefix + "-[" + newPx + unit + "]";
            el.classList.remove(cls);
            el.classList.add(newClass);
            changes.push({ from: cls, to: newClass });
          }
        }
      }

      return changes;
    }`,
    { typeDef, depth: step.depth, tag: WS_TAG, typeName: step.typeName }
  );
}
var _a;
const decodeMap = /* @__PURE__ */ new Map([
  [0, 65533],
  [128, 8364],
  [130, 8218],
  [131, 402],
  [132, 8222],
  [133, 8230],
  [134, 8224],
  [135, 8225],
  [136, 710],
  [137, 8240],
  [138, 352],
  [139, 8249],
  [140, 338],
  [142, 381],
  [145, 8216],
  [146, 8217],
  [147, 8220],
  [148, 8221],
  [149, 8226],
  [150, 8211],
  [151, 8212],
  [152, 732],
  [153, 8482],
  [154, 353],
  [155, 8250],
  [156, 339],
  [158, 382],
  [159, 376]
]);
const fromCodePoint = (
  (_a = String.fromCodePoint) !== null && _a !== void 0 ? _a : ((codePoint) => {
    let output = "";
    if (codePoint > 65535) {
      codePoint -= 65536;
      output += String.fromCharCode(codePoint >>> 10 & 1023 | 55296);
      codePoint = 56320 | codePoint & 1023;
    }
    output += String.fromCharCode(codePoint);
    return output;
  })
);
function replaceCodePoint(codePoint) {
  var _a2;
  if (codePoint >= 55296 && codePoint <= 57343 || codePoint > 1114111) {
    return 65533;
  }
  return (_a2 = decodeMap.get(codePoint)) !== null && _a2 !== void 0 ? _a2 : codePoint;
}
function decodeBase64(input) {
  const binary = (
    typeof atob === "function" ? (
      atob(input)
    ) : (
      typeof Buffer.from === "function" ? (
        Buffer.from(input, "base64").toString("binary")
      ) : (
        new Buffer(input, "base64").toString("binary")
      )
    )
  );
  const evenLength = binary.length & -2;
  const out = new Uint16Array(evenLength / 2);
  for (let index = 0, outIndex = 0; index < evenLength; index += 2) {
    const lo = binary.charCodeAt(index);
    const hi = binary.charCodeAt(index + 1);
    out[outIndex++] = lo | hi << 8;
  }
  return out;
}
const htmlDecodeTree = /* @__PURE__ */ decodeBase64("QR08ALkAAgH6AYsDNQR2BO0EPgXZBQEGLAbdBxMISQrvCmQLfQurDKQNLw4fD4YPpA+6D/IPAAAAAAAAAAAAAAAAKhBMEY8TmxUWF2EYLBkxGuAa3RsJHDscWR8YIC8jSCSIJcMl6ie3Ku8rEC0CLjoupS7kLgAIRU1hYmNmZ2xtbm9wcnN0dVQAWgBeAGUAaQBzAHcAfgCBAIQAhwCSAJoAoACsALMAbABpAGcAO4DGAMZAUAA7gCYAJkBjAHUAdABlADuAwQDBQHIiZXZlAAJhAAFpeW0AcgByAGMAO4DCAMJAEGRyAADgNdgE3XIAYQB2AGUAO4DAAMBA8CFoYZFj4SFjcgBhZAAAoFMqAAFncIsAjgBvAG4ABGFmAADgNdg43fAlbHlGdW5jdGlvbgCgYSBpAG4AZwA7gMUAxUAAAWNzpACoAHIAAOA12Jzc6SFnbgCgVCJpAGwAZABlADuAwwDDQG0AbAA7gMQAxEAABGFjZWZvcnN1xQDYANoA7QDxAPYA+QD8AAABY3LJAM8AayNzbGFzaAAAoBYidgHTANUAAKDnKmUAZAAAoAYjeQARZIABY3J0AOAA5QDrAGEidXNlAACgNSLuI291bGxpcwCgLCFhAJJjcgAA4DXYBd1wAGYAAOA12Dnd5SF2ZdhiYwDyAOoAbSJwZXEAAKBOIgAHSE9hY2RlZmhpbG9yc3UXARoBHwE6AVIBVQFiAWQBZgGCAakB6QHtAfIBYwB5ACdkUABZADuAqQCpQIABY3B5ACUBKAE1AfUhdGUGYWmg0iJ0KGFsRGlmZmVyZW50aWFsRAAAoEUhbCJleXMAAKAtIQACYWVpb0EBRAFKAU0B8iFvbgxhZABpAGwAO4DHAMdAcgBjAAhhbiJpbnQAAKAwIm8AdAAKYQABZG5ZAV0BaSJsbGEAuGB0I2VyRG90ALdg8gA5AWkAp2NyImNsZQAAAkRNUFRwAXQBeQF9AW8AdAAAoJkiaSJudXMAAKCWIuwhdXMAoJUiaSJtZXMAAKCXIm8AAAFjc4cBlAFrKndpc2VDb250b3VySW50ZWdyYWwAAKAyImUjQ3VybHkAAAFEUZwBpAFvJXVibGVRdW90ZQAAoB0gdSJvdGUAAKAZIAACbG5wdbABtgHNAdgBbwBuAGWgNyIAoHQqgAFnaXQAvAHBAcUB8iJ1ZW50AKBhIm4AdAAAoC8i7yV1ckludGVncmFsAKAuIgABZnLRAdMBAKACIe8iZHVjdACgECJuLnRlckNsb2Nrd2lzZUNvbnRvdXJJbnRlZ3JhbAAAoDMi7yFzcwCgLypjAHIAAOA12J7ccABDoNMiYQBwAACgTSKABURKU1phY2VmaW9zAAsCEgIVAhgCGwIsAjQCOQI9AnMCfwNvoEUh9CJyYWhkAKARKWMAeQACZGMAeQAFZGMAeQAPZIABZ3JzACECJQIoAuchZXIAoCEgcgAAoKEhaAB2AACg5CoAAWF5MAIzAvIhb24OYRRkbAB0oAciYQCUY3IAAOA12AfdAAFhZkECawIAAWNtRQJnAvIjaXRpY2FsAAJBREdUUAJUAl8CYwJjInV0ZQC0YG8AdAFZAloC2WJiJGxlQWN1dGUA3WJyImF2ZQBgYGkibGRlANxi7yFuZACgxCJmJWVyZW50aWFsRAAAoEYhcAR9AgAAAAAAAIECjgIAABoDZgAA4DXYO91EoagAhQKJAm8AdAAAoNwgcSJ1YWwAAKBQIuIhbGUAA0NETFJVVpkCqAK1Au8C/wIRA28AbgB0AG8AdQByAEkAbgB0AGUAZwByAGEA7ADEAW8AdAKvAgAAAACwAqhgbiNBcnJvdwAAoNMhAAFlb7kC0AJmAHQAgAFBUlQAwQLGAs0CciJyb3cAAKDQIekkZ2h0QXJyb3cAoNQhZQDlACsCbgBnAAABTFLWAugC5SFmdAABQVLcAuECciJyb3cAAKD4J+kkZ2h0QXJyb3cAoPon6SRnaHRBcnJvdwCg+SdpImdodAAAAUFU9gL7AnIicm93AACg0iFlAGUAAKCoInAAQQIGAwAAAAALA3Iicm93AACg0SFvJHduQXJyb3cAAKDVIWUlcnRpY2FsQmFyAACgJSJuAAADQUJMUlRhJAM2AzoDWgNxA3oDciJyb3cAAKGTIUJVLAMwA2EAcgAAoBMpcCNBcnJvdwAAoPUhciJldmUAEWPlIWZ00gJDAwAASwMAAFIDaSVnaHRWZWN0b3IAAKBQKWUkZVZlY3RvcgAAoF4p5SJjdG9yQqC9IWEAcgAAoFYpaSJnaHQA1AFiAwAAaQNlJGVWZWN0b3IAAKBfKeUiY3RvckKgwSFhAHIAAKBXKWUAZQBBoKQiciJyb3cAAKCnIXIAcgBvAPcAtAIAAWN0gwOHA3IA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YwAAoN8i4SFycnCgtiEAoD0pgKIqImJjZG9zACsVMBU6FT4VQRVyImNhcAAAoEgqAAFhdTQVNxVwAACgRipwAACgSipvAHQAAKCNInIAAKBFKgDgKiIA/gACYWxydksVURVuFXMVcgByAG2gtyEAoDwpeQCAAWV2dwBYFWUVaRVxAHACXxUAAAAAYxVyAGUA4wAXFXUA4wAZFWUAZQAAoM4iZSJkZ2UAAKDPImUAbgA7gKQApEBlI2Fycm93AAABbHJ7FX8V5SFmdACgtiFpImdodAAAoLchZQDkAG0VAAFjaYsVkRVvAG4AaQBuAPQAkwFuAHQAAKAxImwiY3R5AACgLSOACUFIYWJjZGVmaGlqbG9yc3R1d3oAuBW7Fb8V1RXgFegV+RUKFhUWHxZUFlcWZRbFFtsW7xb7FgUXChdyAPIAtAJhAHIAAKBlKQACZ2xyc8YVyhXOFdAV5yFlcgCgICDlIXRoAKA4IfIA9QxoAHagECAAoKMiawHZFd4VYSJyb3cAAKAPKWEA4wBfAgABYXnkFecV8iFvbg9hNGQAoUYhYW/tFfQVAAFnciEC8RVyAACgyiF0InNlcQAAoHcqgAFnbG0A/xUCFgUWO4CwALBAdABhALRjcCJ0eXYAAKCxKQABaXIOFhIW8yFodACgfykA4DXYId1hAHIAAAFschsWHRYAoMMhAKDCIYACYWVnc3YAKBauAjYWOhY+Fm0AAKHEIm9zLhY0Fm4AZABzoMQi9SFpdACgZiZhIm1tYQDdY2kAbgAAoPIiAKH3AGlvQxZRFmQAZQAAgfcAO29KFksW90BuI3RpbWVzAACgxyJuAPgAUBZjAHkAUmRjAG8CXhYAAAAAYhZyAG4AAKAeI28AcAAAoA0jgAJscHR1dwBuFnEWdRaSFp4W7CFhciRgZgAA4DXYVd0AotkCZW1wc30WhBaJFo0WcQBkoFAibwB0AACgUSJpIm51cwAAoDgi7CF1cwCgFCLxInVhcmUAoKEiYgBsAGUAYgBhAHIAdwBlAGQAZwDlANcAbgCAAWFkaAClFqoWtBZyAHIAbwD3APUMbwB3AG4AYQByAHIAbwB3APMA8xVhI3Jwb29uAAABbHK8FsAWZQBmAPQAHBZpAGcAaAD0AB4WYgHJFs8WawBhAHIAbwD3AJILbwLUFgAAAADYFnIAbgAAoB8jbwBwAACgDCOAAWNvdADhFukW7BYAAXJ55RboFgDgNdi53FVkbAAAoPYp8iFvaxFhAAFkcvMW9xZvAHQAAKDxImkA5qC/JVsSAAFhaP8WAhdyAPIANQNhAPIA1wvhIm5nbGUAoKYpAAFjaQ4XEBd5AF9k5yJyYXJyAKD/JwAJRGFjZGVmZ2xtbm9wcXJzdHV4MRc4F0YXWxcyBF4XaRd5F40XrBe0F78X2RcVGCEYLRg1GEAYAAFEbzUXgRZvAPQA+BUAAWNzPBdCF3UAdABlADuA6QDpQPQhZXIAoG4qAAJhaW95TRdQF1YXWhfyIW9uG2FyAGOgViI7gOoA6kDsIW9uAKBVIk1kbwB0ABdhAAFEcmIXZhdvAHQAAKBSIgDgNdgi3XKhmipuF3QXYQB2AGUAO4DoAOhAZKCWKm8AdAAAoJgqgKGZKmlscwCAF4UXhxfuInRlcnMAoOcjAKATIWSglSpvAHQAAKCXKoABYXBzAJMXlheiF2MAcgATYXQAeQBzogUinxcAAAAAoRdlAHQAAKAFInAAMaADIDMBqRerFwCgBCAAoAUgAAFnc7AXsRdLYXAAAKACIAABZ3C4F7sXbwBuABlhZgAA4DXYVt2AAWFscwDFF8sXzxdyAHOg1SJsAACg4yl1AHMAAKBxKmkAAKG1A2x21RfYF28AbgC1Y/VjAAJjc3V24BfoF/0XEBgAAWlv5BdWF3IAYwAAoFYiaQLuFwAAAADwF+0ADQThIW50AAFnbPUX+Rd0AHIAAKCWKuUhc3MAoJUqgAFhZWkAAxgGGAoYbABzAD1gcwB0AACgXyJ2AESgYSJEAACgeCrwImFyc2wAoOUpAAFEYRkYHRhvAHQAAKBTInIAcgAAoHEpgAFjZGkAJxgqGO0XcgAAoC8hbwD0AIwCAAFhaDEYMhi3YzuA8ADwQAABbXI5GD0YbAA7gOsA60BvAACgrCCAAWNpcABGGEgYSxhsACFgcwD0ACwEAAFlb08YVxhjAHQAYQB0AGkAbwDuABoEbgBlAG4AdABpAGEAbADlADME4Ql1GAAAgRgAAIMYiBgAAAAAoRilGAAAqhgAALsYvhjRGAAA1xgnGWwAbABpAG4AZwBkAG8AdABzAGUA8QBlF3kARGRtImFsZQAAoEAmgAFpbHIAjRiRGJ0Y7CFpZwCgA/tpApcYAAAAAJoYZwAAoAD7aQBnAACgBPsA4DXYI93sIWlnAKAB++whaWcA4GYAagCAAWFsdACvGLIYthh0AACgbSZpAGcAAKAC+24AcwAAoLElbwBmAJJh8AHCGAAAxhhmAADgNdhX3QABYWvJGMwYbADsAGsEdqDUIgCg2SphI3J0aW50AACgDSoAAWFv2hgiGQABY3PeGB8ZsQPnGP0YBRkSGRUZAAAdGbID7xjyGPQY9xj5GAAA+xg7gL0AvUAAoFMhO4C8ALxAAKBVIQCgWSEAoFshswEBGQAAAxkAoFQhAKBWIbQCCxkOGQAAAAAQGTuAvgC+QACgVyEAoFwhNQAAoFghtgEZGQAAGxkAoFohAKBdITgAAKBeIWwAAKBEIHcAbgAAoCIjYwByAADgNdi73IAIRWFiY2RlZmdpamxub3JzdHYARhlKGVoZXhlmGWkZkhmWGZkZnRmgGa0ZxhnLGc8Z4BkjGmygZyIAoIwqgAFjbXAAUBlTGVgZ9SF0ZfVhbQBhAOSgswM6FgCghipyImV2ZQAfYQABaXliGWUZcgBjAB1hM2RvAHQAIWGAoWUibHFzAMYEcBl6GfGhZSLOBAAAdhlsAGEAbgD0AN8EgKF+KmNkbACBGYQZjBljAACgqSpvAHQAb6CAKmyggioAoIQqZeDbIgD+cwAAoJQqcgAA4DXYJN3noGsirATtIWVsAKA3IWMAeQBTZIChdyJFYWoApxmpGasZAKCSKgCgpSoAoKQqAAJFYWVztBm2Gb0ZwhkAoGkicABwoIoq8iFveACgiipxoIgq8aCIKrUZaQBtAACg5yJwAGYAAOA12FjdYQB2AOUAYwIAAWNp0xnWGXIAAKAKIW0AAKFzImVs3BneGQCgjioAoJAqAIM+ADtjZGxxco0E6xn0GfgZ/BkBGgABY2nvGfEZAKCnKnIAAKB6Km8AdAAAoNci0CFhcgCglSl1ImVzdAAAoHwqgAJhZGVscwAKGvQZFhrVBCAa8AEPGgAAFBpwAHIAbwD4AFkZcgAAoHgpcQAAAWxxxAQbGmwAZQBzAPMASRlpAO0A5AQAAWVuJxouGnIjdG5lcXEAAOBpIgD+xQAsGgAFQWFiY2Vma29zeUAaQxpmGmoabRqDGocalhrCGtMacgDyAMwCAAJpbG1yShpOGlAaVBpyAHMA8ABxD2YAvWBpAGwA9AASBQABZHJYGlsaYwB5AEpkAKGUIWN3YBpkGmkAcgAAoEgpAKCtIWEAcgAAoA8h6SFyYyVhgAFhbHIAcxp7Gn8a8iF0c3WgZSZpAHQAAKBlJuwhaXAAoCYg4yFvbgCguSJyAADgNdgl3XMAAAFld4wakRphInJvdwAAoCUpYSJyb3cAAKAmKYACYW1vcHIAnxqjGqcauhq+GnIAcgAAoP8h9CFodACgOyJrAAABbHKsGrMaZSRmdGFycm93AACgqSHpJGdodGFycm93AKCqIWYAAOA12Fnd4iFhcgCgFSCAAWNsdADIGswa0BpyAADgNdi93GEAcwDoAGka8iFvaydhAAFicNca2xr1IWxsAKBDIOghZW4AoBAg4Qr2GgAA/RoAAAgbExsaGwAAIRs7GwAAAAA+G2IbmRuVG6sbAACyG80b0htjAHUAdABlADuA7QDtQAChYyBpeQEbBhtyAGMAO4DuAO5AOGQAAWN4CxsNG3kANWRjAGwAO4ChAKFAAAFmcssCFhsA4DXYJt1yAGEAdgBlADuA7ADsQIChSCFpbm8AJxsyGzYbAAFpbisbLxtuAHQAAKAMKnQAAKAtIuYhaW4AoNwpdABhAACgKSHsIWlnM2GAAWFvcABDG1sbXhuAAWNndABJG0sbWRtyACthgAFlbHAAcQVRG1UbaQBuAOUAyAVhAHIA9AByBWgAMWFmAACgtyJlAGQAtWEAoggiY2ZvdGkbbRt1G3kb4SFyZQCgBSFpAG4AdKAeImkAZQAAoN0pZABvAPQAWxsAoisiY2VscIEbhRuPG5QbYQBsAACguiIAAWdyiRuNG2UAcgDzACMQ4wCCG2EicmhrAACgFyryIW9kAKA8KgACY2dwdJ8boRukG6gbeQBRZG8AbgAvYWYAAOA12FrdYQC5Y3UAZQBzAHQAO4C/AL9AAAFjabUbuRtyAADgNdi+3G4AAKIIIkVkc3bCG8QbyBvQAwCg+SJvAHQAAKD1Inag9CIAoPMiaaBiIOwhZGUpYesB1hsAANkbYwB5AFZkbAA7gO8A70AAA2NmbW9zdeYb7hvyG/Ub+hsFHAABaXnqG+0bcgBjADVhOWRyAADgNdgn3eEhdGg3YnAAZgAA4DXYW93jAf8bAAADHHIAAOA12L/c8iFjeVhk6yFjeVRkAARhY2ZnaGpvcxUcGhwiHCYcKhwtHDAcNRzwIXBhdqC6A/BjAAFleR4cIRzkIWls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ZmdobG1vcHJzdHV3CiwNLBEsHSwnLDEsQCxLLFIsYix6LIQsjyzLLOgs7Sz/LAotcgDyAAkDYQByAACgYykAAWNyFSwbLHUAdABlADuA+gD6QPIACQ1yAOMBIywAACUseQBeZHYAZQBtYQABaXkrLDAscgBjADuA+wD7QENkgAFhYmgANyw6LD0scgDyANEO7CFhY3FhYQDyAOAOAAFpckQsSCzzIWh0AKB+KQDgNdgy3XIAYQB2AGUAO4D5APlAYQFWLF8scgAAAWxyWixcLACgvyEAoL4hbABrAACggCUAAWN0Zix2LG8CbCwAAAAAcyxyAG4AZaAcI3IAAKAcI28AcAAAoA8jcgBpAACg+CUAAWFsfiyBLGMAcgBrYTuAqACoQAABZ3CILIssbwBuAHNhZgAA4DXYZt0AA2FkaGxzdZksniynLLgsuyzFLHIAcgBvAPcACQ1vAHcAbgBhAHIAcgBvAPcA2A5hI3Jwb29uAAABbHKvLLMsZQBmAPQAWyxpAGcAaAD0AF0sdQDzAKYOaQAAocUDaGzBLMIs0mNvAG4AxWPwI2Fycm93cwCgyCGAAWNpdADRLOEs5CxvAtcsAAAAAN4scgBuAGWgHSNyAACgHSNvAHAAAKAOI24AZwBvYXIAaQAAoPklYwByAADgNdjK3IABZGlyAPMs9yz6LG8AdAAAoPAi7CFkZWlhaQBmoLUlAKC0JQABYW0DLQYtcgDyAMosbAA7gPwA/EDhIm5nbGUAoKcpgAdBQkRhY2RlZmxub3Byc3oAJy0qLTAtNC2bLZ0toS2/LcMtxy3TLdgt3C3gLfwtcgDyABADYQByAHag6CoAoOkqYQBzAOgA/gIAAW5yOC08LechcnQAoJwpgANla25wcnN0AJkpSC1NLVQtXi1iLYItYQBwAHAA4QAaHG8AdABoAGkAbgDnAKEXgAFoaXIAoSmzJFotbwBwAPQAdCVooJUh7wD4JgABaXVmLWotZwBtAOEAuygAAWJwbi14LXMjZXRuZXEAceCKIgD+AODLKgD+cyNldG5lcQBx4IsiAP4A4MwqAP4AAWhyhi2KLWUAdADhABIraSNhbmdsZQAAAWxyki2WLeUhZnQAoLIiaSJnaHQAAKCzInkAMmThIXNoAKCiIoABZWxyAKcttC24LWKiKCKuLQAAAACyLWEAcgAAoLsicQAAoFoi7CFpcACg7iIAAWJ0vC1eD2EA8gBfD3IAAOA12DPddAByAOkAlS1zAHUAAAFicM0t0C0A4IIi0iAA4IMi0iBwAGYAAOA12GfdcgBvAPAAWQt0AHIA6QCaLQABY3XkLegtcgAA4DXYy9wAAWJw7C30LW4AAAFFZXUt8S0A4IoiAP5uAAABRWV/LfktAOCLIgD+6SJnemFnAKCaKYADY2Vmb3BycwANLhAuJS4pLiMuLi40LukhcmN1YQABZGkULiEuAAFiZxguHC5hAHIAAKBfKmUAcaAnIgCgWSLlIXJwAKAYIXIAAOA12DTdcABmAADgNdho3WWgQCJhAHQA6ABqD2MAcgAA4DXYzNzjCuQRUC4AAFQuAABYLmIuAAAAAGMubS5wLnQuAAAAAIguki4AAJouJxIqEnQAcgDpAB0ScgAA4DXYNd0AAUFhWy5eLnIA8gDnAnIA8gCTB75jAAFBYWYuaS5yAPIA4AJyAPIAjAdhAPAAeh5pAHMAAKD7IoABZHB0APgReS6DLgABZmx9LoAuAOA12GnddQDzAP8RaQBtAOUABBIAAUFhiy6OLnIA8gDuAnIA8gCaBwABY3GVLgoScgAA4DXYzdwAAXB0nS6hLmwAdQDzACUScgDpACASAARhY2VmaW9zdbEuvC7ELsguzC7PLtQu2S5jAAABdXm2LrsudABlADuA/QD9QE9kAAFpecAuwy5yAGMAd2FLZG4AO4ClAKVAcgAA4DXYNt1jAHkAV2RwAGYAAOA12GrdYwByAADgNdjO3AABY23dLt8ueQBOZGwAO4D/AP9AAAVhY2RlZmhpb3N38y73Lv8uAi8MLxAvEy8YLx0vIi9jInV0ZQB6YQABYXn7Lv4u8iFvbn5hN2RvAHQAfGEAAWV0Bi8KL3QAcgDmAB8QYQC2Y3IAAOA12DfdYwB5ADZk5yJyYXJyAKDdIXAAZgAA4DXYa91jAHIAAOA12M/cAAFqbiYvKC8AoA0gagAAoAwg");
const xmlDecodeTree = /* @__PURE__ */ decodeBase64("AAJhZ2xxBwARABMAFQBtAg0AAAAAAA8AcAAmYG8AcwAnYHQAPmB0ADxg9SFvdCJg");
var BinTrieFlags;
(function(BinTrieFlags2) {
  BinTrieFlags2[BinTrieFlags2["VALUE_LENGTH"] = 49152] = "VALUE_LENGTH";
  BinTrieFlags2[BinTrieFlags2["FLAG13"] = 8192] = "FLAG13";
  BinTrieFlags2[BinTrieFlags2["BRANCH_LENGTH"] = 8064] = "BRANCH_LENGTH";
  BinTrieFlags2[BinTrieFlags2["JUMP_TABLE"] = 127] = "JUMP_TABLE";
})(BinTrieFlags || (BinTrieFlags = {}));
var CharCodes$1;
(function(CharCodes2) {
  CharCodes2[CharCodes2["NUM"] = 35] = "NUM";
  CharCodes2[CharCodes2["SEMI"] = 59] = "SEMI";
  CharCodes2[CharCodes2["EQUALS"] = 61] = "EQUALS";
  CharCodes2[CharCodes2["ZERO"] = 48] = "ZERO";
  CharCodes2[CharCodes2["NINE"] = 57] = "NINE";
  CharCodes2[CharCodes2["LOWER_A"] = 97] = "LOWER_A";
  CharCodes2[CharCodes2["LOWER_F"] = 102] = "LOWER_F";
  CharCodes2[CharCodes2["LOWER_X"] = 120] = "LOWER_X";
  CharCodes2[CharCodes2["LOWER_Z"] = 122] = "LOWER_Z";
  CharCodes2[CharCodes2["UPPER_A"] = 65] = "UPPER_A";
  CharCodes2[CharCodes2["UPPER_F"] = 70] = "UPPER_F";
  CharCodes2[CharCodes2["UPPER_Z"] = 90] = "UPPER_Z";
})(CharCodes$1 || (CharCodes$1 = {}));
const TO_LOWER_BIT = 32;
function isNumber(code) {
  return code >= CharCodes$1.ZERO && code <= CharCodes$1.NINE;
}
function isHexadecimalCharacter(code) {
  return code >= CharCodes$1.UPPER_A && code <= CharCodes$1.UPPER_F || code >= CharCodes$1.LOWER_A && code <= CharCodes$1.LOWER_F;
}
function isAsciiAlphaNumeric(code) {
  return code >= CharCodes$1.UPPER_A && code <= CharCodes$1.UPPER_Z || code >= CharCodes$1.LOWER_A && code <= CharCodes$1.LOWER_Z || isNumber(code);
}
function isEntityInAttributeInvalidEnd(code) {
  return code === CharCodes$1.EQUALS || isAsciiAlphaNumeric(code);
}
var EntityDecoderState;
(function(EntityDecoderState2) {
  EntityDecoderState2[EntityDecoderState2["EntityStart"] = 0] = "EntityStart";
  EntityDecoderState2[EntityDecoderState2["NumericStart"] = 1] = "NumericStart";
  EntityDecoderState2[EntityDecoderState2["NumericDecimal"] = 2] = "NumericDecimal";
  EntityDecoderState2[EntityDecoderState2["NumericHex"] = 3] = "NumericHex";
  EntityDecoderState2[EntityDecoderState2["NamedEntity"] = 4] = "NamedEntity";
})(EntityDecoderState || (EntityDecoderState = {}));
var DecodingMode;
(function(DecodingMode2) {
  DecodingMode2[DecodingMode2["Legacy"] = 0] = "Legacy";
  DecodingMode2[DecodingMode2["Strict"] = 1] = "Strict";
  DecodingMode2[DecodingMode2["Attribute"] = 2] = "Attribute";
})(DecodingMode || (DecodingMode = {}));
class EntityDecoder {
  constructor(decodeTree, emitCodePoint, errors) {
    this.decodeTree = decodeTree;
    this.emitCodePoint = emitCodePoint;
    this.errors = errors;
    this.state = EntityDecoderState.EntityStart;
    this.consumed = 1;
    this.result = 0;
    this.treeIndex = 0;
    this.excess = 1;
    this.decodeMode = DecodingMode.Strict;
    this.runConsumed = 0;
  }
  startEntity(decodeMode) {
    this.decodeMode = decodeMode;
    this.state = EntityDecoderState.EntityStart;
    this.result = 0;
    this.treeIndex = 0;
    this.excess = 1;
    this.consumed = 1;
    this.runConsumed = 0;
  }
  write(input, offset) {
    switch (this.state) {
      case EntityDecoderState.EntityStart: {
        if (input.charCodeAt(offset) === CharCodes$1.NUM) {
          this.state = EntityDecoderState.NumericStart;
          this.consumed += 1;
          return this.stateNumericStart(input, offset + 1);
        }
        this.state = EntityDecoderState.NamedEntity;
        return this.stateNamedEntity(input, offset);
      }
      case EntityDecoderState.NumericStart: {
        return this.stateNumericStart(input, offset);
      }
      case EntityDecoderState.NumericDecimal: {
        return this.stateNumericDecimal(input, offset);
      }
      case EntityDecoderState.NumericHex: {
        return this.stateNumericHex(input, offset);
      }
      case EntityDecoderState.NamedEntity: {
        return this.stateNamedEntity(input, offset);
      }
    }
  }
  stateNumericStart(input, offset) {
    if (offset >= input.length) {
      return -1;
    }
    if ((input.charCodeAt(offset) | TO_LOWER_BIT) === CharCodes$1.LOWER_X) {
      this.state = EntityDecoderState.NumericHex;
      this.consumed += 1;
      return this.stateNumericHex(input, offset + 1);
    }
    this.state = EntityDecoderState.NumericDecimal;
    return this.stateNumericDecimal(input, offset);
  }
  stateNumericHex(input, offset) {
    while (offset < input.length) {
      const char = input.charCodeAt(offset);
      if (isNumber(char) || isHexadecimalCharacter(char)) {
        const digit = char <= CharCodes$1.NINE ? char - CharCodes$1.ZERO : (char | TO_LOWER_BIT) - CharCodes$1.LOWER_A + 10;
        this.result = this.result * 16 + digit;
        this.consumed++;
        offset++;
      } else {
        return this.emitNumericEntity(char, 3);
      }
    }
    return -1;
  }
  stateNumericDecimal(input, offset) {
    while (offset < input.length) {
      const char = input.charCodeAt(offset);
      if (isNumber(char)) {
        this.result = this.result * 10 + (char - CharCodes$1.ZERO);
        this.consumed++;
        offset++;
      } else {
        return this.emitNumericEntity(char, 2);
      }
    }
    return -1;
  }
  emitNumericEntity(lastCp, expectedLength) {
    var _a2;
    if (this.consumed <= expectedLength) {
      (_a2 = this.errors) === null || _a2 === void 0 ? void 0 : _a2.absenceOfDigitsInNumericCharacterReference(this.consumed);
      return 0;
    }
    if (lastCp === CharCodes$1.SEMI) {
      this.consumed += 1;
    } else if (this.decodeMode === DecodingMode.Strict) {
      return 0;
    }
    this.emitCodePoint(replaceCodePoint(this.result), this.consumed);
    if (this.errors) {
      if (lastCp !== CharCodes$1.SEMI) {
        this.errors.missingSemicolonAfterCharacterReference();
      }
      this.errors.validateNumericCharacterReference(this.result);
    }
    return this.consumed;
  }
  stateNamedEntity(input, offset) {
    const { decodeTree } = this;
    let current = decodeTree[this.treeIndex];
    let valueLength = (current & BinTrieFlags.VALUE_LENGTH) >> 14;
    while (offset < input.length) {
      if (valueLength === 0 && (current & BinTrieFlags.FLAG13) !== 0) {
        const runLength = (current & BinTrieFlags.BRANCH_LENGTH) >> 7;
        if (this.runConsumed === 0) {
          const firstChar = current & BinTrieFlags.JUMP_TABLE;
          if (input.charCodeAt(offset) !== firstChar) {
            return this.result === 0 ? 0 : this.emitNotTerminatedNamedEntity();
          }
          offset++;
          this.excess++;
          this.runConsumed++;
        }
        while (this.runConsumed < runLength) {
          if (offset >= input.length) {
            return -1;
          }
          const charIndexInPacked = this.runConsumed - 1;
          const packedWord = decodeTree[this.treeIndex + 1 + (charIndexInPacked >> 1)];
          const expectedChar = charIndexInPacked % 2 === 0 ? packedWord & 255 : packedWord >> 8 & 255;
          if (input.charCodeAt(offset) !== expectedChar) {
            this.runConsumed = 0;
            return this.result === 0 ? 0 : this.emitNotTerminatedNamedEntity();
          }
          offset++;
          this.excess++;
          this.runConsumed++;
        }
        this.runConsumed = 0;
        this.treeIndex += 1 + (runLength >> 1);
        current = decodeTree[this.treeIndex];
        valueLength = (current & BinTrieFlags.VALUE_LENGTH) >> 14;
      }
      if (offset >= input.length)
        break;
      const char = input.charCodeAt(offset);
      if (char === CharCodes$1.SEMI && valueLength !== 0 && (current & BinTrieFlags.FLAG13) !== 0) {
        return this.emitNamedEntityData(this.treeIndex, valueLength, this.consumed + this.excess);
      }
      this.treeIndex = determineBranch(decodeTree, current, this.treeIndex + Math.max(1, valueLength), char);
      if (this.treeIndex < 0) {
        return this.result === 0 || // If we are parsing an attribute
        this.decodeMode === DecodingMode.Attribute && // We shouldn't have consumed any characters after the entity,
        (valueLength === 0 || // And there should be no invalid characters.
        isEntityInAttributeInvalidEnd(char)) ? 0 : this.emitNotTerminatedNamedEntity();
      }
      current = decodeTree[this.treeIndex];
      valueLength = (current & BinTrieFlags.VALUE_LENGTH) >> 14;
      if (valueLength !== 0) {
        if (char === CharCodes$1.SEMI) {
          return this.emitNamedEntityData(this.treeIndex, valueLength, this.consumed + this.excess);
        }
        if (this.decodeMode !== DecodingMode.Strict && (current & BinTrieFlags.FLAG13) === 0) {
          this.result = this.treeIndex;
          this.consumed += this.excess;
          this.excess = 0;
        }
      }
      offset++;
      this.excess++;
    }
    return -1;
  }
  emitNotTerminatedNamedEntity() {
    var _a2;
    const { result, decodeTree } = this;
    const valueLength = (decodeTree[result] & BinTrieFlags.VALUE_LENGTH) >> 14;
    this.emitNamedEntityData(result, valueLength, this.consumed);
    (_a2 = this.errors) === null || _a2 === void 0 ? void 0 : _a2.missingSemicolonAfterCharacterReference();
    return this.consumed;
  }
  emitNamedEntityData(result, valueLength, consumed) {
    const { decodeTree } = this;
    this.emitCodePoint(valueLength === 1 ? decodeTree[result] & ~(BinTrieFlags.VALUE_LENGTH | BinTrieFlags.FLAG13) : decodeTree[result + 1], consumed);
    if (valueLength === 3) {
      this.emitCodePoint(decodeTree[result + 2], consumed);
    }
    return consumed;
  }
  end() {
    var _a2;
    switch (this.state) {
      case EntityDecoderState.NamedEntity: {
        return this.result !== 0 && (this.decodeMode !== DecodingMode.Attribute || this.result === this.treeIndex) ? this.emitNotTerminatedNamedEntity() : 0;
      }
      case EntityDecoderState.NumericDecimal: {
        return this.emitNumericEntity(0, 2);
      }
      case EntityDecoderState.NumericHex: {
        return this.emitNumericEntity(0, 3);
      }
      case EntityDecoderState.NumericStart: {
        (_a2 = this.errors) === null || _a2 === void 0 ? void 0 : _a2.absenceOfDigitsInNumericCharacterReference(this.consumed);
        return 0;
      }
      case EntityDecoderState.EntityStart: {
        return 0;
      }
    }
  }
}
function determineBranch(decodeTree, current, nodeIndex, char) {
  const branchCount = (current & BinTrieFlags.BRANCH_LENGTH) >> 7;
  const jumpOffset = current & BinTrieFlags.JUMP_TABLE;
  if (branchCount === 0) {
    return jumpOffset !== 0 && char === jumpOffset ? nodeIndex : -1;
  }
  if (jumpOffset) {
    const value = char - jumpOffset;
    return value < 0 || value >= branchCount ? -1 : decodeTree[nodeIndex + value] - 1;
  }
  const packedKeySlots = branchCount + 1 >> 1;
  let lo = 0;
  let hi = branchCount - 1;
  while (lo <= hi) {
    const mid = lo + hi >>> 1;
    const slot = mid >> 1;
    const packed = decodeTree[nodeIndex + slot];
    const midKey = packed >> (mid & 1) * 8 & 255;
    if (midKey < char) {
      lo = mid + 1;
    } else if (midKey > char) {
      hi = mid - 1;
    } else {
      return decodeTree[nodeIndex + packedKeySlots + mid];
    }
  }
  return -1;
}
var CharCodes;
(function(CharCodes2) {
  CharCodes2[CharCodes2["Tab"] = 9] = "Tab";
  CharCodes2[CharCodes2["NewLine"] = 10] = "NewLine";
  CharCodes2[CharCodes2["FormFeed"] = 12] = "FormFeed";
  CharCodes2[CharCodes2["CarriageReturn"] = 13] = "CarriageReturn";
  CharCodes2[CharCodes2["Space"] = 32] = "Space";
  CharCodes2[CharCodes2["ExclamationMark"] = 33] = "ExclamationMark";
  CharCodes2[CharCodes2["Number"] = 35] = "Number";
  CharCodes2[CharCodes2["Amp"] = 38] = "Amp";
  CharCodes2[CharCodes2["SingleQuote"] = 39] = "SingleQuote";
  CharCodes2[CharCodes2["DoubleQuote"] = 34] = "DoubleQuote";
  CharCodes2[CharCodes2["Dash"] = 45] = "Dash";
  CharCodes2[CharCodes2["Slash"] = 47] = "Slash";
  CharCodes2[CharCodes2["Zero"] = 48] = "Zero";
  CharCodes2[CharCodes2["Nine"] = 57] = "Nine";
  CharCodes2[CharCodes2["Semi"] = 59] = "Semi";
  CharCodes2[CharCodes2["Lt"] = 60] = "Lt";
  CharCodes2[CharCodes2["Eq"] = 61] = "Eq";
  CharCodes2[CharCodes2["Gt"] = 62] = "Gt";
  CharCodes2[CharCodes2["Questionmark"] = 63] = "Questionmark";
  CharCodes2[CharCodes2["UpperA"] = 65] = "UpperA";
  CharCodes2[CharCodes2["LowerA"] = 97] = "LowerA";
  CharCodes2[CharCodes2["UpperF"] = 70] = "UpperF";
  CharCodes2[CharCodes2["LowerF"] = 102] = "LowerF";
  CharCodes2[CharCodes2["UpperZ"] = 90] = "UpperZ";
  CharCodes2[CharCodes2["LowerZ"] = 122] = "LowerZ";
  CharCodes2[CharCodes2["LowerX"] = 120] = "LowerX";
  CharCodes2[CharCodes2["OpeningSquareBracket"] = 91] = "OpeningSquareBracket";
})(CharCodes || (CharCodes = {}));
var State;
(function(State2) {
  State2[State2["Text"] = 1] = "Text";
  State2[State2["BeforeTagName"] = 2] = "BeforeTagName";
  State2[State2["InTagName"] = 3] = "InTagName";
  State2[State2["InSelfClosingTag"] = 4] = "InSelfClosingTag";
  State2[State2["BeforeClosingTagName"] = 5] = "BeforeClosingTagName";
  State2[State2["InClosingTagName"] = 6] = "InClosingTagName";
  State2[State2["AfterClosingTagName"] = 7] = "AfterClosingTagName";
  State2[State2["BeforeAttributeName"] = 8] = "BeforeAttributeName";
  State2[State2["InAttributeName"] = 9] = "InAttributeName";
  State2[State2["AfterAttributeName"] = 10] = "AfterAttributeName";
  State2[State2["BeforeAttributeValue"] = 11] = "BeforeAttributeValue";
  State2[State2["InAttributeValueDq"] = 12] = "InAttributeValueDq";
  State2[State2["InAttributeValueSq"] = 13] = "InAttributeValueSq";
  State2[State2["InAttributeValueNq"] = 14] = "InAttributeValueNq";
  State2[State2["BeforeDeclaration"] = 15] = "BeforeDeclaration";
  State2[State2["InDeclaration"] = 16] = "InDeclaration";
  State2[State2["InProcessingInstruction"] = 17] = "InProcessingInstruction";
  State2[State2["BeforeComment"] = 18] = "BeforeComment";
  State2[State2["CDATASequence"] = 19] = "CDATASequence";
  State2[State2["InSpecialComment"] = 20] = "InSpecialComment";
  State2[State2["InCommentLike"] = 21] = "InCommentLike";
  State2[State2["BeforeSpecialS"] = 22] = "BeforeSpecialS";
  State2[State2["BeforeSpecialT"] = 23] = "BeforeSpecialT";
  State2[State2["SpecialStartSequence"] = 24] = "SpecialStartSequence";
  State2[State2["InSpecialTag"] = 25] = "InSpecialTag";
  State2[State2["InEntity"] = 26] = "InEntity";
})(State || (State = {}));
function isWhitespace(c) {
  return c === CharCodes.Space || c === CharCodes.NewLine || c === CharCodes.Tab || c === CharCodes.FormFeed || c === CharCodes.CarriageReturn;
}
function isEndOfTagSection(c) {
  return c === CharCodes.Slash || c === CharCodes.Gt || isWhitespace(c);
}
function isASCIIAlpha(c) {
  return c >= CharCodes.LowerA && c <= CharCodes.LowerZ || c >= CharCodes.UpperA && c <= CharCodes.UpperZ;
}
var QuoteType;
(function(QuoteType2) {
  QuoteType2[QuoteType2["NoValue"] = 0] = "NoValue";
  QuoteType2[QuoteType2["Unquoted"] = 1] = "Unquoted";
  QuoteType2[QuoteType2["Single"] = 2] = "Single";
  QuoteType2[QuoteType2["Double"] = 3] = "Double";
})(QuoteType || (QuoteType = {}));
const Sequences = {
  Cdata: new Uint8Array([67, 68, 65, 84, 65, 91]),
  CdataEnd: new Uint8Array([93, 93, 62]),
  CommentEnd: new Uint8Array([45, 45, 62]),
  ScriptEnd: new Uint8Array([60, 47, 115, 99, 114, 105, 112, 116]),
  StyleEnd: new Uint8Array([60, 47, 115, 116, 121, 108, 101]),
  TitleEnd: new Uint8Array([60, 47, 116, 105, 116, 108, 101]),
  TextareaEnd: new Uint8Array([
    60,
    47,
    116,
    101,
    120,
    116,
    97,
    114,
    101,
    97
  ]),
  XmpEnd: new Uint8Array([60, 47, 120, 109, 112])
};
class Tokenizer {
  constructor({ xmlMode = false, decodeEntities = true }, cbs) {
    this.cbs = cbs;
    this.state = State.Text;
    this.buffer = "";
    this.sectionStart = 0;
    this.index = 0;
    this.entityStart = 0;
    this.baseState = State.Text;
    this.isSpecial = false;
    this.running = true;
    this.offset = 0;
    this.currentSequence = void 0;
    this.sequenceIndex = 0;
    this.xmlMode = xmlMode;
    this.decodeEntities = decodeEntities;
    this.entityDecoder = new EntityDecoder(xmlMode ? xmlDecodeTree : htmlDecodeTree, (cp, consumed) => this.emitCodePoint(cp, consumed));
  }
  reset() {
    this.state = State.Text;
    this.buffer = "";
    this.sectionStart = 0;
    this.index = 0;
    this.baseState = State.Text;
    this.currentSequence = void 0;
    this.running = true;
    this.offset = 0;
  }
  write(chunk) {
    this.offset += this.buffer.length;
    this.buffer = chunk;
    this.parse();
  }
  end() {
    if (this.running)
      this.finish();
  }
  pause() {
    this.running = false;
  }
  resume() {
    this.running = true;
    if (this.index < this.buffer.length + this.offset) {
      this.parse();
    }
  }
  stateText(c) {
    if (c === CharCodes.Lt || !this.decodeEntities && this.fastForwardTo(CharCodes.Lt)) {
      if (this.index > this.sectionStart) {
        this.cbs.ontext(this.sectionStart, this.index);
      }
      this.state = State.BeforeTagName;
      this.sectionStart = this.index;
    } else if (this.decodeEntities && c === CharCodes.Amp) {
      this.startEntity();
    }
  }
  stateSpecialStartSequence(c) {
    const isEnd = this.sequenceIndex === this.currentSequence.length;
    const isMatch = isEnd ? (
      isEndOfTagSection(c)
    ) : (
      (c | 32) === this.currentSequence[this.sequenceIndex]
    );
    if (!isMatch) {
      this.isSpecial = false;
    } else if (!isEnd) {
      this.sequenceIndex++;
      return;
    }
    this.sequenceIndex = 0;
    this.state = State.InTagName;
    this.stateInTagName(c);
  }
  stateInSpecialTag(c) {
    if (this.sequenceIndex === this.currentSequence.length) {
      if (c === CharCodes.Gt || isWhitespace(c)) {
        const endOfText = this.index - this.currentSequence.length;
        if (this.sectionStart < endOfText) {
          const actualIndex = this.index;
          this.index = endOfText;
          this.cbs.ontext(this.sectionStart, endOfText);
          this.index = actualIndex;
        }
        this.isSpecial = false;
        this.sectionStart = endOfText + 2;
        this.stateInClosingTagName(c);
        return;
      }
      this.sequenceIndex = 0;
    }
    if ((c | 32) === this.currentSequence[this.sequenceIndex]) {
      this.sequenceIndex += 1;
    } else if (this.sequenceIndex === 0) {
      if (this.currentSequence === Sequences.TitleEnd) {
        if (this.decodeEntities && c === CharCodes.Amp) {
          this.startEntity();
        }
      } else if (this.fastForwardTo(CharCodes.Lt)) {
        this.sequenceIndex = 1;
      }
    } else {
      this.sequenceIndex = Number(c === CharCodes.Lt);
    }
  }
  stateCDATASequence(c) {
    if (c === Sequences.Cdata[this.sequenceIndex]) {
      if (++this.sequenceIndex === Sequences.Cdata.length) {
        this.state = State.InCommentLike;
        this.currentSequence = Sequences.CdataEnd;
        this.sequenceIndex = 0;
        this.sectionStart = this.index + 1;
      }
    } else {
      this.sequenceIndex = 0;
      this.state = State.InDeclaration;
      this.stateInDeclaration(c);
    }
  }
  fastForwardTo(c) {
    while (++this.index < this.buffer.length + this.offset) {
      if (this.buffer.charCodeAt(this.index - this.offset) === c) {
        return true;
      }
    }
    this.index = this.buffer.length + this.offset - 1;
    return false;
  }
  stateInCommentLike(c) {
    if (c === this.currentSequence[this.sequenceIndex]) {
      if (++this.sequenceIndex === this.currentSequence.length) {
        if (this.currentSequence === Sequences.CdataEnd) {
          this.cbs.oncdata(this.sectionStart, this.index, 2);
        } else {
          this.cbs.oncomment(this.sectionStart, this.index, 2);
        }
        this.sequenceIndex = 0;
        this.sectionStart = this.index + 1;
        this.state = State.Text;
      }
    } else if (this.sequenceIndex === 0) {
      if (this.fastForwardTo(this.currentSequence[0])) {
        this.sequenceIndex = 1;
      }
    } else if (c !== this.currentSequence[this.sequenceIndex - 1]) {
      this.sequenceIndex = 0;
    }
  }
  isTagStartChar(c) {
    return this.xmlMode ? !isEndOfTagSection(c) : isASCIIAlpha(c);
  }
  startSpecial(sequence, offset) {
    this.isSpecial = true;
    this.currentSequence = sequence;
    this.sequenceIndex = offset;
    this.state = State.SpecialStartSequence;
  }
  stateBeforeTagName(c) {
    if (c === CharCodes.ExclamationMark) {
      this.state = State.BeforeDeclaration;
      this.sectionStart = this.index + 1;
    } else if (c === CharCodes.Questionmark) {
      this.state = State.InProcessingInstruction;
      this.sectionStart = this.index + 1;
    } else if (this.isTagStartChar(c)) {
      const lower = c | 32;
      this.sectionStart = this.index;
      if (this.xmlMode) {
        this.state = State.InTagName;
      } else if (lower === Sequences.ScriptEnd[2]) {
        this.state = State.BeforeSpecialS;
      } else if (lower === Sequences.TitleEnd[2] || lower === Sequences.XmpEnd[2]) {
        this.state = State.BeforeSpecialT;
      } else {
        this.state = State.InTagName;
      }
    } else if (c === CharCodes.Slash) {
      this.state = State.BeforeClosingTagName;
    } else {
      this.state = State.Text;
      this.stateText(c);
    }
  }
  stateInTagName(c) {
    if (isEndOfTagSection(c)) {
      this.cbs.onopentagname(this.sectionStart, this.index);
      this.sectionStart = -1;
      this.state = State.BeforeAttributeName;
      this.stateBeforeAttributeName(c);
    }
  }
  stateBeforeClosingTagName(c) {
    if (isWhitespace(c)) ;
    else if (c === CharCodes.Gt) {
      this.state = State.Text;
    } else {
      this.state = this.isTagStartChar(c) ? State.InClosingTagName : State.InSpecialComment;
      this.sectionStart = this.index;
    }
  }
  stateInClosingTagName(c) {
    if (c === CharCodes.Gt || isWhitespace(c)) {
      this.cbs.onclosetag(this.sectionStart, this.index);
      this.sectionStart = -1;
      this.state = State.AfterClosingTagName;
      this.stateAfterClosingTagName(c);
    }
  }
  stateAfterClosingTagName(c) {
    if (c === CharCodes.Gt || this.fastForwardTo(CharCodes.Gt)) {
      this.state = State.Text;
      this.sectionStart = this.index + 1;
    }
  }
  stateBeforeAttributeName(c) {
    if (c === CharCodes.Gt) {
      this.cbs.onopentagend(this.index);
      if (this.isSpecial) {
        this.state = State.InSpecialTag;
        this.sequenceIndex = 0;
      } else {
        this.state = State.Text;
      }
      this.sectionStart = this.index + 1;
    } else if (c === CharCodes.Slash) {
      this.state = State.InSelfClosingTag;
    } else if (!isWhitespace(c)) {
      this.state = State.InAttributeName;
      this.sectionStart = this.index;
    }
  }
  stateInSelfClosingTag(c) {
    if (c === CharCodes.Gt) {
      this.cbs.onselfclosingtag(this.index);
      this.state = State.Text;
      this.sectionStart = this.index + 1;
      this.isSpecial = false;
    } else if (!isWhitespace(c)) {
      this.state = State.BeforeAttributeName;
      this.stateBeforeAttributeName(c);
    }
  }
  stateInAttributeName(c) {
    if (c === CharCodes.Eq || isEndOfTagSection(c)) {
      this.cbs.onattribname(this.sectionStart, this.index);
      this.sectionStart = this.index;
      this.state = State.AfterAttributeName;
      this.stateAfterAttributeName(c);
    }
  }
  stateAfterAttributeName(c) {
    if (c === CharCodes.Eq) {
      this.state = State.BeforeAttributeValue;
    } else if (c === CharCodes.Slash || c === CharCodes.Gt) {
      this.cbs.onattribend(QuoteType.NoValue, this.sectionStart);
      this.sectionStart = -1;
      this.state = State.BeforeAttributeName;
      this.stateBeforeAttributeName(c);
    } else if (!isWhitespace(c)) {
      this.cbs.onattribend(QuoteType.NoValue, this.sectionStart);
      this.state = State.InAttributeName;
      this.sectionStart = this.index;
    }
  }
  stateBeforeAttributeValue(c) {
    if (c === CharCodes.DoubleQuote) {
      this.state = State.InAttributeValueDq;
      this.sectionStart = this.index + 1;
    } else if (c === CharCodes.SingleQuote) {
      this.state = State.InAttributeValueSq;
      this.sectionStart = this.index + 1;
    } else if (!isWhitespace(c)) {
      this.sectionStart = this.index;
      this.state = State.InAttributeValueNq;
      this.stateInAttributeValueNoQuotes(c);
    }
  }
  handleInAttributeValue(c, quote) {
    if (c === quote || !this.decodeEntities && this.fastForwardTo(quote)) {
      this.cbs.onattribdata(this.sectionStart, this.index);
      this.sectionStart = -1;
      this.cbs.onattribend(quote === CharCodes.DoubleQuote ? QuoteType.Double : QuoteType.Single, this.index + 1);
      this.state = State.BeforeAttributeName;
    } else if (this.decodeEntities && c === CharCodes.Amp) {
      this.startEntity();
    }
  }
  stateInAttributeValueDoubleQuotes(c) {
    this.handleInAttributeValue(c, CharCodes.DoubleQuote);
  }
  stateInAttributeValueSingleQuotes(c) {
    this.handleInAttributeValue(c, CharCodes.SingleQuote);
  }
  stateInAttributeValueNoQuotes(c) {
    if (isWhitespace(c) || c === CharCodes.Gt) {
      this.cbs.onattribdata(this.sectionStart, this.index);
      this.sectionStart = -1;
      this.cbs.onattribend(QuoteType.Unquoted, this.index);
      this.state = State.BeforeAttributeName;
      this.stateBeforeAttributeName(c);
    } else if (this.decodeEntities && c === CharCodes.Amp) {
      this.startEntity();
    }
  }
  stateBeforeDeclaration(c) {
    if (c === CharCodes.OpeningSquareBracket) {
      this.state = State.CDATASequence;
      this.sequenceIndex = 0;
    } else {
      this.state = c === CharCodes.Dash ? State.BeforeComment : State.InDeclaration;
    }
  }
  stateInDeclaration(c) {
    if (c === CharCodes.Gt || this.fastForwardTo(CharCodes.Gt)) {
      this.cbs.ondeclaration(this.sectionStart, this.index);
      this.state = State.Text;
      this.sectionStart = this.index + 1;
    }
  }
  stateInProcessingInstruction(c) {
    if (c === CharCodes.Gt || this.fastForwardTo(CharCodes.Gt)) {
      this.cbs.onprocessinginstruction(this.sectionStart, this.index);
      this.state = State.Text;
      this.sectionStart = this.index + 1;
    }
  }
  stateBeforeComment(c) {
    if (c === CharCodes.Dash) {
      this.state = State.InCommentLike;
      this.currentSequence = Sequences.CommentEnd;
      this.sequenceIndex = 2;
      this.sectionStart = this.index + 1;
    } else {
      this.state = State.InDeclaration;
    }
  }
  stateInSpecialComment(c) {
    if (c === CharCodes.Gt || this.fastForwardTo(CharCodes.Gt)) {
      this.cbs.oncomment(this.sectionStart, this.index, 0);
      this.state = State.Text;
      this.sectionStart = this.index + 1;
    }
  }
  stateBeforeSpecialS(c) {
    const lower = c | 32;
    if (lower === Sequences.ScriptEnd[3]) {
      this.startSpecial(Sequences.ScriptEnd, 4);
    } else if (lower === Sequences.StyleEnd[3]) {
      this.startSpecial(Sequences.StyleEnd, 4);
    } else {
      this.state = State.InTagName;
      this.stateInTagName(c);
    }
  }
  stateBeforeSpecialT(c) {
    const lower = c | 32;
    switch (lower) {
      case Sequences.TitleEnd[3]: {
        this.startSpecial(Sequences.TitleEnd, 4);
        break;
      }
      case Sequences.TextareaEnd[3]: {
        this.startSpecial(Sequences.TextareaEnd, 4);
        break;
      }
      case Sequences.XmpEnd[3]: {
        this.startSpecial(Sequences.XmpEnd, 4);
        break;
      }
      default: {
        this.state = State.InTagName;
        this.stateInTagName(c);
      }
    }
  }
  startEntity() {
    this.baseState = this.state;
    this.state = State.InEntity;
    this.entityStart = this.index;
    this.entityDecoder.startEntity(this.xmlMode ? DecodingMode.Strict : this.baseState === State.Text || this.baseState === State.InSpecialTag ? DecodingMode.Legacy : DecodingMode.Attribute);
  }
  stateInEntity() {
    const indexInBuffer = this.index - this.offset;
    const length = this.entityDecoder.write(this.buffer, indexInBuffer);
    if (length >= 0) {
      this.state = this.baseState;
      if (length === 0) {
        this.index -= 1;
      }
    } else {
      if (indexInBuffer < this.buffer.length && this.buffer.charCodeAt(indexInBuffer) === CharCodes.Amp) {
        this.state = this.baseState;
        this.index -= 1;
        return;
      }
      this.index = this.offset + this.buffer.length - 1;
    }
  }
  cleanup() {
    if (this.running && this.sectionStart !== this.index) {
      if (this.state === State.Text || this.state === State.InSpecialTag && this.sequenceIndex === 0) {
        this.cbs.ontext(this.sectionStart, this.index);
        this.sectionStart = this.index;
      } else if (this.state === State.InAttributeValueDq || this.state === State.InAttributeValueSq || this.state === State.InAttributeValueNq) {
        this.cbs.onattribdata(this.sectionStart, this.index);
        this.sectionStart = this.index;
      }
    }
  }
  shouldContinue() {
    return this.index < this.buffer.length + this.offset && this.running;
  }
  parse() {
    while (this.shouldContinue()) {
      const c = this.buffer.charCodeAt(this.index - this.offset);
      switch (this.state) {
        case State.Text: {
          this.stateText(c);
          break;
        }
        case State.SpecialStartSequence: {
          this.stateSpecialStartSequence(c);
          break;
        }
        case State.InSpecialTag: {
          this.stateInSpecialTag(c);
          break;
        }
        case State.CDATASequence: {
          this.stateCDATASequence(c);
          break;
        }
        case State.InAttributeValueDq: {
          this.stateInAttributeValueDoubleQuotes(c);
          break;
        }
        case State.InAttributeName: {
          this.stateInAttributeName(c);
          break;
        }
        case State.InCommentLike: {
          this.stateInCommentLike(c);
          break;
        }
        case State.InSpecialComment: {
          this.stateInSpecialComment(c);
          break;
        }
        case State.BeforeAttributeName: {
          this.stateBeforeAttributeName(c);
          break;
        }
        case State.InTagName: {
          this.stateInTagName(c);
          break;
        }
        case State.InClosingTagName: {
          this.stateInClosingTagName(c);
          break;
        }
        case State.BeforeTagName: {
          this.stateBeforeTagName(c);
          break;
        }
        case State.AfterAttributeName: {
          this.stateAfterAttributeName(c);
          break;
        }
        case State.InAttributeValueSq: {
          this.stateInAttributeValueSingleQuotes(c);
          break;
        }
        case State.BeforeAttributeValue: {
          this.stateBeforeAttributeValue(c);
          break;
        }
        case State.BeforeClosingTagName: {
          this.stateBeforeClosingTagName(c);
          break;
        }
        case State.AfterClosingTagName: {
          this.stateAfterClosingTagName(c);
          break;
        }
        case State.BeforeSpecialS: {
          this.stateBeforeSpecialS(c);
          break;
        }
        case State.BeforeSpecialT: {
          this.stateBeforeSpecialT(c);
          break;
        }
        case State.InAttributeValueNq: {
          this.stateInAttributeValueNoQuotes(c);
          break;
        }
        case State.InSelfClosingTag: {
          this.stateInSelfClosingTag(c);
          break;
        }
        case State.InDeclaration: {
          this.stateInDeclaration(c);
          break;
        }
        case State.BeforeDeclaration: {
          this.stateBeforeDeclaration(c);
          break;
        }
        case State.BeforeComment: {
          this.stateBeforeComment(c);
          break;
        }
        case State.InProcessingInstruction: {
          this.stateInProcessingInstruction(c);
          break;
        }
        case State.InEntity: {
          this.stateInEntity();
          break;
        }
      }
      this.index++;
    }
    this.cleanup();
  }
  finish() {
    if (this.state === State.InEntity) {
      this.entityDecoder.end();
      this.state = this.baseState;
    }
    this.handleTrailingData();
    this.cbs.onend();
  }
  handleTrailingData() {
    const endIndex = this.buffer.length + this.offset;
    if (this.sectionStart >= endIndex) {
      return;
    }
    if (this.state === State.InCommentLike) {
      if (this.currentSequence === Sequences.CdataEnd) {
        this.cbs.oncdata(this.sectionStart, endIndex, 0);
      } else {
        this.cbs.oncomment(this.sectionStart, endIndex, 0);
      }
    } else if (this.state === State.InTagName || this.state === State.BeforeAttributeName || this.state === State.BeforeAttributeValue || this.state === State.AfterAttributeName || this.state === State.InAttributeName || this.state === State.InAttributeValueSq || this.state === State.InAttributeValueDq || this.state === State.InAttributeValueNq || this.state === State.InClosingTagName) ;
    else {
      this.cbs.ontext(this.sectionStart, endIndex);
    }
  }
  emitCodePoint(cp, consumed) {
    if (this.baseState !== State.Text && this.baseState !== State.InSpecialTag) {
      if (this.sectionStart < this.entityStart) {
        this.cbs.onattribdata(this.sectionStart, this.entityStart);
      }
      this.sectionStart = this.entityStart + consumed;
      this.index = this.sectionStart - 1;
      this.cbs.onattribentity(cp);
    } else {
      if (this.sectionStart < this.entityStart) {
        this.cbs.ontext(this.sectionStart, this.entityStart);
      }
      this.sectionStart = this.entityStart + consumed;
      this.index = this.sectionStart - 1;
      this.cbs.ontextentity(cp, this.sectionStart);
    }
  }
}
const formTags = /* @__PURE__ */ new Set([
  "input",
  "option",
  "optgroup",
  "select",
  "button",
  "datalist",
  "textarea"
]);
const pTag = /* @__PURE__ */ new Set(["p"]);
const tableSectionTags = /* @__PURE__ */ new Set(["thead", "tbody"]);
const ddtTags = /* @__PURE__ */ new Set(["dd", "dt"]);
const rtpTags = /* @__PURE__ */ new Set(["rt", "rp"]);
const openImpliesClose = /* @__PURE__ */ new Map([
  ["tr", /* @__PURE__ */ new Set(["tr", "th", "td"])],
  ["th", /* @__PURE__ */ new Set(["th"])],
  ["td", /* @__PURE__ */ new Set(["thead", "th", "td"])],
  ["body", /* @__PURE__ */ new Set(["head", "link", "script"])],
  ["li", /* @__PURE__ */ new Set(["li"])],
  ["p", pTag],
  ["h1", pTag],
  ["h2", pTag],
  ["h3", pTag],
  ["h4", pTag],
  ["h5", pTag],
  ["h6", pTag],
  ["select", formTags],
  ["input", formTags],
  ["output", formTags],
  ["button", formTags],
  ["datalist", formTags],
  ["textarea", formTags],
  ["option", /* @__PURE__ */ new Set(["option"])],
  ["optgroup", /* @__PURE__ */ new Set(["optgroup", "option"])],
  ["dd", ddtTags],
  ["dt", ddtTags],
  ["address", pTag],
  ["article", pTag],
  ["aside", pTag],
  ["blockquote", pTag],
  ["details", pTag],
  ["div", pTag],
  ["dl", pTag],
  ["fieldset", pTag],
  ["figcaption", pTag],
  ["figure", pTag],
  ["footer", pTag],
  ["form", pTag],
  ["header", pTag],
  ["hr", pTag],
  ["main", pTag],
  ["nav", pTag],
  ["ol", pTag],
  ["pre", pTag],
  ["section", pTag],
  ["table", pTag],
  ["ul", pTag],
  ["rt", rtpTags],
  ["rp", rtpTags],
  ["tbody", tableSectionTags],
  ["tfoot", tableSectionTags]
]);
const voidElements = /* @__PURE__ */ new Set([
  "area",
  "base",
  "basefont",
  "br",
  "col",
  "command",
  "embed",
  "frame",
  "hr",
  "img",
  "input",
  "isindex",
  "keygen",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr"
]);
const foreignContextElements = /* @__PURE__ */ new Set(["math", "svg"]);
const htmlIntegrationElements = /* @__PURE__ */ new Set([
  "mi",
  "mo",
  "mn",
  "ms",
  "mtext",
  "annotation-xml",
  "foreignobject",
  "desc",
  "title"
]);
const reNameEnd = /\s|\//;
class Parser {
  constructor(cbs, options = {}) {
    var _a2, _b, _c, _d, _e, _f;
    this.options = options;
    this.startIndex = 0;
    this.endIndex = 0;
    this.openTagStart = 0;
    this.tagname = "";
    this.attribname = "";
    this.attribvalue = "";
    this.attribs = null;
    this.stack = [];
    this.buffers = [];
    this.bufferOffset = 0;
    this.writeIndex = 0;
    this.ended = false;
    this.cbs = cbs !== null && cbs !== void 0 ? cbs : {};
    this.htmlMode = !this.options.xmlMode;
    this.lowerCaseTagNames = (_a2 = options.lowerCaseTags) !== null && _a2 !== void 0 ? _a2 : this.htmlMode;
    this.lowerCaseAttributeNames = (_b = options.lowerCaseAttributeNames) !== null && _b !== void 0 ? _b : this.htmlMode;
    this.recognizeSelfClosing = (_c = options.recognizeSelfClosing) !== null && _c !== void 0 ? _c : !this.htmlMode;
    this.tokenizer = new ((_d = options.Tokenizer) !== null && _d !== void 0 ? _d : Tokenizer)(this.options, this);
    this.foreignContext = [!this.htmlMode];
    (_f = (_e = this.cbs).onparserinit) === null || _f === void 0 ? void 0 : _f.call(_e, this);
  }
  ontext(start, endIndex) {
    var _a2, _b;
    const data = this.getSlice(start, endIndex);
    this.endIndex = endIndex - 1;
    (_b = (_a2 = this.cbs).ontext) === null || _b === void 0 ? void 0 : _b.call(_a2, data);
    this.startIndex = endIndex;
  }
  ontextentity(cp, endIndex) {
    var _a2, _b;
    this.endIndex = endIndex - 1;
    (_b = (_a2 = this.cbs).ontext) === null || _b === void 0 ? void 0 : _b.call(_a2, fromCodePoint(cp));
    this.startIndex = endIndex;
  }
  isVoidElement(name) {
    return this.htmlMode && voidElements.has(name);
  }
  onopentagname(start, endIndex) {
    this.endIndex = endIndex;
    let name = this.getSlice(start, endIndex);
    if (this.lowerCaseTagNames) {
      name = name.toLowerCase();
    }
    this.emitOpenTag(name);
  }
  emitOpenTag(name) {
    var _a2, _b, _c, _d;
    this.openTagStart = this.startIndex;
    this.tagname = name;
    const impliesClose = this.htmlMode && openImpliesClose.get(name);
    if (impliesClose) {
      while (this.stack.length > 0 && impliesClose.has(this.stack[0])) {
        const element = this.stack.shift();
        (_b = (_a2 = this.cbs).onclosetag) === null || _b === void 0 ? void 0 : _b.call(_a2, element, true);
      }
    }
    if (!this.isVoidElement(name)) {
      this.stack.unshift(name);
      if (this.htmlMode) {
        if (foreignContextElements.has(name)) {
          this.foreignContext.unshift(true);
        } else if (htmlIntegrationElements.has(name)) {
          this.foreignContext.unshift(false);
        }
      }
    }
    (_d = (_c = this.cbs).onopentagname) === null || _d === void 0 ? void 0 : _d.call(_c, name);
    if (this.cbs.onopentag)
      this.attribs = {};
  }
  endOpenTag(isImplied) {
    var _a2, _b;
    this.startIndex = this.openTagStart;
    if (this.attribs) {
      (_b = (_a2 = this.cbs).onopentag) === null || _b === void 0 ? void 0 : _b.call(_a2, this.tagname, this.attribs, isImplied);
      this.attribs = null;
    }
    if (this.cbs.onclosetag && this.isVoidElement(this.tagname)) {
      this.cbs.onclosetag(this.tagname, true);
    }
    this.tagname = "";
  }
  onopentagend(endIndex) {
    this.endIndex = endIndex;
    this.endOpenTag(false);
    this.startIndex = endIndex + 1;
  }
  onclosetag(start, endIndex) {
    var _a2, _b, _c, _d, _e, _f, _g, _h;
    this.endIndex = endIndex;
    let name = this.getSlice(start, endIndex);
    if (this.lowerCaseTagNames) {
      name = name.toLowerCase();
    }
    if (this.htmlMode && (foreignContextElements.has(name) || htmlIntegrationElements.has(name))) {
      this.foreignContext.shift();
    }
    if (!this.isVoidElement(name)) {
      const pos = this.stack.indexOf(name);
      if (pos !== -1) {
        for (let index = 0; index <= pos; index++) {
          const element = this.stack.shift();
          (_b = (_a2 = this.cbs).onclosetag) === null || _b === void 0 ? void 0 : _b.call(_a2, element, index !== pos);
        }
      } else if (this.htmlMode && name === "p") {
        this.emitOpenTag("p");
        this.closeCurrentTag(true);
      }
    } else if (this.htmlMode && name === "br") {
      (_d = (_c = this.cbs).onopentagname) === null || _d === void 0 ? void 0 : _d.call(_c, "br");
      (_f = (_e = this.cbs).onopentag) === null || _f === void 0 ? void 0 : _f.call(_e, "br", {}, true);
      (_h = (_g = this.cbs).onclosetag) === null || _h === void 0 ? void 0 : _h.call(_g, "br", false);
    }
    this.startIndex = endIndex + 1;
  }
  onselfclosingtag(endIndex) {
    this.endIndex = endIndex;
    if (this.recognizeSelfClosing || this.foreignContext[0]) {
      this.closeCurrentTag(false);
      this.startIndex = endIndex + 1;
    } else {
      this.onopentagend(endIndex);
    }
  }
  closeCurrentTag(isOpenImplied) {
    var _a2, _b;
    const name = this.tagname;
    this.endOpenTag(isOpenImplied);
    if (this.stack[0] === name) {
      (_b = (_a2 = this.cbs).onclosetag) === null || _b === void 0 ? void 0 : _b.call(_a2, name, !isOpenImplied);
      this.stack.shift();
    }
  }
  onattribname(start, endIndex) {
    this.startIndex = start;
    const name = this.getSlice(start, endIndex);
    this.attribname = this.lowerCaseAttributeNames ? name.toLowerCase() : name;
  }
  onattribdata(start, endIndex) {
    this.attribvalue += this.getSlice(start, endIndex);
  }
  onattribentity(cp) {
    this.attribvalue += fromCodePoint(cp);
  }
  onattribend(quote, endIndex) {
    var _a2, _b;
    this.endIndex = endIndex;
    (_b = (_a2 = this.cbs).onattribute) === null || _b === void 0 ? void 0 : _b.call(_a2, this.attribname, this.attribvalue, quote === QuoteType.Double ? '"' : quote === QuoteType.Single ? "'" : quote === QuoteType.NoValue ? void 0 : null);
    if (this.attribs && !Object.prototype.hasOwnProperty.call(this.attribs, this.attribname)) {
      this.attribs[this.attribname] = this.attribvalue;
    }
    this.attribvalue = "";
  }
  getInstructionName(value) {
    const index = value.search(reNameEnd);
    let name = index < 0 ? value : value.substr(0, index);
    if (this.lowerCaseTagNames) {
      name = name.toLowerCase();
    }
    return name;
  }
  ondeclaration(start, endIndex) {
    this.endIndex = endIndex;
    const value = this.getSlice(start, endIndex);
    if (this.cbs.onprocessinginstruction) {
      const name = this.getInstructionName(value);
      this.cbs.onprocessinginstruction(`!${name}`, `!${value}`);
    }
    this.startIndex = endIndex + 1;
  }
  onprocessinginstruction(start, endIndex) {
    this.endIndex = endIndex;
    const value = this.getSlice(start, endIndex);
    if (this.cbs.onprocessinginstruction) {
      const name = this.getInstructionName(value);
      this.cbs.onprocessinginstruction(`?${name}`, `?${value}`);
    }
    this.startIndex = endIndex + 1;
  }
  oncomment(start, endIndex, offset) {
    var _a2, _b, _c, _d;
    this.endIndex = endIndex;
    (_b = (_a2 = this.cbs).oncomment) === null || _b === void 0 ? void 0 : _b.call(_a2, this.getSlice(start, endIndex - offset));
    (_d = (_c = this.cbs).oncommentend) === null || _d === void 0 ? void 0 : _d.call(_c);
    this.startIndex = endIndex + 1;
  }
  oncdata(start, endIndex, offset) {
    var _a2, _b, _c, _d, _e, _f, _g, _h, _j, _k;
    this.endIndex = endIndex;
    const value = this.getSlice(start, endIndex - offset);
    if (!this.htmlMode || this.options.recognizeCDATA) {
      (_b = (_a2 = this.cbs).oncdatastart) === null || _b === void 0 ? void 0 : _b.call(_a2);
      (_d = (_c = this.cbs).ontext) === null || _d === void 0 ? void 0 : _d.call(_c, value);
      (_f = (_e = this.cbs).oncdataend) === null || _f === void 0 ? void 0 : _f.call(_e);
    } else {
      (_h = (_g = this.cbs).oncomment) === null || _h === void 0 ? void 0 : _h.call(_g, `[CDATA[${value}]]`);
      (_k = (_j = this.cbs).oncommentend) === null || _k === void 0 ? void 0 : _k.call(_j);
    }
    this.startIndex = endIndex + 1;
  }
  onend() {
    var _a2, _b;
    if (this.cbs.onclosetag) {
      this.endIndex = this.startIndex;
      for (let index = 0; index < this.stack.length; index++) {
        this.cbs.onclosetag(this.stack[index], true);
      }
    }
    (_b = (_a2 = this.cbs).onend) === null || _b === void 0 ? void 0 : _b.call(_a2);
  }
  reset() {
    var _a2, _b, _c, _d;
    (_b = (_a2 = this.cbs).onreset) === null || _b === void 0 ? void 0 : _b.call(_a2);
    this.tokenizer.reset();
    this.tagname = "";
    this.attribname = "";
    this.attribs = null;
    this.stack.length = 0;
    this.startIndex = 0;
    this.endIndex = 0;
    (_d = (_c = this.cbs).onparserinit) === null || _d === void 0 ? void 0 : _d.call(_c, this);
    this.buffers.length = 0;
    this.foreignContext.length = 0;
    this.foreignContext.unshift(!this.htmlMode);
    this.bufferOffset = 0;
    this.writeIndex = 0;
    this.ended = false;
  }
  parseComplete(data) {
    this.reset();
    this.end(data);
  }
  getSlice(start, end) {
    while (start - this.bufferOffset >= this.buffers[0].length) {
      this.shiftBuffer();
    }
    let slice = this.buffers[0].slice(start - this.bufferOffset, end - this.bufferOffset);
    while (end - this.bufferOffset > this.buffers[0].length) {
      this.shiftBuffer();
      slice += this.buffers[0].slice(0, end - this.bufferOffset);
    }
    return slice;
  }
  shiftBuffer() {
    this.bufferOffset += this.buffers[0].length;
    this.writeIndex--;
    this.buffers.shift();
  }
  write(chunk) {
    var _a2, _b;
    if (this.ended) {
      (_b = (_a2 = this.cbs).onerror) === null || _b === void 0 ? void 0 : _b.call(_a2, new Error(".write() after done!"));
      return;
    }
    this.buffers.push(chunk);
    if (this.tokenizer.running) {
      this.tokenizer.write(chunk);
      this.writeIndex++;
    }
  }
  end(chunk) {
    var _a2, _b;
    if (this.ended) {
      (_b = (_a2 = this.cbs).onerror) === null || _b === void 0 ? void 0 : _b.call(_a2, new Error(".end() after done!"));
      return;
    }
    if (chunk)
      this.write(chunk);
    this.ended = true;
    this.tokenizer.end();
  }
  pause() {
    this.tokenizer.pause();
  }
  resume() {
    this.tokenizer.resume();
    while (this.tokenizer.running && this.writeIndex < this.buffers.length) {
      this.tokenizer.write(this.buffers[this.writeIndex++]);
    }
    if (this.ended)
      this.tokenizer.end();
  }
  parseChunk(chunk) {
    this.write(chunk);
  }
  done(chunk) {
    this.end(chunk);
  }
}
const VOID_ELEMENTS = /* @__PURE__ */ new Set([
  "area",
  "base",
  "br",
  "col",
  "embed",
  "hr",
  "img",
  "input",
  "link",
  "meta",
  "param",
  "source",
  "track",
  "wbr",
  "stop",
  "circle",
  "path",
  "rect",
  "line",
  "polyline",
  "polygon",
  "ellipse",
  "use",
  "image",
  "feblend",
  "fecolormatrix",
  "fecomposite",
  "feconvolvematrix",
  "fediffuselighting",
  "fedisplacementmap",
  "fedistantlight",
  "feflood",
  "fefunca",
  "fefuncb",
  "fefuncg",
  "fefuncr",
  "fegaussianblur",
  "feimage",
  "femerge",
  "femergenode",
  "femorphology",
  "feoffset",
  "fepointlight",
  "fespecularlighting",
  "fespotlight",
  "fetile",
  "feturbulence"
]);
function analyzeWithParser(html) {
  const realTags = [];
  const impliedCloseEvents = [];
  const rawRanges = [];
  const commentRanges = [];
  let currentRawTag = null;
  let rawStart = -1;
  const parser = new Parser(
    {
      onopentag(name, _attribs, isImplied = false) {
        if (isImplied) {
          return;
        }
        const tagName = name.toLowerCase();
        realTags.push({ type: "open", tagName, startIndex: parser.startIndex, endIndex: parser.endIndex });
        if (tagName === "script" || tagName === "style") {
          currentRawTag = tagName;
          rawStart = parser.endIndex + 1;
        }
      },
      onclosetag(name, isImplied) {
        const tagName = name.toLowerCase();
        if (isImplied) {
          impliedCloseEvents.push({ name: tagName, afterPos: parser.endIndex });
          return;
        }
        realTags.push({ type: "close", tagName, startIndex: parser.startIndex, endIndex: parser.endIndex });
        if (tagName === "script" || tagName === "style") {
          rawRanges.push({ start: rawStart, end: parser.startIndex, tag: currentRawTag });
          currentRawTag = null;
          rawStart = -1;
        }
      },
      oncomment(_data) {
      }
    },
    { recognizeSelfClosing: true, lowerCaseTags: true, lowerCaseAttributeNames: true }
  );
  parser.write(html);
  parser.end();
  const correctedRawRanges = [];
  for (const r of rawRanges) {
    const closeRe = new RegExp(`</${r.tag}\\s*>`, "gi");
    closeRe.lastIndex = r.start;
    let lastMatch = null;
    for (let m = closeRe.exec(html); m !== null; m = closeRe.exec(html)) {
      if (m.index >= r.end) {
        lastMatch = m;
      }
    }
    if (lastMatch) {
      correctedRawRanges.push({ start: r.start, end: lastMatch.index + lastMatch[0].length, tag: r.tag });
    } else {
      correctedRawRanges.push(r);
    }
  }
  const commentRe = /<!--[\s\S]*?-->/g;
  for (let cm = commentRe.exec(html); cm !== null; cm = commentRe.exec(html)) {
    commentRanges.push({ start: cm.index, end: cm.index + cm[0].length });
  }
  return { realTags, impliedCloseEvents, rawRanges: correctedRawRanges, commentRanges };
}
function getLineNumber(html, index) {
  return html.substring(0, index).split("\n").length;
}
function analyzeAndFix(html) {
  const fixes = [];
  const { realTags, rawRanges, commentRanges } = analyzeWithParser(html);
  const attrRanges = [];
  const tagStartRe = /<([a-zA-Z][a-zA-Z0-9-]*)\s/g;
  for (let tsMatch = tagStartRe.exec(html); tsMatch !== null; tsMatch = tagStartRe.exec(html)) {
    let pos = tsMatch.index + tsMatch[0].length;
    let inQuote = null;
    let tagEnd = -1;
    while (pos < html.length) {
      const ch = html[pos];
      if (inQuote) {
        if (ch === inQuote) {
          inQuote = null;
        }
      } else {
        if (ch === '"' || ch === "'") {
          inQuote = ch;
        } else if (ch === ">") {
          tagEnd = pos;
          break;
        }
      }
      pos++;
    }
    if (tagEnd === -1) {
      continue;
    }
    const tagFull = html.substring(tsMatch.index, tagEnd + 1);
    const tagStart = tsMatch.index;
    let qPos = 0;
    while (qPos < tagFull.length) {
      const qi = tagFull.substring(qPos).search(/["']/);
      if (qi === -1) {
        break;
      }
      const qChar = tagFull[qPos + qi];
      const qStart = qPos + qi;
      const qEnd = tagFull.indexOf(qChar, qStart + 1);
      if (qEnd === -1) {
        break;
      }
      attrRanges.push({ start: tagStart + qStart, end: tagStart + qEnd + 1 });
      qPos = qEnd + 1;
    }
  }
  const cdataRanges = [];
  const cdataRe = /<!\[CDATA\[[\s\S]*?\]\]>/g;
  for (let cdataMatch = cdataRe.exec(html); cdataMatch !== null; cdataMatch = cdataRe.exec(html)) {
    cdataRanges.push({ start: cdataMatch.index, end: cdataMatch.index + cdataMatch[0].length });
  }
  function isInSkippedRange(index) {
    for (const r of rawRanges) {
      if (index >= r.start && index < r.end) {
        return true;
      }
    }
    for (const r of commentRanges) {
      if (index >= r.start && index < r.end) {
        return true;
      }
    }
    for (const r of attrRanges) {
      if (index >= r.start && index < r.end) {
        return true;
      }
    }
    for (const r of cdataRanges) {
      if (index >= r.start && index < r.end) {
        return true;
      }
    }
    return false;
  }
  const tagStack = [];
  for (const tag of realTags) {
    if (tag.type === "open") {
      if (VOID_ELEMENTS.has(tag.tagName)) {
        continue;
      }
      tagStack.push({ tagName: tag.tagName, startIndex: tag.startIndex, endIndex: tag.endIndex });
    } else if (tag.type === "close") {
      if (tagStack.length === 0) {
        fixes.push({
          type: 4,
          description: `多余闭标签 </${tag.tagName}>`,
          line: getLineNumber(html, tag.startIndex),
          start: tag.startIndex,
          end: tag.endIndex + 1,
          replacement: ""
        });
      } else if (tagStack[tagStack.length - 1].tagName === tag.tagName) {
        tagStack.pop();
      } else {
        const sameNameIdx = tagStack.findIndex((t) => t.tagName === tag.tagName);
        if (sameNameIdx === -1) {
          fixes.push({
            type: 2,
            description: `孤立闭标签 </${tag.tagName}>（无对应开标签）`,
            line: getLineNumber(html, tag.startIndex),
            start: tag.startIndex,
            end: tag.endIndex + 1,
            replacement: ""
          });
        } else {
          const tagsToClose = tagStack.slice(sameNameIdx + 1);
          for (const t of tagsToClose) {
            fixes.push({
              type: 1,
              description: `补闭合标签 </${t.tagName}>（第 ${getLineNumber(html, t.startIndex)} 行 <${t.tagName}> 未闭合，因 </${tag.tagName}> 闭合而暴露）`,
              line: getLineNumber(html, tag.startIndex),
              start: tag.startIndex,
              end: tag.startIndex,
              replacement: `</${t.tagName}>`
            });
          }
          tagStack.splice(sameNameIdx);
        }
      }
    }
  }
  if (tagStack.length > 0) {
    const bodyCloseMatch = html.match(/<\/body>/i);
    const insertPos = bodyCloseMatch?.index ?? html.length;
    const closingTags = tagStack.slice().reverse().map((t) => `</${t.tagName}>`).join("");
    const unclosedList = tagStack.slice().reverse().map((t) => `<${t.tagName}>（第 ${getLineNumber(html, t.startIndex)} 行）`).join(", ");
    fixes.push({
      type: 1,
      description: `补闭合标签 ${closingTags}（${unclosedList} 未闭合）`,
      line: getLineNumber(html, insertPos),
      start: insertPos,
      end: insertPos,
      replacement: closingTags
    });
  }
  const detectedClosePositions = new Set(realTags.filter((t) => t.type === "close").map((t) => t.startIndex));
  const TAG_RE = /<\/([a-zA-Z][a-zA-Z0-9-]*)\s*>/g;
  for (let m = TAG_RE.exec(html); m !== null; m = TAG_RE.exec(html)) {
    if (detectedClosePositions.has(m.index)) {
      continue;
    }
    if (isInSkippedRange(m.index)) {
      continue;
    }
    const tagName = m[1].toLowerCase();
    if (VOID_ELEMENTS.has(tagName)) {
      continue;
    }
    fixes.push({
      type: 2,
      description: `孤立闭标签 </${tagName}>（无对应开标签，被解析器忽略）`,
      line: getLineNumber(html, m.index),
      start: m.index,
      end: m.index + m[0].length,
      replacement: ""
    });
  }
  const RAW_TAG_PAIRS = { script: "style", style: "script" };
  const rawOpenClosePairs = [];
  const rawOpenStack = [];
  for (const tag of realTags) {
    if (tag.tagName !== "script" && tag.tagName !== "style") {
      continue;
    }
    if (tag.type === "open") {
      rawOpenStack.push(tag);
    } else if (tag.type === "close") {
      for (let i = rawOpenStack.length - 1; i >= 0; i--) {
        if (rawOpenStack[i].tagName === tag.tagName) {
          rawOpenClosePairs.push({
            tag: tag.tagName,
            openEnd: rawOpenStack[i].endIndex + 1,
            closeStart: tag.startIndex
          });
          rawOpenStack.splice(i, 1);
          break;
        }
      }
    }
  }
  for (const pair of rawOpenClosePairs) {
    const wrongClose = RAW_TAG_PAIRS[pair.tag];
    if (!wrongClose) {
      continue;
    }
    const content = html.substring(pair.openEnd, pair.closeStart);
    const wrongRe = new RegExp(`<\\/${wrongClose}\\s*>`, "gi");
    let wm = wrongRe.exec(content);
    while (wm !== null) {
      const absPos = pair.openEnd + wm.index;
      fixes.push({
        type: 3,
        description: `闭标签名错误 </${wrongClose}> → </${pair.tag}>（<${pair.tag}> 内容中出现错误的 </${wrongClose}>）`,
        line: getLineNumber(html, absPos),
        start: absPos,
        end: absPos + wm[0].length,
        replacement: `</${pair.tag}>`
      });
      wm = wrongRe.exec(content);
    }
  }
  return deduplicateFixes(fixes);
}
function deduplicateFixes(fixes, _html) {
  const STRUCTURAL_TAGS = /* @__PURE__ */ new Set(["body", "html", "head"]);
  const type1Fixes = fixes.filter((f) => f.type === 1);
  const type24Fixes = fixes.filter((f) => f.type === 2 || f.type === 4);
  const otherFixes = fixes.filter((f) => f.type !== 1 && f.type !== 2 && f.type !== 4);
  const preservedByType1 = /* @__PURE__ */ new Set();
  for (const fix of type1Fixes) {
    const tagMatches = fix.replacement.match(/<\/?(\w+)>/g);
    if (tagMatches) {
      for (const m of tagMatches) {
        const tagName = m.match(/<\/?(\w+)>/)?.[1]?.toLowerCase();
        if (tagName) {
          preservedByType1.add(tagName);
        }
      }
    }
  }
  const mergedType1 = [];
  const consumedType24 = /* @__PURE__ */ new Set();
  for (const t1 of type1Fixes) {
    let mergedEnd = t1.end;
    const replTags = /* @__PURE__ */ new Set();
    const replTagMatches = t1.replacement.match(/<\/(\w+)>/g);
    if (replTagMatches) {
      for (const m of replTagMatches) {
        const tagName = m.match(/<\/(\w+)>/)?.[1]?.toLowerCase();
        if (tagName) {
          replTags.add(tagName);
        }
      }
    }
    let changed = true;
    while (changed) {
      changed = false;
      for (let i = 0; i < type24Fixes.length; i++) {
        if (consumedType24.has(i)) {
          continue;
        }
        const t24 = type24Fixes[i];
        const tagNameMatch = (t24.description || "").match(/<\/(\w+)>/);
        const tagName = tagNameMatch ? tagNameMatch[1].toLowerCase() : null;
        if (tagName && replTags.has(tagName) && (t24.start === t1.start || t24.start === mergedEnd)) {
          mergedEnd = Math.max(mergedEnd, t24.end);
          consumedType24.add(i);
          changed = true;
        }
      }
    }
    mergedType1.push({ ...t1, end: mergedEnd });
  }
  const remainingType24 = type24Fixes.filter((t24, idx) => {
    if (consumedType24.has(idx)) {
      return false;
    }
    const tagNameMatch = (t24.description || "").match(/<\/(\w+)>/);
    const tagName = tagNameMatch ? tagNameMatch[1].toLowerCase() : null;
    if (tagName && STRUCTURAL_TAGS.has(tagName) && !preservedByType1.has(tagName)) {
      return false;
    }
    return true;
  });
  return [...mergedType1, ...remainingType24, ...otherFixes];
}
function applyFixes(html, fixes) {
  const sorted = [...fixes].sort((a, b) => {
    if (b.start !== a.start) {
      return b.start - a.start;
    }
    return a.end - b.end;
  });
  let result = html;
  for (const fix of sorted) {
    result = result.substring(0, fix.start) + fix.replacement + result.substring(fix.end);
  }
  return result;
}
function buildTempHtmlPath(sourcePath) {
  return join(
    dirname(resolve(sourcePath)),
    `__render_${process.pid}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}.html`
  );
}
async function createRenderRuntime(input) {
  const htmlDir = resolveHtmlDirFromInput(input);
  const renderServer = await startRenderServer(htmlDir);
  return buildRenderRuntime(renderServer);
}
function buildRenderRuntime(renderServer) {
  return {
    htmlDir: renderServer.htmlDir,
    origin: renderServer.origin,
    buildPageUrl(filePath) {
      return buildRenderPageUrl(renderServer.origin, renderServer.htmlDir, filePath);
    },
    async prepareHtml(html, sourcePath) {
      const filePath = buildTempHtmlPath(sourcePath);
      const localizedHtml = rewriteHtmlCdnUrlsToLocalAssets(html, renderServer.origin);
      await writeFile(filePath, localizedHtml, "utf-8");
      return {
        filePath,
        pageUrl: buildRenderPageUrl(renderServer.origin, renderServer.htmlDir, filePath),
        cleanup: async () => {
          await rm(filePath, { force: true });
        }
      };
    },
    close: renderServer.close
  };
}
let chromiumModulePromise = null;
class PlaywrightRenderer {
  constructor(options) {
    this.browser = null;
    this.page = null;
    this.options = options ?? {};
  }
  static async create(options) {
    const instance = new PlaywrightRenderer(options);
    await instance.init();
    return instance;
  }
  async init() {
    const executablePath = await ensureChromium();
    if (!chromiumModulePromise) {
      chromiumModulePromise = import("playwright").then((m) => m.chromium);
    }
    const chromium = await chromiumModulePromise;
    this.browser = await chromium.launch({
      executablePath,
      args: ["--no-sandbox", "--disable-setuid-sandbox"]
    });
    this.page = await this.browser.newPage();
    await this.page.setViewportSize({
      width: this.options.width ?? 1280,
      height: this.options.height ?? 720
    });
  }
  async load(html, options) {
    if (!this.page) {
      throw new Error("PlaywrightRenderer not initialized");
    }
    const { writeFile: writeFile2, unlink } = await import("node:fs/promises");
    const { join: join2 } = await import("node:path");
    const { tmpdir } = await import("node:os");
    const sourcePath = options?.baseUrl ?? this.options.sourcePath;
    if (this.options.renderRuntime && sourcePath) {
      const prepared = await this.options.renderRuntime.prepareHtml(html, sourcePath);
      try {
        await this.page.goto(prepared.pageUrl, {
          waitUntil: options?.waitUntil ?? "load",
          timeout: options?.timeout ?? 12e4
        });
        await this.page.waitForTimeout(500);
      } finally {
        await prepared.cleanup().catch(() => {
        });
      }
      return;
    }
    const tmpPath = join2(tmpdir(), `pptx-craft-${Date.now()}.html`);
    try {
      await writeFile2(tmpPath, html, "utf-8");
      await this.page.goto(`file://${tmpPath}`, {
        waitUntil: options?.waitUntil ?? "load",
        timeout: options?.timeout ?? 12e4
      });
      await this.page.waitForTimeout(500);
    } finally {
      try {
        await unlink(tmpPath);
      } catch {
      }
    }
  }
  async evaluate(code, args) {
    if (!this.page) {
      throw new Error("PlaywrightRenderer not initialized");
    }
    const argsJson = args === void 0 ? "undefined" : JSON.stringify(args);
    const iife = `(${code})(document, window, ${argsJson})`;
    return await this.page.evaluate(iife);
  }
  async evaluateAsync(fn) {
    if (!this.page) {
      throw new Error("PlaywrightRenderer not initialized");
    }
    const fnStr = fn.toString();
    const iife = `(async () => { return (${fnStr})(document, window); })()`;
    return this.page.evaluate(iife);
  }
  async getContent() {
    if (!this.page) {
      throw new Error("PlaywrightRenderer not initialized");
    }
    return this.page.content();
  }
  async close() {
    if (this.page) {
      await this.page.close().catch((err) => {
        console.error("[PlaywrightRenderer] 关闭页面失败:", err);
      });
      this.page = null;
    }
    if (this.browser) {
      await this.browser.close().catch((err) => {
        console.error("[PlaywrightRenderer] 关闭浏览器失败:", err);
      });
      this.browser = null;
    }
  }
}
function backupHtmlFiles(dir) {
  const timestamp = (/* @__PURE__ */ new Date()).toISOString().replace(/[-:T]/g, "").replace(/\.\d{3}Z$/, "").slice(0, 14);
  const backupDir = join(dir, "_backup", timestamp);
  mkdirSync(backupDir, { recursive: true });
  const htmlFiles = readdirSync(dir).filter((f) => /^page-.*\.pptx\.html$/.test(f));
  if (htmlFiles.length === 0) {
    log("  无 HTML 文件需要备份");
    return backupDir;
  }
  for (const file of htmlFiles) {
    const src = join(dir, file);
    const dest = join(backupDir, file);
    copyFileSync(src, dest);
  }
  log(`  已备份 ${htmlFiles.length} 个 HTML 文件到 _backup/${timestamp}/`);
  return backupDir;
}
async function pptxFix(opts) {
  await runFix(opts.pagesDir, opts.options?.fix ?? false, opts.options?.debug ?? false);
}
async function runFix(targetDir, fixMode, debug) {
  const singleModeFlag = process.argv.find(
    (a) => ["--tags", "--fonts", "--layout", "--charts", "--deps", "--overflow", "--whitespace"].includes(a)
  );
  const singleMode = singleModeFlag ? singleModeFlag.replace("--", "") : void 0;
  const operations = singleMode ? [singleMode] : ALL_OPERATIONS;
  log("🔍 PPT HTML 校验/修复");
  log(`📁 目标目录: ${targetDir}`);
  if (debug) {
    log("🐛 调试模式已启用");
  }
  log(`${"=".repeat(50)}
`);
  const tStart = debug ? Date.now() : 0;
  if (fixMode) {
    backupHtmlFiles(targetDir);
  }
  const htmlFiles = readdirSync(targetDir).filter((f) => /^page-.*\.pptx\.html$/.test(f));
  if (htmlFiles.length === 0) {
    warn("未找到匹配的 HTML 文件（需要 page-*.pptx.html 格式）");
    return;
  }
  let totalFixed = 0;
  let totalIssues = 0;
  const renderRuntime = operations.some((op) => op === "overflow" || op === "whitespace") ? await createRenderRuntime(targetDir) : null;
  const rendererRef = { current: null };
  const getRenderer = async (sourcePath) => {
    if (!rendererRef.current) {
      const t0 = Date.now();
      rendererRef.current = await PlaywrightRenderer.create({ renderRuntime: renderRuntime ?? void 0, sourcePath });
      if (debug) {
        log(`  ⏱️ [renderer] 初始化(单实例复用): ${ms(Date.now() - t0)}`);
      }
    }
    return rendererRef.current;
  };
  try {
    for (const file of htmlFiles) {
      const filePath = join(targetDir, file);
      const html = readFileSync(filePath, "utf-8");
      log(`
▶ 处理: ${file}`);
      const executors = createExecutors(debug, () => getRenderer(filePath));
      try {
        const dryRun = !fixMode;
        const dbg = debug ? (msg) => log(msg) : void 0;
        const result = await fixAll(executors, html, { operations, dryRun, debug: dbg });
        for (const op of result.report.operations) {
          if (op.details && op.details.length > 0) {
            for (const detail of op.details) {
              log(`  [${op.operation}] ${detail}`);
            }
          }
        }
        log(
          `  操作: ${result.report.operations.map((o) => `${o.operation}(${o.issueCount}问题/${o.fixedCount}修复)`).join(", ")}`
        );
        log(`  总计: ${result.report.totalIssues} 问题 / ${result.report.totalFixed} 修复`);
        if (!dryRun && result.html !== html) {
          writeFileSync(filePath, result.html, "utf-8");
          log(`  ✅ 已保存修复后的文件`);
        }
        totalIssues += result.report.totalIssues;
        totalFixed += result.report.totalFixed;
      } catch (err) {
        warn(`❌ ${file} 处理失败: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
  } finally {
    await rendererRef.current?.close();
    await renderRuntime?.close();
  }
  log(`
${"=".repeat(50)}`);
  log(`📊 总计: ${totalIssues} 问题 / ${totalFixed} 修复`);
  if (totalIssues === 0) {
    log("✨ 所有检查通过！");
  } else if (!fixMode) {
    log("💡 提示：使用 --fix 参数自动修复检测到的问题");
  }
  if (debug && tStart) {
    log(`⏱️ 总耗时: ${ms(Date.now() - tStart)}`);
  }
}
function createExecutors(debug, getRenderer) {
  const executors = {
    tags: async (html, opts) => {
      const t0 = Date.now();
      const fixes = analyzeAndFix(html);
      if (debug) {
        log(`  ⏱️ [tags] 分析: ${ms(Date.now() - t0)}`);
      }
      const t1 = Date.now();
      const deduped = deduplicateFixes(fixes);
      if (debug) {
        log(`  ⏱️ [tags] 去重: ${ms(Date.now() - t1)}`);
      }
      const fixedHtml = opts.dryRun ? html : applyFixes(html, deduped);
      if (debug && !opts.dryRun) {
        log(`  ⏱️ [tags] 应用修复: ${ms(Date.now() - t0 - (Date.now() - t1))}`);
      }
      const details = fixes.length > 0 ? fixes.map((f) => f.description) : [];
      if (debug) {
        log(`  ⏱️ [tags] 总计: ${ms(Date.now() - t0)}`);
      }
      return {
        html: fixedHtml,
        report: {
          fixedCount: opts.dryRun ? 0 : deduped.length,
          issueCount: fixes.length,
          details
        }
      };
    },
    fonts: async (html, opts) => {
      const t0 = Date.now();
      const fixes = analyzeFonts(html);
      const fixedHtml = opts.dryRun ? html : applyFontFixes(html, fixes);
      const details = fixes.map((fix) => fix.description);
      if (debug) {
        log(`  ⏱️ [fonts] ${opts.dryRun ? "检测" : "修复"}: ${ms(Date.now() - t0)}`);
      }
      return {
        html: fixedHtml,
        report: {
          fixedCount: opts.dryRun ? 0 : fixes.length,
          issueCount: fixes.length,
          details
        }
      };
    },
    layout: async (html, opts) => {
      const t0 = Date.now();
      const tags = rebuildTagTree(html);
      if (debug) {
        log(`  ⏱️ [layout] 重建标签树: ${ms(Date.now() - t0)}`);
      }
      const t1 = Date.now();
      const issues = runAllChecks(tags, html);
      if (debug) {
        log(`  ⏱️ [layout] 检查: ${ms(Date.now() - t1)}`);
      }
      const fixable = issues.filter((i) => i.fixable);
      let fixedHtml = html;
      if (!opts.dryRun && fixable.length > 0) {
        const t2 = Date.now();
        const result = applyFixes$1(html, fixable);
        fixedHtml = result.html;
        if (debug) {
          log(`  ⏱️ [layout] 应用修复: ${ms(Date.now() - t2)}`);
        }
      }
      const details = issues.length > 0 ? issues.map((i) => {
        return `${i.fixable ? "[可修复]" : "[需人工]"} ${i.message}`;
      }) : [];
      if (debug) {
        log(`  ⏱️ [layout] 总计: ${ms(Date.now() - t0)}`);
      }
      return {
        html: fixedHtml,
        report: {
          fixedCount: opts.dryRun ? 0 : fixable.length,
          issueCount: issues.length,
          details
        }
      };
    },
    deps: async (html, opts) => {
      const t0 = Date.now();
      const result = fixHtmlDeps(html);
      const details = debug && result.detected.length > 0 ? result.detected.map((d) => `缺少依赖: ${d}`) : [];
      if (debug) {
        log(`  ⏱️ [deps] 检测: ${ms(Date.now() - t0)}`);
      }
      return {
        html: opts.dryRun ? html : result.html,
        report: {
          fixedCount: opts.dryRun ? 0 : result.injected.length,
          issueCount: result.detected.length,
          details
        }
      };
    },
    charts: async (html, opts) => {
      const t0 = Date.now();
      const result = fixChartLayout(html, { dryRun: opts.dryRun });
      if (debug) {
        log(`  ⏱️ [charts] ${opts.dryRun ? "检测" : "修复"}: ${ms(Date.now() - t0)}`);
      }
      const details = result.fixedCount > 0 ? [`${result.fixedCount} 个 ECharts 实例缺少 renderer: 'svg'`] : [];
      return {
        html: result.html,
        report: {
          fixedCount: opts.dryRun ? 0 : result.fixedCount,
          issueCount: result.fixedCount,
          details
        }
      };
    },
    overflow: async (html, opts) => {
      const t0 = Date.now();
      if (opts.dryRun) {
        const t12 = Date.now();
        const results2 = await detectOverflow(await getRenderer(), html, { debug: opts.debug });
        if (debug) {
          log(`  ⏱️ [overflow] 检测: ${ms(Date.now() - t12)}`);
        }
        const details2 = results2.map(
          (res) => `${res.tagName ?? "unknown"}: overflow ${res.overflow}px (${res.ratio}%) — ${res.domPath ?? ""}`
        );
        if (debug) {
          log(`  ⏱️ [overflow] 总计: ${ms(Date.now() - t0)}`);
        }
        return {
          html,
          report: { fixedCount: 0, issueCount: results2.length, details: details2 }
        };
      }
      const t1 = Date.now();
      const fixResult = await fixOverflow(await getRenderer(), html, { debug: opts.debug });
      if (debug) {
        log(`  ⏱️ [overflow] 修复: ${ms(Date.now() - t1)}`);
      }
      const t2 = Date.now();
      const results = await detectOverflow(await getRenderer(), fixResult.html, { debug: opts.debug, skipLoad: true });
      if (debug) {
        log(`  ⏱️ [overflow] 复验: ${ms(Date.now() - t2)}`);
      }
      const details = results.map(
        (res) => `${res.tagName ?? "unknown"}: overflow ${res.overflow}px (${res.ratio}%) — ${res.domPath ?? ""}`
      );
      if (debug) {
        log(`  ⏱️ [overflow] 总计: ${ms(Date.now() - t0)}`);
      }
      return {
        html: fixResult.html,
        report: { fixedCount: fixResult.fixedCount, issueCount: fixResult.issueCount, details }
      };
    },
    whitespace: async (html, opts) => {
      const t0 = Date.now();
      if (opts.dryRun) {
        const t12 = Date.now();
        const results2 = await detectWhitespace(await getRenderer(), html, { debug: opts.debug });
        if (debug) {
          log(`  ⏱️ [whitespace] 检测: ${ms(Date.now() - t12)}`);
        }
        const details2 = results2.map(
          (res) => `空白率 ${res.whitespaceRatio}% (${res.whitespace}px) — ${res.domPath ?? ""}`
        );
        if (debug) {
          log(`  ⏱️ [whitespace] 总计: ${ms(Date.now() - t0)}`);
        }
        return {
          html,
          report: { fixedCount: 0, issueCount: results2.length, details: details2 }
        };
      }
      const t1 = Date.now();
      const fixResult = await fixWhitespace(await getRenderer(), html, { debug: opts.debug });
      if (debug) {
        log(`  ⏱️ [whitespace] 修复: ${ms(Date.now() - t1)}`);
      }
      const t2 = Date.now();
      const results = await detectWhitespace(await getRenderer(), fixResult.html, {
        debug: opts.debug,
        skipLoad: true
      });
      if (debug) {
        log(`  ⏱️ [whitespace] 复验: ${ms(Date.now() - t2)}`);
      }
      const details = results.map(
        (res) => `空白率 ${res.whitespaceRatio}% (${res.whitespace}px) — ${res.domPath ?? ""}`
      );
      if (debug) {
        log(`  ⏱️ [whitespace] 总计: ${ms(Date.now() - t0)}`);
      }
      return {
        html: fixResult.html,
        report: { fixedCount: fixResult.fixedCount, issueCount: fixResult.issueCount, details }
      };
    }
  };
  return executors;
}
const isDirectCliRun = process.argv[1]?.endsWith("pptx-fix");
if (isDirectCliRun) {
  const args = process.argv.slice(2);
  const fixMode = args.includes("--fix");
  const debug = args.includes("--debug");
  const targetDir = args.find((a) => !a.startsWith("--"));
  if (!targetDir) {
    error("用法: node pptx-fix.ts <目录> [--fix|--tags|--layout|--charts|--deps|--overflow|--whitespace]");
    process.exit(1);
  }
  runFix(targetDir, fixMode, debug).catch((err) => {
    error(`执行失败: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  });
}
export {
  pptxFix
};
