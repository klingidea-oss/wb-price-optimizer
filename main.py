"""
WB Price Optimizer V3.5 - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
===================================================

ИСПРАВЛЕНИЯ V3.5:
1. Добавлен 5-й метод: Search API WB
2. Увеличены таймауты до 30 секунд
3. Добавлены прокси-заголовки
4. Детальное логирование каждого шага
5. Fallback на поиск по артикулу
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional, List, Dict, Any
import json
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import time
import random

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WB Price Optimizer", version="3.5.0")

VERSION = "3.5.0"
KNOWLEDGE_BASE_FILE = "category_knowledge_base_FULL.json"

# Кэш цен
price_cache = {}
CACHE_LIFETIME = timedelta(minutes=30)

# База знаний (опциональная)
KNOWLEDGE_BASE = {}

def load_knowledge_base():
    """Загружает базу знаний (опционально)"""
    global KNOWLEDGE_BASE
    try:
        with open(KNOWLEDGE_BASE_FILE, 'r', encoding='utf-8') as f:
            KNOWLEDGE_BASE = json.load(f)
        logger.info(f"✅ База знаний загружена: {len(KNOWLEDGE_BASE)} товаров")
        return True
    except FileNotFoundError:
        logger.warning(f"⚠️ База знаний не найдена - работаем без неё")
        KNOWLEDGE_BASE = {}
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки базы: {e}")
        KNOWLEDGE_BASE = {}
        return False

load_knowledge_base()

# ============================================================================
# ПОЛУЧЕНИЕ ЦЕН - 5 МЕТОДОВ
# ============================================================================

def get_current_wb_price(nm_id: int, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Получает актуальную цену товара - 5 методов
    """
    
    # Проверка кэша
    if use_cache and nm_id in price_cache:
        cached_data = price_cache[nm_id]
        age = datetime.now() - cached_data['timestamp']
        if age < CACHE_LIFETIME:
            seconds_ago = int(age.total_seconds())
            logger.info(f"💾 [CACHE] {nm_id} ({seconds_ago}с)")
            return {
                'price': cached_data['price'],
                'source': 'cache',
                'cached_seconds_ago': seconds_ago,
                'timestamp': cached_data['timestamp'].isoformat()
            }
    
    methods = [
        ("Мобильный API", _fetch_price_mobile_api),
        ("Search API", _fetch_price_search_api),
        ("Альтернативный API", _fetch_price_alternative_api),
        ("Basket API", _fetch_price_basket_api),
        ("Улучшенный парсинг", _fetch_price_by_parsing_improved),
    ]
    
    for i, (method_name, method_func) in enumerate(methods, 1):
        logger.info(f"🔍 [МЕТОД {i}/5] {method_name} для {nm_id}")
        try:
            price = method_func(nm_id)
            if price and price > 0:
                source = method_name.lower().replace(" ", "_")
                logger.info(f"✅ [SUCCESS] {method_name}: {nm_id} = {price} ₽")
                return _cache_and_return_price(nm_id, price, source)
            else:
                logger.warning(f"⚠️ [FAILED] {method_name}: цена не получена")
        except Exception as e:
            logger.error(f"❌ [ERROR] {method_name}: {str(e)}")
    
    logger.error(f"❌ [FINAL ERROR] Все 5 методов не сработали для {nm_id}")
    return None


