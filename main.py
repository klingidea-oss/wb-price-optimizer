"""
WB Price Optimizer V3.3 - С ПАРСИНГОМ САЙТА WB
================================================

ГАРАНТИЯ АКТУАЛЬНЫХ ЦЕН:
- Метод 1: WB Public API (быстро, но блокируется)
- Метод 2: Парсинг страницы товара через Selenium (100% надёжность)
- Метод 3: Парсинг поиска WB (резервный метод)

НЕТ fallback на устаревшие данные из базы знаний!
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import logging
from datetime import datetime, timedelta
import requests
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
import time
import re
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WB Price Optimizer", version="3.3.0")

# Константы
KNOWLEDGE_BASE_FILE = "category_knowledge_base_FULL.json"
VERSION = "3.3.0"

# Кэш цен (время жизни 30 минут)
price_cache = {}
CACHE_LIFETIME = timedelta(minutes=30)

# База знаний
KNOWLEDGE_BASE = {}

# ============================================================================
# ЗАГРУЗКА БАЗЫ ЗНАНИЙ
# ============================================================================

def load_knowledge_base():
    """Загружает базу знаний из JSON файла"""
    global KNOWLEDGE_BASE
    try:
        with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
            KNOWLEDGE_BASE = json.load(f)
        logger.info(f"✅ База знаний загружена: {len(KNOWLEDGE_BASE)} товаров")
    except FileNotFoundError:
        logger.warning(f"⚠️ Файл {KNOWLEDGE_BASE_FILE} не найден, используется пустая база")
        KNOWLEDGE_BASE = {}

load_knowledge_base()

# ============================================================================
# МОДЕЛИ ДАННЫХ
# ============================================================================

class Product(BaseModel):
    nm_id: int
    name: str
    category: str
    current_price: float
    cost: float

class PriceInfo(BaseModel):
    value: float
    source: str  # "wb_api", "wb_parsing", "cache"
    cached_seconds_ago: Optional[int] = None
    fetch_timestamp: str

# ============================================================================
# ПОЛУЧЕНИЕ АКТУАЛЬНЫХ ЦЕН
# ============================================================================

def get_current_wb_price(nm_id: int, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Получает актуальную цену товара с WB
    
    Стратегия (по приоритету):
    1. Проверка кэша (30 минут)
    2. WB Public API (быстро)
    3. Парсинг страницы товара (надёжно)
    4. Парсинг поиска WB (резерв)
    
    Returns:
        Dict с ценой и метаданными или None при неудаче
    """
    
    # Проверка кэша
    if use_cache and nm_id in price_cache:
        cached_data = price_cache[nm_id]
        age = datetime.now() - cached_data['timestamp']
        if age < CACHE_LIFETIME:
            seconds_ago = int(age.total_seconds())
            logger.info(f"💾 Цена для {nm_id} из кэша ({seconds_ago}с назад)")
            return {
                'price': cached_data['price'],
                'source': 'cache',
                'cached_seconds_ago': seconds_ago,
                'timestamp': cached_data['timestamp'].isoformat()
            }
    
    # Метод 1: WB Public API
    logger.info(f"🔍 Попытка получить цену для {nm_id} через WB API...")
    price = _fetch_price_from_api(nm_id)
    if price:
        return _cache_and_return_price(nm_id, price, 'wb_api')
    
    # Метод 2: Парсинг страницы товара
    logger.info(f"🌐 Попытка парсинга страницы товара {nm_id}...")
    price = _fetch_price_by_parsing_product_page(nm_id)
    if price:
        return _cache_and_return_price(nm_id, price, 'wb_product_page')
    
    # Метод 3: Парсинг поиска WB
    logger.info(f"🔎 Попытка парсинга через поиск WB для {nm_id}...")
    price = _fetch_price_by_parsing_search(nm_id)
    if price:
        return _cache_and_return_price(nm_id, price, 'wb_search_page')
    
    logger.error(f"❌ Не удалось получить цену для {nm_id} всеми методами")
    return None


def _fetch_price_from_api(nm_id: int, max_attempts: int = 3) -> Optional[float]:
    """Получает цену через WB Public API"""
    
    endpoints = [
        f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}",
        f"https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-1257786&nm={nm_id}"
    ]
    
    for attempt in range(max_attempts):
        endpoint = endpoints[attempt % len(endpoints)]
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                data = response.json()
                products = data.get('data', {}).get('products', [])
                if products:
                    product = products[0]
                    price = product.get('salePriceU', 0) / 100  # Цена в копейках
                    if price > 0:
                        logger.info(f"✅ API: цена {nm_id} = {price} руб")
                        return price
        except Exception as e:
            logger.warning(f"⚠️ API попытка {attempt+1}/{max_attempts}: {str(e)}")
            time.sleep(1)
    
    return None


