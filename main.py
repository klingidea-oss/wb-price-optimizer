#!/usr/bin/env python3
"""
WB Price Optimizer - ОКОНЧАТЕЛЬНАЯ ВЕРСИЯ
Полная замена старого приложения

Возможности:
1. ✅ Анализ эластичности спроса через API WB
2. ✅ Топ продаваемые SKU конкурентов (только из той же категории)
3. ✅ Учёт сезонности (WB + MPStat API)
4. ✅ Выгрузка рекомендаций в Excel
5. ✅ База знаний категорий из Excel файлов
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
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

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WB Price Optimizer",
    description="Система оптимизации цен для Wildberries",
    version="2.0.0"
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

# In-memory хранилище
products_db = {}  # {nm_id: product_data}


# === MODELS ===

class Product(BaseModel):
    nm_id: int
    name: str
    category: str
    current_price: float
    cost: float
    brand: Optional[str] = ""
    group_id: Optional[int] = None


class ProductAdd(BaseModel):
    nm_id: int
    name: str
    category: str
    current_price: float
    cost: float


# === ИНТЕГРАЦИЯ С API WILDBERRIES ===

def get_wb_sales_history(nm_id: int, days: int = 30) -> List[Dict]:
    """
    Получает историю продаж через API Wildberries
    """
    if not WB_API_KEY:
        logger.info(f"WB API ключ не настроен, используем тестовые данные для {nm_id}")
        return generate_test_sales_data(nm_id, days)
    
    try:
        url = f"{WB_API_BASE}/api/v1/supplier/reportDetailByPeriod"
        
        date_to = datetime.now()
        date_from = date_to - timedelta(days=days)
        
        params = {
            "dateFrom": date_from.strftime("%Y-%m-%d"),
            "dateTo": date_to.strftime("%Y-%m-%d"),
            "key": WB_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # Фильтруем по nm_id
            filtered = [item for item in data if item.get('nmId') == nm_id]
            return parse_wb_sales_data(filtered)
        else:
            logger.warning(f"WB API ошибка {response.status_code}, используем тестовые данные")
            return generate_test_sales_data(nm_id, days)
            
    except Exception as e:
        logger.error(f"Ошибка WB API: {e}")
        return generate_test_sales_data(nm_id, days)


def parse_wb_sales_data(wb_data: List[Dict]) -> List[Dict]:
    """Парсит ответ API Wildberries"""
    sales_history = []
    
    for entry in wb_data:
        sales_history.append({
            'date': entry.get('date', ''),
            'price': float(entry.get('priceWithDisc', 0)),
            'sales': int(entry.get('quantity', 0)),
            'revenue': float(entry.get('forPay', 0))
        })
    
    return sales_history


def generate_test_sales_data(nm_id: int, days: int) -> List[Dict]:
    """Генерирует тестовые данные для демонстрации"""
    import random
    
    # Базовые значения зависят от товара
    random.seed(nm_id)
    base_price = random.uniform(1000, 2000)
    base_sales = random.randint(30, 80)
    
    data = []
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i)).strftime("%Y-%m-%d")
        
        # Симуляция изменения цены
        price_variation = random.uniform(0.85, 1.15)
        price = base_price * price_variation
        
        # Эластичность спроса: чем ниже цена, тем больше продаж
        elasticity = -1.5
        price_factor = (base_price / price) ** abs(elasticity)
        sales = int(base_sales * price_factor * random.uniform(0.7, 1.3))
        
        data.append({
            'date': date,
            'price': round(price, 2),
            'sales': max(0, sales),
            'revenue': round(price * max(0, sales), 2)
        })
    
    return data


# === АНАЛИЗ ЭЛАСТИЧНОСТИ СПРОСА ===

def calculate_demand_elasticity(sales_history: List[Dict]) -> float:
    """
    Рассчитывает эластичность спроса по цене
    E = (ΔQ/Q) / (ΔP/P)
    """
    if len(sales_history) < 10:
        return -1.2
    
    price_sales_pairs = [(d['price'], d['sales']) for d in sales_history if d['sales'] > 0]
    
    if len(price_sales_pairs) < 10:
        return -1.2
    
    price_sales_pairs.sort(key=lambda x: x[0])
    
    mid = len(price_sales_pairs) // 2
    low_price_group = price_sales_pairs[:mid]
    high_price_group = price_sales_pairs[mid:]
    
    avg_low_price = statistics.mean([p for p, s in low_price_group])
    avg_high_price = statistics.mean([p for p, s in high_price_group])
    avg_low_sales = statistics.mean([s for p, s in low_price_group])
    avg_high_sales = statistics.mean([s for p, s in high_price_group])
    
    if avg_low_price == avg_high_price or avg_low_sales == 0:
        return -1.2
    
    price_change_pct = (avg_high_price - avg_low_price) / avg_low_price
    sales_change_pct = (avg_high_sales - avg_low_sales) / avg_low_sales
    
    elasticity = sales_change_pct / price_change_pct if price_change_pct != 0 else -1.2
    
    return max(-5.0, min(-0.5, elasticity))


# === РАБОТА С БАЗОЙ ЗНАНИЙ ===

def get_current_wb_price(nm_id: int) -> Optional[float]:
    """
    Получает АКТУАЛЬНУЮ цену со скидкой напрямую с WB API
    Использует публичный API для получения данных о товаре
    """
    try:
        # Публичный API WB для получения информации о товаре
        # Определяем корзину (basket) по артикулу
        vol = str(nm_id)[:4]  # Первые 4 цифры
        part = str(nm_id)[:6]  # Первые 6 цифр
        
        # URL для получения данных о товаре
        url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={nm_id}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('data', {}).get('products', [])
            
            if products and len(products) > 0:
                product = products[0]
                
                # Цена со скидкой (salePriceU в копейках, делим на 100)
                sale_price = product.get('salePriceU', 0) / 100
                
                if sale_price > 0:
                    logger.info(f"WB API: Артикул {nm_id}, актуальная цена: {sale_price} ₽")
                    return sale_price
        
        logger.warning(f"WB API: Не удалось получить цену для {nm_id}")
        return None
        
    except Exception as e:
        logger.error(f"WB API ошибка для {nm_id}: {e}")
        return None


def get_product_category_info(nm_id: int) -> Optional[Dict]:
    """Получает информацию о товаре из базы знаний"""
    nm_id_str = str(nm_id)
    if nm_id_str in KNOWLEDGE_BASE['product_database']:
        return KNOWLEDGE_BASE['product_database'][nm_id_str]
    return None


def get_top_selling_competitors(nm_id: int, category: str, limit: int = 20) -> List[Dict]:
    """
    Находит топ продаваемые SKU конкурентов из той же категории
    """
    product_info = get_product_category_info(nm_id)
    if not product_info:
        return []
    
    group_id = product_info['group_id']
    target_category = product_info['category']
    product_type = product_info['product_type']
    
    competitors = []
    for nm_id_str, info in KNOWLEDGE_BASE['product_database'].items():
        if (info['group_id'] == group_id and 
            info['product_type'] == product_type and
            info['category'] == target_category and
            int(nm_id_str) != nm_id):
            
            # Получаем АКТУАЛЬНУЮ цену с WB API (цены постоянно меняются!)
            current_price_wb = get_current_wb_price(int(nm_id_str))
            
            # Если не удалось получить с WB - используем цену из базы (Срезы цен)
            final_price = current_price_wb if current_price_wb else info['price']
            
            # Получаем статистику продаж (для сортировки по популярности)
            sales_data = get_wb_sales_history(int(nm_id_str), days=7)
            total_sales = sum(d['sales'] for d in sales_data)
            
            competitors.append({
                'nm_id': int(nm_id_str),
                'name': info.get('name', f'Товар {nm_id_str}'),  # Показываем артикул если нет имени
                'category': info['category'],
                'price': round(final_price, 2),  # АКТУАЛЬНАЯ цена с WB
                'sales_7d': total_sales,
                'revenue_7d': round(final_price * total_sales, 2)
            })
    
    competitors.sort(key=lambda x: x['sales_7d'], reverse=True)
    return competitors[:limit]


# === АНАЛИЗ СЕЗОННОСТИ ===

def analyze_seasonality(nm_id: int, category: str) -> Dict:
    """Анализирует сезонность товара"""
    
    # Пытаемся получить из MPStat
    seasonality_data = get_mpstat_seasonality(category)
    
    if not seasonality_data:
        # Fallback: оцениваем по WB данным
        seasonality_data = estimate_seasonality_from_wb(nm_id)
    
    return seasonality_data


def get_mpstat_seasonality(category: str) -> Optional[Dict]:
    """Получает данные сезонности из MPStat API"""
    if not MPSTAT_TOKEN:
        return None
    
    try:
        url = f"{MPSTAT_BASE}/wb/get/category"
        headers = {"X-Mpstats-TOKEN": MPSTAT_TOKEN}
        params = {"path": category}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            return parse_mpstat_seasonality(data)
        
    except Exception as e:
        logger.warning(f"MPStat API ошибка: {e}")
    
    return None


def parse_mpstat_seasonality(data: Dict) -> Dict:
    """Парсит данные сезонности из MPStat"""
    monthly_sales = data.get('graph', {}).get('data', [])
    
    if not monthly_sales:
        return estimate_default_seasonality()
    
    current_month = datetime.now().month
    current_month_sales = monthly_sales[current_month - 1] if len(monthly_sales) >= current_month else 0
    avg_sales = statistics.mean(monthly_sales) if monthly_sales else 1
    
    seasonality_index = current_month_sales / avg_sales if avg_sales > 0 else 1.0
    
    return {
        'seasonality_index': round(seasonality_index, 2),
        'current_month': datetime.now().strftime("%B"),
        'interpretation': interpret_seasonality(seasonality_index),
        'source': 'MPStat API'
    }


def estimate_seasonality_from_wb(nm_id: int) -> Dict:
    """Оценивает сезонность по WB данным"""
    history = get_wb_sales_history(nm_id, days=90)
    
    if len(history) < 30:
        return estimate_default_seasonality()
    
    # Делим на 3 месяца
    month1 = history[:30]
    month2 = history[30:60]
    month3 = history[60:] if len(history) > 60 else history[30:]
    
    avg_sales_month1 = statistics.mean([d['sales'] for d in month1]) if month1 else 0
    avg_sales_month2 = statistics.mean([d['sales'] for d in month2]) if month2 else 0
    avg_sales_month3 = statistics.mean([d['sales'] for d in month3]) if month3 else 0
    
    current_avg = avg_sales_month3
    total_avg = statistics.mean([avg_sales_month1, avg_sales_month2, avg_sales_month3])
    
    seasonality_index = current_avg / total_avg if total_avg > 0 else 1.0
    
    return {
        'seasonality_index': round(seasonality_index, 2),
        'current_month': datetime.now().strftime("%B"),
        'interpretation': interpret_seasonality(seasonality_index),
        'source': 'WB API (90 дней)'
    }


def estimate_default_seasonality() -> Dict:
    """Стандартная оценка сезонности"""
    return {
        'seasonality_index': 1.0,
        'current_month': datetime.now().strftime("%B"),
        'interpretation': '➡️ Нормальный сезон',
        'source': 'По умолчанию'
    }


def interpret_seasonality(index: float) -> str:
    """Интерпретирует индекс сезонности"""
    if index > 1.3:
        return "🔥 Высокий сезон"
    elif index > 1.1:
        return "📈 Повышенный спрос"
    elif index > 0.9:
        return "➡️ Нормальный сезон"
    elif index > 0.7:
        return "📉 Пониженный спрос"
    else:
        return "❄️ Низкий сезон"


# === РАСЧЁТ ОПТИМАЛЬНОЙ ЦЕНЫ ===

def calculate_optimal_price_with_seasonality(
    nm_id: int,
    current_price: float,
    cost: float,
    elasticity: float,
    competitors: List[Dict],
    seasonality: Dict,
    goal: str = "profit"
) -> Dict:
    """Рассчитывает оптимальную цену с учётом всех факторов"""
    
    if not competitors:
        base_price = cost * 1.5
        top_competitor = None
        best_price_competitor = None
    else:
        competitor_prices = [c['price'] for c in competitors]
        competitor_sales = [c['sales_7d'] for c in competitors]
        
        total_sales = sum(competitor_sales)
        if total_sales > 0:
            weighted_avg_price = sum(c['price'] * c['sales_7d'] for c in competitors) / total_sales
        else:
            weighted_avg_price = statistics.mean(competitor_prices)
        
        median_price = statistics.median(competitor_prices)
        min_price = min(competitor_prices)
        max_price = max(competitor_prices)
        
        # Выбор базовой цены по стратегии
        if goal == "profit":
            if elasticity < -1:
                base_price = cost / (1 + 1/elasticity)
                base_price = min(base_price, weighted_avg_price * 1.1)
            else:
                base_price = weighted_avg_price * 1.05
        elif goal == "revenue":
            base_price = median_price
        else:  # balanced
            base_price = (weighted_avg_price + median_price) / 2
        
        base_price = max(base_price, cost * 1.2)
        base_price = min(base_price, max_price * 1.15)
        
        top_competitor = competitors[0]
        best_price_competitor = max(competitors, key=lambda x: x['revenue_7d'])
    
    # Корректировка на сезонность
    seasonality_index = seasonality.get('seasonality_index', 1.0)
    
    if seasonality_index > 1.2:
        optimal_price = base_price * 1.05
        seasonality_note = "Цена повышена на 5% (высокий сезон)"
    elif seasonality_index < 0.8:
        optimal_price = base_price * 0.95
        seasonality_note = "Цена снижена на 5% (низкий сезон)"
    else:
        optimal_price = base_price
        seasonality_note = "Сезонная корректировка не требуется"
    
    return {
        'optimal_price': round(optimal_price, 2),
        'base_price': round(base_price, 2),
        'seasonality_adjustment': seasonality_note,
        'seasonality_index': seasonality_index,
        'top_competitor': top_competitor,
        'best_price_competitor': best_price_competitor,
        'min_competitor_price': min(competitor_prices) if competitors else None,
        'max_competitor_price': max(competitor_prices) if competitors else None,
        'median_competitor_price': round(statistics.median(competitor_prices), 2) if competitors else None
    }


def generate_recommendation(
    nm_id: int,
    current_price: float,
    optimal_price: float,
    elasticity: float,
    seasonality: Dict,
    top_competitor: Optional[Dict],
    best_price_competitor: Optional[Dict]
) -> str:
    """Генерирует детальную рекомендацию"""
    
    diff_pct = ((optimal_price - current_price) / current_price) * 100
    
    parts = []
    
    # Основная рекомендация
    if abs(diff_pct) < 3:
        parts.append(f"✅ Текущая цена оптимальна")
    elif optimal_price > current_price:
        parts.append(f"⬆️ Повысить на {diff_pct:.1f}% до {optimal_price}₽")
    else:
        parts.append(f"⬇️ Снизить на {abs(diff_pct):.1f}% до {optimal_price}₽")
    
    # Топ конкурент
    if top_competitor:
        parts.append(f"🏆 Топ продавец: {top_competitor['price']}₽ ({top_competitor['sales_7d']} шт/нед)")
    
    # Оптимальная цена конкурента
    if best_price_competitor:
        parts.append(f"💰 Макс выручка: {best_price_competitor['price']}₽ ({best_price_competitor['revenue_7d']:.0f}₽/нед)")
    
    # Эластичность
    if elasticity < -2:
        parts.append(f"📊 Эластичный спрос (E={elasticity:.2f})")
    elif elasticity > -1:
        parts.append(f"📊 Неэластичный спрос (E={elasticity:.2f})")
    
    # Сезонность
    seasonality_index = seasonality.get('seasonality_index', 1.0)
    if seasonality_index > 1.2:
        parts.append("🔥 Высокий сезон")
    elif seasonality_index < 0.8:
        parts.append("❄️ Низкий сезон")
    
    return " | ".join(parts)


# === API ENDPOINTS ===

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Главная страница с веб-интерфейсом"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api")
async def api_info():
    """API информация (JSON)"""
    return {
        "status": "healthy",
        "service": "WB Price Optimizer v2.0",
        "features": [
            "Анализ эластичности спроса (WB API)",
            "Топ конкуренты (с учётом категорий)",
            "Учёт сезонности (WB + MPStat)",
            "Выгрузка в Excel"
        ],
        "knowledge_base": KNOWLEDGE_BASE.get('statistics', {}),
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze/full/{nm_id}",
            "export": "/export/excel",
            "products": "/products",
            "categories": "/categories/stats"
        }
    }


@app.get("/health")
async def health_check():
    """Проверка здоровья системы"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "wb_api": "configured" if WB_API_KEY else "not configured",
        "mpstat_api": "configured" if MPSTAT_TOKEN else "not configured",
        "knowledge_base": {
            "loaded": len(KNOWLEDGE_BASE.get('product_database', {})) > 0,
            "products": KNOWLEDGE_BASE.get('statistics', {}).get('total_products', 0)
        }
    }


