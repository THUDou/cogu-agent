import fs from "node:fs";
import path from "node:path";
const STRUCTURAL_TYPES = /* @__PURE__ */ new Set(["cover", "intro", "agenda", "section", "chapter", "ending", "conclusion"]);
function realResolve(p) {
  const resolved = path.resolve(p);
  let prefix = resolved;
  const tail = [];
  while (prefix !== path.dirname(prefix)) {
    try {
      const real = fs.realpathSync(prefix);
      return tail.length > 0 ? path.join(real, ...tail.reverse()) : real;
    } catch {
      tail.push(path.basename(prefix));
      prefix = path.dirname(prefix);
    }
  }
  return resolved;
}
function readText(filePath) {
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch (err) {
    if (err?.code === "ENOENT") {
      throw new Error(`Missing file: ${filePath}`);
    }
    throw err;
  }
}
function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function extractField(block, name) {
  const match = block.match(new RegExp(`^-\\s*\\*\\*${escapeRegExp(name)}\\*\\*[:：]\\s*(.+?)\\s*$`, "m"));
  return match ? match[1].trim() : null;
}
function parsePages(outline) {
  const matches = [...outline.matchAll(/^###\s*P(\d+)\s*[:：]\s*(.+?)\s*$/gm)];
  const pages = [];
  for (let index = 0; index < matches.length; index++) {
    const match = matches[index];
    const number = Number.parseInt(match[1], 10);
    const heading = match[2].trim();
    const start = (match.index ?? 0) + match[0].length;
    const end = index + 1 < matches.length ? matches[index + 1].index ?? outline.length : outline.length;
    const block = outline.slice(start, end);
    const pageType = (extractField(block, "类型") || "unknown").trim().toLowerCase();
    const title = extractField(block, "标题") || heading;
    const needs = extractField(block, "研究需求") || "";
    let isContent;
    if (needs.includes("✅")) {
      isContent = true;
    } else if (needs.includes("❌")) {
      isContent = false;
    } else {
      isContent = !STRUCTURAL_TYPES.has(pageType);
    }
    pages.push({ page: number, title, type: pageType, isContent });
  }
  return pages;
}
function buildCommon(skillRoot, style, outlinePath) {
  const designer = path.join(skillRoot, "pptx-craft", "designer", "SKILL.md");
  const styleLine = style ? style : "（无风格文件：自行根据主题设计配色和字体，不询问用户）";
  return `## 通用规范（所有页必读）

### 禁止与用户交互
- 所有设计规范、视觉风格、内容素材的路径均已由主控提供，直接读取执行。
- 不得向用户提问、确认风格选择、请求补充设计参数。
- 若风格文件路径为空，自行根据主题设计配色和字体，不询问用户。

### 环境准备（必读）
- 设计规范：${designer}
- 视觉风格：${styleLine}
- 大纲：${outlinePath}

### 约束要求
- **配色/字体唯一权威 = 视觉风格文件**：designer/SKILL.md 及其附录 charts.md 中的任何示例配色（配色表、\`tailwind.config\` 示例、ECharts \`color\`/\`borderRadius\` 等）仅示意代码结构，**严禁照抄其 hex 值**；指定了视觉风格文件时，配色/字体/圆角/阴影一律以风格文件为准，与本文档示例冲突时以风格文件为准。
- 严格遵循视觉风格文件中的配色方案、字体和组件样式。
- 禁止使用文件中未定义的颜色或字体。
- 图表候选页必须遵循图表附录 charts.md 中的图表规范与 JavaScript 安全编码规范；结构性页面无需读取本附录。
- **容器与防溢出（强制）**：必须使用标准 \`<div class="ppt-slide flex flex-col" type="...">\` 容器，并在 \`<head>\` 内完整包含 designer/SKILL.md「防溢出硬性约束 → 全局 CSS 约束」整段。禁止自创简化容器（如裸 \`style="height:720px"\` / \`.slide-container\`），否则全局防溢出失效、内容溢出。
`;
}
function buildPage(p, outputDir, pagesDir, chartsPath) {
  const n = p.page;
  const out = path.join(pagesDir, `page-${n}.pptx.html`);
  let material;
  let chartsNote;
  let task;
  if (p.isContent) {
    const research = path.join(outputDir, `research-P${n}.md`);
    material = `${path.join(outputDir, "outline.md")} + ${research}`;
    chartsNote = `需要（内容页默认按图表候选页处理，必读图表附录：${chartsPath}）`;
    task = `仅生成该页面，确保内容完整提取自本页研究素材 research-P${n}.md。`;
  } else {
    material = `${path.join(outputDir, "outline.md")}（结构性页面仅依据大纲生成，无 research 文件）`;
    chartsNote = "不需要（结构页不含数据图表）";
    task = "该页为结构性页面，内容仅从 outline.md 提取（标题、概要），不依赖研究素材。";
  }
  return `### P${n}  [${p.isContent ? "内容页" : "结构页"} / ${p.type}]
- 输出文件（最高优先级，禁止违反）：${out}
- 内容素材：${material}
- 图表附录：${chartsNote}
- 任务：你负责生成第 ${n} 页的 HTML 幻灯片。${task}
`;
}
function generateCharlieTasks(opts) {
  const outlinePath = realResolve(opts.outline);
  const outputDir = realResolve(opts.outputDir);
  const skillRoot = realResolve(opts.skillRoot);
  const pagesDir = path.join(outputDir, "pages");
  const outputPath = realResolve(opts.output || path.join(outputDir, "charlie_tasks.md"));
  const pages = parsePages(readText(outlinePath));
  if (pages.length === 0) {
    throw new Error(`No pages found in outline: ${outlinePath}`);
  }
  const chartsPath = path.join(skillRoot, "pptx-craft", "designer", "charts.md");
  const parts = [
    "# Charlie 生成任务清单",
    "",
    "> 每个 Charlie subagent：先读「通用规范」全部，再找到自己负责的 `### P{N}` 段，按其执行、输出到该段指定路径。",
    "",
    buildCommon(skillRoot, opts.style || "", outlinePath),
    "## 逐页任务",
    ""
  ];
  for (const p of [...pages].sort((a, b) => a.page - b.page)) {
    parts.push(buildPage(p, outputDir, pagesDir, chartsPath));
  }
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, parts.join("\n"), "utf-8");
  const contentPages = pages.filter((p) => p.isContent).length;
  console.log(
    `Wrote ${outputPath} (${pages.length} pages: ${contentPages} content / ${pages.length - contentPages} structural)`
  );
}
export {
  generateCharlieTasks
};
