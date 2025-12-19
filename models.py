"""
Модели данных для приложения оптимизации цен
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


# SQLAlchemy модели
class ProductDB(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    nm_id = Column(Integer, unique=True, index=True)  # Артикул WB
    name = Column(String)
    category = Column(String)
    current_price = Column(Float)  # Текущая цена со скидкой
    cost_price = Column(Float)  # Себестоимость
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceHistoryDB(Base):
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    nm_id = Column(Integer, index=True)
    price = Column(Float)  # Цена со скидкой
    sales_count = Column(Integer)
    revenue = Column(Float)
    date = Column(DateTime, default=datetime.utcnow)


class OptimizationResultDB(Base):
    __tablename__ = "optimization_results"
    
    id = Column(Integer, primary_key=True, index=True)
    nm_id = Column(Integer, index=True)
    current_price = Column(Float)
    optimal_price = Column(Float)
    predicted_revenue = Column(Float)
    predicted_profit = Column(Float)
    predicted_sales = Column(Integer)
    elasticity_coefficient = Column(Float)
    confidence_score = Column(Float)
    recommendation = Column(String)
    ai_insights = Column(JSON)
    competitor_data = Column(JSON)  # Данные о конкурентах
    created_at = Column(DateTime, default=datetime.utcnow)
    applied = Column(Boolean, default=False)


# Pydantic модели для API
class Product(BaseModel):
    nm_id: int = Field(..., description="Артикул товара на Wildberries")
    name: str = Field(..., description="Название товара")
    category: Optional[str] = Field(None, description="Категория товара")
    current_price: float = Field(..., gt=0, description="Текущая цена (со скидкой)")
    cost_price: float = Field(..., gt=0, description="Себестоимость товара")


class ProductCreate(BaseModel):
    nm_id: int
    name: str
    category: Optional[str] = None
    current_price: float  # Цена со скидкой
    cost_price: float


class PricePoint(BaseModel):
    date: datetime
    price: float  # Цена со скидкой
    sales_count: int
    revenue: float


class ElasticityAnalysis(BaseModel):
    elasticity_coefficient: float = Field(..., description="Коэффициент эластичности спроса")
    is_elastic: bool = Field(..., description="Является ли спрос эластичным")
    confidence: float = Field(..., ge=0, le=1, description="Уровень уверенности в анализе")
    data_points: int = Field(..., description="Количество точек данных")
    
    
class OptimalPriceRecommendation(BaseModel):
    nm_id: int
    product_name: str
    current_price: float  # Текущая цена со скидкой
    optimal_price: float  # Оптимальная цена со скидкой
    price_change_percent: float
    
    # Прогнозы
    current_daily_sales: int
    predicted_daily_sales: int
    current_daily_revenue: float
    predicted_daily_revenue: float
    current_daily_profit: float
    predicted_daily_profit: float
    
    # Анализ
    elasticity: ElasticityAnalysis
    
    # Рекомендации AI
    recommendation: str
    risk_level: str  # low, medium, high
    ai_insights: dict
    
    # Альтернативные сценарии
    alternative_scenarios: List[dict]
    
    # Анализ конкурентов
    competitor_analysis: Optional[Dict] = None


class OptimizationRequest(BaseModel):
    nm_ids: Optional[List[int]] = Field(None, description="Список артикулов для оптимизации")
    optimize_for: str = Field("profit", description="Цель оптимизации: profit, revenue, or balanced")
    min_confidence: float = Field(0.6, ge=0, le=1, description="Минимальная уверенность для рекомендаций")
    consider_competitors: bool = Field(True, description="Учитывать цены конкурентов")


class BulkOptimizationResponse(BaseModel):
    total_products: int
    optimized_products: int
    total_potential_profit_increase: float
    total_potential_revenue_increase: float
    recommendations: List[OptimalPriceRecommendation]


class CompetitorAnalysisRequest(BaseModel):
    nm_id: int = Field(..., description="Артикул товара")
    min_reviews: int = Field(500, description="Минимальное количество отзывов у конкурентов")


class CompetitorProduct(BaseModel):
    nm_id: int
    name: str
    brand: str
    price_with_discount: float
    original_price: float
    discount_percent: float
    rating: float
    reviews_count: int
    size: str
