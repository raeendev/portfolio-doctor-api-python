"""Exchanges router"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import List, Dict, Any

from app.core.dependencies import get_current_user
from app.core.database import get_db_dependency
from app.models import ExchangeAPIKey, User, Trade

router = APIRouter()


@router.get("/list")
async def get_exchanges_list():
    """Get available exchanges list"""
    exchanges = [
        {
            "id": "lbank",
            "name": "LBank",
            "description": "Global cryptocurrency exchange with advanced trading features",
            "status": "available",
            "features": ["Spot Trading", "Futures Trading", "Staking", "High Liquidity"],
            "icon": "🏦",
            "website": "https://www.lbank.com",
            "supportedFeatures": {
                "spot": True,
                "futures": True,
                "margin": False,
                "staking": True,
            },
        },
        {
            "id": "binance",
            "name": "Binance",
            "description": "World's largest cryptocurrency exchange by trading volume",
            "status": "coming_soon",
            "features": ["Spot Trading", "Futures Trading", "Margin Trading", "Staking"],
            "icon": "🟡",
            "website": "https://www.binance.com",
            "supportedFeatures": {
                "spot": True,
                "futures": True,
                "margin": True,
                "staking": True,
            },
        },
    ]
    return {"exchanges": exchanges}


@router.get("/connected")
async def get_connected_exchanges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Get user connected exchanges"""
    connected = db.query(ExchangeAPIKey).filter(
        ExchangeAPIKey.userId == current_user.id,
        ExchangeAPIKey.isActive == True
    ).all()
    return {"exchanges": [{"exchange": ex.exchange, "createdAt": ex.createdAt.isoformat()} for ex in connected]}


