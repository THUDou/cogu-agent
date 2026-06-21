/**
 * json_utils.js — JSON 安全解析工具
 *
 * 提供 safeJsonParse()，在标准 JSON.parse() 失败时自动尝试修复
 * 常见问题：字符串值中未转义的双引号、控制字符等。
 */

/**
 * Safely parse JSON with recovery for common issues like unescaped quotes
 * and control characters in string values.
 */
function safeJsonParse(raw) {
  // First try standard parse
  try {
    return JSON.parse(raw);
  } catch (e) {
    // Attempt recovery
  }

  // Strategy: walk the string character by character, tracking whether we are
  // inside a JSON string.  Inside strings, escape any unescaped double-quote
  // that is NOT followed by structural chars (comma, colon, bracket, brace,
  // end-of-input) — those are almost certainly content quotes, not JSON
  // delimiters.  Also strip bare control characters (newlines, tabs, etc.)
  // that are invalid in JSON strings.
  const len = raw.length;
  const out = [];
  let inString = false;
  let i = 0;

  while (i < len) {
    const ch = raw[i];

    if (!inString) {
      out.push(ch);
      if (ch === '"') inString = true;
      i++;
      continue;
    }

    // We are inside a JSON string
    if (ch === '\\') {
      // Already-escaped sequence — copy verbatim
      out.push(ch);
      if (i + 1 < len) {
        out.push(raw[i + 1]);
        i += 2;
      } else {
        i++;
      }
      continue;
    }

    if (ch === '"') {
      // Is this a closing quote or a stray content quote?
      // Look ahead: if the next non-whitespace char is structural, this is
      // a real closing quote. Otherwise treat it as content.
      let j = i + 1;
      while (j < len && raw[j] === ' ') j++;
      const nextCh = j < len ? raw[j] : '';
      const isStructural = nextCh === '' || ',:]}\n\r'.includes(nextCh);

      if (isStructural) {
        // Real closing quote
        out.push(ch);
        inString = false;
        i++;
      } else {
        // Stray content quote — escape it
        out.push('\\"');
        i++;
      }
      continue;
    }

    // Strip bare control characters (0x00-0x1F except already-handled cases)
    if (ch.charCodeAt(0) < 0x20) {
      if (ch === '\n') {
        out.push('\\n');
      } else if (ch === '\r') {
        // skip bare CR
      } else if (ch === '\t') {
        out.push('\\t');
      }
      // other control chars are silently dropped
      i++;
      continue;
    }

    out.push(ch);
    i++;
  }

  const repaired = out.join('');

  try {
    return JSON.parse(repaired);
  } catch (e2) {
    throw new Error(
      `Failed to parse content JSON even after recovery.\n` +
      `Original error: ${e2.message}\n` +
      `Please check your content.json for: unescaped quotes inside text ` +
      `values, trailing commas, missing brackets, or other syntax issues.`
    );
  }
}

module.exports = { safeJsonParse };
