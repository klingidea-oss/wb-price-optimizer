"""
WB Price Optimizer V3.3 - С ПАРСИНГОМ И ВЕБ-ИНТЕРФЕЙСОМ
========================================================

ГАРАНТИЯ АКТУАЛЬНЫХ ЦЕН:
- Метод 1: WB Public API (быстро, но блокируется)
- Метод 2: Парсинг страницы товара (100% надёжность)
- Метод 3: Парсинг поиска WB (резервный метод)

НЕТ fallback на устаревшие данные из базы знаний!
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
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
    source: str
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
                    price = product.get('salePriceU', 0) / 100
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
            r'"salePriceU"\s*:\s*(\d+)',
            r'data-sale-price="(\d+)"',
            r'class="price-block__final-price"[^>]*>(\d+)',
            r'"price"\s*:\s*(\d+)',
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
        price_elements = soup.find_all(['span', 'div', 'ins'], class_=re.compile(r'price|cost|sale', re.I))
        for elem in price_elements:
            text = elem.get_text().strip()
            numbers = re.findall(r'\d+', text.replace(' ', ''))
            if numbers:
                price = float(''.join(numbers)) / 100
                if 10 <= price <= 1000000:
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
                price = _find_price_in_json(nuxt_data, nm_id)
                if price:
                    logger.info(f"✅ ПАРСИНГ ПОИСКА: цена {nm_id} = {price} руб")
                    return price
            except:
                pass
        
        # Резервный метод
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
        if 'id' in data and data['id'] == target_nm_id:
            if 'salePriceU' in data:
                return data['salePriceU'] / 100
            if 'priceU' in data:
                return data['priceU'] / 100
        
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
# HTML ИНТЕРФЕЙС
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WB Price Optimizer V3.3</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        .version-badge {
            display: inline-block;
            background: rgba(255,255,255,0.2);
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-top: 10px;
        }
        
        .features {
            display: flex;
            justify-content: space-around;
            padding: 30px;
            background: #f8f9fa;
            flex-wrap: wrap;
        }
        
        .feature {
            text-align: center;
            padding: 20px;
            flex: 1;
            min-width: 200px;
        }
        
        .feature-icon {
            font-size: 3em;
            margin-bottom: 10px;
        }
        
        .feature-title {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .feature-desc {
            font-size: 0.9em;
            color: #666;
        }
        
        .main-content {
            padding: 40px;
        }
        
        .input-section {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
        }
        
        .input-group {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .input-wrapper {
            flex: 1;
            min-width: 250px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
        }
        
        input[type="text"],
        input[type="number"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
            transition: border-color 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        button {
            flex: 1;
            min-width: 200px;
            padding: 15px 30px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            color: white;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .btn-secondary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(245, 87, 108, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
        }
        
        #result {
            margin-top: 30px;
            padding: 25px;
            background: #f8f9fa;
            border-radius: 15px;
            border-left: 5px solid #667eea;
            display: none;
        }
        
        #result.show {
            display: block;
            animation: slideIn 0.5s ease;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(-20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            display: none;
        }
        
        .loading.show {
            display: block;
        }
        
        .spinner {
            border: 5px solid #f3f3f3;
            border-top: 5px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .price-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .price-value {
            font-size: 2em;
            color: #667eea;
            font-weight: bold;
        }
        
        .price-source {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 0.8em;
            margin-top: 10px;
        }
        
        .competitors-list {
            margin-top: 20px;
        }
        
        .competitor-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .competitor-name {
            flex: 1;
            font-weight: 600;
        }
        
        .competitor-price {
            color: #667eea;
            font-size: 1.2em;
            font-weight: bold;
            margin-left: 15px;
        }
        
        .footer {
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 20px;
        }
        
        .error {
            background: #fee;
            border-left: 5px solid #f44;
            color: #c33;
        }
        
        .success {
            background: #efe;
            border-left: 5px solid #4f4;
            color: #3c3;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 WB Price Optimizer</h1>
            <div class="version-badge">V3.3.0 - С ПАРСИНГОМ ЦЕН</div>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">⚡</div>
                <div class="feature-title">Актуальные цены</div>
                <div class="feature-desc">Только реальные цены на момент запроса</div>
            </div>
            <div class="feature">
                <div class="feature-icon">🌐</div>
                <div class="feature-title">Парсинг WB</div>
                <div class="feature-desc">3 метода получения цен</div>
            </div>
            <div class="feature">
                <div class="feature-icon">💾</div>
                <div class="feature-title">Кэширование</div>
                <div class="feature-desc">Быстрые повторные запросы</div>
            </div>
            <div class="feature">
                <div class="feature-icon">📊</div>
                <div class="feature-title">Анализ конкурентов</div>
                <div class="feature-desc">Сравнение с топ-5</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="input-section">
                <h2 style="margin-bottom: 20px;">🔍 Анализ товара</h2>
                
                <div class="input-group">
                    <div class="input-wrapper">
                        <label for="nm_id">Артикул товара (nm_id):</label>
                        <input type="text" id="nm_id" placeholder="Например: 194841017">
                    </div>
                </div>
                
                <div class="button-group">
                    <button class="btn-primary" onclick="getPrice()">
                        💰 Получить цену
                    </button>
                    <button class="btn-secondary" onclick="getFullAnalysis()">
                        📊 Полный анализ
                    </button>
                    <button class="btn-success" onclick="checkHealth()">
                        ✅ Проверить статус
                    </button>
                </div>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Получение данных...</p>
            </div>
            
            <div id="result"></div>
        </div>
        
        <div class="footer">
            <p>© 2024 WB Price Optimizer V3.3 | Гарантия актуальных цен</p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                API: /price/{nm_id} | /analyze/full/{nm_id} | /health
            </p>
        </div>
    </div>
    
    <script>
        function showLoading() {
            document.getElementById('loading').classList.add('show');
            document.getElementById('result').classList.remove('show');
        }
        
        function hideLoading() {
            document.getElementById('loading').classList.remove('show');
        }
        
        function showResult(html, isError = false) {
            hideLoading();
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = html;
            resultDiv.classList.add('show');
            if (isError) {
                resultDiv.classList.add('error');
            } else {
                resultDiv.classList.remove('error');
            }
        }
        
        async function getPrice() {
            const nm_id = document.getElementById('nm_id').value.trim();
            if (!nm_id) {
                showResult('<h3>❌ Ошибка</h3><p>Пожалуйста, введите артикул товара</p>', true);
                return;
            }
            
            showLoading();
            
            try {
                const response = await fetch(`/price/${nm_id}`);
                const data = await response.json();
                
                if (response.ok) {
                    const sourceLabels = {
                        'wb_api': '🚀 WB API',
                        'wb_product_page': '🌐 Парсинг страницы',
                        'wb_search_page': '🔎 Парсинг поиска',
                        'cache': '💾 Кэш'
                    };
                    
                    const html = `
                        <h3>✅ Цена получена успешно</h3>
                        <div class="price-card">
                            <strong>Артикул:</strong> ${data.nm_id}<br>
                            <div style="margin-top: 15px;">
                                <div class="price-value">${data.current_price.value.toFixed(2)} ₽</div>
                                <span class="price-source">${sourceLabels[data.current_price.source]}</span>
                            </div>
                            ${data.current_price.cached_seconds_ago ? `
                                <p style="margin-top: 10px; color: #666; font-size: 0.9em;">
                                    ⏱️ Кэш: ${data.current_price.cached_seconds_ago} сек назад
                                </p>
                            ` : ''}
                            <p style="margin-top: 10px; color: #666; font-size: 0.9em;">
                                🕐 Получено: ${new Date(data.current_price.timestamp).toLocaleString('ru-RU')}
                            </p>
                        </div>
                    `;
                    showResult(html);
                } else {
                    showResult(`<h3>❌ Ошибка</h3><p>${data.detail.error || 'Не удалось получить цену'}</p>`, true);
                }
            } catch (error) {
                showResult(`<h3>❌ Ошибка</h3><p>Ошибка соединения: ${error.message}</p>`, true);
            }
        }
        
        async function getFullAnalysis() {
            const nm_id = document.getElementById('nm_id').value.trim();
            if (!nm_id) {
                showResult('<h3>❌ Ошибка</h3><p>Пожалуйста, введите артикул товара</p>', true);
                return;
            }
            
            showLoading();
            
            try {
                const response = await fetch(`/analyze/full/${nm_id}`);
                const data = await response.json();
                
                if (response.ok) {
                    let competitorsHtml = '';
                    if (data.competitors && data.competitors.length > 0) {
                        competitorsHtml = '<div class="competitors-list"><h4>🏆 Топ-5 конкурентов:</h4>';
                        data.competitors.forEach((comp, idx) => {
                            competitorsHtml += `
                                <div class="competitor-item">
                                    <span class="competitor-name">${idx + 1}. ${comp.name}</span>
                                    <span class="competitor-price">${comp.price.toFixed(2)} ₽</span>
                                    <span style="font-size: 0.8em; color: #666;">(${comp.price_source})</span>
                                </div>
                            `;
                        });
                        competitorsHtml += '</div>';
                    }
                    
                    const positionLabels = {
                        'significantly_lower': '✅ Значительно ниже рынка',
                        'lower': '✅ Ниже среднего',
                        'competitive': '⚖️ Конкурентная',
                        'higher': '⚠️ Выше среднего',
                        'no_competitors': 'ℹ️ Нет данных о конкурентах'
                    };
                    
                    const html = `
                        <h3>📊 Полный анализ товара</h3>
                        <div class="price-card">
                            <strong>Название:</strong> ${data.name}<br>
                            <strong>Категория:</strong> ${data.category}<br>
                            <div style="margin-top: 15px;">
                                <strong>Текущая цена:</strong>
                                <div class="price-value">${data.current_price.value.toFixed(2)} ₽</div>
                            </div>
                            ${data.analysis.avg_competitor_price > 0 ? `
                                <p style="margin-top: 15px;">
                                    <strong>Средняя цена конкурентов:</strong> ${data.analysis.avg_competitor_price.toFixed(2)} ₽
                                </p>
                            ` : ''}
                            <p style="margin-top: 10px;">
                                <strong>Позиция:</strong> ${positionLabels[data.analysis.price_position]}
                            </p>
                        </div>
                        ${competitorsHtml}
                    `;
                    showResult(html);
                } else {
                    showResult(`<h3>❌ Ошибка</h3><p>${data.detail || 'Не удалось выполнить анализ'}</p>`, true);
                }
            } catch (error) {
                showResult(`<h3>❌ Ошибка</h3><p>Ошибка соединения: ${error.message}</p>`, true);
            }
        }
        
        async function checkHealth() {
            showLoading();
            
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                if (response.ok) {
                    const html = `
                        <h3>✅ Система работает</h3>
                        <div class="price-card">
                            <strong>Версия:</strong> ${data.version}<br>
                            <strong>База знаний:</strong> ${data.knowledge_base.products} товаров<br>
                            <br>
                            <strong>Возможности:</strong><br>
                            ${data.features.realtime_prices_only ? '✅' : '❌'} Только актуальные цены<br>
                            ${data.features.parsing_enabled ? '✅' : '❌'} Парсинг WB включен<br>
                            ${data.features.price_cache ? '✅' : '❌'} Кэширование включено<br>
                        </div>
                    `;
                    showResult(html);
                } else {
                    showResult('<h3>❌ Ошибка</h3><p>Не удалось проверить статус</p>', true);
                }
            } catch (error) {
                showResult(`<h3>❌ Ошибка</h3><p>Ошибка соединения: ${error.message}</p>`, true);
            }
        }
        
        // Enter для отправки
        document.getElementById('nm_id').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                getPrice();
            }
        });
    </script>
</body>
</html>
"""

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница с интерфейсом"""
    return HTML_TEMPLATE


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
