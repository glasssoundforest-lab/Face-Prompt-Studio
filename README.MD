# Face Prompt Studio — Master Snapshot v0.2.0-dev

## Status
Architecture approved.

## Vision
A long-term, extensible prompt-processing platform with ComfyUI as one adapter, not a dependency.

---

## Overview
Face Prompt Studio (FPS) is a modular prompt-processing engine built with Clean Architecture, SOLID principles, and an Adapter Pattern.  
The core is framework‑agnostic and never imports ComfyUI.

---

## Repository Structure
- fps-core (pure Python, no ComfyUI dependency)
- fps-data (dictionaries, presets, rules)
- fps-adapters
  - comfyui
  - cli
  - python
  - rest
- fps-tools
- docs / tests / examples

---

## Architecture Principles
- Clean Architecture  
- SOLID  
- Adapter pattern  
- Plugin system  
- Event system  
- JSON/YAML configurable  
- Hot reload  
- Cache  
- Backup  
- Logging  
- LTS mindset  

Core never imports ComfyUI.  
Adapters may support multiple ComfyUI API versions.

---

## Processing Pipeline
1. Parser  
2. Normalizer  
3. Duplicate Cleaner  
4. Blacklist  
5. Whitelist  
6. Categorizer  
7. Rule Engine  
8. Weight Engine  
9. Optimizer  
10. Exporter  

---

## Dictionary System
```
system/
user/
```

- User dictionaries always override system dictionaries  
- System updates never overwrite user data  
- JSON/YAML  
- Hot reload capable  

---

## Rule Engine
External JSON/YAML rules supporting:

- IF  
- ADD  
- REMOVE  
- WEIGHT  
- KEEP CATEGORY  

---

## ComfyUI Integration
- ComfyUI is only an adapter  
- Core never imports ComfyUI  
- Multiple API versions supported  
- Adapter can be replaced (REST, CLI, SD.Next, etc.)

---

## Planned Development Phases
1. Foundation  
2. Face Prompt Cleaner  
3. Prompt Optimizer  
4. AI Adapters  
5. GUI Studio  

---

## Coding Standards
- PEP8  
- Type hints  
- Docstrings  
- Logging  
- Unit tests  
- Compatibility tests  
- Performance tests  

---

## Next Sprint (Sprint 1)
Implement:

- ConfigManager  
- Logger  
- DictionaryManager  
- RuleManager  
- PresetManager  
- Cache  
- Backup  
- Minimal ComfyUI adapter  

---

## Resume
Load this snapshot and continue from Sprint 1.
