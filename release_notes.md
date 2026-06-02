# Release v1.2.18

## New Features

- Agents running on models without a built-in web search (such as DeepSeek and MiniMax) now have reliable Internet Search. It draws on several search providers behind the scenes and automatically falls back to another whenever one is unavailable or out of quota, so searches keep succeeding without any manual switching.

## Improvements

- Web search is now delivered through a single, consistent built-in capability for these models; the standalone Tavily skill has been retired and its functionality folded into the unified search.
