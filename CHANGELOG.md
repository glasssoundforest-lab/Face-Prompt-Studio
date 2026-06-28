# Changelog

All notable changes to Face Prompt Studio are documented here.
Format: [Semantic Versioning](https://semver.org/)

---

## [Unreleased] — v0.2.0-dev

### Sprint 1 — Foundation
- [ ] Repository structure
- [ ] ConfigManager
- [ ] Logger
- [ ] DictionaryManager
- [ ] RuleManager
- [ ] PresetManager
- [ ] Cache
- [ ] Backup
- [ ] Pipeline (10-stage)
- [ ] Minimal ComfyUI adapter

---

## [0.1.0] — DSL Prototype (fps v0.5.0 legacy)

### Added
- 7-stage pipeline: Lexer → Tokenizer → AST Builder → PIR Builder
  → Semantic Resolver → Optimizer → ComfyUI Adapter
- DSL syntax: `(category:value)`, `(category:value:weight)`,
  `[negative]`, `{constraint:value}`
- Resolver map (dictionary stub)
- Split file architecture (models / lexer / tokenizer / ... / pipeline)

### Known Limitations
- Single-file resolver map (no system/user split)
- No external rule support
- No logging, config, cache, or backup
- ComfyUI tightly coupled to core
