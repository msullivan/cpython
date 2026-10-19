from collections.abc import Callable, Iterable
import sys
from types import ModuleType
from importlib import import_module
import pkgutil
import tracemalloc
from annotationlib import Format
import timeit
from pathlib import Path
from typing import eval_annotate_as_types
from contextlib import redirect_stdout

import subprocess


def run_test():
    VENV_PATH = Path() / ".venv/Lib/site-packages"
    sys.path.insert(0, str(VENV_PATH))
    PACKAGES = [
        "urllib3",
        "certifi",
        "idna",
        "requests",
        "charset_normalizer",
        "cryptography",
        "pluggy",
        "pytest",
        "click",
        "iniconfig",
        "anyio",
        "attrs",
        "h11",
    ]


    def iter_modules(package: str) -> Iterable[ModuleType]:
        try:
            package_module = import_module(package)
        except Exception as e:
            if "." not in package:
                raise
            return
        yield package_module
        if hasattr(package_module, "__path__"):
            for _, name, _ in pkgutil.iter_modules(package_module.__path__, package + "."):
                yield from iter_modules(name)


    def iter_annotates(obj: object) -> Iterable[Callable[[int], object]]:
        obj_cache.add(id(obj))
        if getattr(obj, "__annotate__", None) is not None and callable(obj.__annotate__):
            yield obj.__annotate__
        if isinstance(obj, (type, ModuleType)) and hasattr(obj, "__dict__"):
            for attr_value in obj.__dict__.values():
                if id(attr_value) not in obj_cache:
                    yield from iter_annotates(attr_value)

    obj_cache = set()

    tracemalloc.start()
    with open("/dev/null", "w") as dev_null, redirect_stdout(dev_null):
        start, _ = tracemalloc.get_traced_memory()
        time = timeit.default_timer()
        for package in PACKAGES:
            for mod in iter_modules(package):
                pass
        import_time = timeit.default_timer() - time
    end, _ = tracemalloc.get_traced_memory()
    memory = end - start

    pyc_size = 0
    for path in VENV_PATH.glob("**/*.pyc"):
        pyc_size += path.stat().st_size

    time = 0
    for package in PACKAGES:
        for mod in iter_modules(package):
            for annotate in iter_annotates(mod):
                time_start = timeit.default_timer()
                eval_annotate_as_types(annotate, format=Format.VALUE)
                time += timeit.default_timer() - time_start

    return import_time, memory, pyc_size, time


code = """
import annotation_tests
print(*annotation_tests.run_test())
"""

if __name__ == "__main__":
    count = 10
    if len(sys.argv) >= 2:
        count = int(sys.argv[1])

    import_time, memory, pyc, exec_time = 0, 0, 0, 0
    if count > 1:
        procs = [subprocess.run([sys.executable, "-c", code], capture_output=True, text=True) for _ in range(count)]
        for proc in procs:
            if proc.stderr:
                print(proc.stderr)
                raise SystemExit
            i, m, p, e = (float(x) / len(procs) for x in proc.stdout.split())
            import_time += i
            memory += m
            pyc += p
            exec_time += e
    else:
        sys.argv = ["annotation_tests.py"]
        import_time, memory, pyc, exec_time = run_test()

    print(
        f"Import time: {import_time:.2f}s\n"
        f"Memory: {memory / 1_000_000:.3f} MB\n"
        f"Pyc size: {pyc / 1_000_000:.3f} MB\n"
        f"Exec time: {exec_time:.4f}s"
    )
