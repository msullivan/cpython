# Lazy Imports Backport to 3.14

## Prerequisite: `_PyDict_LookupIndexAndValue` from #142843

Cherry-picked the dict API addition from `bb25f7280af` (gh-132657, by Neil
Schemenauer, 2026-01-16). This extracts just the `Objects/dictobject.c` and
`Include/internal/pycore_dict.h` changes — a new
`_PyDict_LookupIndexAndValue()` that returns both the index and value in a
single hash lookup. The existing `_PyDict_LookupIndex()` becomes a thin wrapper
around it.

PEP 810's specialization guards in `specialize.c` depend on this API to check
whether a looked-up value is a lazy import proxy without a second hash lookup.

## #142351 — Implement PEP 810 - Explicit lazy imports

Cherry-picking `46d5106cfa9` onto 3.14 produced 16 conflicted files.

### Deleted files (modify/delete conflicts)

| File | Resolution |
|------|-----------|
| `Doc/whatsnew/3.15.rst` | Removed — doesn't exist in 3.14. What's-new content would go in 3.14 docs if desired. |
| `Modules/_testinternalcapi/test_cases.c.h` | Removed — file was deleted in 3.14. |
| `Python/ceval.h` | Removed — doesn't exist in 3.14 (contents were folded into `ceval.c` before 3.14 branched). Added the one new include (`#include "pycore_lazyimportobject.h"`) to `Python/ceval.c` instead. |

### Documentation

| File | Resolution |
|------|-----------|
| `Doc/c-api/import.rst` | Kept lazy import C-API docs (`PyImport_GetLazyImportsMode`, etc.). Dropped `PyImport_CreateModuleFromInitfunc` section — that API is 3.15-only and doesn't exist in 3.14. |
| `Doc/library/types.rst` | Added `LazyImportType` entry. Dropped `FrameLocalsProxyType` — that was added in 3.15 and `types.py` on 3.14 doesn't define it. |

### C headers

| File | Resolution |
|------|-----------|
| `Include/internal/pycore_dict.h` | Kept both 3.14's `_Py_Identifier` variant functions (removed in 3.15) and PEP 810's new `_PyDict_ClearKeysVersionLockHeld` declaration. |
| `Include/internal/pycore_magic_number.h` | Added magic number `3628` ("Lazy imports IMPORT_NAME opcode changes") after 3.14's last entry (`3627`). Dropped all 3.15 magic number history (`3650`–`3661`). |
| `Include/internal/pycore_moduleobject.h` | Added `_PyModule_InitModuleDictWatcher` declaration from PEP 810. Dropped `_Py_modexecfunc` typedef — it existed in 3.15's base but not in 3.14. |

### Python source

| File | Resolution |
|------|-----------|
| `Lib/traceback.py` | Combined 3.14's `_get_safe___dir__()` refactor (see gh-131001, gh-139933 — uses `obj.__dir__()` to avoid `TypeError` from `dir()`) with PEP 810's `_is_lazy_import()` helper. The 3.15 base didn't have `_get_safe___dir__()` and used raw `dir()` calls; those were replaced on 3.14 before the cherry-pick. Both the 3.14 function and the lazy import filtering are kept: `_get_safe___dir__()` produces the attribute list, then lazy imports are filtered out of it. |

### C source

| File | Resolution |
|------|-----------|
| `Python/bytecodes.c` | Trivial — kept 3.14's `#include "pycore_ceval.h"` with PEP 810's comment annotation. |
| `Python/specialize.c` | **See detailed notes below.** Uses `_PyDict_LookupIndexAndValue` from the prerequisite commit. |
| `PCbuild/pythoncore.vcxproj.filters` | Added `pycore_lazyimportobject.h` entry. Dropped `pycore_mmap.h` — that header doesn't exist in 3.14. |

### Regenerated files

These files are generated from source and were regenerated after resolving all
hand-editable conflicts:

| File | Generator |
|------|-----------|
| `Parser/parser.c` | `make regen-pegen` (from `Grammar/python.gram`, which auto-merged) |
| `Python/executor_cases.c.h` | `make regen-cases` (from `Python/bytecodes.c`) |
| `Python/generated_cases.c.h` | `make regen-cases` (auto-merged cleanly, regenerated for consistency) |
| `Python/clinic/bltinmodule.c.h` | `make clinic` |
| `Python/clinic/sysmodule.c.h` | `make clinic` |

## Follow-up PRs

### #144726 — Fix build errors from PEP 810

Clean cherry-pick, no conflicts.

### #144733 — Fix refcount corruption in lazy import specialization

