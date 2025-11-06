"""SQLAlchemy models for Portfolio Doctor"""
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, 
    ForeignKey, Text, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default="USER", nullable=False)
    isActive = Column(Boolean, default=True, nullable=False)
    createdAt = Column(DateTime, default=func.now(), nullable=False)
    updatedAt = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    exchangeAPIKeys = relationship("ExchangeAPIKey", back_populates="user", cascade="all, delete-orphan")
    portfolio = relationship("Portfolio", back_populates="user", uselist=False, cascade="all, delete-orphan")


class ExchangeAPIKey(Base):
    """Exchange API Key model"""
    __tablename__ = "exchange_api_keys"
    
    id = Column(String, primary_key=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(String, default="lbank", nullable=False)
    apiKey = Column(String, nullable=False)
    apiSecret = Column(String, nullable=False)
    isActive = Column(Boolean, default=True, nullable=False)
    createdAt = Column(DateTime, default=func.now(), nullable=False)
    updatedAt = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="exchangeAPIKeys")
    
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Portfolio(Base):
    """Portfolio model"""
    __tablename__ = "portfolios"
    
    id = Column(String, primary_key=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    totalValueUSD = Column(Float, default=0, nullable=False)
    costBasis = Column(Float, default=0, nullable=False)
    unrealizedPnl = Column(Float, default=0, nullable=False)
    unrealizedPnlPercent = Column(Float, default=0, nullable=False)
    createdAt = Column(DateTime, default=func.now(), nullable=False)
    updatedAt = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="portfolio")
    assets = relationship("PortfolioAsset", back_populates="portfolio", cascade="all, delete-orphan")


class PortfolioAsset(Base):
    """Portfolio Asset model"""
    __tablename__ = "portfolio_assets"
    
    id = Column(String, primary_key=True)
    portfolioId = Column(String, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    assetSymbol = Column(String, nullable=False)
    totalQuantity = Column(Float, nullable=False)
    totalValueUSD = Column(Float, nullable=False)
    costBasis = Column(Float, default=0, nullable=False)
    averageBuyPrice = Column(Float, default=0, nullable=False)
    unrealizedPnl = Column(Float, default=0, nullable=False)
    unrealizedPnlPercent = Column(Float, default=0, nullable=False)
    tier = Column(String, default="CORE", nullable=False)
    updatedAt = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    portfolio = relationship("Portfolio", back_populates="assets")
    
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Trade(Base):
    """Trade model"""
    __tablename__ = "trades"
    
    id = Column(String, primary_key=True)
    userId = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    tradeId = Column(String, nullable=False)
    orderId = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    quoteQuantity = Column(Float, nullable=False)
    commission = Column(Float, default=0, nullable=False)
    isBuyer = Column(Boolean, default=True, nullable=False)
    isMaker = Column(Boolean, default=False, nullable=False)
    tradeTime = Column(DateTime, nullable=False)
    createdAt = Column(DateTime, default=func.now(), nullable=False)
    
    # Optional risk management fields
    targetPrice = Column(Float, nullable=True)
    stopLossPrice = Column(Float, nullable=True)
    riskRewardRatio = Column(Float, nullable=True)
    riskAmount = Column(Float, nullable=True)
    expectedReward = Column(Float, nullable=True)
    
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
