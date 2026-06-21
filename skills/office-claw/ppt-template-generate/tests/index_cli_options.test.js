const assert = require('assert');
const {
  parseCliOptions,
  resolveVlmAvailability,
  selectInitialStyleName,
} = require('../scripts/index.js');

function testDefaultEnablesVlm() {
  const options = parseCliOptions(['demo.pptx']);
  assert.strictEqual(options.pptxPath, 'demo.pptx');
  assert.strictEqual(options.skipVlm, false);
  assert.strictEqual(options.strictVlm, false);
}

function testSkipVlmOverridesDefault() {
  const options = parseCliOptions(['demo.pptx', '--skip-vlm']);
  assert.strictEqual(options.skipVlm, true);
}

function testEnableVlmRemainsCompatible() {
  const options = parseCliOptions(['demo.pptx', '--enable-vlm']);
  assert.strictEqual(options.skipVlm, false);
}

function testStrictVlmOptionRequiresVlm() {
  const options = parseCliOptions(['demo.pptx', '--strict-vlm']);
  assert.strictEqual(options.skipVlm, false);
  assert.strictEqual(options.strictVlm, true);
}

function testUnavailableVlmFallsBackByDefault() {
  const result = resolveVlmAvailability({
    skipVlm: false,
    strictVlm: false,
    vlmApiOk: false,
    failureReason: 'VLM API 未配置',
  });

  assert.strictEqual(result.skipVlm, true);
  assert.match(result.fallbackReason, /VLM API 未配置/);
}

function testUnavailableVlmFailsInStrictMode() {
  assert.throws(() => resolveVlmAvailability({
    skipVlm: false,
    strictVlm: true,
    vlmApiOk: false,
    failureReason: 'VLM API 未配置',
  }), /VLM_DEPENDENCY_MISSING/);
}

function testVlmDoesNotAutoNameWithoutExplicitName() {
  const name = selectInitialStyleName({
    pptxPath: '年度总结.pptx',
    explicitName: null,
  });
  assert.strictEqual(name, '年度总结');
}

function testExplicitNameStillWins() {
  const name = selectInitialStyleName({
    pptxPath: '年度总结.pptx',
    explicitName: '深红商务汇报',
  });
  assert.strictEqual(name, '深红商务汇报');
}

testDefaultEnablesVlm();
testSkipVlmOverridesDefault();
testEnableVlmRemainsCompatible();
testStrictVlmOptionRequiresVlm();
testUnavailableVlmFallsBackByDefault();
testUnavailableVlmFailsInStrictMode();
testVlmDoesNotAutoNameWithoutExplicitName();
testExplicitNameStillWins();

console.log('index_cli_options tests passed');
