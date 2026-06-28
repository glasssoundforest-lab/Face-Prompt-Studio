# Face Prompt Studio (FPS)

Long-term prompt processing platform. ComfyUI is one adapter among many.

## Repository Structure

```
fps/
├── fps-core/          Pure Python core. No ComfyUI dependency.
│   ├── config/        ConfigManager  (JSON/YAML, hot reload)
│   ├── logging/       Logger
│   ├── dictionary/    DictionaryManager (system/ + user/)
│   ├── rules/         RuleManager (external JSON/YAML)
│   ├── preset/        PresetManager
│   ├── cache/         Cache
│   ├── backup/        Backup
│   ├── pipeline/      10-stage pipeline
│   ├── events/        Event system
│   └── plugins/       Plugin system
├── fps-adapters/      Adapters (core never imports these)
│   ├── comfyui/       ComfyUI adapter
│   ├── cli/           CLI adapter
│   ├── python/        Python API adapter
│   └── rest/          REST API adapter
├── fps-data/          Dictionaries, rules, presets (data only)
│   ├── dictionaries/
│   │   ├── system/    System dictionaries (read-only for users)
│   │   └── user/      User dictionaries (always override system)
│   ├── rules/         External rule definitions
│   └── presets/       Preset definitions
└── fps-tools/
    ├── docs/
    ├── tests/
    │   ├── unit/
    │   ├── compat/
    │   └── performance/
    └── examples/
```

## Pipeline (v0.2.0-dev)

```
Parser → Normalizer → Duplicate Cleaner → Blacklist → Whitelist
→ Categorizer → Rule Engine → Weight Engine → Optimizer → Exporter
```

## Design Principles

- Clean Architecture — core has zero adapter dependencies
- SOLID
- Adapter pattern
- Plugin system
- Event system
- JSON/YAML configurable (JSON primary)
- Hot reload
- LTS mindset

## Versioning

`MAJOR.MINOR.PATCH[-dev|-alpha|-beta|-rc]`

Adapters maintain their own version matrix for ComfyUI API compatibility.

## Development Phases

| Phase | Name |
|---|---|
| 1 | Foundation |
| 2 | Face Prompt Cleaner |
| 3 | Prompt Optimizer |
| 4 | AI Adapters |
| 5 | GUI Studio |
