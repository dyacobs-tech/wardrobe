import runpy, sys
import playwright.sync_api as sa
_orig = sa.sync_playwright
class _Ctx:
    def __init__(self): self._c = _orig()
    def __enter__(self):
        pw = self._c.__enter__()
        class P:
            def __getattr__(s, k): return getattr(pw, "chromium" if k == "webkit" else k)
        return P()
    def __exit__(self, *a): return self._c.__exit__(*a)
sa.sync_playwright = _Ctx
path = sys.argv[1]; sys.argv = [path] + sys.argv[2:]
sys.path.insert(0, path.rsplit("/", 1)[0])
runpy.run_path(path, run_name="__main__")
