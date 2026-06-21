#!/usr/bin/env node
/**
 * VLM (Visual Language Model) 分析器
 * 调用视觉大模型分析 PPT 幻灯片图片
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { URL } = require('url');

/**
 * 加载 VLM 配置文件
 */
function replaceEnvPlaceholders(configContent) {
  return configContent.replace(/\$\{(\w+)\}/g, (match, envVar) => {
    return process.env[envVar] || '';
  });
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

function deepMerge(base, override) {
  const result = { ...base };
  for (const [key, value] of Object.entries(override || {})) {
    if (isPlainObject(value) && isPlainObject(result[key])) {
      result[key] = deepMerge(result[key], value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function loadConfig(configPath) {
  if (!fs.existsSync(configPath)) {
    throw new Error(`配置文件不存在: ${configPath}`);
  }

  const configContent = replaceEnvPlaceholders(fs.readFileSync(configPath, 'utf-8'));
  let config = JSON.parse(configContent);

  const localSecretPath = path.join(path.dirname(configPath), 'vlm-secrets.local.json');
  if (fs.existsSync(localSecretPath)) {
    const secretContent = replaceEnvPlaceholders(fs.readFileSync(localSecretPath, 'utf-8'));
    const secretConfig = JSON.parse(secretContent);
    config = deepMerge(config, secretConfig);
  }

  return config;
}

/**
 * 将图片转换为 base64
 */
function imageToBase64(imagePath) {
  const imageBuffer = fs.readFileSync(imagePath);
  return imageBuffer.toString('base64');
}

function imageMediaType(imagePath) {
  const ext = path.extname(imagePath).toLowerCase();
  if (ext === '.jpg' || ext === '.jpeg') return 'image/jpeg';
  if (ext === '.webp') return 'image/webp';
  return 'image/png';
}

/**
 * Anthropic API 调用
 */
async function callAnthropicAPI(config, images, prompt) {
  const apiConfig = config.api.anthropic;

  const content = [
    {
      type: 'text',
      text: prompt
    }
  ];

  for (const img of images) {
    content.push({
      type: 'image',
      source: {
        type: 'base64',
        media_type: img.mediaType || 'image/png',
        data: img.base64
      }
    });
  }

  const payload = {
    model: apiConfig.model || config.model,
    max_tokens: apiConfig.maxTokens || 4096,
    system: config.prompts?.system || '你是一位专业的PPT设计分析师。',
    messages: [
      {
        role: 'user',
        content: content
      }
    ]
  };

  return new Promise((resolve, reject) => {
    const url = new URL(`${apiConfig.baseUrl}/v1/messages`);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiConfig.apiKey,
        'anthropic-version': '2023-06-01'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.error) {
            reject(new Error(result.error.message));
          } else {
            resolve(result.content?.[0]?.text || '');
          }
        } catch (e) {
          reject(new Error(`解析响应失败: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(JSON.stringify(payload));
    req.end();
  });
}

/**
 * OpenAI API 调用
 */
async function callOpenAIAPI(config, images, prompt) {
  const apiConfig = config.api.openai;

  // 构建消息内容
  const messages = [
    {
      role: 'system',
      content: config.prompts?.system || '你是一位专业的PPT设计分析师。'
    },
    {
      role: 'user',
      content: [
        { type: 'text', text: prompt },
        ...images.map(img => ({
          type: 'image_url',
          image_url: {
            url: `data:${img.mediaType || 'image/png'};base64,${img.base64}`
          }
        }))
      ]
    }
  ];

  const payload = {
    model: apiConfig.model || config.model,
    max_tokens: apiConfig.maxTokens || 4096,
    messages
  };

  return new Promise((resolve, reject) => {
    const url = new URL(`${apiConfig.baseUrl}/chat/completions`);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiConfig.apiKey}`
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.error) {
            reject(new Error(result.error.message));
          } else {
            resolve(result.choices?.[0]?.message?.content || '');
          }
        } catch (e) {
          reject(new Error(`解析响应失败: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.write(JSON.stringify(payload));
    req.end();
  });
}

/**
 * 解析 VLM 返回的 JSON 分析结果
 */
function parseAnalysisResult(text) {
  try {
    // 尝试直接解析
    return JSON.parse(text);
  } catch (e) {
    // 尝试提取 JSON 块
    const jsonMatch = text.match(/```json\n([\s\S]*?)\n```/) ||
                     text.match(/\{[\s\S]*\}/);

    if (jsonMatch) {
      try {
        return JSON.parse(jsonMatch[1] || jsonMatch[0]);
      } catch (e2) {
        // 返回原始文本
        return {
          raw_text: text,
          error: '无法解析 JSON'
        };
      }
    }

    return {
      raw_text: text,
      error: '无法解析 JSON'
    };
  }
}

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function firstArray(...values) {
  for (const value of values) {
    if (Array.isArray(value)) return value;
  }
  return [];
}

/**
 * 将新旧 VLM 返回统一为增强结构，同时保留旧字段以兼容现有聚合逻辑。
 */
function normalizeAnalysisResult(result) {
  const data = isPlainObject(result) ? result : {};
  const enhanced = isPlainObject(data.design_analysis) ? data.design_analysis : {};

  return {
    ...data,
    schema_version: data.schema_version || 'ppt-template-vlm-enhanced-v1',
    page_roles: firstArray(data.page_roles, data['页面类型'], data['页面角色'], enhanced.page_roles),
    visual_assets: firstArray(data.visual_assets, data['视觉资产'], data['风格资产'], enhanced.visual_assets),
    layout_semantics: firstArray(data.layout_semantics, data['版式语义'], data['版式复刻规则'], enhanced.layout_semantics),
    fixed_composition: firstArray(data.fixed_composition, data['固定构图'], data['模板固定构图'], data['固定构图规范'], enhanced.fixed_composition),
    corrections: firstArray(data.corrections, data['纠偏规则'], data['视觉纠偏'], enhanced.corrections),
    replication_rules: firstArray(data.replication_rules, data['复刻规则'], data['复刻优先级'], enhanced.replication_rules),
    overlay_policy: isPlainObject(data.overlay_policy) ? data.overlay_policy : null,
  };
}

/**
 * VLM 分析主函数
 */
async function analyzeWithVLM(imagePaths, configPath) {
  const config = loadConfig(configPath);

  if (!config.enabled) {
    console.log('VLM 分析已禁用');
    return null;
  }

  // 检查 API 密钥
  const provider = config.provider;
  const apiConfig = config.api?.[provider];

  if (!apiConfig?.apiKey) {
    throw new Error(`${provider} API 密钥未配置，请检查 vlm-config.json`);
  }

  // 准备图片
  const maxImages = config.analysis?.maxImagesPerRequest || 5;
  const imagesToAnalyze = imagePaths.slice(0, maxImages);

  console.log(`准备分析 ${imagesToAnalyze.length} 张图片...`);

  const images = imagesToAnalyze.map(imgPath => ({
    path: imgPath,
    base64: imageToBase64(imgPath),
    mediaType: imageMediaType(imgPath)
  }));

  // 生成 prompt
  const analysisPrompt = (config.prompts?.analysisPrompt || '')
    .replace('{count}', String(images.length));

  // 调用 API
  let resultText;
  if (provider === 'anthropic') {
    resultText = await callAnthropicAPI(config, images, analysisPrompt);
  } else if (provider === 'openai') {
    resultText = await callOpenAIAPI(config, images, analysisPrompt);
  } else {
    throw new Error(`不支持的 provider: ${provider}`);
  }

  // 解析结果
  const analysisResult = normalizeAnalysisResult(parseAnalysisResult(resultText));

  return {
    provider,
    model: apiConfig.model || config.model,
    imagesAnalyzed: imagesToAnalyze.length,
    analysis: analysisResult,
    rawText: resultText
  };
}

/**
 * 批量分析多个图片集
 */
async function batchAnalyze(imageDir, configPath, outputPath) {
  const config = loadConfig(configPath);

  // 查找所有图片
  const imageFiles = fs.readdirSync(imageDir)
    .filter(f => /\.(png|jpg|jpeg)$/i.test(f))
    .sort()
    .map(f => path.join(imageDir, f));

  if (imageFiles.length === 0) {
    console.log('未找到图片文件');
    return null;
  }

  const maxImages = config.analysis?.maxImagesPerRequest || 5;
  const concurrency = config.analysis?.concurrency || 3;
  const results = [];

  // 建批
  const batches = [];
  for (let i = 0; i < imageFiles.length; i += maxImages) {
    batches.push(imageFiles.slice(i, i + maxImages));
  }

  console.log(`共 ${batches.length} 个批次，并发数: ${concurrency}`);

  // 分组并发执行
  for (let i = 0; i < batches.length; i += concurrency) {
    const chunk = batches.slice(i, i + concurrency);
    console.log(`\n并发执行批次 ${i + 1} - ${i + chunk.length} / ${batches.length}`);

    const settled = await Promise.allSettled(
      chunk.map((batch, idx) => {
        const batchNo = i + idx + 1;
        const startImg = (i + idx) * maxImages + 1;
        console.log(`  批次 ${batchNo}: 图片 ${startImg} - ${startImg + batch.length - 1}`);
        return analyzeWithVLM(batch, configPath);
      })
    );

    for (const s of settled) {
      if (s.status === 'fulfilled' && s.value) {
        results.push(s.value);
      } else if (s.status === 'rejected') {
        console.error(`批次分析失败: ${s.reason.message}`);
      }
    }
  }

  // 合并结果
  const mergedResult = {
    totalImages: imageFiles.length,
    batches: results.length,
    analyses: results.map(r => r.analysis)
  };

  // 保存结果
  if (outputPath) {
    fs.writeFileSync(outputPath, JSON.stringify(mergedResult, null, 2), 'utf-8');
    console.log(`\n分析结果已保存到: ${outputPath}`);
  }

  return mergedResult;
}

/**
 * 测试 API 连接
 */
async function testConnection(configPath) {
  const config = loadConfig(configPath);

  console.log('测试 VLM API 连接...');
  console.log(`Provider: ${config.provider}`);
  console.log(`Model: ${config.model}`);

  const provider = config.provider;
  const apiConfig = config.api?.[provider];

  if (!apiConfig?.apiKey) {
    console.log(`❌ ${provider} API 密钥未配置`);
    return false;
  }

  if (apiConfig.apiKey.startsWith('${') || apiConfig.apiKey === '') {
    console.log(`❌ ${provider} API 密钥未设置（环境变量未定义）`);
    return false;
  }

  // 测试调用（使用空图片列表，只测试连接）
  try {
    const testPrompt = '请回复 "API 连接测试成功"';
    if (provider === 'anthropic') {
      await callAnthropicAPI(config, [], testPrompt);
    } else {
      await callOpenAIAPI(config, [], testPrompt);
    }
    console.log(`✅ ${provider} API 连接成功`);
    return true;
  } catch (error) {
    console.log(`❌ ${provider} API 连接失败: ${error.message}`);
    return false;
  }
}

// CLI 入口
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help') {
    console.log(`
用法: node vlm-analyzer.js <图片目录> [输出JSON路径] [选项]

选项:
  --config=<路径>       配置文件路径 (默认: ../vlm-config.json)
  --test                测试 API 连接

示例:
  node vlm-analyzer.js ./slides --config=../vlm-config.json
  node vlm-analyzer.js ./slides ./vlm_analysis.json
  node vlm-analyzer.js --test --config=../vlm-config.json
`);
    process.exit(0);
  }

  // 解析选项
  let configPath = path.join(__dirname, '..', 'vlm-config.json');
  let outputPath = null;
  let imageDir = null;
  let testMode = false;

  for (const arg of args) {
    if (arg.startsWith('--config=')) {
      configPath = arg.slice('--config='.length);
    } else if (arg.startsWith('--test')) {
      testMode = true;
    } else if (!arg.startsWith('--') && !imageDir) {
      imageDir = arg;
    } else if (!arg.startsWith('--') && !outputPath) {
      outputPath = arg;
    }
  }

  if (testMode) {
    await testConnection(configPath);
    process.exit(0);
  }

  if (!imageDir) {
    console.log('错误: 请指定图片目录');
    process.exit(1);
  }

  try {
    const result = await batchAnalyze(imageDir, configPath, outputPath);
    if (result) {
      console.log('\n分析完成!');
    }
  } catch (error) {
    console.error(`错误: ${error.message}`);
    process.exit(1);
  }
}

// 导出
module.exports = {
  loadConfig,
  parseAnalysisResult,
  normalizeAnalysisResult,
  analyzeWithVLM,
  batchAnalyze,
  testConnection,
  imageToBase64,
  imageMediaType
};

if (require.main === module) {
  main();
}
