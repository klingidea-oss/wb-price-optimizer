"""
WB Price Optimizer V3.8 - HYBRID INTELLIGENCE
============================================

✅ ИСПОЛЬЗУЕТ ВАШУ БАЗУ ЗНАНИЙ (8089 товаров, период 24.11-07.12.25)
✅ НЕ ДЕЛАЕТ ЗАПРОСОВ К WB API (нет блокировок)
✅ АКТУАЛЬНЫЕ ЦЕНЫ из вашего файла
✅ ИНТЕЛЛЕКТУАЛЬНЫЙ ПОДБОР конкурентов по категориям

Особенности V3.8:
- Полностью автономная работа без внешних API
- База знаний из ваших реальных данных
- Конкуренты подбираются по категории и выручке
- Цены актуальны на период 24.11-07.12.25
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import logging
from datetime import datetime
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI приложение
app = FastAPI(
    title="WB Price Optimizer V3.8",
    description="Hybrid Intelligence System - использует вашу базу знаний",
    version="3.8.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальная база знаний
KNOWLEDGE_BASE = {
    "loaded": False,
    "version": "0.0.0",
    "source": "",
    "period": "",
    "total_products": 0,
    "categories": {},
    "products": [],
    "products_by_id": {}  # Быстрый поиск по ID
}

def load_knowledge_base():
    """Загрузка базы знаний из JSON файла"""
    global KNOWLEDGE_BASE
    
    try:
        # Пробуем загрузить из разных мест
        paths = [
            "/app/category_knowledge_base.json",  # Render
            "./category_knowledge_base.json",     # Локально
            "/home/user/data/category_knowledge_base.json"  # Sandbox
        ]
        
        for path in paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    kb = json.load(f)
                    
                    # Создаем индекс для быстрого поиска
                    products_by_id = {}
                    for product in kb.get('products', []):
                        products_by_id[product['nm_id']] = product
                    
                    KNOWLEDGE_BASE = {
                        "loaded": True,
                        "version": kb.get('version', '3.8.0'),
                        "source": kb.get('source', 'WB_latest.xlsx'),
                        "period": kb.get('period', '24.11.25-07.12.25'),
                        "total_products": kb.get('total_products', 0),
                        "categories": kb.get('categories', {}),
                        "products": kb.get('products', []),
                        "products_by_id": products_by_id
                    }
                    
                    logger.info(f"✅ База знаний загружена из {path}")
                    logger.info(f"   Товаров: {KNOWLEDGE_BASE['total_products']}")
                    logger.info(f"   Категорий: {len(KNOWLEDGE_BASE['categories'])}")
                    logger.info(f"   Период: {KNOWLEDGE_BASE['period']}")
                    return True
                    
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при загрузке {path}: {e}")
                continue
        
        logger.warning("⚠️ База знаний не найдена ни в одном из путей")
        return False
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при загрузке базы знаний: {e}")
        return False

# Загружаем базу знаний при старте
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 WB Price Optimizer V3.8 запускается...")
    load_knowledge_base()
    if KNOWLEDGE_BASE['loaded']:
        logger.info(f"✅ Система готова к работе с базой знаний ({KNOWLEDGE_BASE['total_products']} товаров)")
    else:
        logger.warning("⚠️ Система запущена БЕЗ базы знаний")

@app.get("/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "version": "3.8.0",
        "features": {
            "hybrid_intelligence": True,
            "local_knowledge_base": True,
            "no_external_api": True,
            "smart_competitor_matching": True,
            "excel_export": True
        },
        "knowledge_base": {
            "loaded": KNOWLEDGE_BASE['loaded'],
            "products": KNOWLEDGE_BASE['total_products'],
            "categories": len(KNOWLEDGE_BASE['categories']),
            "source": KNOWLEDGE_BASE['source'],
            "period": KNOWLEDGE_BASE['period']
        }
    }

def get_product_info(nm_id: int) -> Optional[Dict]:
    """Получение информации о товаре из базы знаний"""
    if not KNOWLEDGE_BASE['loaded']:
        return None
    
    return KNOWLEDGE_BASE['products_by_id'].get(nm_id)

def get_competitors(nm_id: int, limit: int = 5) -> List[Dict]:
    """Получение конкурентов из той же категории"""
    if not KNOWLEDGE_BASE['loaded']:
        return []
    
    # Получаем информацию о товаре
    product = get_product_info(nm_id)
    if not product:
        logger.warning(f"⚠️ Товар {nm_id} не найден в базе знаний")
        return []
    
    category = product.get('category')
    if not category or category not in KNOWLEDGE_BASE['categories']:
        logger.warning(f"⚠️ Категория '{category}' не найдена")
        return []
    
    # Получаем топ конкурентов из той же категории
    top_performers = KNOWLEDGE_BASE['categories'][category].get('top_performers', [])
    
    # Исключаем сам товар
    competitors = []
    for comp_id in top_performers:
        if comp_id != nm_id:
            comp = get_product_info(comp_id)
            if comp:
                competitors.append({
                    "nm_id": comp['nm_id'],
                    "name": comp['name'],
                    "brand": comp['brand'],
                    "price": comp['avg_price'],  # Средняя цена
                    "revenue": comp['revenue'],  # Выручка для сортировки
                    "sales": comp['sales_count']
                })
                
                if len(competitors) >= limit:
                    break
    
    logger.info(f"✅ Найдено {len(competitors)} конкурентов для товара {nm_id} в категории '{category}'")
    return competitors

@app.get("/price/{nm_id}")
async def get_price(nm_id: int):
    """Получение цены товара"""
    try:
        product = get_product_info(nm_id)
        
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Товар {nm_id} не найден в базе знаний"
            )
        
        return {
            "nm_id": nm_id,
            "current_price": {
                "value": product['avg_price'],
                "source": "knowledge_base",
                "period": KNOWLEDGE_BASE['period']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при получении цены {nm_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/full/{nm_id}")
async def analyze_full(nm_id: int):
    """Полный анализ с конкурентами"""
    try:
        product = get_product_info(nm_id)
        
        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Товар {nm_id} не найден в базе знаний (всего: {KNOWLEDGE_BASE['total_products']} товаров)"
            )
        
        # Получаем конкурентов
        competitors = get_competitors(nm_id, limit=5)
        
        # Анализ цен
        competitor_prices = [c['price'] for c in competitors if c['price'] > 0]
        avg_competitor_price = sum(competitor_prices) / len(competitor_prices) if competitor_prices else 0
        
        return {
            "nm_id": nm_id,
            "name": product['name'],
            "category": product['category'],
            "brand": product['brand'],
            "current_price": {
                "value": product['avg_price'],
                "source": "knowledge_base",
                "period": KNOWLEDGE_BASE['period']
            },
            "competitors": competitors,
            "analysis": {
                "avg_competitor_price": round(avg_competitor_price, 2),
                "competitors_count": len(competitors),
                "price_position": "Выше среднего" if product['avg_price'] > avg_competitor_price else "Ниже среднего" if avg_competitor_price > 0 else "Нет данных",
                "recommendation": "Рассмотрите снижение цены" if product['avg_price'] > avg_competitor_price * 1.1 else "Цена конкурентоспособна"
            },
            "search_method": "knowledge_base_by_category"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при анализе {nm_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/export/excel/{nm_id}")
async def export_excel(nm_id: int):
    """Экспорт анализа в Excel"""
    try:
        # Получаем полный анализ
        analysis = await analyze_full(nm_id)
        
        # Создаем Excel файл
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Анализ конкурентов"
        
        # Заголовок
        ws['A1'] = "WB Price Optimizer V3.8 - Анализ конкурентов"
        ws['A1'].font = Font(size=14, bold=True)
        ws.merge_cells('A1:F1')
        
        # Информация о товаре
        ws['A3'] = "Артикул:"
        ws['B3'] = analysis['nm_id']
        ws['A4'] = "Название:"
        ws['B4'] = analysis['name']
        ws['A5'] = "Категория:"
        ws['B5'] = analysis['category']
        ws['A6'] = "Ваша цена:"
        ws['B6'] = f"{analysis['current_price']['value']:.2f} ₽"
        ws['A7'] = "Период данных:"
        ws['B7'] = KNOWLEDGE_BASE['period']
        
        # Конкуренты
        ws['A9'] = "Топ-5 конкурентов"
        ws['A9'].font = Font(size=12, bold=True)
        
        headers = ['№', 'Артикул', 'Название', 'Бренд', 'Цена', 'Выручка']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=10, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        for idx, comp in enumerate(analysis['competitors'], 1):
            ws.cell(row=10+idx, column=1, value=idx)
            ws.cell(row=10+idx, column=2, value=comp['nm_id'])
            ws.cell(row=10+idx, column=3, value=comp['name'])
            ws.cell(row=10+idx, column=4, value=comp['brand'])
            ws.cell(row=10+idx, column=5, value=f"{comp['price']:.2f} ₽")
            ws.cell(row=10+idx, column=6, value=f"{comp['revenue']:,.0f} ₽")
        
        # Сохраняем в BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=wb_analysis_{nm_id}.xlsx"}
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при экспорте в Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница с веб-интерфейсом"""
    
    kb_status = "✅ Загружена" if KNOWLEDGE_BASE['loaded'] else "⚠️ Не загружена"
    kb_badge_color = "#10b981" if KNOWLEDGE_BASE['loaded'] else "#f59e0b"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WB Price Optimizer V3.8</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 900px;
                margin: 0 auto;
            }}
            
            .header {{
                background: white;
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            
            .title {{
                font-size: 32px;
                font-weight: 700;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}
            
            .status {{
                display: flex;
                gap: 15px;
                flex-wrap: wrap;
                margin-top: 20px;
            }}
            
            .badge {{
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 8px;
            }}
            
            .badge-kb {{
                background: {kb_badge_color};
                color: white;
            }}
            
            .badge-version {{
                background: #3b82f6;
                color: white;
            }}
            
            .badge-products {{
                background: #8b5cf6;
                color: white;
            }}
            
            .main-card {{
                background: white;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            
            .input-group {{
                margin-bottom: 20px;
            }}
            
            label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #374151;
            }}
            
            input {{
                width: 100%;
                padding: 12px 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                font-size: 16px;
                transition: all 0.3s;
            }}
            
            input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .button-group {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
            }}
            
            .btn {{
                flex: 1;
                min-width: 150px;
                padding: 14px 24px;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
            
            .btn-primary {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }}
            
            .btn-primary:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }}
            
            .btn-secondary {{
                background: #10b981;
                color: white;
            }}
            
            .btn-secondary:hover {{
                background: #059669;
                transform: translateY(-2px);
            }}
            
            .btn-info {{
                background: #3b82f6;
                color: white;
            }}
            
            .btn-info:hover {{
                background: #2563eb;
                transform: translateY(-2px);
            }}
            
            .result {{
                margin-top: 20px;
                padding: 20px;
                border-radius: 10px;
                background: #f9fafb;
                border: 2px solid #e5e7eb;
                display: none;
            }}
            
            .result.show {{
                display: block;
                animation: slideIn 0.3s ease-out;
            }}
            
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            
            .loading {{
                text-align: center;
                padding: 20px;
                color: #6b7280;
            }}
            
            .spinner {{
                border: 3px solid #f3f4f6;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }}
            
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            .competitor-card {{
                background: white;
                padding: 15px;
                border-radius: 10px;
                margin-top: 10px;
                border: 1px solid #e5e7eb;
            }}
            
            .price-badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 15px;
                font-size: 14px;
                font-weight: 600;
                background: #dbeafe;
                color: #1e40af;
            }}
            
            .features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }}
            
            .feature-card {{
                background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
            }}
            
            .feature-icon {{
                font-size: 32px;
                margin-bottom: 10px;
            }}
            
            .feature-title {{
                font-weight: 600;
                color: #374151;
                margin-bottom: 5px;
            }}
            
            .feature-desc {{
                font-size: 14px;
                color: #6b7280;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title">🚀 WB Price Optimizer V3.8</div>
                <p style="color: #6b7280; margin-top: 10px;">Hybrid Intelligence System - Анализ конкурентов на основе вашей базы знаний</p>
                <div class="status">
                    <span class="badge badge-version">📦 Версия: 3.8.0</span>
                    <span class="badge badge-kb">📚 База знаний: {kb_status} ({KNOWLEDGE_BASE['total_products']} товаров)</span>
                    <span class="badge badge-products">📅 Период: {KNOWLEDGE_BASE['period']}</span>
                </div>
                
                <div class="features">
                    <div class="feature-card">
                        <div class="feature-icon">🎯</div>
                        <div class="feature-title">Без API</div>
                        <div class="feature-desc">Нет блокировок</div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">💰</div>
                        <div class="feature-title">Актуальные цены</div>
                        <div class="feature-desc">Из вашего файла</div>
                    </div>
                    <div class="feature-card">
                        <div class="feature-icon">🧠</div>
                        <div class="feature-title">Умный подбор</div>
                        <div class="feature-desc">По категориям</div>
                    </div>
                </div>
            </div>
            
            <div class="main-card">
                <div class="input-group">
                    <label for="nmId">Введите артикул WB (nm_id):</label>
                    <input type="number" id="nmId" placeholder="Например: 197424064" />
                </div>
                
                <div class="button-group">
                    <button class="btn btn-primary" onclick="getPrice()">
                        💰 Получить цену
                    </button>
                    <button class="btn btn-secondary" onclick="analyzeCompetitors()">
                        📊 Полный анализ
                    </button>
                    <button class="btn btn-info" onclick="checkStatus()">
                        ✅ Статус системы
                    </button>
                </div>
                
                <div id="result" class="result"></div>
            </div>
        </div>
        
        <script>
            async function getPrice() {{
                const nmId = document.getElementById('nmId').value;
                if (!nmId) {{
                    alert('Введите артикул!');
                    return;
                }}
                
                const result = document.getElementById('result');
                result.innerHTML = '<div class="loading"><div class="spinner"></div><p>Получение цены...</p></div>';
                result.classList.add('show');
                
                try {{
                    const response = await fetch(`/price/${{nmId}}`);
                    const data = await response.json();
                    
                    if (response.ok) {{
                        result.innerHTML = `
                            <h3 style="margin-bottom: 15px;">💰 Цена товара ${{nmId}}</h3>
                            <div style="font-size: 24px; font-weight: 700; color: #10b981; margin: 20px 0;">
                                ${{data.current_price.value.toFixed(2)}} ₽
                            </div>
                            <div style="color: #6b7280;">
                                <p>📚 Источник: База знаний</p>
                                <p>📅 Период данных: ${{data.current_price.period}}</p>
                            </div>
                        `;
                    }} else {{
                        result.innerHTML = `<div style="color: #ef4444;">❌ ${{data.detail}}</div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div style="color: #ef4444;">❌ Ошибка: ${{error.message}}</div>`;
                }}
            }}
            
            async function analyzeCompetitors() {{
                const nmId = document.getElementById('nmId').value;
                if (!nmId) {{
                    alert('Введите артикул!');
                    return;
                }}
                
                const result = document.getElementById('result');
                result.innerHTML = '<div class="loading"><div class="spinner"></div><p>Анализ конкурентов...</p></div>';
                result.classList.add('show');
                
                try {{
                    const response = await fetch(`/analyze/full/${{nmId}}`);
                    const data = await response.json();
                    
                    if (response.ok) {{
                        let html = `
                            <h3 style="margin-bottom: 15px;">📊 Анализ конкурентов</h3>
                            <div style="margin-bottom: 20px;">
                                <h4 style="color: #374151; margin-bottom: 10px;">📦 ${{data.name}}</h4>
                                <p><strong>🏷️ Категория:</strong> ${{data.category}}</p>
                                <p><strong>🏭 Бренд:</strong> ${{data.brand}}</p>
                                <p><strong>💰 Ваша цена:</strong> <span class="price-badge">${{data.current_price.value.toFixed(2)}} ₽</span></p>
                                <p><strong>📈 Средняя цена конкурентов:</strong> <span class="price-badge">${{data.analysis.avg_competitor_price.toFixed(2)}} ₽</span></p>
                                <p><strong>🎯 Рекомендация:</strong> ${{data.analysis.recommendation}}</p>
                            </div>
                            
                            <h4 style="margin-top: 20px; margin-bottom: 10px;">🔥 Топ-5 конкурентов (по выручке):</h4>
                        `;
                        
                        if (data.competitors.length === 0) {{
                            html += '<p style="color: #6b7280;">Конкуренты не найдены</p>';
                        }} else {{
                            data.competitors.forEach((comp, idx) => {{
                                html += `
                                    <div class="competitor-card">
                                        <div style="display: flex; justify-content: space-between; align-items: center;">
                                            <div>
                                                <strong>${{idx + 1}}. ${{comp.name}}</strong>
                                                <p style="color: #6b7280; font-size: 14px; margin-top: 5px;">
                                                    Артикул: ${{comp.nm_id}} | Бренд: ${{comp.brand}}
                                                </p>
                                            </div>
                                            <div style="text-align: right;">
                                                <div class="price-badge">${{comp.price.toFixed(2)}} ₽</div>
                                                <p style="color: #6b7280; font-size: 12px; margin-top: 5px;">
                                                    Выручка: ${{comp.revenue.toLocaleString()}} ₽
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }});
                            
                            html += `
                                <div style="margin-top: 20px;">
                                    <a href="/export/excel/${{nmId}}" class="btn btn-secondary" style="text-decoration: none; display: inline-block;">
                                        📥 Скачать Excel отчёт
                                    </a>
                                </div>
                            `;
                        }}
                        
                        result.innerHTML = html;
                    }} else {{
                        result.innerHTML = `<div style="color: #ef4444;">❌ ${{data.detail}}</div>`;
                    }}
                }} catch (error) {{
                    result.innerHTML = `<div style="color: #ef4444;">❌ Ошибка: ${{error.message}}</div>`;
                }}
            }}
            
            async function checkStatus() {{
                const result = document.getElementById('result');
                result.innerHTML = '<div class="loading"><div class="spinner"></div><p>Проверка статуса...</p></div>';
                result.classList.add('show');
                
                try {{
                    const response = await fetch('/health');
                    const data = await response.json();
                    
                    result.innerHTML = `
                        <h3 style="margin-bottom: 15px;">✅ Статус системы</h3>
                        <p><strong>Версия:</strong> ${{data.version}}</p>
                        <p><strong>Статус:</strong> ${{data.status}}</p>
                        <p><strong>База знаний:</strong> ${{data.knowledge_base.loaded ? '✅ Загружена' : '❌ Не загружена'}}</p>
                        <p><strong>Товаров в базе:</strong> ${{data.knowledge_base.products}}</p>
                        <p><strong>Категорий:</strong> ${{data.knowledge_base.categories}}</p>
                        <p><strong>Источник данных:</strong> ${{data.knowledge_base.source}}</p>
                        <p><strong>Период данных:</strong> ${{data.knowledge_base.period}}</p>
                        
                        <h4 style="margin-top: 20px; margin-bottom: 10px;">🎯 Возможности:</h4>
                        <ul style="list-style: none; padding: 0;">
                            <li>✅ Hybrid Intelligence</li>
                            <li>✅ Локальная база знаний</li>
                            <li>✅ Без внешних API</li>
                            <li>✅ Умный подбор конкурентов</li>
                            <li>✅ Экспорт в Excel</li>
                        </ul>
                    `;
                }} catch (error) {{
                    result.innerHTML = `<div style="color: #ef4444;">❌ Ошибка: ${{error.message}}</div>`;
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
