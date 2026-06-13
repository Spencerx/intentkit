# Release v2.4.0

## New Features

- The package can now be installed with optional extras: `intentkit[pdf]` adds PDF generation support and `intentkit[ollama]` adds local Ollama model support, so deployments that don't need them stay lean.

## Improvements

- Internal architecture cleanup: the codebase now enforces a strict module layering, and the agent execution engine was reorganized into smaller, focused modules. Behavior and public APIs are unchanged.
- The dependency list was tidied — unused packages removed and previously implicit ones now declared explicitly — for more reliable and reproducible installs.
- Stronger automated quality gates (type checking, architecture-layer rules, dependency hygiene) and broader continuous-integration coverage now span the Python, Go and frontend code.
- The DeFi Llama tool test suite was moved out of the shipped package and rewritten, so the published library no longer carries test files.

## Bug Fixes

- Fixed bugs in the tool integration module: external MCP-wrapped tools now send the correct tool name to remote servers, the Jupiter price and quote tools now honor their per-agent enable/disable settings, the Venice image-enhance tool can now be enabled, and the DeFi Llama price-chart tool now returns data instead of an empty result.
