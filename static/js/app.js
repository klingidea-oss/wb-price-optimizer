// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// State
let products = [];
let currentOptimization = null;
let currentCompetitorAnalysis = null;

// Инициализация приложения
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 WB Price Optimizer загружен');
    checkAPIStatus();
    refreshDashboard();
    loadProducts();
});

// === УТИЛИТЫ ===

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    const toastId = 'toast-' + Date.now();
    
    const bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-info';
    
    const icon = {
        'success': 'check-circle',
        'error': 'x-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    }[type] || 'info-circle';
    
    const toastHTML = `
        <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
            <div class="toast-body">
                <i class="bi bi-${icon}"></i> ${message}
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
    
    setTimeout(() => toastElement.remove(), 3500);
}

function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(num));
}

function formatCurrency(num) {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 0
    }).format(num);
}

function showLoading() {
    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Загрузка...</span>
            </div>
            <p class="mt-3 mb-0">Обработка запроса...</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.remove();
}

// === НАВИГАЦИЯ ===

function showSection(sectionName) {
    // Скрыть все секции
    document.querySelectorAll('.content-section').forEach(section => {
        section.style.display = 'none';
    });
    
    // Показать нужную секцию
    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
        targetSection.style.display = 'block';
    }
    
    // Обновить активную ссылку в навигации
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    event.target.closest('.nav-link')?.classList.add('active');
    
    // Загрузить данные для секции
    if (sectionName === 'products') {
        loadProducts();
    } else if (sectionName === 'dashboard') {
        refreshDashboard();
    }
}

// === API СТАТУС ===

async function checkAPIStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        if (data.status === 'healthy') {
            document.getElementById('api-status').innerHTML = 
                '<span class="badge bg-success">Работает</span>';
        }
    } catch (error) {
        document.getElementById('api-status').innerHTML = 
            '<span class="badge bg-danger">Недоступен</span>';
        showToast('API недоступен. Запустите сервер: python main.py', 'error');
    }
}

// === ДАШБОРД ===

async function refreshDashboard() {
    try {
        // Загрузить товары
        const productsResp = await fetch(`${API_BASE_URL}/products`);
        const productsData = await productsResp.json();
        products = productsData;
        
        document.getElementById('total-products').textContent = products.length;
        
        // Здесь можно добавить загрузку статистики оптимизации
        
        showToast('Дашборд обновлен', 'success');
    } catch (error) {
        console.error('Ошибка загрузки дашборда:', error);
        showToast('Ошибка загрузки данных', 'error');
    }
}

// === ТОВАРЫ ===

async function loadProducts() {
    const container = document.getElementById('products-list');
    container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/products`);
        const data = await response.json();
        products = data;
        
        if (products.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="bi bi-box-seam"></i>
                    <h4>Товары не найдены</h4>
                    <p>Добавьте ваш первый товар для начала работы</p>
                    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addProductModal">
                        <i class="bi bi-plus-circle"></i> Добавить товар
                    </button>
                </div>
            `;
            return;
        }
        
        let html = `
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Артикул</th>
                        <th>Название</th>
                        <th>Категория</th>
                        <th>Цена</th>
                        <th>Себестоимость</th>
                        <th>Маржа</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        products.forEach(product => {
            const margin = ((product.current_price - product.cost_price) / product.current_price * 100).toFixed(1);
            const marginClass = margin > 40 ? 'success' : margin > 20 ? 'warning' : 'danger';
            
            html += `
                <tr>
                    <td><code>${product.nm_id}</code></td>
                    <td>${product.name}</td>
                    <td><span class="badge bg-secondary">${product.category || 'N/A'}</span></td>
                    <td><strong>${formatCurrency(product.current_price)}</strong></td>
                    <td>${formatCurrency(product.cost_price)}</td>
                    <td><span class="badge bg-${marginClass}">${margin}%</span></td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="analyzeProduct(${product.nm_id})">
                            <i class="bi bi-graph-up"></i> Анализ
                        </button>
                        <button class="btn btn-sm btn-success" onclick="optimizeProduct(${product.nm_id})">
                            <i class="bi bi-bullseye"></i> Оптимизация
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Ошибка загрузки товаров:', error);
        container.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Ошибка загрузки товаров
            </div>
        `;
    }
}

async function addProduct(event) {
    event.preventDefault();
    
    const productData = {
        nm_id: parseInt(document.getElementById('product-nm-id').value),
        name: document.getElementById('product-name').value,
        category: document.getElementById('product-category').value || null,
        current_price: parseFloat(document.getElementById('product-price').value),
        cost_price: parseFloat(document.getElementById('product-cost').value)
    };
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/products`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(productData)
        });
        
        hideLoading();
        
        if (response.ok) {
            showToast('Товар успешно добавлен!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('addProductModal')).hide();
            document.getElementById('add-product-form').reset();
            loadProducts();
            refreshDashboard();
        } else {
            const error = await response.json();
            showToast(error.detail || 'Ошибка добавления товара', 'error');
        }
    } catch (error) {
        hideLoading();
        console.error('Ошибка:', error);
        showToast('Ошибка соединения с сервером', 'error');
    }
}

function analyzeProduct(nmId) {
    document.getElementById('competitor-nm-id').value = nmId;
    showSection('competitors');
    setTimeout(() => {
        document.getElementById('competitor-search-form').dispatchEvent(new Event('submit'));
    }, 300);
}

function optimizeProduct(nmId) {
    document.getElementById('optimize-nm-id').value = nmId;
    showSection('optimization');
}

// === КОНКУРЕНТЫ ===

async function searchCompetitors(event) {
    event.preventDefault();
    
    const nmId = document.getElementById('competitor-nm-id').value;
    const minReviews = document.getElementById('min-reviews').value;
    
    const resultsContainer = document.getElementById('competitors-results');
    resultsContainer.style.display = 'block';
    resultsContainer.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-3">Поиск конкурентов...</p></div>';
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/competitors/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nm_id: parseInt(nmId),
                min_reviews: parseInt(minReviews)
            })
        });
        
        hideLoading();
        
        if (!response.ok) {
            throw new Error('Ошибка анализа конкурентов');
        }
        
        const data = await response.json();
        currentCompetitorAnalysis = data;
        displayCompetitorResults(data);
        
    } catch (error) {
        hideLoading();
        console.error('Ошибка:', error);
        resultsContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> ${error.message}
            </div>
        `;
    }
}

