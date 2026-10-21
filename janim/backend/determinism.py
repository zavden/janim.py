"""Compatibility controls for the strict-GL rendering mode."""

import os


STRICT_GL_ENV = ()
_OVERRIDE = None


def strict_gl():
    if _OVERRIDE is not None:
        return _OVERRIDE
    return os.environ.get("JANIM_STRICT_GL", "1").lower() not in ("0", "false", "no", "off")


def set_strict_gl(enabled=None):
    global _OVERRIDE
    _OVERRIDE = None if enabled is None else bool(enabled)
    return strict_gl()


def strict_gl_env():
    return STRICT_GL_ENV


def strict_gl_cmd(command):
    return command


def strict_gl_pinned():
    return True
