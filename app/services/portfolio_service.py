"""Portfolio service"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import uuid
import asyncio

from app.core.database import get_db
from app.services.lbank_service import LBankService
from app.models import Portfolio, PortfolioAsset, ExchangeAPIKey

logger = logging.getLogger(__name__)


class PortfolioService:
    """Portfolio management service"""
    
    def __init__(self):
        self.lbank_service = LBankService()

    @staticmethod
    def _safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    
    async def get_portfolio(self, user_id: str) -> Dict[str, Any]:
        """Get user portfolio"""
        try:
            with get_db() as db:
                # Get or create portfolio for user
                portfolio = db.query(Portfolio).filter(Portfolio.userId == user_id).first()
                
                if not portfolio:
                    # Create empty portfolio
                    portfolio = Portfolio(
                        id=str(uuid.uuid4()),
                        userId=user_id,
                        totalValueUSD=0,
                        costBasis=0,
                        unrealizedPnl=0,
                        unrealizedPnlPercent=0,
                    )
                    db.add(portfolio)
                    db.flush()
                
                # Get connected exchanges
                connected_exchanges = db.query(ExchangeAPIKey).filter(
                    ExchangeAPIKey.userId == user_id,
                    ExchangeAPIKey.isActive == True
                ).all()
                
                # Get live portfolio if user has active exchanges
                live_portfolio = None
                active_connections = db.query(ExchangeAPIKey).filter(
                    ExchangeAPIKey.userId == user_id,
                    ExchangeAPIKey.isActive == True
                ).all()
                
                lbank_conn = next((c for c in active_connections if c.exchange == 'lbank'), None)
                if lbank_conn:
                    try:
                        # Add timeout for live data fetching (30 seconds)
                        live_data = await asyncio.wait_for(
                            self.lbank_service.get_portfolio_data(
                                lbank_conn.apiKey,
                                lbank_conn.apiSecret
                            ),
                            timeout=30.0
                        )
                        # Fetch futures balances detail (non-blocking but with same timeout envelope)
                        futures_detail = await asyncio.wait_for(
                            self.lbank_service.get_futures_balances(
                                lbank_conn.apiKey,
                                lbank_conn.apiSecret
                            ),
                            timeout=30.0
                        )
                        
                        # Build account breakdown precisely from spot and futures (no heuristics)
                        assets_list = live_data.get("assets", [])  # spot assets only
                        logger.info(f"Processing {len(assets_list)} live spot assets for account breakdown")

                        spot_total = sum(float(a.get("valueUSD") or 0) for a in assets_list)

                        futures_detail = await asyncio.wait_for(
                            self.lbank_service.get_futures_balances(
                                lbank_conn.apiKey,
                                lbank_conn.apiSecret
                            ),
                            timeout=30.0
                        )
                        futures_assets = futures_detail.get("assets", []) if isinstance(futures_detail, dict) else []
                        futures_positions = futures_detail.get("positions", []) if isinstance(futures_detail, dict) else []
                        futures_total = sum(float(a.get("valueUSD") or 0) for a in futures_assets)

                        # Heuristic: avoid double counting when futures mirrors spot stablecoin wallet (common on accounts without futures activity)
                        total = spot_total + futures_total
                        
                        logger.info(f"Account breakdown - Total: ${total:.2f}, Spot: ${spot_total:.2f}, Futures: ${futures_total:.2f}")
                        
                        live_portfolio = {
                            "totalValueUSD": total,
                            "totalValueUSDT": total,
                            "accounts": {
                                "spot": {
                                    "valueUSD": spot_total,
                                    "percent": (spot_total / total * 100) if total > 0 else 0,
                                },
                                "futures": {
                                    "valueUSD": futures_total,
                                    "percent": (futures_total / total * 100) if total > 0 else 0,
                                },
                                "margin": {"valueUSD": 0, "percent": 0},
                                "funding": {"valueUSD": 0, "percent": 0},
                            },
                            "timeZone": "UTC+8",
                            "timestampUTC8": datetime.utcnow().isoformat(),
                            "assets": assets_list,
                            "futuresBalanceUSD": futures_total,
                            "futuresAssets": futures_assets,
                            "futuresPositions": futures_positions,
                            "openPositions": [],
                            "tradeHistory": [],
                            "pnl": {
                                "daily": {"usdt": None, "percent": None},
                                "weekly": {"usdt": None, "percent": None},
                                "monthly": {"usdt": None, "percent": None},
                            },
                        }
                    except asyncio.TimeoutError:
                        logger.warning(f"Live portfolio fetch timeout for lbank connection")
                        live_portfolio = None
                    except Exception as e:
                        logger.error(f"Live portfolio fetch error: {e}", exc_info=True)
                        live_portfolio = None
                
                # Calculate summary - prioritize live portfolio if available
                if live_portfolio:
                    live_total_value = float(live_portfolio.get("totalValueUSD", 0) or 0)
                    live_asset_count = len(live_portfolio.get("assets", []))
                else:
                    live_total_value = 0.0
                    live_asset_count = 0
                
                # Use live data if available, otherwise use saved portfolio
                display_total_value = live_total_value if live_total_value > 0 else portfolio.totalValueUSD
                display_asset_count = live_asset_count if live_asset_count > 0 else (len(portfolio.assets) if portfolio.assets else 0)
                
                summary = {
                    "totalAssets": display_asset_count,
                    "totalValueUSD": display_total_value,
                    "totalPnl": portfolio.unrealizedPnl,  # Only available from saved portfolio
                    "totalPnlPercent": portfolio.unrealizedPnlPercent,  # Only available from saved portfolio
                    "connectedExchangesCount": len(connected_exchanges),
                }
                
                return {
                    "portfolio": {
                        "id": portfolio.id,
                        "totalValueUSD": portfolio.totalValueUSD,
                        "costBasis": portfolio.costBasis,
                        "unrealizedPnl": portfolio.unrealizedPnl,
                        "unrealizedPnlPercent": portfolio.unrealizedPnlPercent,
                        "lastUpdated": portfolio.updatedAt.isoformat(),
                        "assets": [
                            {
                                "id": asset.id,
                                "symbol": asset.assetSymbol,
                                "quantity": asset.totalQuantity,
                                "valueUSD": asset.totalValueUSD,
                                "costBasis": asset.costBasis,
                                "averageBuyPrice": asset.averageBuyPrice,
                                "unrealizedPnl": asset.unrealizedPnl,
                                "unrealizedPnlPercent": asset.unrealizedPnlPercent,
                                "tier": asset.tier,
                                "lastUpdated": asset.updatedAt.isoformat(),
                            }
                            for asset in (portfolio.assets or [])
                        ],
                    },
                    "connectedExchanges": [ex.exchange for ex in connected_exchanges],
                    "summary": summary,
                    "livePortfolio": live_portfolio,
                }
        except Exception as e:
            logger.error(f"Portfolio service error: {e}")
            return {
                "portfolio": {
                    "id": "error",
                    "totalValueUSD": 0,
                    "costBasis": 0,
                    "unrealizedPnl": 0,
                    "unrealizedPnlPercent": 0,
                    "lastUpdated": datetime.utcnow().isoformat(),
                    "assets": [],
                },
                "connectedExchanges": [],
                "summary": {
                    "totalAssets": 0,
                    "totalValueUSD": 0,
                    "totalPnl": 0,
                    "totalPnlPercent": 0,
                    "connectedExchangesCount": 0,
                },
                "livePortfolio": None,
            }
    
    async def sync_portfolio(self, user_id: str) -> Dict[str, Any]:
        """Sync portfolio from exchanges"""
        with get_db() as db:
            # Get connected exchanges
            connected_exchanges = db.query(ExchangeAPIKey).filter(
                ExchangeAPIKey.userId == user_id,
                ExchangeAPIKey.isActive == True
            ).all()
            
            if not connected_exchanges:
                raise Exception("No connected exchanges found")
            
            # Fetch portfolio data from exchanges
            all_assets = []
            total_value_usd = 0.0
            total_cost_basis = 0.0
            
            for exchange in connected_exchanges:
                if exchange.exchange == "lbank":
                    try:
                        portfolio_data = await self.lbank_service.get_portfolio_data(
                            exchange.apiKey,
                            exchange.apiSecret
                        )
                        all_assets.extend(portfolio_data.get("assets", []))
                        total_value_usd += portfolio_data.get("totalValueUSD", 0)
                        total_cost_basis += portfolio_data.get("costBasis", 0)
                    except Exception as e:
                        logger.error(f"Failed to fetch data from {exchange.exchange}: {e}")
            
            # Calculate total P&L
            total_pnl = total_value_usd - total_cost_basis
            total_pnl_percent = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0
            
            # Update or create portfolio
            portfolio = db.query(Portfolio).filter(Portfolio.userId == user_id).first()
            
            if portfolio:
                portfolio.totalValueUSD = total_value_usd
                portfolio.costBasis = total_cost_basis
                portfolio.unrealizedPnl = total_pnl
                portfolio.unrealizedPnlPercent = total_pnl_percent
            else:
                portfolio = Portfolio(
                    id=str(uuid.uuid4()),
                    userId=user_id,
                    totalValueUSD=total_value_usd,
                    costBasis=total_cost_basis,
                    unrealizedPnl=total_pnl,
                    unrealizedPnlPercent=total_pnl_percent,
                )
                db.add(portfolio)
                db.flush()
            
            # Delete old assets and create new ones
            db.query(PortfolioAsset).filter(PortfolioAsset.portfolioId == portfolio.id).delete()
            
            if all_assets:
                new_assets = [
                    PortfolioAsset(
                        id=str(uuid.uuid4()),
                        portfolioId=portfolio.id,
                        assetSymbol=asset["symbol"],
                        totalQuantity=asset["quantity"],
                        totalValueUSD=asset.get("valueUSD", 0) or 0,
                        costBasis=asset.get("costBasis", 0),
                        averageBuyPrice=asset.get("averageBuyPrice", 0),
                        unrealizedPnl=asset.get("unrealizedPnl", 0),
                        unrealizedPnlPercent=asset.get("unrealizedPnlPercent", 0),
                        tier=asset.get("tier", "CORE"),
                    )
                    for asset in all_assets
                ]
                db.bulk_save_objects(new_assets)
            
            return {
                "message": "Portfolio synced successfully",
                "syncedExchanges": [ex.exchange for ex in connected_exchanges],
                "lastSyncTime": datetime.utcnow().isoformat(),
            }

    async def get_spot_portfolio_overview(self, user_id: str) -> Dict[str, Any]:
        """Return spot-only portfolio snapshot"""
        with get_db() as db:
            lbank_conn = db.query(ExchangeAPIKey).filter(
                ExchangeAPIKey.userId == user_id,
                ExchangeAPIKey.exchange == "lbank",
                ExchangeAPIKey.isActive == True,
            ).first()

        if not lbank_conn:
            return {
                "exchange": None,
                "assetCount": 0,
                "totalValueUSD": 0.0,
                "assets": [],
                "updatedAt": datetime.utcnow().isoformat(),
            }

        live_data = await self.lbank_service.get_portfolio_data(
            lbank_conn.apiKey,
            lbank_conn.apiSecret,
        )
        assets_raw = live_data.get("assets", []) if isinstance(live_data, dict) else []
        normalized_assets = []
        total_value = 0.0

        for asset in assets_raw:
            value = self._safe_float(asset.get("valueUSD"))
            total_value += value
            normalized_assets.append({
                "symbol": asset.get("symbol"),
                "quantity": self._safe_float(asset.get("quantity")),
                "free": self._safe_float(asset.get("free")),
                "frozen": self._safe_float(asset.get("frozen")),
                "priceUSD": self._safe_float(asset.get("priceUSD")),
                "valueUSD": value,
                "tier": asset.get("tier"),
                "accountType": asset.get("accountType", "SPOT"),
                "lastUpdated": asset.get("lastUpdated") or datetime.utcnow().isoformat(),
            })

        return {
            "exchange": lbank_conn.exchange,
            "assetCount": len(normalized_assets),
            "totalValueUSD": total_value,
            "assets": normalized_assets,
            "updatedAt": datetime.utcnow().isoformat(),
        }

    async def get_futures_portfolio_overview(self, user_id: str) -> Dict[str, Any]:
        """Return futures-only portfolio snapshot including positions"""
        with get_db() as db:
            lbank_conn = db.query(ExchangeAPIKey).filter(
                ExchangeAPIKey.userId == user_id,
                ExchangeAPIKey.exchange == "lbank",
                ExchangeAPIKey.isActive == True,
            ).first()

        if not lbank_conn:
            return {
                "exchange": None,
                "assetCount": 0,
                "positionCount": 0,
                "totalValueUSD": 0.0,
                "assets": [],
                "positions": [],
                "updatedAt": datetime.utcnow().isoformat(),
            }

        futures_data = await self.lbank_service.get_futures_balances(
            lbank_conn.apiKey,
            lbank_conn.apiSecret,
        )

        assets_raw = futures_data.get("assets", []) if isinstance(futures_data, dict) else []
        positions_raw = futures_data.get("positions", []) if isinstance(futures_data, dict) else []

        normalized_assets = []
        total_value = 0.0
        for asset in assets_raw:
            value = self._safe_float(asset.get("valueUSD"))
            total_value += value
            normalized_assets.append({
                "symbol": asset.get("symbol"),
                "quantity": self._safe_float(asset.get("quantity")),
                "free": self._safe_float(asset.get("free")),
                "frozen": self._safe_float(asset.get("frozen")),
                "priceUSD": self._safe_float(asset.get("priceUSD")),
                "valueUSD": value,
                "accountType": "FUTURES",
            })

        normalized_positions = []
        for position in positions_raw:
            normalized_positions.append({
                "symbol": position.get("symbol"),
                "side": position.get("side"),
                "quantity": self._safe_float(position.get("quantity")),
                "entryPrice": self._safe_float(position.get("entryPrice")),
                "markPrice": self._safe_float(position.get("markPrice")),
                "leverage": position.get("leverage"),
                "unrealizedPnl": self._safe_float(position.get("unrealizedPnl")),
                "notionalValueUSD": self._safe_float(position.get("notionalValueUSD")),
            })

        total_value = self._safe_float(futures_data.get("totalValueUSD")) if isinstance(futures_data, dict) else total_value

        return {
            "exchange": lbank_conn.exchange,
            "assetCount": len(normalized_assets),
            "positionCount": len(normalized_positions),
            "totalValueUSD": total_value,
            "assets": normalized_assets,
            "positions": normalized_positions,
            "updatedAt": datetime.utcnow().isoformat(),
        }
