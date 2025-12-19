"""
Клиент для работы с API Wildberries
"""
import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from config import Config

logger = logging.getLogger(__name__)


class WildberriesAPIClient:
    """Клиент для работы с API Wildberries"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = Config.WB_API_BASE_URL
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    
    async def get_product_statistics(
        self, 
        nm_id: int, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict:
        """
        Получить статистику по товару
        
        Args:
            nm_id: Артикул товара
            date_from: Начальная дата
            date_to: Конечная дата
        
        Returns:
            Словарь со статистикой товара
        """
        if not date_from:
            date_from = datetime.now() - timedelta(days=Config.ELASTICITY_WINDOW_DAYS)
        if not date_to:
            date_to = datetime.now()
        
        params = {
            "nmID": nm_id,
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d")
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    Config.WB_STATISTICS_URL,
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Ошибка при получении статистики для {nm_id}: {e}")
            return {}
    
    async def get_product_info(self, nm_id: int) -> Dict:
        """
        Получить информацию о товаре
        
        Args:
            nm_id: Артикул товара
        
        Returns:
            Информация о товаре
        """
        url = f"{self.base_url}/content/v1/cards/filter"
        
        payload = {
            "vendorCodes": [str(nm_id)]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                if data and "data" in data and len(data["data"]) > 0:
                    return data["data"][0]
                return {}
        except httpx.HTTPError as e:
            logger.error(f"Ошибка при получении информации о товаре {nm_id}: {e}")
            return {}
    
    async def update_product_price(self, nm_id: int, new_price: float) -> bool:
        """
        Обновить цену товара (цена со скидкой)
        
        Args:
            nm_id: Артикул товара
            new_price: Новая цена со скидкой
        
        Returns:
            True если обновление успешно
        """
        url = Config.WB_PRICES_URL
        
        payload = [{
            "nmId": nm_id,
            "price": int(new_price * 100)  # Цена в копейках
        }]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                logger.info(f"Цена товара {nm_id} обновлена на {new_price}")
                return True
        except httpx.HTTPError as e:
            logger.error(f"Ошибка при обновлении цены товара {nm_id}: {e}")
            return False
    
    async def get_sales_history(
        self, 
        nm_id: int,
        days: int = 30
    ) -> List[Dict]:
        """
        Получить историю продаж товара (с ценами со скидкой!)
        
        Args:
            nm_id: Артикул товара
            days: Количество дней истории
        
        Returns:
            Список с историей продаж (включая цены со скидкой)
        """
        date_from = datetime.now() - timedelta(days=days)
        stats = await self.get_product_statistics(nm_id, date_from)
        
        # Парсинг ответа зависит от структуры API WB
        sales_history = []
        
        if "data" in stats:
            for record in stats["data"]:
                # ВАЖНО: используем цену со скидкой (finishedPrice)
                price_with_discount = record.get("finishedPrice", 0) / 100
                original_price = record.get("price", 0) / 100
                
                # Если finishedPrice нет, используем price
                if price_with_discount == 0:
                    price_with_discount = original_price
                
                sales_history.append({
                    "date": datetime.fromisoformat(record.get("date", "")),
                    "price_with_discount": price_with_discount,  # Цена со скидкой!
                    "original_price": original_price,
                    "sales_count": record.get("quantity", 0),
                    "revenue": record.get("retail_amount", 0) / 100
                })
        
        return sales_history
    
    async def get_product_card_details(self, nm_id: int) -> Dict:
        """
        Получить детальную информацию о карточке товара
        Включая текущие цены со скидкой
        
        Args:
            nm_id: Артикул товара
        
        Returns:
            Детальная информация о товаре
        """
        try:
            # Публичный API для получения карточки товара
            url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("data") or not data["data"].get("products"):
                    return {}
                
                product = data["data"]["products"][0]
                
                # Извлечение цен
                price_with_discount = product.get("salePriceU", 0) / 100  # Цена со скидкой
                original_price = product.get("priceU", 0) / 100  # Цена без скидки
                
                discount_percent = 0
                if original_price > 0:
                    discount_percent = round(((original_price - price_with_discount) / original_price) * 100, 1)
                
                return {
                    "nm_id": nm_id,
                    "name": product.get("name", ""),
                    "brand": product.get("brand", ""),
                    "category": product.get("subjectName", ""),
                    "price_with_discount": price_with_discount,
                    "original_price": original_price,
                    "discount_percent": discount_percent,
                    "rating": product.get("rating", 0),
                    "reviews_count": product.get("feedbacks", 0),
                    "supplier_id": product.get("supplierId", 0)
                }
        
        except Exception as e:
            logger.error(f"Ошибка получения карточки товара {nm_id}: {e}")
            return {}
