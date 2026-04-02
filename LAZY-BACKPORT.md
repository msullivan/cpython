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
