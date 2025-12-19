"""
Основное приложение FastAPI для оптимизации цен на Wildberries
"""
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os

from config import Config
from database import init_db, get_session
from models import (
    Product, ProductCreate, OptimalPriceRecommendation,
    OptimizationRequest, BulkOptimizationResponse,
    CompetitorAnalysisRequest
)
from optimizer_service import PriceOptimizerService
from competitor_analyzer import CompetitorAnalyzer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifecycle manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Инициализация БД при запуске
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    yield
    
    # Очистка при завершении
    logger.info("Завершение работы приложения")


# Создание приложения
app = FastAPI(
    title="Wildberries Price Optimizer",
    description="AI-агент для оптимизации цен на маркетплейсе Wildberries с анализом конкурентов",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтирование статических файлов
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Инициализация сервисов
optimizer_service = PriceOptimizerService(
    wb_api_key=Config.WB_API_KEY,
    ai_api_key=Config.OPENAI_API_KEY or Config.ANTHROPIC_API_KEY
)

competitor_analyzer = CompetitorAnalyzer(Config.WB_API_KEY)


@app.get("/", include_in_schema=False)
async def root():
    """Перенаправление на веб-интерфейс"""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    
    # Если нет веб-интерфейса, возвращаем JSON
    return {
        "name": "Wildberries Price Optimizer",
        "version": "2.0.0",
        "description": "AI-powered price optimization for Wildberries marketplace",
        "features": [
            "Анализ эластичности спроса",
            "Оптимизация цен с помощью AI",
            "Анализ цен конкурентов (500+ отзывов)",
            "Сравнение с аналогичными товарами",
            "Прогнозирование продаж и прибыли",
            "Автоматическое применение цен",
            "Работа с ценами со скидкой"
        ],
        "endpoints": {
            "products": "Управление товарами",
            "optimize": "Оптимизация цен",
            "competitors": "Анализ конкурентов",
            "analytics": "Аналитика"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {"status": "healthy", "timestamp": "2025-12-19"}


@app.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
async def add_product(
    product: ProductCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Добавить товар для отслеживания и оптимизации
    
    Args:
        product: Данные товара (current_price - это цена со скидкой!)
        session: Сессия БД
    
    Returns:
        Созданный товар
    """
    try:
        from database import DatabaseManager
        db_manager = DatabaseManager()
        
        # Проверка существования
        existing = await db_manager.get_product(session, product.nm_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Товар с артикулом {product.nm_id} уже существует"
            )
        
        # Добавление товара
        db_product = await db_manager.add_product(
            session,
            product_data=product.dict()
        )
        
        return Product(
            nm_id=db_product.nm_id,
            name=db_product.name,
            category=db_product.category,
            current_price=db_product.current_price,
            cost_price=db_product.cost_price
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка добавления товара: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/products", response_model=List[Product])
async def get_products(session: AsyncSession = Depends(get_session)):
    """
    Получить список всех товаров
    
    Args:
        session: Сессия БД
    
    Returns:
        Список товаров
    """
    try:
        from database import DatabaseManager
        db_manager = DatabaseManager()
        
        products = await db_manager.get_all_products(session)
        
        return [
            Product(
                nm_id=p.nm_id,
                name=p.name,
                category=p.category,
                current_price=p.current_price,
                cost_price=p.cost_price
            )
            for p in products
        ]
    
    except Exception as e:
        logger.error(f"Ошибка получения товаров: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/optimize/{nm_id}", response_model=OptimalPriceRecommendation)
async def optimize_single_product(
    nm_id: int,
    optimize_for: str = "profit",
    consider_competitors: bool = True,
    session: AsyncSession = Depends(get_session)
):
    """
    Оптимизировать цену одного товара с учетом конкурентов
    
    Args:
        nm_id: Артикул товара на Wildberries
        optimize_for: Цель оптимизации (profit, revenue, balanced)
        consider_competitors: Учитывать цены конкурентов (по умолчанию True)
        session: Сессия БД
    
    Returns:
        Рекомендации по оптимизации цены с анализом конкурентов
    """
    try:
        recommendation = await optimizer_service.optimize_product_price(
            session=session,
            nm_id=nm_id,
            optimize_for=optimize_for,
            consider_competitors=consider_competitors
        )
        
        return recommendation
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Ошибка оптимизации товара {nm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/optimize/bulk", response_model=BulkOptimizationResponse)
async def optimize_multiple_products(
    request: OptimizationRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Оптимизировать несколько товаров одновременно
    
    Args:
        request: Параметры оптимизации (включая consider_competitors)
        session: Сессия БД
    
    Returns:
        Результаты оптимизации для всех товаров с анализом конкурентов
    """
    try:
        result = await optimizer_service.optimize_multiple_products(
            session=session,
            request=request
        )
        
        return BulkOptimizationResponse(**result)
    
    except Exception as e:
        logger.error(f"Ошибка массовой оптимизации: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/competitors/analyze")
async def analyze_competitors(
    request: CompetitorAnalysisRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Анализ цен конкурентов для товара
    
    Находит аналогичные товары конкурентов в той же категории и с тем же размером,
    с количеством отзывов более указанного минимума (по умолчанию 500).
    Сравнивает цены со скидкой.
    
    Args:
        request: Параметры анализа (nm_id, min_reviews)
        session: Сессия БД
    
    Returns:
        Детальный анализ конкурентов с ценами
    """
    try:
        analysis = await competitor_analyzer.analyze_competitors(
            session=session,
            nm_id=request.nm_id,
            min_reviews=request.min_reviews
        )
        
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Не удалось проанализировать конкурентов для товара {request.nm_id}"
            )
        
        return analysis
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа конкурентов для товара {request.nm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/apply-price/{nm_id}")
async def apply_optimal_price(
    nm_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Применить оптимальную цену к товару на Wildberries
    
    Args:
        nm_id: Артикул товара
        session: Сессия БД
    
    Returns:
        Статус применения
    """
    try:
        success = await optimizer_service.apply_optimal_price(session, nm_id)
        
        if success:
            return {
                "success": True,
                "message": f"Цена товара {nm_id} успешно обновлена на Wildberries"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось обновить цену на Wildberries"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Ошибка применения цены для товара {nm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/analytics/{nm_id}")
async def get_product_analytics(
    nm_id: int,
    days: int = 30,
    session: AsyncSession = Depends(get_session)
):
    """
    Получить аналитику по товару
    
    Args:
        nm_id: Артикул товара
        days: Количество дней истории
        session: Сессия БД
    
    Returns:
        Аналитические данные (цены со скидкой)
    """
    try:
        from database import DatabaseManager
        db_manager = DatabaseManager()
        
        # Получение истории
        history = await db_manager.get_price_history(session, nm_id, days)
        
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Нет данных для товара {nm_id}"
            )
        
        # Расчет метрик
        prices = [h.price for h in history]
        sales = [h.sales_count for h in history]
        revenues = [h.revenue for h in history]
        
        analytics = {
            "nm_id": nm_id,
            "period_days": days,
            "data_points": len(history),
            "price": {
                "note": "Все цены указаны со скидкой",
                "current": prices[-1],
                "min": min(prices),
                "max": max(prices),
                "avg": round(sum(prices) / len(prices), 2)
            },
            "sales": {
                "total": sum(sales),
                "avg_daily": round(sum(sales) / len(sales), 1),
                "min_daily": min(sales),
                "max_daily": max(sales)
            },
            "revenue": {
                "total": round(sum(revenues), 2),
                "avg_daily": round(sum(revenues) / len(revenues), 2)
            },
            "history": [
                {
                    "date": h.date.isoformat(),
                    "price": h.price,
                    "sales": h.sales_count,
                    "revenue": h.revenue
                }
                for h in history
            ]
        }
        
        return analytics
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения аналитики для товара {nm_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
