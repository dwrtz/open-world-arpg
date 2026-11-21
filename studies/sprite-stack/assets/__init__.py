"""Asset registry: every module in this package exposes build(**params) -> Vox."""
import importlib
import pkgutil


def names():
    return sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith('_'))


def build(name, **params):
    return importlib.import_module(f'{__name__}.{name}').build(**params)