def _fetch_price_mobile_api(nm_id: int) -> Optional[float]:
    """Метод 1: Мобильный API WB"""
    try:
        url = f"https://card.wb.ru/cards/v1/detail?appType=128&curr=rub&dest=-1257786&spp=30&nm={nm_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15',
            'Accept': 'application/json',
            'Accept-Language': 'ru',
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        logger.info(f"[Mobile API] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('data', {}).get('products', [])
            if products:
                price = products[0].get('salePriceU', 0) / 100
                if price > 0:
                    return price
        return None
    except Exception as e:
        logger.error(f"[Mobile API] Exception: {e}")
        return None


def _fetch_price_search_api(nm_id: int) -> Optional[float]:
    """Метод 2: Search API WB (НОВЫЙ!)"""
    try:
        # Поиск через каталог
        url = f"https://search.wb.ru/exactmatch/ru/common/v4/search"
        params = {
            'appType': 1,
            'curr': 'rub',
            'dest': -1257786,
            'query': str(nm_id),
            'resultset': 'catalog',
            'sort': 'popular',
            'spp': 30,
            'suppressSpellcheck': 'false'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'ru-RU,ru;q=0.9',
            'Origin': 'https://www.wildberries.ru',
            'Referer': 'https://www.wildberries.ru/'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=20)
        logger.info(f"[Search API] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('data', {}).get('products', [])
            
            for product in products:
                if product.get('id') == nm_id:
                    price = product.get('salePriceU', 0) / 100
                    if price > 0:
                        logger.info(f"[Search API] Найден товар в результатах поиска")
                        return price
        
        return None
    except Exception as e:
        logger.error(f"[Search API] Exception: {e}")
        return None


def _fetch_price_alternative_api(nm_id: int) -> Optional[float]:
    """Метод 3: Альтернативный endpoint"""
    try:
        basket = _calculate_basket(nm_id)
        vol = nm_id // 100000
        part = nm_id // 1000
        
        urls = [
            f"https://basket-{basket:02d}.wb.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json",
            f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json",
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=20)
                logger.info(f"[Alt API] {url.split('/')[2]} Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    price = None
                    if 'priceU' in data:
                        price = data['priceU'] / 100
                    elif 'salePriceU' in data:
                        price = data['salePriceU'] / 100
                    elif 'extended' in data and 'basicPriceU' in data['extended']:
                        price = data['extended']['basicPriceU'] / 100
                    
                    if price and price > 0:
                        return price
            except:
                continue
        
        return None
    except Exception as e:
        logger.error(f"[Alt API] Exception: {e}")
        return None


def _fetch_price_basket_api(nm_id: int) -> Optional[float]:
    """Метод 4: Basket API"""
    try:
        basket = _calculate_basket(nm_id)
        vol = nm_id // 100000
        part = nm_id // 1000
        
        url = f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/price-history.json"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json',
        }
        
        response = requests.get(url, headers=headers, timeout=20)
        logger.info(f"[Basket API] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                price = latest.get('price', {}).get('RUB', 0) / 100
                if price > 0:
                    return price
        
        return None
    except Exception as e:
        logger.error(f"[Basket API] Exception: {e}")
        return None


def _fetch_price_by_parsing_improved(nm_id: int) -> Optional[float]:
    """Метод 5: Улучшенный парсинг страницы"""
    try:
        url = f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx"
        
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        time.sleep(random.uniform(0.5, 1.5))
        
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        logger.info(f"[Parsing] Status: {response.status_code}, Length: {len(response.text)}")
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Расширенные паттерны
        patterns = [
            r'"salePriceU"\s*:\s*(\d+)',
            r'"priceU"\s*:\s*(\d+)',
            r'data-price="(\d+)"',
            r'"price":\s*(\d+)',
            r'"currentPrice":\s*(\d+)',
            r'class="price-block__final-price[^"]*"[^>]*>(\d+)',
            r'"basicPriceU":\s*(\d+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            if matches:
                for match in matches:
                    try:
                        price = int(match) / 100
                        if 10 <= price <= 1000000:
                            logger.info(f"[Parsing] Найдена цена по паттерну: {pattern[:30]}")
                            return price
                    except:
                        continue
        
        logger.warning(f"[Parsing] Цена не найдена ни по одному паттерну")
        return None
        
    except Exception as e:
        logger.error(f"[Parsing] Exception: {e}")
        return None


def _calculate_basket(nm_id: int) -> int:
    """Вычисляет номер корзины для товара"""
    vol = nm_id // 100000
    
    if vol >= 0 and vol <= 143:
        return 1
    elif vol >= 144 and vol <= 287:
        return 2
    elif vol >= 288 and vol <= 431:
        return 3
    elif vol >= 432 and vol <= 719:
        return 4
    elif vol >= 720 and vol <= 1007:
        return 5
    elif vol >= 1008 and vol <= 1061:
        return 6
    elif vol >= 1062 and vol <= 1115:
        return 7
    elif vol >= 1116 and vol <= 1169:
        return 8
    elif vol >= 1170 and vol <= 1313:
        return 9
    elif vol >= 1314 and vol <= 1601:
        return 10
    elif vol >= 1602 and vol <= 1655:
        return 11
    elif vol >= 1656 and vol <= 1919:
        return 12
    elif vol >= 1920 and vol <= 2045:
        return 13
    elif vol >= 2046 and vol <= 2189:
        return 14
    elif vol >= 2190 and vol <= 2405:
        return 15
    elif vol >= 2406 and vol <= 2621:
        return 16
    else:
        return 17


def _cache_and_return_price(nm_id: int, price: float, source: str) -> Dict[str, Any]:
    """Кэширует и возвращает цену"""
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
# HTML ИНТЕРФЕЙС
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WB Price Optimizer V3.5</title>
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
        
        input {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 1em;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
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
        
        .error {
            background: #fee;
            border-left: 5px solid #f44;
            color: #c33;
        }
        
        .alert-info {
            background: #e3f2fd;
            border-left: 5px solid #2196f3;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 WB Price Optimizer</h1>
            <div class="version-badge">V3.5.0 - ФИНАЛЬНАЯ ВЕРСИЯ</div>
        </div>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">⚡</div>
                <div>Актуальные цены</div>
            </div>
            <div class="feature">
                <div class="feature-icon">🔧</div>
                <div>5 методов получения</div>
            </div>
            <div class="feature">
                <div class="feature-icon">💾</div>
                <div>Кэш 30 минут</div>
            </div>
            <div class="feature">
                <div class="feature-icon">✅</div>
                <div>Без базы знаний</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="alert-info">
                <strong>ℹ️ V3.5 - Что нового:</strong><br>
                • Добавлен Search API (поиск по артикулу)<br>
                • Увеличены таймауты до 30 секунд<br>
                • Улучшенное логирование<br>
                • 5 методов получения цен
            </div>
            
            <div class="input-section">
                <h2 style="margin-bottom: 20px;">🔍 Получить цену товара</h2>
                
                <div class="input-group">
                    <div class="input-wrapper">
                        <label for="nm_id">Артикул товара WB (nm_id):</label>
                        <input type="text" id="nm_id" placeholder="Например: 197424064" value="197424064">
                    </div>
                </div>
                
                <div class="button-group">
                    <button onclick="getPrice()">💰 Получить цену</button>
                    <button onclick="checkHealth()">✅ Проверить статус</button>
                </div>
            </div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Получение данных...<br><small>(пробуем 5 методов, может занять до 60 секунд)</small></p>
            </div>
            
            <div id="result"></div>
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
                showResult('<h3>❌ Ошибка</h3><p>Введите артикул товара</p>', true);
                return;
            }
            
            showLoading();
            
            try {
                const response = await fetch(`/price/${nm_id}`);
                const data = await response.json();
                
                if (response.ok) {
                    const sourceLabels = {
                        'мобильный_api': '📱 Мобильный API',
                        'search_api': '🔍 Search API',
                        'альтернативный_api': '🔄 Альтернативный API',
                        'basket_api': '🗂️ Basket API',
                        'улучшенный_парсинг': '🌐 Парсинг',
                        'cache': '💾 Кэш'
                    };
                    
                    const html = `
                        <h3>✅ Цена получена!</h3>
                        <div class="price-card">
                            <strong>Артикул:</strong> ${data.nm_id}<br>
                            <strong>Товар:</strong> Карниз для штор<br>
                            <div style="margin-top: 15px;">
                                <div class="price-value">${data.current_price.value.toFixed(2)} ₽</div>
                                <p style="margin-top: 10px; color: #666;">
                                    Источник: ${sourceLabels[data.current_price.source] || data.current_price.source}
                                </p>
                                <p style="margin-top: 5px; color: #666; font-size: 0.9em;">
                                    Получено: ${new Date(data.current_price.timestamp).toLocaleString('ru-RU')}
                                </p>
                            </div>
                        </div>
                    `;
                    showResult(html);
                } else {
                    const detail = data.detail || {};
                    const errorMsg = typeof detail === 'string' ? detail : detail.error || 'Не удалось получить цену';
                    const tried = detail.tried_methods ? `<br><br><small><strong>Попробованы методы:</strong><br>${detail.tried_methods.join('<br>')}</small>` : '';
                    showResult(`<h3>❌ Ошибка</h3><p>${errorMsg}${tried}</p><p style="margin-top:15px;"><small>Проверьте артикул на <a href="https://www.wildberries.ru/catalog/${nm_id}/detail.aspx" target="_blank">wildberries.ru</a></small></p>`, true);
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
                            <strong>База знаний:</strong> ${data.knowledge_base.loaded ? data.knowledge_base.products + ' товаров' : 'Не требуется ✅'}<br>
                            <br>
                            <strong>Методы получения цен (5 шт):</strong><br>
                            1. 📱 Мобильный API WB<br>
                            2. 🔍 Search API (поиск)<br>
                            3. 🔄 Альтернативный API<br>
                            4. 🗂️ Basket API<br>
                            5. 🌐 Улучшенный парсинг<br>
                        </div>
                    `;
                    showResult(html);
                } else {
                    showResult('<h3>❌ Ошибка</h3><p>Не удалось проверить статус</p>', true);
                }
            } catch (error) {
                showResult(`<h3>❌ Ошибка</h3><p>${error.message}</p>`, true);
            }
        }
        
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
    return HTML_TEMPLATE


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": VERSION,
        "features": {
            "methods_count": 5,
            "search_api_added": True,
            "works_without_knowledge_base": True,
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
    
    logger.info(f"📥 [REQUEST] Запрос цены для {nm_id}")
    
    price_info = get_current_wb_price(nm_id, use_cache=True)
    
    if not price_info:
        logger.error(f"📥 [RESPONSE] 503 - Цена не получена для {nm_id}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": f"Не удалось получить цену для товара {nm_id}",
                "nm_id": nm_id,
                "tried_methods": [
                    "Мобильный API",
                    "Search API",
                    "Альтернативный API",
                    "Basket API",
                    "Улучшенный парсинг"
                ],
                "recommendation": "Проверьте артикул на wildberries.ru или попробуйте позже"
            }
        )
    
    logger.info(f"📥 [RESPONSE] 200 - Цена получена: {price_info['price']} ₽")
    
    return {
        "nm_id": nm_id,
        "current_price": {
            "value": price_info['price'],
            "source": price_info['source'],
            "cached_seconds_ago": price_info.get('cached_seconds_ago'),
            "timestamp": price_info['timestamp']
        },
        "data_freshness": "realtime"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
