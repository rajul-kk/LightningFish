from lightningfish_core.registry import registry

from .config import FinanceDomainAdapter

adapter = FinanceDomainAdapter()
registry.register(adapter)