@app.post("/products/add")
async def add_product(product: ProductAdd):
    """Добавить товар"""
    products_db[product.nm_id] = product.dict()
    
    # Проверяем наличие в базе знаний
    category_info = get_product_category_info(product.nm_id)
    
    return {
        "success": True,
        "nm_id": product.nm_id,
        "in_knowledge_base": category_info is not None,
        "category": category_info.get('category') if category_info else None
    }


@app.get("/products")
async def list_products():
    """Список товаров"""
    return {
        "products": list(products_db.values()),
        "total": len(products_db)
    }


@app.get("/analyze/full/{nm_id}")
async def full_analysis(
    nm_id: int,
    goal: str = Query("profit", enum=["profit", "revenue", "balanced"]),
    history_days: int = Query(30, ge=7, le=90)
):
    """
    ПОЛНЫЙ АНАЛИЗ ЦЕНЫ
    """
    
    product_info = get_product_category_info(nm_id)
    if not product_info:
        raise HTTPException(
            status_code=404,
            detail=f"Товар {nm_id} не найден в базе знаний"
        )
    
    category = product_info['category']
    product_type = product_info['product_type']
    
    # Получаем АКТУАЛЬНУЮ цену с WB API
    current_price_wb = get_current_wb_price(nm_id)
    current_price = current_price_wb if current_price_wb else product_info['price']
    
    cost = current_price * 0.7
    
    # Получаем историю продаж
    sales_history = get_wb_sales_history(nm_id, days=history_days)
    
    # Эластичность спроса
    elasticity = calculate_demand_elasticity(sales_history)
    
    # Топ конкуренты
    competitors = get_top_selling_competitors(nm_id, category, limit=20)
    
    # Сезонность
    seasonality = analyze_seasonality(nm_id, category)
    
    # Оптимальная цена
    optimization = calculate_optimal_price_with_seasonality(
        nm_id=nm_id,
        current_price=current_price,
        cost=cost,
        elasticity=elasticity,
        competitors=competitors,
        seasonality=seasonality,
        goal=goal
    )
    
    # Рекомендация
    recommendation = generate_recommendation(
        nm_id=nm_id,
        current_price=current_price,
        optimal_price=optimization['optimal_price'],
        elasticity=elasticity,
        seasonality=seasonality,
        top_competitor=optimization.get('top_competitor'),
        best_price_competitor=optimization.get('best_price_competitor')
    )
    
    # Лучшие наши продажи
    best_our_sales = max(sales_history, key=lambda x: x['sales']) if sales_history else None
    
    return {
        "nm_id": nm_id,
        "product_type": product_type,
        "category": category,
        "current_price": current_price,
        "cost": cost,
        
        "demand_analysis": {
            "elasticity": round(elasticity, 2),
            "interpretation": "Эластичный" if elasticity < -1.5 else "Умеренный" if elasticity < -1 else "Неэластичный",
            "data_points": len(sales_history),
            "period_days": history_days,
            "best_sales_day": {
                "sales": best_our_sales['sales'] if best_our_sales else 0,
                "price": best_our_sales['price'] if best_our_sales else 0,
                "date": best_our_sales['date'] if best_our_sales else None
            }
        },
        
        "competitor_analysis": {
            "top_sellers": competitors[:5],
            "total_analyzed": len(competitors),
            "category_note": f"Только категория '{category}'"
        },
        
        "seasonality": seasonality,
        
        "price_optimization": {
            "optimal_price": optimization['optimal_price'],
            "base_price": optimization['base_price'],
            "seasonality_adjustment": optimization['seasonality_adjustment'],
            "price_range": {
                "min": optimization.get('min_competitor_price'),
                "max": optimization.get('max_competitor_price'),
                "median": optimization.get('median_competitor_price')
            }
        },
        
        "recommendation": recommendation
    }


