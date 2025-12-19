"""
Работа с базой данных
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from datetime import datetime

from models import Base, ProductDB, PriceHistoryDB, OptimizationResultDB
from config import Config


# Создание async engine
engine = create_async_engine(
    Config.DATABASE_URL,
    echo=False,
    future=True
)

# Создание async session factory
async_session = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def init_db():
    """Инициализация базы данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получить сессию базы данных"""
    async with async_session() as session:
        yield session


class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    @staticmethod
    async def add_product(session: AsyncSession, product_data: dict) -> ProductDB:
        """Добавить товар в БД"""
        product = ProductDB(**product_data)
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product
    
    @staticmethod
    async def get_product(session: AsyncSession, nm_id: int) -> Optional[ProductDB]:
        """Получить товар по артикулу"""
        from sqlalchemy import select
        result = await session.execute(
            select(ProductDB).where(ProductDB.nm_id == nm_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_products(session: AsyncSession) -> List[ProductDB]:
        """Получить все товары"""
        from sqlalchemy import select
        result = await session.execute(select(ProductDB))
        return result.scalars().all()
    
    @staticmethod
    async def add_price_history(
        session: AsyncSession,
        nm_id: int,
        price: float,
        sales_count: int,
        revenue: float,
        date: datetime
    ):
        """Добавить запись в историю цен"""
        history = PriceHistoryDB(
            nm_id=nm_id,
            price=price,
            sales_count=sales_count,
            revenue=revenue,
            date=date
        )
        session.add(history)
        await session.commit()
    
    @staticmethod
    async def get_price_history(
        session: AsyncSession,
        nm_id: int,
        days: int = 30
    ) -> List[PriceHistoryDB]:
        """Получить историю цен товара"""
        from sqlalchemy import select
        from datetime import timedelta
        
        date_threshold = datetime.utcnow() - timedelta(days=days)
        
        result = await session.execute(
            select(PriceHistoryDB)
            .where(PriceHistoryDB.nm_id == nm_id)
            .where(PriceHistoryDB.date >= date_threshold)
            .order_by(PriceHistoryDB.date)
        )
        return result.scalars().all()
    
    @staticmethod
    async def save_optimization_result(
        session: AsyncSession,
        result_data: dict
    ) -> OptimizationResultDB:
        """Сохранить результат оптимизации"""
        result = OptimizationResultDB(**result_data)
        session.add(result)
        await session.commit()
        await session.refresh(result)
        return result
    
    @staticmethod
    async def get_latest_optimization(
        session: AsyncSession,
        nm_id: int
    ) -> Optional[OptimizationResultDB]:
        """Получить последний результат оптимизации"""
        from sqlalchemy import select, desc
        
        result = await session.execute(
            select(OptimizationResultDB)
            .where(OptimizationResultDB.nm_id == nm_id)
            .order_by(desc(OptimizationResultDB.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()
