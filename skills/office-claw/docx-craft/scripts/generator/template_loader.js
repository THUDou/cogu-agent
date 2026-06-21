const path = require('path');

const RECIPES_DIR = path.resolve(__dirname, '../../recipes');

const PAGE_SIZES = {
  letter: { width: 12240, height: 15840 },
  a4: { width: 11906, height: 16838 },
  legal: { width: 12240, height: 20160 },
  a3: { width: 16838, height: 23811 },
};

const MARGIN_PRESETS = {
  standard: { top: 1440, bottom: 1440, left: 1440, right: 1440 },
  narrow: { top: 720, bottom: 720, left: 720, right: 720 },
  wide: { top: 1440, bottom: 1440, left: 2160, right: 2160 },
};

function load(recipeName) {
  const recipePath = path.join(RECIPES_DIR, `${recipeName}.json`);
  try {
    const recipe = require(recipePath);
    return recipe;
  } catch (e) {
    throw new Error(`Recipe not found: ${recipeName} (tried ${recipePath})`);
  }
}

function resolvePage(recipe, overrides = {}) {
  const pageSizeKey = overrides.pageSize || recipe.page?.preset || 'a4';
  const marginKey = overrides.margins || recipe.page?.marginPreset || 'standard';

  const pageSize = PAGE_SIZES[pageSizeKey] || PAGE_SIZES.a4;
  const margin = MARGIN_PRESETS[marginKey] || MARGIN_PRESETS.standard;

  return {
    size: {
      width: recipe.page?.width || pageSize.width,
      height: recipe.page?.height || pageSize.height,
    },
    margin: {
      top: recipe.page?.margin?.top ?? margin.top,
      bottom: recipe.page?.margin?.bottom ?? margin.bottom,
      left: recipe.page?.margin?.left ?? margin.left,
      right: recipe.page?.margin?.right ?? margin.right,
    },
  };
}

function listRecipes() {
  const fs = require('fs');
  const files = fs.readdirSync(RECIPES_DIR).filter(f => f.endsWith('.json'));
  return files.map(f => {
    const recipe = require(path.join(RECIPES_DIR, f));
    return { name: recipe.name, label: recipe.label };
  });
}

module.exports = { load, resolvePage, listRecipes, PAGE_SIZES, MARGIN_PRESETS };
