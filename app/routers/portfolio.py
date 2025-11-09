"""Portfolio router"""
from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
from app.services.portfolio_service import PortfolioService
from app.models import User

router = APIRouter()
portfolio_service = PortfolioService()


@router.get("/")
async def get_portfolio(current_user=Depends(get_current_user)):
    """Get user portfolio"""
    try:
        # Access user.id while session is still active
        user_id = current_user.id
        return await portfolio_service.get_portfolio(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_portfolio(current_user=Depends(get_current_user)):
    """Sync portfolio from exchanges"""
    try:
        # Access user.id while session is still active
        user_id = current_user.id
        return await portfolio_service.sync_portfolio(user_id)
    except Exception as e:
        raise HTTPException(status_code=404 if "No connected exchanges" in str(e) else 500, detail=str(e))


@router.get("/spot")
async def get_spot_portfolio(current_user: User = Depends(get_current_user)):
    """Get spot account overview"""
    try:
        return await portfolio_service.get_spot_portfolio_overview(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/futures")
async def get_futures_balances(current_user: User = Depends(get_current_user)):
    """Get detailed futures/trade balances for connected LBank account"""
    try:
        return await portfolio_service.get_futures_portfolio_overview(current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-analysis")
async def get_ai_analysis(current_user: User = Depends(get_current_user)):
    """Lightweight heuristic analysis for the current portfolio (placeholder for AI)."""
    try:
        data = await portfolio_service.get_portfolio(current_user.id)
        live = data.get("livePortfolio") or {}
        assets = live.get("assets") or []
        futures_assets = live.get("futuresAssets") or []
        spot_total = (live.get("accounts") or {}).get("spot", {}).get("valueUSD", 0) or 0
        futures_total = (live.get("accounts") or {}).get("futures", {}).get("valueUSD", 0) or 0

        def topn(arr, n=5):
            arr2 = [a for a in arr if (a.get("valueUSD") or 0) > 0]
            return sorted(arr2, key=lambda x: x.get("valueUSD") or 0, reverse=True)[:n]

        top_assets = topn(assets, 5)
        top_futures = topn(futures_assets, 5)
        total = (live.get("totalValueUSD") or 0) + 0
        concentration = sum(a.get("valueUSD") or 0 for a in top_assets[:3]) / total * 100 if total > 0 else 0

        insights = []
        if concentration > 60:
            insights.append("High concentration: Top 3 assets > 60% of portfolio.")
        if futures_total > 0 and futures_total / (total or 1) > 0.4:
            insights.append("Elevated derivatives exposure: Futures > 40% of portfolio.")
        if not insights:
            insights.append("Diversification and derivatives exposure appear within typical ranges.")

        return {
            "summary": {
                "totalValueUSD": total,
                "spotValueUSD": spot_total,
                "futuresValueUSD": futures_total,
                "spotPercent": (spot_total / total * 100) if total > 0 else 0,
                "futuresPercent": (futures_total / total * 100) if total > 0 else 0,
            },
            "topAssets": top_assets,
            "topFutures": top_futures,
            "insights": insights,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

