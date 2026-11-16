"""Single entry point:  ../../.venv/bin/python run_all.py   (writes results/*.json)"""
import platform
import sys
import time

import build123d
import OCP

import q1_euler
import q2_history
import q3_determinism


def env():
    import glob
    import os
    libs = glob.glob(os.path.join(os.path.dirname(OCP.__file__), ".dylibs", "libTKernel.*.dylib")) + \
        glob.glob(os.path.join(os.path.dirname(OCP.__file__), "..", "*.libs", "libTKernel*"))
    print(f"python {sys.version.split()[0]} on {platform.platform()} ({platform.machine()})")
    print(f"build123d {build123d.__version__}, OCP {OCP.__version__}, OCCT lib: {[os.path.basename(l) for l in libs]}")


if __name__ == "__main__":
    env()
    for mod in (q1_euler, q2_history, q3_determinism):
        t0 = time.perf_counter()
        mod.main()
        print(f"\n[{mod.__name__} finished in {time.perf_counter() - t0:.1f}s]")
