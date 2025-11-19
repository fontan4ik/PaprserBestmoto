# Vendored from Python 3.11's distutils.version (public domain)
import re


class DistutilsError(Exception):
    pass


class DistutilsSetupError(DistutilsError):
    pass


class Version:
    def __init__(self, vstring=None):
        if vstring:
            self.parse(vstring)

    def __repr__(self):
        return f"{self.__class__.__name__} ('{self.vstring}')"

    def __str__(self):
        return self.vstring

    def _cmp(self, other):
        raise NotImplementedError

    def __lt__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c < 0

    def __le__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c <= 0

    def __eq__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c == 0

    def __ge__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c >= 0

    def __gt__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c > 0

    def __ne__(self, other):
        c = self._cmp(other)
        if c is NotImplemented:
            return c
        return c != 0


class StrictVersion(Version):
    version_re = re.compile(
        r"""
            ^
            (?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)
            (?P<prerel>[ab]\d+)?
            $
        """,
        re.VERBOSE,
    )

    def parse(self, vstring):
        match = self.version_re.match(vstring)
        if not match:
            raise DistutilsSetupError(f"invalid StrictVersion: '{vstring}'")
        self.vstring = vstring
        self.version = tuple(int(match.group(name)) for name in ("major", "minor", "patch"))
        prerel = match.group("prerel")
        if prerel:
            self.prerelease = (prerel[0], int(prerel[1:]))
        else:
            self.prerelease = None

    def _cmp(self, other):
        if isinstance(other, str):
            other = StrictVersion(other)
        if not isinstance(other, StrictVersion):
            return NotImplemented
        if self.version != other.version:
            return (self.version > other.version) - (self.version < other.version)
        if self.prerelease is None and other.prerelease is None:
            return 0
        if self.prerelease is None:
            return 1
        if other.prerelease is None:
            return -1
        return (self.prerelease > other.prerelease) - (self.prerelease < other.prerelease)


class LooseVersion(Version):
    component_re = re.compile(r"(\d+ | [a-z]+ | \.)", re.VERBOSE)

    def parse(self, vstring):
        self.vstring = vstring
        components = [c for c in self.component_re.split(vstring) if c and c != "."]
        self.components = []
        for component in components:
            if component.isdigit():
                self.components.append(int(component))
            else:
                self.components.append(component.lower())

    def _cmp(self, other):
        if isinstance(other, str):
            other = LooseVersion(other)
        if not isinstance(other, LooseVersion):
            return NotImplemented
        for self_comp, other_comp in zip(self.components, other.components):
            if self_comp == other_comp:
                continue
            if isinstance(self_comp, int) and isinstance(other_comp, str):
                return 1
            if isinstance(self_comp, str) and isinstance(other_comp, int):
                return -1
            return (self_comp > other_comp) - (self_comp < other_comp)
        return (len(self.components) > len(other.components)) - (
            len(self.components) < len(other.components)
        )


__all__ = ["LooseVersion", "StrictVersion"]

