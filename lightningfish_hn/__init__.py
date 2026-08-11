from lightningfish_core.registry import registry

from .config import HNDomainAdapter

adapter = HNDomainAdapter()
registry.register(adapter)
