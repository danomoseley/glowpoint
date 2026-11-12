"""Check that this Python environment can run glowpoint.

  python3 -m glowpoint.doctor

Prints the versions of Python, numpy and OpenCV, and what works. Run it first in a new environment
(for example a chat sandbox without internet).
"""
import sys, platform


def main():
    ok = True
    try:
        from glowpoint import __version__
    except Exception:
        __version__ = "unknown"
    print(f"glowpoint {__version__}")
    print(f"Python  {sys.version.split()[0]}  ({platform.platform()})")
    if sys.version_info < (3, 9):
        print("  PROBLEM: Python 3.9 or newer is necessary"); ok = False
    try:
        import numpy
        print(f"numpy   {numpy.__version__}")
    except ImportError:
        print("numpy   MISSING: pip install numpy"); ok = False
    try:
        import cv2
        lsd = hasattr(cv2, "createLineSegmentDetector")
        if lsd:
            try: cv2.createLineSegmentDetector(0)
            except Exception: lsd = False
        print(f"OpenCV  {cv2.__version__}  line detector: {'LSD' if lsd else 'Hough (fallback, a little less accurate)'}")
    except ImportError:
        print("OpenCV  MISSING: pip install opencv-python (or opencv-python-headless)"); ok = False
    if ok:
        try:
            import os
            from glowpoint.model import Model
            here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures", "lobby")
            if os.path.isdir(here):
                m = Model(here); ids = m.raycast((70, 105))[0]
                print(f"model   OK ({len(m.surfaces)} surfaces in the test lobby)")
        except Exception as e:
            print(f"model   PROBLEM: {e}"); ok = False
    try:
        import os
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if not os.path.isdir(os.path.join(root, ".git")):
            from glowpoint.patch import save_baseline
            save_baseline(root)
    except Exception as e:
        print(f"note: could not save the base for patches ({e})")
    print("READY" if ok else "NOT READY")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
