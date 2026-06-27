from lightningfish_core.registry import registry

from .config import CodingDomainAdapter

adapter = CodingDomainAdapter()
registry.register(adapter)
