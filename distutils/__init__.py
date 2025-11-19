"""
Lightweight shim for the removed stdlib ``distutils`` package.

Some third-party libraries (e.g. ``undetected_chromedriver``) still import
``distutils.version.LooseVersion``.  Python 3.12+ no longer bundles distutils,
so we vendor the minimal pieces we need to keep those imports working.
"""

from .version import LooseVersion, StrictVersion

__all__ = ["LooseVersion", "StrictVersion"]

