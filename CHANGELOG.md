# Changelog

## [0.8.0] — 2026-06-20

### Added
- **CLI `skills run` command**: Execute Markdown skills via `cogu skills run <name>` with `--input` JSON, `--context`, `--script` and `--script-args` options
- **Script interpreter detection**: `execute_script()` auto-detects `.py`/`.sh`/`.bat` extensions and uses appropriate interpreter

### Changed
- `SkillExecutor.execute_script()` now uses `sys.executable` for `.py` scripts instead of direct execution
- Updated `--help` examples to include `skills run`

## [0.7.1] — 2026-06-19

### Fixed
- `Settings.load()` workspace path resolution
- SSE parser OpenAI format handling
- `remember()` API parameter validation
- CLI duplicate skill discovery

## [0.7.0] — 2026-06-18

### Added
- **Skills layer**: Markdown-based `SkillSpec` + `SkillRegistry` + `SkillExecutor` with YAML frontmatter parsing, script execution, LLM-driven execution
- **Builtin skills**: `BuiltinSkillRegistry` with 9 builtin skills (Reasoning, GuiVision, CodeOffice, BrowserAutomation, DataAnalysis, WebSearch, Shell, Finance, Gateway)
- **CLI skills commands**: `list`, `install`, `discover`, `info`, `builtin list`, `builtin run`
- `SkillRegistry.build_context()` for skill context injection into agent sessions

## [0.6.0] — 2026-06-17

### Added
- **CLI**: argparse-based CLI with `run`, `debate`, `skills`, `memory`, `serve`, `version`, `tui` subcommands
- PES debate engine integration via `DebateOrchestrator`
- Memory recall integration in agent run loop
- DeepSeek API client with multi-provider fallback

## [0.5.0] — 2026-06-16

### Added
- EnhancedSuperMemory with 5 recall strategies (FTS, semantic, hybrid, comprehensive, entity-graph)
- Memory-grade auto-compression (STM→MTM→LTM pipeline)
- Debate layer: Expert, Team, PESEngine, DebateOrchestrator

## [0.4.0] — 2026-06-15

### Added
- Memory layer: SuperMemory (SQLite FTS5), MemoryStore (MiMo), MemoryGraph (M3), EntityGraph, GradeMemory

## [0.3.0] — 2026-06-14

### Added
- Core layer: Runner, ReActAgent, Rails (4-level guard), Session

## [0.2.0] — 2026-06-12

### Fixed
- 5 critical bugs: Settings.load(), SSE parser, @classmethod@property, remember() API, CLI dedup

## [0.1.0] — 2026-06-12

### Added
- Initial release: 41 files, 6194 insertions