@router.post("/connect")
async def connect_exchange(
    exchange_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Connect to exchange"""
    exchange_id = exchange_data.get("exchangeId")
    api_key = exchange_data.get("apiKey")
    api_secret = exchange_data.get("apiSecret")
    
    # Check if already connected
    existing = db.query(ExchangeAPIKey).filter(
        ExchangeAPIKey.userId == current_user.id,
        ExchangeAPIKey.exchange == exchange_id
    ).first()
    
    if existing:
        if existing.isActive:
            existing.apiKey = api_key
            existing.apiSecret = api_secret
            db.flush()
            return {
                "message": "Exchange already connected. API keys updated.",
                "exchange": exchange_id,
                "id": existing.id,
            }
        else:
            existing.apiKey = api_key
            existing.apiSecret = api_secret
            existing.isActive = True
            db.flush()
            return {
                "message": "Exchange reconnected successfully",
                "exchange": exchange_id,
                "id": existing.id,
            }
    
    # Create new connection
    connection = ExchangeAPIKey(
        id=str(uuid.uuid4()),
        userId=current_user.id,
        exchange=exchange_id,
        apiKey=api_key,
        apiSecret=api_secret,
        isActive=True,
    )
    db.add(connection)
    db.flush()
    
    return {
        "message": "Exchange connected successfully",
        "exchange": exchange_id,
        "id": connection.id,
    }


@router.delete("/{exchange_id}")
async def disconnect_exchange(
    exchange_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Disconnect exchange"""
    exchange_connection = db.query(ExchangeAPIKey).filter(
        ExchangeAPIKey.userId == current_user.id,
        ExchangeAPIKey.exchange == exchange_id
    ).first()
    
    if not exchange_connection:
        raise HTTPException(
            status_code=404,
            detail="Exchange connection not found"
        )
    
    exchange_connection.isActive = False
    db.flush()
    
    return {
        "message": "Exchange disconnected successfully",
        "exchange": exchange_id,
    }


@router.put("/{exchange_id}")
async def update_exchange_keys(
    exchange_id: str,
    update_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Update exchange API keys"""
    exchange_connection = db.query(ExchangeAPIKey).filter(
        ExchangeAPIKey.userId == current_user.id,
        ExchangeAPIKey.exchange == exchange_id
    ).first()
    
    if not exchange_connection:
        raise HTTPException(
            status_code=404,
            detail="Exchange connection not found"
        )
    
    exchange_connection.apiKey = update_data.get("apiKey")
    exchange_connection.apiSecret = update_data.get("apiSecret")
    db.flush()
    
    return {
        "message": "Exchange API keys updated successfully",
        "exchange": exchange_id,
        "updatedAt": exchange_connection.updatedAt.isoformat(),
    }


@router.post("/import-trades")
async def import_trade_data(
    import_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_dependency)
):
    """Import trade data from file"""
    try:
        trades_data = import_data.get("data", [])
        file_name = import_data.get("fileName", "imported")
        file_type = import_data.get("fileType", "text/csv")
        
        if not trades_data or not isinstance(trades_data, list):
            raise HTTPException(
                status_code=400,
                detail="Invalid data format. Expected a list of trades."
            )
        
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for idx, trade_data in enumerate(trades_data):
            try:
                # Extract required fields with flexible mapping
                symbol = str(trade_data.get("symbol") or trade_data.get("pair") or trade_data.get("market", "")).upper()
                quantity = float(trade_data.get("quantity") or trade_data.get("qty") or trade_data.get("amount", 0))
                price = float(trade_data.get("price") or trade_data.get("price_usd") or trade_data.get("rate", 0))
                
                # Try to parse timestamp in various formats
                timestamp_str = trade_data.get("timestamp") or trade_data.get("time") or trade_data.get("date") or trade_data.get("tradeTime")
                if timestamp_str:
                    try:
                        # Try ISO format first
                        if isinstance(timestamp_str, str):
                            # Handle ISO format with timezone
                            if 'Z' in timestamp_str or '+' in timestamp_str:
                                trade_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            else:
                                # Try parsing common date formats
                                try:
                                    trade_time = datetime.fromisoformat(timestamp_str)
                                except:
                                    # Fallback to current time if parsing fails
                                    trade_time = datetime.utcnow()
                        else:
                            trade_time = datetime.fromtimestamp(float(timestamp_str))
                    except Exception:
                        trade_time = datetime.utcnow()
                else:
                    trade_time = datetime.utcnow()
                
                # Generate unique trade ID
                trade_id = trade_data.get("tradeId") or trade_data.get("id") or f"{symbol}-{int(trade_time.timestamp() * 1000)}-{idx}"
                order_id = trade_data.get("orderId") or trade_data.get("order_id") or trade_id
                exchange = trade_data.get("exchange") or "manual_import"
                quote_quantity = float(trade_data.get("quoteQuantity") or trade_data.get("quote_qty") or price * quantity)
                commission = float(trade_data.get("commission") or trade_data.get("fee") or 0)
                is_buyer = trade_data.get("isBuyer") or trade_data.get("side", "").lower() == "buy" or True
                is_maker = trade_data.get("isMaker") or False
                
                # Validate required fields
                if not symbol or quantity <= 0 or price <= 0:
                    skipped_count += 1
                    errors.append(f"Row {idx + 1}: Missing required fields (symbol, quantity, or price)")
                    continue
                
                # Check if trade already exists
                existing_trade = db.query(Trade).filter(
                    Trade.userId == current_user.id,
                    Trade.exchange == exchange,
                    Trade.tradeId == str(trade_id)
                ).first()
                
                if existing_trade:
                    skipped_count += 1
                    continue
                
                # Create new trade record
                trade = Trade(
                    id=str(uuid.uuid4()),
                    userId=current_user.id,
                    exchange=exchange,
                    symbol=symbol,
                    tradeId=str(trade_id),
                    orderId=str(order_id),
                    price=price,
                    quantity=quantity,
                    quoteQuantity=quote_quantity,
                    commission=commission,
                    isBuyer=is_buyer,
                    isMaker=is_maker,
                    tradeTime=trade_time,
                )
                
                db.add(trade)
                imported_count += 1
                
            except Exception as e:
                skipped_count += 1
                errors.append(f"Row {idx + 1}: {str(e)}")
                continue
        
        db.commit()
        
        response_data = {
            "message": f"Import completed. {imported_count} trades imported, {skipped_count} skipped.",
            "importedCount": imported_count,
            "skippedCount": skipped_count,
            "fileName": file_name,
        }
        
        if errors:
            response_data["errors"] = errors[:10]  # Limit errors to first 10
        
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import trade data: {str(e)}"
        )
