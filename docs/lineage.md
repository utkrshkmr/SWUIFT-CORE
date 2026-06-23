# SWUIFT Lineage

Monorepo layout (see [structure.md](structure.md)):

```
doe-wildfire/
    └── packages/core     (shared physics: kernels + spread + hardening)
            ├── apps/desktop
            └── packages/cli
```

| Component | Role |
|-----------|------|
| `packages/core` | Shared physics package (Numba + Python fallback, full-grid radiation) |
| `apps/desktop` | PySide6 desktop GUI; depends on `swuift-core` |
| `packages/cli` | Installable `swuift` CLI; depends on `swuift-core` |
| `reference/matlab` | Original MATLAB reference implementation |

All Python implementations share the same physics core in `packages/core/`. The desktop app and CLI differ only in workflow (GUI vs terminal/batch).
