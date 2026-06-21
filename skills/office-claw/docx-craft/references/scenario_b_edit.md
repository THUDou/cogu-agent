# Pipeline B: 编辑已有文档场景指南

## 适用场景

- 用户有一个现有的 .docx 文件需要修改
- 信号: "edit", "modify", "update", "change text", "add section", "修复"

## 三步流程

### Step 1: Unpack

```bash
python scripts/office/unpack.py input.docx unpacked/
```

解包后目录结构:
```
unpacked/
├── [Content_Types].xml
├── _rels/.rels
├── word/
│   ├── document.xml        ← 主要编辑目标
│   ├── document.xml.rels   ← 关系文件（图片/批注等引用）
│   ├── styles.xml          ← 样式定义
│   ├── comments.xml        ← 批注内容（如果存在）
│   └── media/              ← 嵌入的图片
└── ...
```

解包过程自动执行:
1. ZIP 提取
2. XML 美化打印（便于阅读和编辑）
3. 简化修订标记（合并同作者相邻 ins/del）
4. 合并相邻 Run（合并相同格式的 Run）
5. 智能引号转义（" → `&#x201C;` 等）

### Step 2: Edit XML

**核心原则**:
- 使用 Edit 工具直接进行字符串替换，不要写 Python 脚本
- 使用 "Claude" 作为作者名（除非用户要求其他名称）
- 保留原有格式（复制 `<w:rPr>` 到修改后的元素）
- 替换整个 `<w:r>` 元素块，不在 Run 内部注入标记

#### 常见操作速查

| 操作 | 方法 |
|------|------|
| 修改文本 | del(旧) + ins(新)，复制原有 rPr |
| 插入文本 | 在段落中添加 `<w:ins>` 包裹的新 Run |
| 删除文本 | 用 `<w:del>` 包裹，`w:t` 改为 `w:delText` |
| 删除整段 | 段落属性加 `<w:del/>`，内容加 `<w:del>` |
| 添加批注 | `python scripts/comment.py`，然后插入标记 |
| 插入图片 | 放入 media/ + 添加关系 + 注册类型 + 插入绘图元素 |

#### XML 元素顺序规则

```
w:p   → pPr → runs
w:r   → rPr → t/br/tab
w:pPr → pStyle → numPr → spacing → ind → jc → rPr (最后!)
w:tbl → tblPr → tblGrid → tr
w:tr  → trPr → tc
w:tc  → tcPr → p (最少一个 <w:p/>)
w:body → block content → sectPr (必须是最后子元素!)
```

#### 智能引号

添加新文本时使用 XML 实体:

| 实体 | 字符 | 用途 |
|------|------|------|
| `&#x2018;` | ' | 左单引号 |
| `&#x2019;` | ' | 右单引号/撇号 |
| `&#x201C;` | " | 左双引号 |
| `&#x201D;` | " | 右双引号 |

#### 修订标记规则

```xml
<!-- 插入: 使用 w:t -->
<w:ins w:id="1" w:author="Claude" w:date="2026-04-29T10:00:00Z">
  <w:r><w:rPr>...</w:rPr><w:t>inserted</w:t></w:r>
</w:ins>

<!-- 删除: 使用 w:delText，绝不用 w:t -->
<w:del w:id="2" w:author="Claude" w:date="2026-04-29T10:00:00Z">
  <w:r><w:rPr>...</w:rPr><w:delText>deleted</w:delText></w:r>
</w:del>
```

### Step 3: Pack

```bash
python scripts/office/pack.py unpacked/ output.docx --original input.docx
```

打包过程自动执行:
1. 复制到临时目录（不修改原始解包文件）
2. 自动修复（whitespace preservation、durableId 越界）
3. 验证（XML 良构性、命名空间、ID 唯一性、XSD 模式等）
4. XML 压缩（移除空白文本节点和注释）
5. ZIP 打包

## 添加批注

```bash
# 添加批注
python scripts/comment.py unpacked/ 3 "批注文本"

# 添加回复
python scripts/comment.py unpacked/ 1 "回复文本" --parent 0

# 自定义作者
python scripts/comment.py unpacked/ 0 "批注" --author "Reviewer"
```

然后在 document.xml 中插入标记:
```xml
<w:commentRangeStart w:id="0"/>
  <!-- 被批注的文本 -->
<w:commentRangeEnd w:id="0"/>
<w:r>
  <w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>
  <w:commentReference w:id="0"/>
</w:r>
```

**注意**: `commentRangeStart/End` 是 `w:r` 的兄弟元素，不能放在 `w:r` 内部。

## 常见问题

### Q: 修改后 Word 打开报错？
通常是元素顺序错误。检查 `w:pPr`、`w:rPr` 内的子元素顺序，确保符合规范。

### Q: 修改后格式丢失？
复制了内容但丢失了 `<w:rPr>` 格式。确保修改后的 Run 保留原有 rPr。

### Q: 修订验证失败？
运行 `python scripts/office/validate.py unpacked/ --original input.docx --author Claude` 查看差异报告。常见原因:
1. 在其他作者的修订标记内修改了内容
2. 编辑了文本但未添加修订标记
3. `w:del` 内用了 `w:t` 而非 `w:delText`
