
function safeJsonParse(raw) {
  try {
    return JSON.parse(raw);
  } catch (e) {
  }

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

    if (ch === '\\') {
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
      let j = i + 1;
      while (j < len && raw[j] === ' ') j++;
      const nextCh = j < len ? raw[j] : '';
      const isStructural = nextCh === '' || ',:]}\n\r'.includes(nextCh);

      if (isStructural) {
        out.push(ch);
        inString = false;
        i++;
      } else {
        out.push('\\"');
        i++;
      }
      continue;
    }

    if (ch.charCodeAt(0) < 0x20) {
      if (ch === '\n') {
        out.push('\\n');
      } else if (ch === '\r') {
      } else if (ch === '\t') {
        out.push('\\t');
      }
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
