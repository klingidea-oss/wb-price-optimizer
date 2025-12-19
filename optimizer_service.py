"""
Сервис оптимизации цен
"""
import logging
from typing import List, Optional, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Product, PricePoint, OptimalPriceRecommendation,
    ElasticityAnalysis, OptimizationRequest
)
from wb_api_client import WildberriesAPIClient
from elasticity_analyzer import ElasticityAnalyzer
from ai_agent import PricingAIAgent
from database import DatabaseManager
from competitor_analyzer import CompetitorAnalyzer
from config import Config

logger = logging.getLogger(__name__)


class PriceOptimizerService:
    """Сервис для оптимизации цен на товары"""
    
    def __init__(self, wb_api_key: str, ai_api_key: Optional[str] = None):
        """
        Инициализация сервиса
        
        Args:
            wb_api_key: API ключ Wildberries
            ai_api_key: API ключ для AI агента
        """
        self.wb_client = WildberriesAPIClient(wb_api_key)
        self.ai_agent = PricingAIAgent(ai_api_key)
        self.elasticity_analyzer = ElasticityAnalyzer()
        self.competitor_analyzer = CompetitorAnalyzer(wb_api_key)
        self.db_manager = DatabaseManager()
    
    async def optimize_product_price(
        self,
        session: AsyncSession,
        nm_id: int,
        optimize_for: str = "profit",
        consider_competitors: bool = True
    ) -> OptimalPriceRecommendation:
        """
        Оптимизировать цену одного товара
        
        Args:
            session: Сессия БД
            nm_id: Артикул товара
            optimize_for: Цель оптимизации (profit, revenue, balanced)
            consider_competitors: Учитывать цены конкурентов
        
        Returns:
            Рекомендации по оптимизации
        """
        logger.info(f"Начало оптимизации товара {nm_id}")
        
        # Получение данных о товаре
        product = await self.db_manager.get_product(session, nm_id)
        if not product:
            raise ValueError(f"Товар {nm_id} не найден в базе данных")
        
        # Получение истории продаж (используем цены со скидкой)
        sales_history = await self.wb_client.get_sales_history(
            nm_id, 
            days=Config.ELASTICITY_WINDOW_DAYS
        )
        
        if len(sales_history) < Config.MIN_DATA_POINTS:
            logger.warning(f"Недостаточно данных для товара {nm_id}")
            raise ValueError(
                f"Недостаточно исторических данных. "
                f"Требуется минимум {Config.MIN_DATA_POINTS} точек, "
                f"получено {len(sales_history)}"
            )
        
        # Сохранение истории в БД
        for record in sales_history:
            await self.db_manager.add_price_history(
                session,
                nm_id=nm_id,
                price=record["price_with_discount"],  # Цена со скидкой!
                sales_count=record["sales_count"],
                revenue=record["revenue"],
                date=record["date"]
            )
        
        # Преобразование в PricePoint
        price_points = [
            PricePoint(
                date=record["date"],
                price=record["price_with_discount"],  # Цена со скидкой!
                sales_count=record["sales_count"],
                revenue=record["revenue"]
            )
            for record in sales_history
        ]
        
        # Анализ конкурентов
        competitor_data = None
        if consider_competitors:
            try:
                competitor_data = await self.competitor_analyzer.analyze_competitors(
                    session=session,
                    nm_id=nm_id,
                    min_reviews=500
                )
                logger.info(f"Найдено {competitor_data['total_competitors']} конкурентов для товара {nm_id}")
            except Exception as e:
                logger.warning(f"Ошибка анализа конкурентов: {e}")
                competitor_data = None
        
        # Анализ эластичности
        elasticity_analysis = self.elasticity_analyzer.calculate_price_elasticity(
            price_points
        )
        
        # Расчет оптимальной цены с учетом конкурентов
        optimal_price, price_details = self.elasticity_analyzer.calculate_optimal_price(
            price_points=price_points,
            cost_price=product.cost_price,
            elasticity_analysis=elasticity_analysis,
            optimize_for=optimize_for,
            competitor_data=competitor_data
        )
        
        # Текущие метрики (средние за последние 7 дней)
        recent_points = price_points[-7:] if len(price_points) >= 7 else price_points
        current_daily_sales = sum(p.sales_count for p in recent_points) // len(recent_points)
        current_daily_revenue = sum(p.revenue for p in recent_points) / len(recent_points)
        current_daily_profit = (product.current_price - product.cost_price) * current_daily_sales
        
        # Прогнозные метрики
        predicted_daily_sales = price_details.get("predicted_sales", current_daily_sales)
        predicted_daily_revenue = price_details.get("predicted_revenue", 0)
        predicted_daily_profit = price_details.get("predicted_profit", 0)
        
        # Изменение цены в процентах
        price_change_percent = ((optimal_price - product.current_price) / product.current_price) * 100
        
        # AI анализ с учетом конкурентов
        product_data = {
            "name": product.name,
            "category": product.category,
            "cost_price": product.cost_price,
            "current_sales": current_daily_sales,
            "predicted_sales": predicted_daily_sales,
            "current_profit": current_daily_profit,
            "predicted_profit": predicted_daily_profit,
            "competitor_data": competitor_data
        }
        
        ai_insights = await self.ai_agent.analyze_pricing_strategy(
            product_data=product_data,
            elasticity=elasticity_analysis,
            optimal_price=optimal_price,
            current_price=product.current_price,
            market_context=competitor_data
        )
        
        # Альтернативные сценарии с учетом конкурентов
        alternative_scenarios = self._generate_alternative_scenarios(
            price_points=price_points,
            current_price=product.current_price,
            optimal_price=optimal_price,
            cost_price=product.cost_price,
            elasticity=elasticity_analysis.elasticity_coefficient,
            competitor_data=competitor_data
        )
        
        # Формирование рекомендации
        recommendation = OptimalPriceRecommendation(
            nm_id=nm_id,
            product_name=product.name,
            current_price=product.current_price,
            optimal_price=optimal_price,
            price_change_percent=price_change_percent,
            current_daily_sales=current_daily_sales,
            predicted_daily_sales=predicted_daily_sales,
            current_daily_revenue=current_daily_revenue,
            predicted_daily_revenue=predicted_daily_revenue,
            current_daily_profit=current_daily_profit,
            predicted_daily_profit=predicted_daily_profit,
            elasticity=elasticity_analysis,
            recommendation=ai_insights.get("recommendation", ""),
            risk_level=ai_insights.get("risk_level", "medium"),
            ai_insights=ai_insights,
            alternative_scenarios=alternative_scenarios,
            competitor_analysis=competitor_data
        )
        
        # Сохранение результата в БД
        await self.db_manager.save_optimization_result(
            session,
            result_data={
                "nm_id": nm_id,
                "current_price": product.current_price,
                "optimal_price": optimal_price,
                "predicted_revenue": predicted_daily_revenue,
                "predicted_profit": predicted_daily_profit,
                "predicted_sales": predicted_daily_sales,
                "elasticity_coefficient": elasticity_analysis.elasticity_coefficient,
                "confidence_score": elasticity_analysis.confidence,
                "recommendation": recommendation.recommendation,
                "ai_insights": ai_insights,
                "competitor_data": competitor_data
            }
        )
        
        logger.info(f"Оптимизация товара {nm_id} завершена")
        return recommendation
    
    async def optimize_multiple_products(
        self,
        session: AsyncSession,
        request: OptimizationRequest
    ) -> Dict:
        """
        Оптимизировать несколько товаров
        
        Args:
            session: Сессия БД
            request: Параметры оптимизации
        
        Returns:
            Результаты оптимизации
        """
        # Определение списка товаров
        if request.nm_ids:
            products = []
            for nm_id in request.nm_ids:
                product = await self.db_manager.get_product(session, nm_id)
                if product:
                    products.append(product)
        else:
            products = await self.db_manager.get_all_products(session)
        
        logger.info(f"Начало оптимизации {len(products)} товаров")
        
        recommendations = []
        total_profit_increase = 0
        total_revenue_increase = 0
        
        for product in products:
            try:
                recommendation = await self.optimize_product_price(
                    session,
                    product.nm_id,
                    optimize_for=request.optimize_for,
                    consider_competitors=request.consider_competitors
                )
                
                # Фильтрация по минимальной уверенности
                if recommendation.elasticity.confidence >= request.min_confidence:
                    recommendations.append(recommendation)
                    
                    profit_increase = (
                        recommendation.predicted_daily_profit - 
                        recommendation.current_daily_profit
                    )
                    revenue_increase = (
                        recommendation.predicted_daily_revenue - 
                        recommendation.current_daily_revenue
                    )
                    
                    total_profit_increase += profit_increase
                    total_revenue_increase += revenue_increase
                
            except Exception as e:
                logger.error(f"Ошибка оптимизации товара {product.nm_id}: {e}")
                continue
        
        logger.info(f"Оптимизация завершена. Обработано {len(recommendations)} товаров")
        
        return {
            "total_products": len(products),
            "optimized_products": len(recommendations),
            "total_potential_profit_increase": total_profit_increase,
            "total_potential_revenue_increase": total_revenue_increase,
            "recommendations": recommendations
        }
    
    async def apply_optimal_price(
        self,
        session: AsyncSession,
        nm_id: int
    ) -> bool:
        """
        Применить оптимальную цену к товару на Wildberries
        
        Args:
            session: Сессия БД
            nm_id: Артикул товара
        
        Returns:
            True если успешно применено
        """
        # Получение последней рекомендации
        optimization = await self.db_manager.get_latest_optimization(session, nm_id)
        
        if not optimization:
            raise ValueError(f"Нет рекомендаций по оптимизации для товара {nm_id}")
        
        # Применение цены через API WB
        success = await self.wb_client.update_product_price(
            nm_id, 
            optimization.optimal_price
        )
        
        if success:
            # Обновление статуса в БД
            optimization.applied = True
            await session.commit()
            
            # Обновление текущей цены товара
            product = await self.db_manager.get_product(session, nm_id)
            if product:
                product.current_price = optimization.optimal_price
                await session.commit()
            
            logger.info(f"Цена товара {nm_id} успешно обновлена")
        
        return success
    
    def _generate_alternative_scenarios(
        self,
        price_points: List[PricePoint],
        current_price: float,
        optimal_price: float,
        cost_price: float,
        elasticity: float,
        competitor_data: Optional[Dict] = None
    ) -> List[Dict]:
        """Генерация альтернативных ценовых сценариев"""
        
        scenarios = []
        
        # Сценарий 1: Консервативный (меньшее изменение)
        conservative_price = current_price + (optimal_price - current_price) * 0.5
        conservative_sales, _ = self.elasticity_analyzer.predict_sales_at_price(
            price_points, conservative_price, elasticity
        )
        scenarios.append({
            "name": "Консервативный",
            "price": round(conservative_price, 2),
            "predicted_sales": conservative_sales,
            "predicted_profit": round((conservative_price - cost_price) * conservative_sales, 2),
            "description": "Умеренное изменение цены для снижения рисков"
        })
        
        # Сценарий 2: Агрессивный (большее изменение)
        if optimal_price > current_price:
            aggressive_price = optimal_price * 1.1
        else:
            aggressive_price = optimal_price * 0.95
        
        aggressive_sales, _ = self.elasticity_analyzer.predict_sales_at_price(
            price_points, aggressive_price, elasticity
        )
        scenarios.append({
            "name": "Агрессивный",
            "price": round(aggressive_price, 2),
            "predicted_sales": aggressive_sales,
            "predicted_profit": round((aggressive_price - cost_price) * aggressive_sales, 2),
            "description": "Максимальное изменение для быстрых результатов"
        })
        
        # Сценарий 3: Фокус на обороте
        revenue_focused_price = current_price * 0.9 if optimal_price < current_price else current_price * 1.05
        revenue_sales, _ = self.elasticity_analyzer.predict_sales_at_price(
            price_points, revenue_focused_price, elasticity
        )
        scenarios.append({
            "name": "Фокус на обороте",
            "price": round(revenue_focused_price, 2),
            "predicted_sales": revenue_sales,
            "predicted_revenue": round(revenue_focused_price * revenue_sales, 2),
            "description": "Максимизация общего оборота"
        })
        
        # Сценарий 4: Конкурентный (если есть данные о конкурентах)
        if competitor_data and competitor_data.get("competitors"):
            avg_competitor_price = competitor_data.get("avg_price", current_price)
            # Цена чуть ниже средней у конкурентов (на 5%)
            competitive_price = avg_competitor_price * 0.95
            competitive_sales, _ = self.elasticity_analyzer.predict_sales_at_price(
                price_points, competitive_price, elasticity
            )
            scenarios.append({
                "name": "Конкурентный",
                "price": round(competitive_price, 2),
                "predicted_sales": competitive_sales,
                "predicted_profit": round((competitive_price - cost_price) * competitive_sales, 2),
                "description": f"Цена ниже средней конкурентов ({avg_competitor_price:.2f} руб) на 5%"
            })
        
        return scenarios
