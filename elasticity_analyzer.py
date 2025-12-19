"""
Анализатор эластичности спроса
"""
import numpy as np
from scipy import stats
from typing import List, Tuple, Optional, Dict
import logging

from models import PricePoint, ElasticityAnalysis

logger = logging.getLogger(__name__)


class ElasticityAnalyzer:
    """Анализатор эластичности спроса по цене"""
    
    @staticmethod
    def calculate_price_elasticity(price_points: List[PricePoint]) -> ElasticityAnalysis:
        """
        Рассчитать коэффициент эластичности спроса
        
        Формула: E = (ΔQ/Q) / (ΔP/P)
        где E > 1 - эластичный спрос
            E < 1 - неэластичный спрос
        
        Args:
            price_points: Исторические данные о ценах и продажах
        
        Returns:
            Результаты анализа эластичности
        """
        if len(price_points) < 3:
            return ElasticityAnalysis(
                elasticity_coefficient=0.0,
                is_elastic=False,
                confidence=0.0,
                data_points=len(price_points)
            )
        
        # Сортировка по дате
        sorted_points = sorted(price_points, key=lambda x: x.date)
        
        # Извлечение данных
        prices = np.array([p.price for p in sorted_points])
        sales = np.array([p.sales_count for p in sorted_points])
        
        # Фильтрация нулевых значений
        valid_mask = (sales > 0) & (prices > 0)
        prices = prices[valid_mask]
        sales = sales[valid_mask]
        
        if len(prices) < 3:
            return ElasticityAnalysis(
                elasticity_coefficient=0.0,
                is_elastic=False,
                confidence=0.0,
                data_points=len(prices)
            )
        
        # Логарифмическая регрессия для более точной оценки
        # ln(Q) = a + b*ln(P), где b - коэффициент эластичности
        log_prices = np.log(prices)
        log_sales = np.log(sales)
        
        # Линейная регрессия на логарифмах
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_prices, log_sales)
        
        # Коэффициент эластичности (отрицательный по природе)
        elasticity_coefficient = abs(slope)
        
        # Уровень уверенности основан на R²
        confidence = r_value ** 2
        
        # Спрос считается эластичным если |E| > 1
        is_elastic = elasticity_coefficient > 1.0
        
        logger.info(f"Эластичность: {elasticity_coefficient:.2f}, "
                   f"Уверенность: {confidence:.2f}, "
                   f"Точек данных: {len(prices)}")
        
        return ElasticityAnalysis(
            elasticity_coefficient=elasticity_coefficient,
            is_elastic=is_elastic,
            confidence=confidence,
            data_points=len(prices)
        )
    
    @staticmethod
    def predict_sales_at_price(
        price_points: List[PricePoint],
        target_price: float,
        elasticity: Optional[float] = None
    ) -> Tuple[int, float]:
        """
        Прогнозировать объем продаж при заданной цене
        
        Args:
            price_points: Исторические данные
            target_price: Целевая цена
            elasticity: Коэффициент эластичности (если уже рассчитан)
        
        Returns:
            Кортеж (прогноз продаж, уровень уверенности)
        """
        if not price_points:
            return 0, 0.0
        
        prices = np.array([p.price for p in price_points])
        sales = np.array([p.sales_count for p in price_points])
        
        # Фильтрация
        valid_mask = (sales > 0) & (prices > 0)
        prices = prices[valid_mask]
        sales = sales[valid_mask]
        
        if len(prices) < 2:
            return 0, 0.0
        
        # Средние значения для расчета
        avg_price = np.mean(prices)
        avg_sales = np.mean(sales)
        
        # Если эластичность не предоставлена, используем простую оценку
        if elasticity is None:
            price_changes = np.diff(prices) / prices[:-1]
            sales_changes = np.diff(sales) / sales[:-1]
            
            if len(price_changes) > 0:
                # Средняя эластичность по изменениям
                elasticity = np.mean(np.abs(sales_changes / (price_changes + 1e-10)))
            else:
                elasticity = 1.0
        
        # Прогноз на основе эластичности
        # Q_new = Q_old * (P_new / P_old) ^ (-elasticity)
        price_ratio = target_price / avg_price
        predicted_sales = avg_sales * (price_ratio ** (-elasticity))
        
        # Уверенность снижается при удалении от средней цены
        price_deviation = abs(target_price - avg_price) / avg_price
        confidence = max(0.3, 1.0 - price_deviation)
        
        return int(predicted_sales), confidence
    
    @staticmethod
    def calculate_optimal_price(
        price_points: List[PricePoint],
        cost_price: float,
        elasticity_analysis: ElasticityAnalysis,
        optimize_for: str = "profit",
        competitor_data: Optional[Dict] = None
    ) -> Tuple[float, dict]:
        """
        Рассчитать оптимальную цену с учетом конкурентов
        
        Args:
            price_points: Исторические данные
            cost_price: Себестоимость товара
            elasticity_analysis: Результаты анализа эластичности
            optimize_for: Цель оптимизации (profit, revenue, balanced)
            competitor_data: Данные о ценах конкурентов
        
        Returns:
            Кортеж (оптимальная цена, детали расчета)
        """
        if not price_points:
            return cost_price * 1.5, {}
        
        prices = np.array([p.price for p in price_points])
        current_avg_price = np.mean(prices)
        
        # Определение диапазона цен для тестирования
        price_min = max(cost_price * 1.1, current_avg_price * 0.7)
        price_max = current_avg_price * 1.5
        
        # Учет цен конкурентов
        if competitor_data and competitor_data.get("analysis"):
            analysis = competitor_data["analysis"]
            median_price = analysis.get("median_price", current_avg_price)
            
            # Расширяем диапазон с учетом конкурентов
            price_min = max(cost_price * 1.1, median_price * 0.8)
            price_max = median_price * 1.2
            
            logger.info(f"Учет конкурентов: медиана = {median_price:.2f}, "
                       f"диапазон [{price_min:.2f}, {price_max:.2f}]")
        
        test_prices = np.linspace(price_min, price_max, 50)
        
        best_price = current_avg_price
        best_score = 0
        best_details = {}
        
        elasticity = elasticity_analysis.elasticity_coefficient
        
        for test_price in test_prices:
            # Прогноз продаж
            predicted_sales, confidence = ElasticityAnalyzer.predict_sales_at_price(
                price_points, test_price, elasticity
            )
            
            # Расчет метрик
            predicted_revenue = test_price * predicted_sales
            predicted_profit = (test_price - cost_price) * predicted_sales
            
            # Базовый скоринг в зависимости от цели
            if optimize_for == "profit":
                score = predicted_profit * confidence
            elif optimize_for == "revenue":
                score = predicted_revenue * confidence
            else:  # balanced
                margin_rate = (test_price - cost_price) / test_price
                score = predicted_profit * 0.6 + predicted_revenue * 0.4
                score *= confidence * (0.8 + 0.2 * margin_rate)
            
            # Бонус за конкурентоспособность
            if competitor_data and competitor_data.get("analysis"):
                analysis = competitor_data["analysis"]
                median_price = analysis.get("median_price", current_avg_price)
                
                # Если цена близка к медиане рынка (±10%), даем бонус
                price_diff_pct = abs(test_price - median_price) / median_price
                if price_diff_pct < 0.10:
                    score *= 1.15  # +15% за конкурентоспособность
                # Если цена немного ниже медианы (5-15%), еще больший бонус
                elif test_price < median_price and 0.05 < (median_price - test_price) / median_price < 0.15:
                    score *= 1.25  # +25% за привлекательность для покупателей
            
            if score > best_score:
                best_score = score
                best_price = test_price
                best_details = {
                    "predicted_sales": predicted_sales,
                    "predicted_revenue": predicted_revenue,
                    "predicted_profit": predicted_profit,
                    "confidence": confidence,
                    "margin_rate": (test_price - cost_price) / test_price
                }
        
        # Добавляем информацию о позиции относительно конкурентов
        if competitor_data and competitor_data.get("analysis"):
            analysis = competitor_data["analysis"]
            median_price = analysis.get("median_price", 0)
            
            if median_price > 0:
                best_details["vs_market_median"] = round(
                    ((best_price - median_price) / median_price) * 100, 1
                )
        
        logger.info(f"Оптимальная цена: {best_price:.2f}, "
                   f"Прогноз прибыли: {best_details.get('predicted_profit', 0):.2f}")
        
        return best_price, best_details