function displayCompetitorResults(data) {
    const container = document.getElementById('competitors-results');
    
    if (!data.competitors || data.competitors.length === 0) {
        container.innerHTML = `
            <div class="alert alert-warning">
                <i class="bi bi-info-circle"></i> Конкуренты не найдены. Попробуйте уменьшить минимальное количество отзывов.
            </div>
        `;
        return;
    }
    
    const analysis = data.analysis;
    const ourProduct = data.our_product;
    
    let html = `
        <!-- Наш товар -->
        <div class="card mb-4">
            <div class="card-header bg-primary text-white">
                <h5><i class="bi bi-box"></i> Ваш товар</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>Название:</strong> ${ourProduct.name}</p>
                        <p><strong>Категория:</strong> ${ourProduct.category}</p>
                        <p><strong>Размер:</strong> ${ourProduct.size}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Цена со скидкой:</strong> <span class="text-primary fs-4">${formatCurrency(ourProduct.price_with_discount)}</span></p>
                        <p><strong>Отзывов:</strong> ${ourProduct.reviews_count}</p>
                        <p><strong>Рейтинг:</strong> ⭐ ${ourProduct.rating}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Анализ рынка -->
        <div class="card mb-4">
            <div class="card-header bg-success text-white">
                <h5><i class="bi bi-graph-up"></i> Анализ рынка</h5>
            </div>
            <div class="card-body">
                <div class="row text-center mb-4">
                    <div class="col-md-3">
                        <h6 class="text-muted">Конкурентов найдено</h6>
                        <h3 class="text-primary">${data.total_competitors}</h3>
                    </div>
                    <div class="col-md-3">
                        <h6 class="text-muted">Медиана рынка</h6>
                        <h3 class="text-success">${formatCurrency(analysis.median_price)}</h3>
                    </div>
                    <div class="col-md-3">
                        <h6 class="text-muted">Средняя цена</h6>
                        <h3>${formatCurrency(analysis.avg_price)}</h3>
                    </div>
                    <div class="col-md-3">
                        <h6 class="text-muted">Ваша позиция</h6>
                        <h3 class="text-info">${analysis.our_position.percentile}%</h3>
                    </div>
                </div>
                
                <div class="alert alert-info">
                    <strong>Позиция на рынке:</strong> ${analysis.our_position.position_description}
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <h6>Диапазон цен конкурентов:</h6>
                        <p>От ${formatCurrency(analysis.min_price)} до ${formatCurrency(analysis.max_price)}</p>
                    </div>
                    <div class="col-md-6">
                        <h6>Оптимальный диапазон (±5% от медианы):</h6>
                        <p>От ${formatCurrency(analysis.optimal_range.low)} до ${formatCurrency(analysis.optimal_range.high)}</p>
                    </div>
                </div>
                
                ${analysis.recommendations ? `
                    <div class="alert alert-warning mt-3">
                        <h6><i class="bi bi-lightbulb"></i> Рекомендации:</h6>
                        ${analysis.recommendations.map(r => `<p class="mb-1">• ${r}</p>`).join('')}
                    </div>
                ` : ''}
            </div>
        </div>
        
        <!-- Топ конкурентов -->
        <div class="card">
            <div class="card-header">
                <h5><i class="bi bi-trophy"></i> Топ-5 конкурентов по отзывам</h5>
            </div>
            <div class="card-body">
                <div class="row">
    `;
    
    analysis.top_competitors.slice(0, 5).forEach((competitor, index) => {
        const priceCompare = competitor.price_with_discount < ourProduct.price_with_discount ? 'Дешевле' : 'Дороже';
        const priceClass = competitor.price_with_discount < ourProduct.price_with_discount ? 'success' : 'danger';
        
        html += `
            <div class="col-md-6 mb-3">
                <div class="card competitor-card h-100">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <span class="badge bg-primary">#${index + 1}</span>
                            <span class="badge bg-${priceClass}">${priceCompare}</span>
                        </div>
                        <h6 class="card-title">${competitor.name.substring(0, 60)}...</h6>
                        <p class="mb-1"><strong>Бренд:</strong> ${competitor.brand}</p>
                        <p class="mb-1"><strong>Цена:</strong> <span class="fs-5 text-primary">${formatCurrency(competitor.price_with_discount)}</span></p>
                        <p class="mb-1"><strong>Отзывов:</strong> ${formatNumber(competitor.reviews_count)} ⭐ ${competitor.rating}</p>
                        <small class="text-muted">Артикул: ${competitor.nm_id}</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
    showToast('Анализ конкурентов завершен!', 'success');
}

// === ОПТИМИЗАЦИЯ ===

async function runOptimization(event) {
    event.preventDefault();
    
    const nmId = document.getElementById('optimize-nm-id').value;
    const optimizeFor = document.getElementById('optimize-for').value;
    const considerCompetitors = document.getElementById('consider-competitors').value === 'true';
    
    const resultsContainer = document.getElementById('optimization-results');
    resultsContainer.style.display = 'block';
    resultsContainer.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-success"></div><p class="mt-3">Расчет оптимальной цены...</p></div>';
    
    showLoading();
    
    try {
        const url = `${API_BASE_URL}/optimize/${nmId}?optimize_for=${optimizeFor}&consider_competitors=${considerCompetitors}`;
        const response = await fetch(url, { method: 'POST' });
        
        hideLoading();
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка оптимизации');
        }
        
        const data = await response.json();
        currentOptimization = data;
        displayOptimizationResults(data);
        
    } catch (error) {
        hideLoading();
        console.error('Ошибка:', error);
        resultsContainer.innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> ${error.message}
            </div>
        `;
    }
}

function displayOptimizationResults(data) {
    const container = document.getElementById('optimization-results');
    
    const priceChange = data.price_change_percent;
    const priceChangeClass = priceChange > 0 ? 'danger' : 'success';
    const priceChangeIcon = priceChange > 0 ? 'arrow-up' : 'arrow-down';
    
    const profitChange = data.predicted_daily_profit - data.current_daily_profit;
    const profitChangePercent = (profitChange / data.current_daily_profit * 100).toFixed(1);
    
    const riskClass = {
        'low': 'success',
        'medium': 'warning',
        'high': 'danger'
    }[data.risk_level] || 'secondary';
    
    let html = `
        <!-- Основные результаты -->
        <div class="card optimization-card success mb-4">
            <div class="card-body">
                <h4 class="card-title"><i class="bi bi-check-circle-fill text-success"></i> Оптимизация завершена</h4>
                <h5 class="text-muted mb-4">${data.product_name}</h5>
                
                <div class="row text-center mb-4">
                    <div class="col-md-4">
                        <h6 class="text-muted">Текущая цена</h6>
                        <h2>${formatCurrency(data.current_price)}</h2>
                    </div>
                    <div class="col-md-4">
                        <h6 class="text-muted">Оптимальная цена</h6>
                        <h2 class="text-success">${formatCurrency(data.optimal_price)}</h2>
                        <span class="badge bg-${priceChangeClass}">
                            <i class="bi bi-${priceChangeIcon}"></i> ${Math.abs(priceChange).toFixed(1)}%
                        </span>
                    </div>
                    <div class="col-md-4">
                        <h6 class="text-muted">Прирост прибыли</h6>
                        <h2 class="text-primary">${formatCurrency(profitChange)}</h2>
                        <span class="badge bg-primary">+${profitChangePercent}%</span>
                    </div>
                </div>
                
                <div class="alert alert-${riskClass}">
                    <strong>Уровень риска:</strong> ${data.risk_level.toUpperCase()}
                </div>
            </div>
        </div>
        
        <!-- Прогнозы -->
        <div class="card mb-4">
            <div class="card-header">
                <h5><i class="bi bi-graph-up"></i> Прогнозы</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <h6>Продажи (шт/день)</h6>
                        <p class="mb-1">Текущие: <strong>${data.current_daily_sales}</strong></p>
                        <p>Прогноз: <strong class="text-success">${data.predicted_daily_sales}</strong></p>
                    </div>
                    <div class="col-md-4">
                        <h6>Выручка (руб/день)</h6>
                        <p class="mb-1">Текущая: <strong>${formatCurrency(data.current_daily_revenue)}</strong></p>
                        <p>Прогноз: <strong class="text-success">${formatCurrency(data.predicted_daily_revenue)}</strong></p>
                    </div>
                    <div class="col-md-4">
                        <h6>Прибыль (руб/день)</h6>
                        <p class="mb-1">Текущая: <strong>${formatCurrency(data.current_daily_profit)}</strong></p>
                        <p>Прогноз: <strong class="text-success">${formatCurrency(data.predicted_daily_profit)}</strong></p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Анализ эластичности -->
        <div class="card mb-4">
            <div class="card-header">
                <h5><i class="bi bi-bar-chart"></i> Анализ эластичности спроса</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4">
                        <p><strong>Коэффициент эластичности:</strong></p>
                        <h3 class="text-primary">${data.elasticity.elasticity_coefficient.toFixed(2)}</h3>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Тип спроса:</strong></p>
                        <h3>${data.elasticity.is_elastic ? 'Эластичный' : 'Неэластичный'}</h3>
                    </div>
                    <div class="col-md-4">
                        <p><strong>Уверенность:</strong></p>
                        <h3 class="text-info">${(data.elasticity.confidence * 100).toFixed(0)}%</h3>
                    </div>
                </div>
                <p class="text-muted mt-3">На основе ${data.elasticity.data_points} точек данных</p>
            </div>
        </div>
        
        <!-- Рекомендация AI -->
        <div class="card mb-4">
            <div class="card-header bg-info text-white">
                <h5><i class="bi bi-robot"></i> Рекомендация AI</h5>
            </div>
            <div class="card-body">
                <p>${data.recommendation}</p>
            </div>
        </div>
        
        <!-- Альтернативные сценарии -->
        <div class="card mb-4">
            <div class="card-header">
                <h5><i class="bi bi-signpost-split"></i> Альтернативные сценарии</h5>
            </div>
            <div class="card-body">
                <div class="row">
    `;
    
    data.alternative_scenarios.forEach((scenario, index) => {
        html += `
            <div class="col-md-6 mb-3">
                <div class="scenario-card ${index === 0 ? 'active' : ''}">
                    <h6><i class="bi bi-tag"></i> ${scenario.name}</h6>
                    <p class="text-muted small">${scenario.description}</p>
                    <p class="mb-1"><strong>Цена:</strong> ${formatCurrency(scenario.price)}</p>
                    <p class="mb-1"><strong>Прогноз продаж:</strong> ${scenario.predicted_sales || 'N/A'} шт</p>
                    <p class="mb-0"><strong>Прогноз прибыли:</strong> ${formatCurrency(scenario.predicted_profit || scenario.predicted_revenue || 0)}</p>
                </div>
            </div>
        `;
    });
    
    html += `
                </div>
            </div>
        </div>
        
        <!-- Действия -->
        <div class="card">
            <div class="card-body text-center">
                <button class="btn btn-success btn-lg me-2" onclick="applyOptimalPrice(${data.nm_id})">
                    <i class="bi bi-check-circle"></i> Применить оптимальную цену
                </button>
                <button class="btn btn-secondary btn-lg" onclick="window.print()">
                    <i class="bi bi-printer"></i> Печать отчета
                </button>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
    showToast('Оптимизация завершена!', 'success');
}

async function applyOptimalPrice(nmId) {
    if (!confirm('Вы уверены, что хотите применить оптимальную цену на Wildberries?')) {
        return;
    }
    
    showLoading();
    
    try {
        const response = await fetch(`${API_BASE_URL}/apply-price/${nmId}`, {
            method: 'POST'
        });
        
        hideLoading();
        
        if (response.ok) {
            const data = await response.json();
            showToast(data.message, 'success');
        } else {
            const error = await response.json();
            showToast(error.detail || 'Ошибка применения цены', 'error');
        }
    } catch (error) {
        hideLoading();
        console.error('Ошибка:', error);
        showToast('Ошибка соединения с сервером', 'error');
    }
}