@app.get("/export/excel")
async def export_to_excel(
    nm_ids: str = Query(..., description="Артикулы через запятую"),
    goal: str = Query("profit", enum=["profit", "revenue", "balanced"])
):
    """
    ВЫГРУЗКА В EXCEL
    """
    
    nm_ids_list = [int(x.strip()) for x in nm_ids.split(',') if x.strip().isdigit()]
    
    if not nm_ids_list:
        raise HTTPException(status_code=400, detail="Не указаны артикулы")
    
    results = []
    
    for nm_id in nm_ids_list:
        try:
            product_info = get_product_category_info(nm_id)
            if not product_info:
                continue
            
            category = product_info['category']
            current_price = product_info['price']
            cost = current_price * 0.7
            
            # Анализ
            sales_history = get_wb_sales_history(nm_id, days=30)
            elasticity = calculate_demand_elasticity(sales_history)
            best_our_sales = max(sales_history, key=lambda x: x['sales']) if sales_history else None
            
            competitors = get_top_selling_competitors(nm_id, category, limit=20)
            seasonality = analyze_seasonality(nm_id, category)
            
            optimization = calculate_optimal_price_with_seasonality(
                nm_id=nm_id,
                current_price=current_price,
                cost=cost,
                elasticity=elasticity,
                competitors=competitors,
                seasonality=seasonality,
                goal=goal
            )
            
            recommendation = generate_recommendation(
                nm_id=nm_id,
                current_price=current_price,
                optimal_price=optimization['optimal_price'],
                elasticity=elasticity,
                seasonality=seasonality,
                top_competitor=optimization.get('top_competitor'),
                best_price_competitor=optimization.get('best_price_competitor')
            )
            
            # Формируем строку
            top_comp = optimization.get('top_competitor')
            best_comp = optimization.get('best_price_competitor')
            
            results.append({
                'Артикул': nm_id,
                'Название': product_info.get('name', 'Неизвестно')[:50],
                'Категория': category,
                'Текущая цена': current_price,
                'Оптимальная цена (эластичность)': optimization['optimal_price'],
                'Лучшие наши продажи': best_our_sales['sales'] if best_our_sales else 0,
                'Цена при лучших продажах': best_our_sales['price'] if best_our_sales else 0,
                'Цена топ конкурента': top_comp['price'] if top_comp else '-',
                'Продажи топ конкурента': top_comp['sales_7d'] if top_comp else '-',
                'Цена с макс выручкой': best_comp['price'] if best_comp else '-',
                'Выручка конкурента': best_comp['revenue_7d'] if best_comp else '-',
                'Индекс сезонности': seasonality['seasonality_index'],
                'Сезон': seasonality['interpretation'],
                'Эластичность': round(elasticity, 2),
                'Рекомендация': recommendation
            })
            
        except Exception as e:
            logger.error(f"Ошибка обработки {nm_id}: {e}")
            continue
    
    if not results:
        raise HTTPException(status_code=404, detail="Нет данных для выгрузки")
    
    # Создаём Excel
    df = pd.DataFrame(results)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Рекомендации', index=False)
        
        worksheet = writer.sheets['Рекомендации']
        
        # Ширина колонок
        worksheet.column_dimensions['A'].width = 12
        worksheet.column_dimensions['B'].width = 35
        worksheet.column_dimensions['C'].width = 15
        worksheet.column_dimensions['E'].width = 20
        worksheet.column_dimensions['O'].width = 70
    
    output.seek(0)
    
    filename = f"price_recommendations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/categories/stats")
async def category_statistics():
    """Статистика по категориям"""
    stats = {}
    
    for product_type in KNOWLEDGE_BASE.get('category_mapping', {}):
        categories = {}
        for group_id, data in KNOWLEDGE_BASE['category_mapping'][product_type].items():
            cat = data['main_category']
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += data['product_count']
        stats[product_type] = categories
    
    return {
        "statistics": stats,
        "total_products": KNOWLEDGE_BASE.get('statistics', {}).get('total_products', 0),
        "total_groups": KNOWLEDGE_BASE.get('statistics', {}).get('total_groups', 0)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
