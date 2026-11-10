# Contributing to certification-lab-ci-tools

This document provides the information needed to contribute to the tools in
this repository.

## Commit messages and versioning

Pushes to `main` that change files in `cert-tools/` or `scriptlets/` directories
or to `install_tools.sh` will trigger a workflow that will automatically get a
semantic version tag (`vX.Y.Z`), created by the
[tag-tools workflow][tag-tools-workflow]. The bump is derived
from the commit messages since the previous tag:

| Commit message contains           | Bump  |
|-----------------------------------|-------|
| `breaking(scope):` or `breaking:` | major |
| `feat(scope):` or `feat:`         | minor |
| anything else                     | patch |

Examples: `feat(toolbox): add ...`, `breaking(launcher): rename ...`.

Both commit subjects and bodies are searched, so with squash merges either the
PR title or the listed commits can carry the prefix. Avoid using these prefixes
elsewhere in a message (e.g. in quoted text), as they would trigger a bump.

[tag-tools-workflow]: .github/workflows/tag-tools.yaml