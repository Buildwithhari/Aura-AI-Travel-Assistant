"""
Minimal test runner for machines without pytest.
    python run_tests.py                 # all suites
    python run_tests.py tests.test_dates  # one module
With pytest installed you can simply run:  pytest -q
"""
import contextlib
import importlib
import inspect
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests")]
os.environ["LLM_PROVIDER"] = "custom"
os.environ["USE_MBERT"] = "false"

DEFAULT = ["tests.test_locations", "tests.test_multilingual", "tests.test_dates", "tests.test_i18n", "tests.test_conversation",
           "tests.test_api_and_llm", "test_multiturn", "test_mbert", "test_advanced_features", "test_llm_provider"]


def main(mods):
    passed, fails = 0, []
    for m in mods:
        mod = importlib.import_module(m)
        tests = [(n, f) for n, f in inspect.getmembers(mod, inspect.isfunction) if n.startswith("test_") and f.__module__ == m]
        for name, fn in tests:
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    fn()
                passed += 1
            except Exception as e:
                fails.append(f"{m}.{name}: {type(e).__name__}: {str(e)[:300]}")
        suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
        if suite.countTestCases():
            res = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
            passed += res.testsRun - len(res.failures) - len(res.errors)
            fails += [f"{m}.{t.id()}: {tb.strip().splitlines()[-1]}" for t, tb in res.failures + res.errors]
        print(f"{m:32s} done")
    print(f"\nPASSED {passed}  FAILED {len(fails)}")
    for f in fails:
        print("  FAIL", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or DEFAULT))