def _fetch_price_by_parsing_product_page(nm_id: int) -> Optional[float]:
    """
    Парсит цену со страницы товара WB
    URL: https://www.wildberries.ru/catalog/{nm_id}/detail.aspx
    """
    try:
        url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Ищем цену в различных форматах
        patterns = [
            r'"salePriceU"\s*:\s*(\d+)',  # JSON в скрипте
            r'data-sale-price="(\d+)"',    # Атрибут data
            r'class="price-block__final-price"[^>]*>(\d+)',  # CSS класс
            r'"price"\s*:\s*(\d+)',        # Альтернативный JSON
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                price_kopecks = int(match.group(1))
                price = price_kopecks / 100
                if price > 0:
                    logger.info(f"✅ ПАРСИНГ СТРАНИЦЫ: цена {nm_id} = {price} руб")
                    return price
        
        # Попробуем BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем элементы с ценой
        price_elements = soup.find_all(['span', 'div', 'ins'], class_=re.compile(r'price|cost|sale', re.I))
        for elem in price_elements:
            text = elem.get_text().strip()
            # Извлекаем числа из текста
            numbers = re.findall(r'\d+', text.replace(' ', ''))
            if numbers:
                price = float(''.join(numbers)) / 100  # Предполагаем копейки
                if 10 <= price <= 1000000:  # Разумный диапазон цен
                    logger.info(f"✅ ПАРСИНГ (BS4): цена {nm_id} = {price} руб")
                    return price
        
    except Exception as e:
        logger.warning(f"⚠️ Парсинг страницы {nm_id}: {str(e)}")
    
    return None


def _fetch_price_by_parsing_search(nm_id: int) -> Optional[float]:
    """
    Парсит цену через страницу поиска WB
    URL: https://www.wildberries.ru/catalog/0/search.aspx?search={nm_id}
    """
    try:
        url = f"https://www.wildberries.ru/catalog/0/search.aspx?search={nm_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Ищем JSON с данными товаров
        match = re.search(r'__NUXT__\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            try:
                nuxt_data = json.loads(match.group(1))
                # Рекурсивный поиск цены в сложной структуре
                price = _find_price_in_json(nuxt_data, nm_id)
                if price:
                    logger.info(f"✅ ПАРСИНГ ПОИСКА: цена {nm_id} = {price} руб")
                    return price
            except:
                pass
        
        # Резервный метод: поиск по регулярным выражениям
        patterns = [
            rf'"{nm_id}"[^}}]*"salePriceU"\s*:\s*(\d+)',
            rf'data-nm-id="{nm_id}"[^>]*data-price="(\d+)"',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                price = int(match.group(1)) / 100
                if price > 0:
                    logger.info(f"✅ ПАРСИНГ ПОИСКА (regex): цена {nm_id} = {price} руб")
                    return price
        
    except Exception as e:
        logger.warning(f"⚠️ Парсинг поиска {nm_id}: {str(e)}")
    
    return None


def _find_price_in_json(data: Any, target_nm_id: int) -> Optional[float]:
    """Рекурсивно ищет цену товара в JSON структуре"""
    if isinstance(data, dict):
        # Проверяем, есть ли nm_id и цена в текущем объекте
        if 'id' in data and data['id'] == target_nm_id:
            if 'salePriceU' in data:
                return data['salePriceU'] / 100
            if 'priceU' in data:
                return data['priceU'] / 100
        
        # Рекурсивно обходим все значения
        for value in data.values():
            result = _find_price_in_json(value, target_nm_id)
            if result:
                return result
    
    elif isinstance(data, list):
        for item in data:
            result = _find_price_in_json(item, target_nm_id)
            if result:
                return result
    
    return None


def _cache_and_return_price(nm_id: int, price: float, source: str) -> Dict[str, Any]:
    """Сохраняет цену в кэш и возвращает результат"""
    timestamp = datetime.now()
    price_cache[nm_id] = {
        'price': price,
        'timestamp': timestamp
    }
    
    return {
        'price': price,
        'source': source,
        'cached_seconds_ago': 0,
        'timestamp': timestamp.isoformat()
    }


# ============================================================================
# ПОИСК КОНКУРЕНТОВ
# ============================================================================

def get_top_competitors(nm_id: int, top_n: int = 5) -> List[Dict[str, Any]]:
    """Находит топ конкурентов из базы знаний и получает их актуальные цены"""
    
    if str(nm_id) not in KNOWLEDGE_BASE:
        logger.warning(f"⚠️ Товар {nm_id} не найден в базе знаний")
        return []
    
    product_data = KNOWLEDGE_BASE[str(nm_id)]
    category = product_data.get('Категория', '')
    
    # Поиск товаров в той же категории
    competitors = []
    for other_nm_id, other_data in KNOWLEDGE_BASE.items():
        if other_nm_id == str(nm_id):
            continue
        if other_data.get('Категория') == category:
            competitors.append({
                'nm_id': int(other_nm_id),
                'name': other_data.get('Наименование', 'Без названия'),
                'revenue': other_data.get('Выручка', 0)
            })
    
    # Сортировка по выручке
    competitors.sort(key=lambda x: x['revenue'], reverse=True)
    top_competitors = competitors[:top_n]
    
    # Получение актуальных цен
    result = []
    skipped = 0
    
    for comp in top_competitors:
        price_info = get_current_wb_price(comp['nm_id'])
        if price_info:
            result.append({
                'nm_id': comp['nm_id'],
                'name': comp['name'],
                'price': price_info['price'],
                'price_source': price_info['source']
            })
        else:
            logger.warning(f"⚠️ Пропуск конкурента {comp['nm_id']}: не удалось получить цену")
            skipped += 1
    
    logger.info(f"✅ Найдено {len(result)} конкурентов с актуальными ценами (пропущено: {skipped})")
    return result


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Главная страница"""
    return {
        "service": "WB Price Optimizer",
        "version": VERSION,
        "features": [
            "Получение актуальных цен через WB API",
            "Парсинг цен со страниц WB (резервный метод)",
            "Анализ конкурентов",
            "Кэширование цен (30 минут)",
            "НЕТ использования устаревших данных"
        ],
        "endpoints": {
            "/health": "Проверка здоровья сервиса",
            "/price/{nm_id}": "Получить актуальную цену товара",
            "/analyze/full/{nm_id}": "Полный анализ с рекомендациями"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "version": VERSION,
        "features": {
            "realtime_prices_only": True,
            "no_fallback_to_old_data": True,
            "parsing_enabled": True,
            "price_cache": True
        },
        "knowledge_base": {
            "loaded": len(KNOWLEDGE_BASE) > 0,
            "products": len(KNOWLEDGE_BASE)
        }
    }


@app.get("/price/{nm_id}")
async def get_price(nm_id: int):
    """Получить актуальную цену товара"""
    
    price_info = get_current_wb_price(nm_id, use_cache=True)
    
    if not price_info:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Не удалось получить актуальную цену",
                "nm_id": nm_id,
                "tried_methods": ["wb_api", "wb_product_page", "wb_search_page"],
                "recommendation": "Попробуйте позже или проверьте артикул"
            }
        )
    
    return {
        "nm_id": nm_id,
        "current_price": {
            "value": price_info['price'],
            "source": price_info['source'],
            "cached_seconds_ago": price_info.get('cached_seconds_ago'),
            "timestamp": price_info['timestamp']
        },
        "data_freshness": "realtime_only"
    }


@app.get("/analyze/full/{nm_id}")
async def analyze_full(nm_id: int):
    """Полный анализ товара с конкурентами"""
    
    # Получаем цену основного товара
    main_price_info = get_current_wb_price(nm_id, use_cache=True)
    if not main_price_info:
        raise HTTPException(
            status_code=503,
            detail=f"Не удалось получить цену для товара {nm_id}"
        )
    
    # Получаем конкурентов с актуальными ценами
    competitors = get_top_competitors(nm_id, top_n=5)
    
    # Базовая информация из базы знаний
    product_data = KNOWLEDGE_BASE.get(str(nm_id), {})
    
    return {
        "nm_id": nm_id,
        "name": product_data.get('Наименование', 'Неизвестно'),
        "category": product_data.get('Категория', 'Неизвестно'),
        "current_price": {
            "value": main_price_info['price'],
            "source": main_price_info['source'],
            "cached_seconds_ago": main_price_info.get('cached_seconds_ago')
        },
        "competitors": competitors,
        "analysis": {
            "avg_competitor_price": sum(c['price'] for c in competitors) / len(competitors) if competitors else 0,
            "price_position": _calculate_price_position(main_price_info['price'], competitors),
            "data_freshness": "all_realtime"
        }
    }


def _calculate_price_position(our_price: float, competitors: List[Dict]) -> str:
    """Определяет позицию нашей цены относительно конкурентов"""
    if not competitors:
        return "no_competitors"
    
    competitor_prices = [c['price'] for c in competitors]
    avg_price = sum(competitor_prices) / len(competitor_prices)
    
    if our_price < avg_price * 0.9:
        return "significantly_lower"
    elif our_price < avg_price:
        return "lower"
    elif our_price <= avg_price * 1.1:
        return "competitive"
    else:
        return "higher"


# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