Clean cherry-pick, no conflicts. (The spurious `Py_DECREF(value)` on a
borrowed reference in the LOAD_GLOBAL lazy import bail-out was intentionally
preserved in the #142351 backport so this fix applies cleanly.)

### #144840 — Add CODEOWNERS for lazy imports

**Conflict:** `.github/CODEOWNERS` — large context conflict due to 3.14/3.15
divergence in the file. **Resolution:** Took 3.14's version and appended the new
lazy imports entries at the end.

### #144838 — Add test for circular lazy import crash

Clean cherry-pick, no conflicts.

### #144889 — Gate PEP 810 builtins in xpickle compat tests

Clean cherry-pick, no conflicts.

### #144893 — Fix ast.unparse for lazy import statements

Clean cherry-pick, no conflicts.

### #145054 — Use `lazy` imports in `collections`

Clean cherry-pick, no conflicts.

### #145086 — Check globals type in `__lazy_import__()`

**Conflict:** `Lib/test/test_import/test_lazy_imports.py` — the
`test_dunder_lazy_import_invalid_arguments` test method had been deleted during
the #142351 backport (it didn't exist in the cherry-pick's HEAD side).
**Resolution:** Restored the full test method from the incoming side, including
the new `globals=1` type check.

**Additional fix:** The test exposed a crash — `_PyImport_LazyImportModuleLevelObject`
in `Python/import.c` was missing validation that `name` is a string and
`level >= 0` before calling `get_abs_name()`. The 3.15 version has these checks
but they were absent from the 3.14 backport of `46d5106cfa9`. Added the same
`PyUnicode_Check(name)` and `level < 0` guards that exist on 3.15 in a separate
fix commit.

### #145213 — Fix "lazy from (...) import (...)" tests

Clean cherry-pick, no conflicts.

### #145221 — Fix compileall in lazy imports test data with bad syntax

Clean cherry-pick, no conflicts.

### #145336 — Make lazy import tests discoverable

**Conflict:** `.github/CODEOWNERS` — same context conflict pattern as #144840.
**Resolution:** Took 3.14's version and updated the lazy imports section to match
the new test path (`Lib/test/test_lazy_import` instead of the old
`Lib/test/test_import/test_lazy_imports.py` and `data/lazy_imports/` paths).

### #144852 — Fix `__lazy_import__` crash with user-defined filters

Clean cherry-pick, no conflicts.

### #145404 — Refactor Platforms/WASI/\_\_main\_\_.py for lazy importing

**Conflict:** `Platforms/WASI/` was renamed to `Tools/wasm/wasi/` on 3.14
(modify/delete conflict). **Resolution:** Aborted the cherry-pick and manually
applied the changes to `Tools/wasm/wasi/__main__.py` and created
`Tools/wasm/wasi/_build.py`. Dropped the `.pre-commit-config.yaml` and
`Platforms/WASI/.ruff.toml` changes since `Tools/wasm/.ruff.toml` already
covers the 3.14 path.

### #145988 — Fix sys.flags tuple size

Clean cherry-pick, no conflicts.

### #146371 — Ensure `PYTHON_LAZY_IMPORTS=none` overrides `__lazy_modules__`

Clean cherry-pick, no conflicts.

---

### `Python/specialize.c` — detailed notes

This file had the most substantive conflict because PEP 810 on 3.15 relied on
`_PyDict_LookupIndexAndValue()`, an internal dict API that did not originally
exist in 3.14. That function returns both the dict index and the value at that
index in a single hash lookup. On 3.14, only `_PyDict_LookupIndex()` (index
only) and `_PyDictKeys_StringLookup()` (index only) were available.

This is resolved by the prerequisite commit which cherry-picks
`_PyDict_LookupIndexAndValue()` from `bb25f7280af` (#142843).

PEP 810 needs to check whether a looked-up value is a `LazyImport` proxy and, if
so, bail out of specialization (the specializer can't handle lazy proxies since
they get replaced in-place when reified). Two call sites were affected:

**1. `LOAD_ATTR` module specialization (`_Py_Specialize_LoadAttr`)**

On 3.15, the `__getattr__` check and `name` lookup were combined into a single
`_PyDict_LookupIndexAndValue` call. On 3.14 the function was refactored to first
check for `__getattr__` (via `_PyDict_LookupIndex(dict, &_Py_ID(__getattr__))`)
and then separately look up `name`. Resolution: kept 3.14's two-step structure
but switched the `name` lookup to `_PyDict_LookupIndexAndValue` to get the value
for the lazy import check:

```c
// 3.14's existing __getattr__ check (unchanged)
Py_ssize_t index = _PyDict_LookupIndex(dict, &_Py_ID(__getattr__));
// ... __getattr__ check ...

// name lookup now uses combined index+value API
PyObject *value;
index = _PyDict_LookupIndexAndValue(dict, name, &value);
if (value != NULL && PyLazyImport_CheckExact(value)) {
    SPECIALIZATION_FAIL(LOAD_ATTR, SPEC_FAIL_ATTR_MODULE_LAZY_VALUE);
    return -1;
}
// ... range check ...
```

**2. `LOAD_GLOBAL` specialization (`_Py_Specialize_LoadGlobal`)**

On 3.14 the lookup used `_PyDictKeys_StringLookup(globals_keys, name)`.
Replaced with `_PyDict_LookupIndexAndValue()` to match 3.15:

```c
PyObject *value;
Py_ssize_t index = _PyDict_LookupIndexAndValue(
    (PyDictObject *)globals, name, &value);
// ... error check ...
if (value != NULL && PyLazyImport_CheckExact(value)) {
    SPECIALIZATION_FAIL(LOAD_GLOBAL, SPEC_FAIL_ATTR_MODULE_LAZY_VALUE);
    goto fail;
}
```
