# 故障排查

## 按症状索引

### 创建文档问题

| 症状 | 可能原因 | 修复方式 |
|------|---------|---------|
| 生成后 Word 无法打开 | docx-js 参数错误导致 XML 无效 | 检查 14 条规则，特别是表格双宽度和 ShadingType |
| 表格显示异常 | 缺少 `width` 或 `columnWidths` | 同时设置 Table width 和 columnWidths |
| 表格背景全黑 | 使用了 `ShadingType.SOLID` | 改为 `ShadingType.CLEAR` |
| 列表无编号/符号 | 使用了 Unicode 字符 | 使用 `LevelFormat.BULLET` / `LevelFormat.DECIMAL` |
| 图片不显示 | 缺少 `type` 参数 | 添加 `type: "png"` 等 |
| 目录为空 | 标题未使用 `HeadingLevel` | 标题段落必须用 `heading: HeadingLevel.HEADING_N` |
| 导航栏无标题 | 缺少 `outlineLevel` | 标题样式中添加 `outlineLevel: N` |
| 页面尺寸不对 | 未显式设置页面尺寸 | 始终设置 `page.size.width/height` |
| CJK 字符显示为方块 | 未设置 `eastAsia` 字体 | 在 RunFonts 中设置 `eastAsia` |
| 字号不对 | 忘记 × 2 | docx-js 中 `size` = pt × 2 |
| 分页无效 | 使用了 `\n` | 使用 `PageBreak` 对象 |

### 编辑文档问题

| 症状 | 可能原因 | 修复方式 |
|------|---------|---------|
| 打包后 Word 报错 | XML 元素顺序错误 | 检查元素顺序规则（pPr/rPr/tblPr/tcPr/sectPr） |
| 修改后格式丢失 | 未保留 `<w:rPr>` | 复制原始 Run 的 rPr 到修改后的元素 |
| 修订标记异常 | `<w:del>` 内用了 `<w:t>` | 改为 `<w:delText>` |
| 批注不显示 | 标记位置错误 | `commentRangeStart/End` 是 `w:r` 的兄弟，不能在内部 |
| 修订验证失败 | 未正确添加修订标记 | 确保所有文本变更都有对应的 ins/del |
| 空白丢失 | `<w:t>` 缺少 `xml:space="preserve"` | 检测前后空白，添加属性 |
| 图片丢失 | 关系或类型未注册 | 检查 .rels 和 [Content_Types].xml |
| 打包后文件变大 | XML 未压缩 | pack.py 自动压缩，确认未跳过 |

### 验证问题

| 症状 | 可能原因 | 修复方式 |
|------|---------|---------|
| XSD 验证大量错误 | 原始文件本身就有违规 | 使用差分验证，只关注新增错误 |
| paraId 越界 | `paraId >= 0x80000000` | pack.py 自动修复，或手动修改 |
| durableId 越界 | `durableId >= 0x7FFFFFFF` | pack.py 自动修复 |
| ID 冲突 | 重复的 bookmark/docPartId | 更换 ID 值 |
| 命名空间错误 | 非标准命名空间声明 | 检查 XML 根元素的命名空间 |

### 环境问题

| 症状 | 可能原因 | 修复方式 |
|------|---------|---------|
| `node` 命令找不到 | Node.js 未安装 | 安装 Node.js >= 18.0 |
| `require('docx')` 失败 | npm 包未安装 | 运行 `npm install` |
| Python 脚本报错 | defusedxml/lxml 缺失 | `pip install defusedxml lxml` |
| LibreOffice 超时 | 沙箱环境限制 | 正常行为，超时视为成功 |
| .doc 无法处理 | 旧格式文件 | 先用 LibreOffice 转换为 .docx |

## 验证流程

```
validate.py 报告错误
       │
       ├─ 可自动修复 → pack.py --validate true 会自动修复
       │   ├── whitespace preservation
       │   └── durableId 越界
       │
       └─ 需人工修复
           ├── unpack → 编辑 XML → repack
           └── 常见修复:
               ├── <w:t> in <w:del> → 改为 <w:delText>
               ├── <w:delText> in <w:ins> → 改为 <w:t>
               ├── 元素顺序错误 → 按规范重排
               └── ID 冲突 → 更换值
```

## 回退策略

### docx-js 生成失败

1. 检查 14 条规则是否全部遵守
2. 简化 content.json（移除图片/复杂表格等）
3. 如果仍然失败: 手动编写 docx-js 代码，不使用 create.js
4. 最后手段: 生成后 unpack → 修复 XML → repack

### 编辑后验证失败

1. 检查 XML 元素顺序
2. 确认 del/ins 元素使用正确的文本元素名
3. 运行 `validate.py --verbose` 获取详细错误
4. 按"可自动修复"和"需人工修复"分类处理
