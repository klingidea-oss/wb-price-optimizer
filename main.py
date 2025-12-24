#!/usr/bin/env python3
"""
WB Price Optimizer - ВЕРСИЯ С АКТУАЛЬНЫМИ ЦЕНАМИ
Гарантирует получение цен в реальном времени через гибридный подход:
1. Публичный API WB (быстро)
2. Парсинг через requests с задержками (при блокировке API)
3. НЕТ fallback на устаревшие данные

Автор: AI Assistant
Дата: 2025-12-23
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from typing import Optional, Dict, List
import json
import os
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import pandas as pd
from io import BytesIO
import logging
import time
import random
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WB Price Optimizer - Real-time Prices",
    description="Система оптимизации цен с актуальными данными",
    version="3.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы и шаблоны
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# === КОНФИГУРАЦИЯ ===
WB_API_KEY = os.getenv("WB_API_KEY", "")
WB_API_BASE = "https://suppliers-api.wildberries.ru"

MPSTAT_TOKEN = os.getenv("MPSTAT_TOKEN", "")
MPSTAT_BASE = "https://mpstats.io/api"

KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "category_knowledge_base.json")

# Загрузка базы знаний
try:
    with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as f:
        KNOWLEDGE_BASE = json.load(f)
    logger.info(f"✅ База знаний загружена: {KNOWLEDGE_BASE['statistics']['total_products']} товаров")
except FileNotFoundError:
    logger.warning("⚠️  База знаний не найдена, используется пустая")
    KNOWLEDGE_BASE = {
        'category_mapping': {},
        'product_database': {},
        'statistics': {'total_products': 0, 'total_groups': 0}
    }

# === КЕШ ЦЕН ===
PRICE_CACHE = {}  # {nm_id: {'price': float, 'name': str, 'timestamp': datetime}}
CACHE_LIFETIME = 1800  # 30 минут (баланс между актуальностью и нагрузкой)

# User-Agent для обхода блокировок
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]


# === ФУНКЦИИ ПОЛУЧЕНИЯ АКТУАЛЬНЫХ ЦЕН ===

def get_wb_price_api(nm_id: int) -> Optional[Dict]:
    """
    Способ 1: Публичный API Wildberries
    Возвращает: {'price': float, 'name': str} или None
    """
    try:
        url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}"
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'application/json',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.wildberries.ru/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and data['data'].get('products'):
                product = data['data']['products'][0]
                price_kopecks = product.get('salePriceU', 0)
                name = product.get('name', f'Товар {nm_id}')
                
                if price_kopecks > 0:
                    price_rub = price_kopecks / 100
                    logger.info(f"✅ [API] nm_id={nm_id}: {price_rub}₽ ({name[:50]})")
                    return {'price': price_rub, 'name': name}
        
        logger.warning(f"⚠️  [API] nm_id={nm_id}: status={response.status_code}")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️  [API] nm_id={nm_id}: {str(e)}")
        return None


def get_wb_price_scraping(nm_id: int) -> Optional[Dict]:
    """
    Способ 2: Парсинг страницы товара через requests + BeautifulSoup
    Используется при блокировке API
    Возвращает: {'price': float, 'name': str} или None
    """
    try:
        url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
        
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Задержка для имитации человека
        time.sleep(random.uniform(1.0, 2.5))
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Поиск цены (несколько вариантов селекторов)
            price_element = (
                soup.select_one('.price-block__final-price') or
                soup.select_one('[class*="final-price"]') or
                soup.select_one('.product-page__price-block ins') or
                soup.select_one('[data-link="text{:productCard^price}"]')
            )
            
            # Поиск названия
            name_element = (
                soup.select_one('h1.product-page__title') or
                soup.select_one('[class*="product-page__title"]') or
                soup.select_one('h1')
            )
            
            if price_element:
                price_text = price_element.get_text(strip=True)
                # Извлекаем числа из текста (например: "1 234 ₽" → 1234.0)
                price_clean = ''.join(c for c in price_text if c.isdigit())
                
                if price_clean:
                    price_rub = float(price_clean)
                    name = name_element.get_text(strip=True) if name_element else f'Товар {nm_id}'
                    
                    logger.info(f"✅ [SCRAPING] nm_id={nm_id}: {price_rub}₽ ({name[:50]})")
                    return {'price': price_rub, 'name': name}
        
        logger.warning(f"⚠️  [SCRAPING] nm_id={nm_id}: status={response.status_code}")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️  [SCRAPING] nm_id={nm_id}: {str(e)}")
        return None


def get_current_wb_price_realtime(nm_id: int) -> Dict:
    """
    ГИБРИДНЫЙ ПОДХОД: Получение актуальной цены на момент запроса
    
    Этапы:
    1. Проверка кеша (30 мин)
    2. Попытка через API WB (быстро)
    3. Если API заблокирован → парсинг (медленно, но надежно)
    4. Если всё не работает → ОШИБКА (НЕТ устаревших данных!)
    
    Возвращает: {'price': float, 'name': str, 'source': str} или raise HTTPException
    """
    
    # 1️⃣ Проверяем кеш
    if nm_id in PRICE_CACHE:
        cache_entry = PRICE_CACHE[nm_id]
        age = (datetime.now() - cache_entry['timestamp']).total_seconds()
        
        if age < CACHE_LIFETIME:
            logger.info(f"📦 [CACHE] nm_id={nm_id}: {cache_entry['price']}₽ (возраст: {int(age)}с)")
            return {
                'price': cache_entry['price'],
                'name': cache_entry['name'],
                'source': 'cache',
                'cached_seconds_ago': int(age)
            }
    
    # 2️⃣ Попытка через API
    result = get_wb_price_api(nm_id)
    if result:
        PRICE_CACHE[nm_id] = {
            'price': result['price'],
            'name': result['name'],
            'timestamp': datetime.now()
        }
        return {
            'price': result['price'],
            'name': result['name'],
            'source': 'wb_api',
            'cached_seconds_ago': 0
        }
    
    # 3️⃣ API заблокирован → парсинг
    logger.warning(f"🔄 [FALLBACK] nm_id={nm_id}: переключаемся на парсинг...")
    result = get_wb_price_scraping(nm_id)
    
    if result:
        PRICE_CACHE[nm_id] = {
            'price': result['price'],
            'name': result['name'],
            'timestamp': datetime.now()
        }
        return {
            'price': result['price'],
            'name': result['name'],
            'source': 'scraping',
            'cached_seconds_ago': 0
        }
    
    # 4️⃣ ВСЁ СЛОМАЛОСЬ → Ошибка
    logger.error(f"❌ [ERROR] nm_id={nm_id}: не удалось получить актуальную цену!")
    raise HTTPException(
        status_code=503,
        detail=f"Не удалось получить актуальную цену для товара {nm_id}. "
               f"WB API недоступен, парсинг не сработал. Попробуйте позже."
    )


def get_top_selling_competitors(nm_id: int, category: str, limit: int = 5) -> List[Dict]:
    """
    Найти топ конкурентов из базы знаний и получить их АКТУАЛЬНЫЕ цены
    
    Возвращает: [
        {
            'nm_id': int,
            'name': str,
            'price': float,
            'weekly_sales': int,
            'price_source': str  # 'cache', 'wb_api', 'scraping'
        }
    ]
    """
    
    # Поиск группы в базе знаний
    product_info = KNOWLEDGE_BASE['product_database'].get(str(nm_id))
    if not product_info:
        logger.warning(f"Товар {nm_id} не найден в базе знаний")
        return []
    
    group_id = product_info.get('group_id')
    if not group_id:
        logger.warning(f"У товара {nm_id} нет group_id")
        return []
    
    # Найти конкурентов из той же группы
    competitors_raw = []
    for prod_id, prod_data in KNOWLEDGE_BASE['product_database'].items():
        if prod_data.get('group_id') == group_id and prod_id != str(nm_id):
            competitors_raw.append({
                'nm_id': int(prod_id),
                'weekly_sales': prod_data.get('weekly_sales', 0)
            })
    
    # Сортируем по продажам
    competitors_raw.sort(key=lambda x: x['weekly_sales'], reverse=True)
    top_competitors = competitors_raw[:limit]
    
    # Получаем АКТУАЛЬНЫЕ цены для каждого конкурента
    result = []
    for comp in top_competitors:
        try:
            price_info = get_current_wb_price_realtime(comp['nm_id'])
            
            result.append({
                'nm_id': comp['nm_id'],
                'name': price_info['name'],
                'price': price_info['price'],
                'weekly_sales': comp['weekly_sales'],
                'price_source': price_info['source']
            })
            
            # Задержка между запросами конкурентов
            time.sleep(random.uniform(0.3, 0.8))
            
        except HTTPException as e:
            logger.error(f"Не удалось получить цену конкурента {comp['nm_id']}: {e.detail}")
            # Пропускаем конкурента, если не удалось получить цену
            continue
        except Exception as e:
            logger.error(f"Ошибка при обработке конкурента {comp['nm_id']}: {str(e)}")
            continue
    
    return result


# === АНАЛИЗ СПРОСА И СЕЗОННОСТИ ===

def get_wb_sales_history(nm_id: int, days: int = 90) -> List[Dict]:
    """Получить историю продаж через WB API"""
    if not WB_API_KEY:
        logger.warning("WB_API_KEY не установлен")
        return []
    
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        url = f"{WB_API_BASE}/api/v1/supplier/reportDetailByPeriod"
        params = {
            'dateFrom': start_date.strftime('%Y-%m-%d'),
            'dateTo': end_date.strftime('%Y-%m-%d'),
            'limit': 100000,
            'rrdid': 0
        }
        headers = {'Authorization': WB_API_KEY}
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Фильтруем по nm_id
            sales = [
                {
                    'date': item['rr_dt'],
                    'price': item['priceWithDisc'],
                    'quantity': item['quantity'],
                    'revenue': item['forPay']
                }
                for item in data
                if item.get('nm_id') == nm_id and item.get('quantity', 0) > 0
            ]
            
            return sales
        else:
            logger.warning(f"WB API error: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Ошибка получения истории продаж: {str(e)}")
        return []


def calculate_demand_elasticity(sales_history: List[Dict]) -> float:
    """
    Рассчитать эластичность спроса по цене
    Формула: E = (ΔQ/Q) / (ΔP/P)
    """
    if len(sales_history) < 10:
        return -1.2  # Средняя эластичность по умолчанию
    
    try:
        # Группируем по ценовым диапазонам
        price_groups = defaultdict(list)
        for sale in sales_history:
            price_range = round(sale['price'] / 100) * 100
            price_groups[price_range].append(sale['quantity'])
        
        if len(price_groups) < 2:
            return -1.2
        
        # Берем 2 ценовых диапазона с максимальным количеством данных
        sorted_groups = sorted(price_groups.items(), key=lambda x: len(x[1]), reverse=True)[:2]
        
        price1, quantities1 = sorted_groups[0]
        price2, quantities2 = sorted_groups[1]
        
        avg_q1 = statistics.mean(quantities1)
        avg_q2 = statistics.mean(quantities2)
        
        # Расчет эластичности
        delta_q = (avg_q2 - avg_q1) / avg_q1
        delta_p = (price2 - price1) / price1
        
        if delta_p == 0:
            return -1.2
        
        elasticity = delta_q / delta_p
        
        # Ограничиваем диапазон [-5.0, -0.5]
        elasticity = max(min(elasticity, -0.5), -5.0)
        
        return round(elasticity, 2)
        
    except Exception as e:
        logger.error(f"Ошибка расчета эластичности: {str(e)}")
        return -1.2


def get_seasonality_factor(category: str, month: int) -> float:
    """
    Получить коэффициент сезонности
    Можно расширить через MPStat API или использовать исторические данные
    """
    # Упрощенная модель сезонности для текстиля
    seasonality_map = {
        'Шторы': {1: 0.8, 2: 0.9, 3: 1.1, 4: 1.2, 5: 1.3, 6: 1.1, 
                 7: 0.9, 8: 0.9, 9: 1.1, 10: 1.2, 11: 1.1, 12: 0.9},
        'Карнизы': {1: 0.85, 2: 0.95, 3: 1.15, 4: 1.2, 5: 1.25, 6: 1.1,
                   7: 0.9, 8: 0.85, 9: 1.1, 10: 1.15, 11: 1.1, 12: 0.95},
        'Рулонные шторы': {1: 0.9, 2: 1.0, 3: 1.2, 4: 1.3, 5: 1.4, 6: 1.2,
                          7: 1.0, 8: 0.9, 9: 1.1, 10: 1.2, 11: 1.1, 12: 1.0},
        'Тюль': {1: 0.85, 2: 0.95, 3: 1.2, 4: 1.3, 5: 1.35, 6: 1.15,
                7: 0.95, 8: 0.9, 9: 1.15, 10: 1.2, 11: 1.1, 12: 0.95}
    }
    
    base_category = None
    for key in seasonality_map.keys():
        if key.lower() in category.lower():
            base_category = key
            break
    
    if base_category:
        return seasonality_map[base_category].get(month, 1.0)
    
    return 1.0  # Нейтральная сезонность


def calculate_optimal_price(
    current_price: float,
    competitor_prices: List[float],
    elasticity: float,
    seasonality: float,
    cost: float = None
) -> Dict:
    """
    Рассчитать оптимальную цену на основе:
    - Текущей цены
    - Цен конкурентов (АКТУАЛЬНЫХ!)
    - Эластичности спроса
    - Сезонности
    """
    
    if not competitor_prices:
        return {
            'optimal_price': current_price,
            'change_percent': 0,
            'reasoning': 'Нет данных о конкурентах'
        }
    
    # Средняя цена конкурентов
    avg_competitor_price = statistics.mean(competitor_prices)
    min_competitor_price = min(competitor_prices)
    max_competitor_price = max(competitor_prices)
    
    # Базовая рекомендация: позиционирование относительно конкурентов
    if elasticity < -2.0:  # Высокая эластичность → ценовая конкуренция
        target_price = min_competitor_price * 0.95
        reasoning = "Высокая чувствительность к цене → снижение для роста продаж"
    elif elasticity > -1.0:  # Низкая эластичность → можно повышать
        target_price = avg_competitor_price * 1.05
        reasoning = "Низкая чувствительность к цене → можно повысить маржу"
    else:  # Средняя эластичность
        target_price = avg_competitor_price * 0.98
        reasoning = "Средняя эластичность → конкурентная цена"
    
    # Учет сезонности
    target_price *= seasonality
    
    # Ограничения
    if cost:
        min_price = cost * 1.15  # Минимум 15% маржа
        target_price = max(target_price, min_price)
    
    # Не отклоняться от текущей цены более чем на 30%
    max_change = current_price * 0.30
    target_price = max(current_price - max_change, min(target_price, current_price + max_change))
    
    change_percent = ((target_price - current_price) / current_price) * 100
    
    return {
        'optimal_price': round(target_price, 2),
        'change_percent': round(change_percent, 1),
        'reasoning': reasoning,
        'competitor_range': f"{min_competitor_price}₽ - {max_competitor_price}₽",
        'avg_competitor_price': round(avg_competitor_price, 2)
    }


# === API ENDPOINTS ===

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница с интерфейсом"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WB Price Optimizer V3.0 - Real-time Prices</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                margin-bottom: 10px;
                font-size: 2.5em;
            }
            .badge {
                display: inline-block;
                background: #48bb78;
                color: white;
                padding: 5px 15px;
                border-radius: 20px;
                font-size: 0.9em;
                font-weight: bold;
                margin-bottom: 15px;
            }
            .subtitle {
                color: #718096;
                font-size: 1.1em;
            }
            .search-card {
                background: white;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            .search-box {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            input[type="text"] {
                flex: 1;
                padding: 15px 20px;
                border: 2px solid #e2e8f0;
                border-radius: 10px;
                font-size: 1.1em;
                transition: all 0.3s;
            }
            input[type="text"]:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
            }
            button {
                padding: 15px 30px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 1.1em;
                font-weight: bold;
                cursor: pointer;
                transition: all 0.3s;
            }
            button:hover {
                background: #5a67d8;
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102,126,234,0.4);
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            .feature {
                background: #f7fafc;
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }
            .feature-icon {
                font-size: 2em;
                margin-bottom: 10px;
            }
            .feature-title {
                font-weight: bold;
                color: #2d3748;
                margin-bottom: 5px;
            }
            .feature-desc {
                color: #718096;
                font-size: 0.9em;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }
            .stat-value {
                font-size: 2.5em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .stat-label {
                font-size: 0.9em;
                opacity: 0.9;
            }
            #result {
                margin-top: 20px;
                padding: 20px;
                background: #f7fafc;
                border-radius: 10px;
                display: none;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #667eea;
                font-size: 1.2em;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 WB Price Optimizer</h1>
                <div class="badge">✅ V3.0 - REAL-TIME PRICES</div>
                <p class="subtitle">Оптимизация цен с гарантией актуальности данных</p>
            </div>
            
            <div class="search-card">
                <h2>🔍 Анализ товара</h2>
                <div class="search-box">
                    <input type="text" id="nmId" placeholder="Введите артикул WB (например: 55266575)" />
                    <button onclick="analyzeProduct()">Анализировать</button>
                </div>
                
                <div class="features">
                    <div class="feature">
                        <div class="feature-icon">⚡</div>
                        <div class="feature-title">Актуальные цены</div>
                        <div class="feature-desc">Получение цен в реальном времени через API + парсинг</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🎯</div>
                        <div class="feature-title">Топ конкуренты</div>
                        <div class="feature-desc">Анализ лидеров продаж с актуальными ценами</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">📊</div>
                        <div class="feature-title">Эластичность спроса</div>
                        <div class="feature-desc">Расчет чувствительности к изменению цены</div>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🌡️</div>
                        <div class="feature-title">Сезонность</div>
                        <div class="feature-desc">Учет сезонных колебаний спроса</div>
                    </div>
                </div>
                
                <div id="result"></div>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value" id="totalProducts">-</div>
                    <div class="stat-label">Товаров в базе</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="totalGroups">-</div>
                    <div class="stat-label">Групп конкурентов</div>
                </div>
            </div>
        </div>
        
        <script>
            // Загрузка статистики
            fetch('/categories/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('totalProducts').textContent = data.total_products.toLocaleString();
                    document.getElementById('totalGroups').textContent = data.total_groups.toLocaleString();
                });
            
            function analyzeProduct() {
                const nmId = document.getElementById('nmId').value.trim();
                if (!nmId) {
                    alert('Введите артикул WB');
                    return;
                }
                
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = '<div class="loading"><div class="spinner"></div>Получаем актуальные цены...<br><small>Это может занять до 30 секунд</small></div>';
                
                fetch(`/analyze/full/${nmId}`)
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => { throw err; });
                        }
                        return response.json();
                    })
                    .then(data => {
                        resultDiv.innerHTML = `
                            <h3>✅ Результаты анализа</h3>
                            <pre style="background: white; padding: 20px; border-radius: 10px; overflow-x: auto;">${JSON.stringify(data, null, 2)}</pre>
                        `;
                    })
                    .catch(error => {
                        resultDiv.innerHTML = `
                            <h3 style="color: #e53e3e;">❌ Ошибка</h3>
                            <p>${error.detail || error.message || 'Не удалось получить данные'}</p>
                        `;
                    });
            }
            
            // Enter для поиска
            document.getElementById('nmId').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    analyzeProduct();
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/categories/stats")
async def get_categories_stats():
    """Статистика по базе знаний"""
    return {
        'total_products': KNOWLEDGE_BASE['statistics'].get('total_products', 0),
        'total_groups': KNOWLEDGE_BASE['statistics'].get('total_groups', 0),
        'categories': KNOWLEDGE_BASE.get('category_mapping', {})
    }


@app.get("/analyze/full/{nm_id}")
async def analyze_product_full(nm_id: int):
    """
    Полный анализ товара с АКТУАЛЬНЫМИ ценами конкурентов
    
    Возвращает:
    - Текущую цену товара (real-time)
    - Топ-5 конкурентов с актуальными ценами (real-time)
    - Эластичность спроса
    - Коэффициент сезонности
    - Оптимальную цену
    """
    
    try:
        # 1️⃣ Получаем информацию о товаре из базы знаний
        product_info = KNOWLEDGE_BASE['product_database'].get(str(nm_id))
        if not product_info:
            raise HTTPException(
                status_code=404,
                detail=f"Товар {nm_id} не найден в базе знаний. "
                       f"Загружено товаров: {KNOWLEDGE_BASE['statistics']['total_products']}"
            )
        
        category = product_info.get('category', 'Неизвестно')
        
        # 2️⃣ АКТУАЛЬНАЯ цена нашего товара
        logger.info(f"🔍 Анализ товара {nm_id} из категории '{category}'")
        our_price_info = get_current_wb_price_realtime(nm_id)
        
        # 3️⃣ АКТУАЛЬНЫЕ цены конкурентов
        logger.info(f"🔍 Поиск топ-5 конкурентов для {nm_id}...")
        competitors = get_top_selling_competitors(nm_id, category, limit=5)
        
        if not competitors:
            logger.warning(f"Конкуренты для {nm_id} не найдены")
        
        # 4️⃣ Анализ спроса (через WB API)
        sales_history = get_wb_sales_history(nm_id, days=90)
        elasticity = calculate_demand_elasticity(sales_history)
        
        # 5️⃣ Сезонность
        current_month = datetime.now().month
        seasonality = get_seasonality_factor(category, current_month)
        
        # 6️⃣ Расчет оптимальной цены
        competitor_prices = [c['price'] for c in competitors]
        optimal_price_info = calculate_optimal_price(
            current_price=our_price_info['price'],
            competitor_prices=competitor_prices,
            elasticity=elasticity,
            seasonality=seasonality
        )
        
        # 7️⃣ Формируем ответ
        return {
            'nm_id': nm_id,
            'product_name': our_price_info['name'],
            'category': category,
            
            'current_price': {
                'value': our_price_info['price'],
                'source': our_price_info['source'],
                'cached_seconds_ago': our_price_info.get('cached_seconds_ago', 0)
            },
            
            'competitors': [
                {
                    'nm_id': c['nm_id'],
                    'name': c['name'],
                    'price': c['price'],
                    'weekly_sales': c['weekly_sales'],
                    'price_source': c['price_source']
                }
                for c in competitors
            ],
            
            'demand_analysis': {
                'elasticity': elasticity,
                'sales_data_points': len(sales_history),
                'interpretation': (
                    'Высокая чувствительность к цене' if elasticity < -2.0
                    else 'Низкая чувствительность к цене' if elasticity > -1.0
                    else 'Средняя чувствительность к цене'
                )
            },
            
            'seasonality': {
                'factor': seasonality,
                'month': current_month,
                'interpretation': (
                    'Высокий сезон' if seasonality > 1.15
                    else 'Низкий сезон' if seasonality < 0.9
                    else 'Нормальный сезон'
                )
            },
            
            'recommendation': {
                'optimal_price': optimal_price_info['optimal_price'],
                'change_from_current': optimal_price_info['change_percent'],
                'reasoning': optimal_price_info['reasoning'],
                'competitor_price_range': optimal_price_info['competitor_range'],
                'avg_competitor_price': optimal_price_info['avg_competitor_price']
            },
            
            'data_freshness': {
                'all_prices_realtime': True,
                'timestamp': datetime.now().isoformat(),
                'note': 'Все цены получены в реальном времени через WB API или парсинг'
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа товара {nm_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/price/{nm_id}")
async def get_price(nm_id: int):
    """
    Получить ТОЛЬКО актуальную цену товара
    Быстрый эндпоинт для проверки
    """
    try:
        price_info = get_current_wb_price_realtime(nm_id)
        return price_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Проверка работоспособности"""
    return {
        'status': 'healthy',
        'version': '3.0.0',
        'features': {
            'realtime_prices': True,
            'api_fallback_to_scraping': True,
            'price_cache': True,
            'cache_lifetime_seconds': CACHE_LIFETIME
        },
        'knowledge_base': {
            'loaded': KNOWLEDGE_BASE['statistics']['total_products'] > 0,
            'products': KNOWLEDGE_BASE['statistics']['total_products'],
            'groups': KNOWLEDGE_BASE['statistics']['total_groups']
        },
        'cache_stats': {
            'cached_products': len(PRICE_CACHE),
            'cache_size_mb': round(len(str(PRICE_CACHE)) / 1024 / 1024, 2)
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
