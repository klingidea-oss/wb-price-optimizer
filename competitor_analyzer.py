"""
Анализатор цен конкурентов на Wildberries
"""
import logging
from typing import Dict, List, Optional
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class CompetitorAnalyzer:
    """Анализ цен конкурентов на аналогичные товары"""
    
    def __init__(self, api_key: str):
        """
        Инициализация анализатора конкурентов
        
        Args:
            api_key: API ключ Wildberries
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    
    async def analyze_competitors(
        self,
        session,
        nm_id: int,
        min_reviews: int = 500
    ) -> Dict:
        """
        Анализировать цены конкурентов на аналогичные товары
        
        Args:
            session: Сессия БД
            nm_id: Артикул нашего товара
            min_reviews: Минимальное количество отзывов у конкурентов
        
        Returns:
            Анализ конкурентов с ценами
        """
        logger.info(f"Анализ конкурентов для товара {nm_id}")
        
        # Получение информации о нашем товаре
        our_product = await self._get_product_details(nm_id)
        
        if not our_product:
            logger.warning(f"Не удалось получить информацию о товаре {nm_id}")
            return {}
        
        # Поиск аналогичных товаров
        competitors = await self._find_similar_products(
            our_product=our_product,
            min_reviews=min_reviews
        )
        
        if not competitors:
            logger.warning(f"Конкуренты для товара {nm_id} не найдены")
            return {
                "our_product": our_product,
                "competitors": [],
                "total_competitors": 0,
                "analysis": {
                    "message": "Конкуренты не найдены"
                }
            }
        
        # Анализ цен конкурентов
        analysis = self._analyze_competitor_prices(our_product, competitors)
        
        return {
            "our_product": {
                "nm_id": our_product["nm_id"],
                "name": our_product["name"],
                "price_with_discount": our_product["price_with_discount"],
                "original_price": our_product["original_price"],
                "discount_percent": our_product["discount_percent"],
                "category": our_product["category"],
                "size": our_product.get("size", "N/A"),
                "reviews_count": our_product.get("reviews_count", 0),
                "rating": our_product.get("rating", 0)
            },
            "competitors": competitors,
            "total_competitors": len(competitors),
            "analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _get_product_details(self, nm_id: int) -> Optional[Dict]:
        """
        Получить детальную информацию о товаре
        
        Args:
            nm_id: Артикул товара
        
        Returns:
            Информация о товаре
        """
        try:
            # Используем публичный API Wildberries для получения информации
            url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("data") or not data["data"].get("products"):
                    return None
                
                product = data["data"]["products"][0]
                
                # Извлечение данных
                salePriceU = product.get("salePriceU", 0) / 100  # Цена со скидкой
                priceU = product.get("priceU", 0) / 100  # Цена без скидки
                
                discount_percent = 0
                if priceU > 0:
                    discount_percent = round(((priceU - salePriceU) / priceU) * 100, 1)
                
                # Получение размеров
                sizes = []
                if "sizes" in product:
                    sizes = [size.get("origName", "") for size in product["sizes"]]
                
                return {
                    "nm_id": nm_id,
                    "name": product.get("name", ""),
                    "brand": product.get("brand", ""),
                    "category": product.get("subjectName", ""),
                    "price_with_discount": salePriceU,
                    "original_price": priceU,
                    "discount_percent": discount_percent,
                    "rating": product.get("rating", 0),
                    "reviews_count": product.get("feedbacks", 0),
                    "size": sizes[0] if sizes else "N/A",
                    "available_sizes": sizes,
                    "supplier_id": product.get("supplierId", 0)
                }
        
        except Exception as e:
            logger.error(f"Ошибка получения информации о товаре {nm_id}: {e}")
            return None
    
    async def _find_similar_products(
        self,
        our_product: Dict,
        min_reviews: int = 500
    ) -> List[Dict]:
        """
        Найти аналогичные товары конкурентов
        
        Args:
            our_product: Данные нашего товара
            min_reviews: Минимальное количество отзывов
        
        Returns:
            Список товаров конкурентов
        """
        try:
            category = our_product.get("category", "")
            brand = our_product.get("brand", "")
            
            # Поиск по категории через API поиска WB
            search_query = category
            
            # URL поиска Wildberries
            url = f"https://search.wb.ru/exactmatch/ru/common/v4/search"
            
            params = {
                "appType": 1,
                "curr": "rub",
                "dest": -1257786,
                "query": search_query,
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30,
                "suppressSpellcheck": False
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("data") or not data["data"].get("products"):
                    logger.warning(f"Товары в категории '{category}' не найдены")
                    return []
                
                products = data["data"]["products"]
                competitors = []
                
                our_nm_id = our_product.get("nm_id")
                our_size = our_product.get("size", "")
                our_supplier = our_product.get("supplier_id", 0)
                
                for product in products:
                    nm_id = product.get("id")
                    
                    # Исключаем наш товар и товары нашего поставщика
                    if nm_id == our_nm_id:
                        continue
                    
                    supplier_id = product.get("supplierId", 0)
                    if supplier_id == our_supplier:
                        continue
                    
                    # Проверка количества отзывов
                    reviews_count = product.get("feedbacks", 0)
                    if reviews_count < min_reviews:
                        continue
                    
                    # Проверка наличия размера
                    sizes = []
                    if "sizes" in product:
                        sizes = [size.get("origName", "") for size in product["sizes"]]
                    
                    # Если у нас указан размер, ищем товары с таким же размером
                    if our_size and our_size != "N/A":
                        if our_size not in sizes:
                            continue
                    
                    # Извлечение цен
                    salePriceU = product.get("salePriceU", 0) / 100
                    priceU = product.get("priceU", 0) / 100
                    
                    if salePriceU == 0:
                        continue
                    
                    discount_percent = 0
                    if priceU > 0:
                        discount_percent = round(((priceU - salePriceU) / priceU) * 100, 1)
                    
                    competitor = {
                        "nm_id": nm_id,
                        "name": product.get("name", ""),
                        "brand": product.get("brand", ""),
                        "price_with_discount": salePriceU,
                        "original_price": priceU,
                        "discount_percent": discount_percent,
                        "rating": product.get("rating", 0),
                        "reviews_count": reviews_count,
                        "size": sizes[0] if sizes else "N/A",
                        "available_sizes": sizes,
                        "supplier_id": supplier_id
                    }
                    
                    competitors.append(competitor)
                    
                    # Ограничение на количество конкурентов
                    if len(competitors) >= 20:
                        break
                
                logger.info(f"Найдено {len(competitors)} конкурентов")
                return competitors
        
        except Exception as e:
            logger.error(f"Ошибка поиска конкурентов: {e}")
            return []
    
    def _analyze_competitor_prices(
        self,
        our_product: Dict,
        competitors: List[Dict]
    ) -> Dict:
        """
        Анализ цен конкурентов
        
        Args:
            our_product: Наш товар
            competitors: Список конкурентов
        
        Returns:
            Анализ цен
        """
        if not competitors:
            return {}
        
        our_price = our_product.get("price_with_discount", 0)
        competitor_prices = [c["price_with_discount"] for c in competitors]
        
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        avg_price = sum(competitor_prices) / len(competitor_prices)
        median_price = sorted(competitor_prices)[len(competitor_prices) // 2]
        
        # Наша позиция относительно конкурентов
        cheaper_than_us = len([p for p in competitor_prices if p < our_price])
        more_expensive_than_us = len([p for p in competitor_prices if p > our_price])
        
        position_percentile = (cheaper_than_us / len(competitors)) * 100
        
        # Определение позиции
        if position_percentile < 25:
            price_position = "Очень низкая цена (дешевле 75% конкурентов)"
        elif position_percentile < 50:
            price_position = "Ниже средней (дешевле 50-75% конкурентов)"
        elif position_percentile < 75:
            price_position = "Выше средней (дороже 50-75% конкурентов)"
        else:
            price_position = "Высокая цена (дороже 75% конкурентов)"
        
        # Рекомендации по конкурентному ценообразованию
        recommendations = []
        
        if our_price > median_price * 1.2:
            recommendations.append(
                f"Ваша цена на 20%+ выше медианы рынка ({median_price:.2f} руб). "
                f"Рассмотрите снижение для повышения конкурентоспособности."
            )
        elif our_price < median_price * 0.8:
            recommendations.append(
                f"Ваша цена на 20%+ ниже медианы рынка ({median_price:.2f} руб). "
                f"Возможность повысить цену без потери конкурентоспособности."
            )
        else:
            recommendations.append(
                f"Ваша цена в пределах рыночной медианы ({median_price:.2f} руб). "
                f"Цена конкурентоспособна."
            )
        
        # Оптимальный диапазон для позиционирования
        optimal_low = median_price * 0.95  # 5% ниже медианы
        optimal_high = median_price * 1.05  # 5% выше медианы
        
        analysis = {
            "our_price": our_price,
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": round(avg_price, 2),
            "median_price": round(median_price, 2),
            "price_range": {
                "min": min_price,
                "max": max_price,
                "spread": round(max_price - min_price, 2)
            },
            "our_position": {
                "cheaper_competitors": cheaper_than_us,
                "more_expensive_competitors": more_expensive_than_us,
                "percentile": round(position_percentile, 1),
                "position_description": price_position
            },
            "price_comparison": {
                "vs_min": round(((our_price - min_price) / min_price) * 100, 1),
                "vs_avg": round(((our_price - avg_price) / avg_price) * 100, 1),
                "vs_median": round(((our_price - median_price) / median_price) * 100, 1),
                "vs_max": round(((our_price - max_price) / max_price) * 100, 1)
            },
            "optimal_range": {
                "low": round(optimal_low, 2),
                "high": round(optimal_high, 2),
                "description": "Оптимальный диапазон ±5% от медианы"
            },
            "recommendations": recommendations,
            "top_competitors": sorted(
                competitors,
                key=lambda x: x["reviews_count"],
                reverse=True
            )[:5]  # Топ-5 по количеству отзывов
        }
        
        return analysis
    
    async def get_competitor_details_batch(
        self,
        nm_ids: List[int]
    ) -> List[Dict]:
        """
        Получить детальную информацию о нескольких товарах конкурентов
        
        Args:
            nm_ids: Список артикулов
        
        Returns:
            Список с информацией о товарах
        """
        products = []
        
        for nm_id in nm_ids:
            product = await self._get_product_details(nm_id)
            if product:
                products.append(product)
        
        return products
