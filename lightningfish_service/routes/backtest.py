from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from lightningfish_core.registry import registry

router = APIRouter()


class BacktestRequest(BaseModel):
    n_agents: int = 200
    n_rounds: int = 8


@router.post("/{domain_id}")
def run_backtest(domain_id: str, req: BacktestRequest):
    """
    Run a calibration backtest for the given domain.
    Returns aggregated accuracy and cost metrics.
    """
    adapter = registry.get(domain_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Unknown domain: {domain_id}")

    if domain_id == "finance":
        from lightningfish_finance.run_backtest import FinanceBacktestHarness
        harness = FinanceBacktestHarness(adapter)
    elif domain_id == "coding":
        from lightningfish_coding.run_backtest import CodingBacktestHarness
        harness = CodingBacktestHarness(adapter)
    else:
        raise HTTPException(status_code=400, detail=f"No backtest harness for domain: {domain_id}")

    harness.N_AGENTS = req.n_agents
    harness.N_ROUNDS = req.n_rounds

    results = harness.run_batch()
    return {
        "domain_id": domain_id,
        "n_agents": req.n_agents,
        "n_rounds": req.n_rounds,
        "results": results,
    }
