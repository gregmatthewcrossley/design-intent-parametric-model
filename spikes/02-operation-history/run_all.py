"""Single entry point:  ../../.venv/bin/python run_all.py   (writes results/q{1..4}.json; tee to results/run_all.log)"""
import glob
import os
import platform
import sys
import time

import common  # noqa: F401  (puts spike 01 on sys.path)
import build123d
import OCP

import q1_roles
import q2_stability
import q3_determinism
import q4_clean


def env():
    libs = glob.glob(os.path.join(os.path.dirname(OCP.__file__), ".dylibs", "libTKernel.*.dylib")) + \
        glob.glob(os.path.join(os.path.dirname(OCP.__file__), "..", "*.libs", "libTKernel*"))
    print(f"python {sys.version.split()[0]} on {platform.platform()} ({platform.machine()})")
    print(f"build123d {build123d.__version__}, OCP {OCP.__version__}, OCCT lib: {[os.path.basename(l) for l in libs]}")


if __name__ == "__main__":
    env()
    for mod in (q1_roles, q2_stability, q3_determinism, q4_clean):
        t0 = time.perf_counter()
        mod.main()
        print(f"\n[{mod.__name__} finished in {time.perf_counter() - t0:.1f}s]")
