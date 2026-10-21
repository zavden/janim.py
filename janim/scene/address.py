"""Scene addresses (`file.py:Class`) and the module a scene file lives in.

One module per PATH, registered under a unique name: two files that both
define `class Main(Scene)` never share a namespace, so asking for A cannot
hand back B. `importlib.reload` re-executes the
file into the same module, and the class is re-resolved afterwards.
"""

import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys

_MODULES = {}


def scene_address(text, extension=".py"):
    """Split at the LAST ':' whose left side ends in `extension`; '' = no name."""
    text = str(text)
    index = text.rfind(":")
    if index >= 0 and text[:index].endswith(extension):
        return text[:index], text[index + 1:]
    return text, ""


def module_name(path):
    return "janim_scene_" + hashlib.sha256(str(Path(path).resolve()).encode()).hexdigest()[:12]


def load_scene_module(path):
    """Execute the scene file into its own module (cached per path)."""
    path = Path(path).resolve()
    module = _MODULES.get(str(path))
    if module is not None:
        return module
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {path}")
    directory = str(path.parent)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    name = module_name(path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    _MODULES[str(path)] = module
    return module


def reload_scene_module(module):
    """Re-execute the file into the same module; callers re-resolve the class.

    `importlib.reload` re-finds the spec through the meta path, which cannot
    locate a module loaded from a path, so the spec is rebuilt from the file
    and executed into the existing namespace — what reload does after that.
    """
    spec = importlib.util.spec_from_file_location(module.__name__, module.__file__)
    module.__spec__ = spec
    spec.loader.exec_module(module)
    return module


def scene_classes(module):
    """The Scene subclasses DEFINED in the module, in definition order."""
    from janim.scene.scene import Scene

    return [
        value
        for value in vars(module).values()
        if isinstance(value, type) and issubclass(value, Scene) and value.__module__ == module.__name__
    ]


def resolve_scene(module, name, path):
    """The scene class `name` of `module`, or the file's only one when `name` is empty."""
    from janim.scene.scene import Scene

    basename = Path(path).name
    if name:
        candidate = getattr(module, name, None)
        if not (isinstance(candidate, type) and issubclass(candidate, Scene)):
            raise LookupError(
                f"scene «{name}» is not defined by {basename} — expected `class {name}(Scene)` in that file "
                f"(with no `:{name}` suffix the file's only Scene subclass is used)",
            )
        return candidate
    classes = scene_classes(module)
    if len(classes) == 1:
        return classes[0]
    if not classes:
        raise LookupError(f"{basename} defines no Scene subclass — expected `class Name(Scene)` in that file")
    names = ", ".join(cls.__name__ for cls in classes)
    raise LookupError(f"{basename} defines {len(classes)} scenes: {names} — name one as {basename}:{classes[0].__name__}")


def load_scene_class(path, name=""):
    """The scene class of `path` (`name` empty = the file's only Scene subclass)."""
    module = load_scene_module(path)
    return resolve_scene(module, name, path)
