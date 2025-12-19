// WB Price Optimizer - Frontend Application
const API_BASE_URL = window.location.origin;

// State Management
const state = {
    products: [],
    currentProduct: null,
    competitorData: null,
    optimizationResult: null,
    analytics: null
};

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 WB Price Optimizer initialized');
    initializeNavigation();
    loadDashboard();
    setupEventListeners();
});

// Navigation
function initializeNavigation() {
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.section;
            showSection(target);
            
            // Update active state
            navTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        });
    });
}

function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Show target section
    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.classList.add('active');
        
        // Load section data
        switch(sectionId) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'products':
                loadProducts();
                break;
            case 'competitors':
                // Competitor form is ready
                break;
            case 'optimize':
                loadProductsForOptimization();
                break;
        }
    }
}

// Event Listeners
function setupEventListeners() {
    // Add Product Form
    const addProductForm = document.getElementById('addProductForm');
    if (addProductForm) {
        addProductForm.addEventListener('submit', handleAddProduct);
    }
    
    // Competitor Analysis Form
    const competitorForm = document.getElementById('competitorForm');
    if (competitorForm) {
        competitorForm.addEventListener('submit', handleCompetitorAnalysis);
    }
    
    // Optimization Form
    const optimizeForm = document.getElementById('optimizeForm');
    if (optimizeForm) {
        optimizeForm.addEventListener('submit', handleOptimization);
    }
    
    // Refresh buttons
    const refreshButtons = document.querySelectorAll('.btn-refresh');
    refreshButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            loadDashboard();
        });
    });
}

// Dashboard
async function loadDashboard() {
    console.log('📊 Loading dashboard...');
    showLoading('dashboard-content');
    
    try {
        const response = await fetch(`${API_BASE_URL}/products/`);
        if (!response.ok) throw new Error('Failed to load products');
        
        const products = await response.json();
        state.products = products;
        
        renderDashboard(products);
    } catch (error) {
        console.error('❌ Dashboard error:', error);
        showError('dashboard-content', 'Не удалось загрузить данные дашборда');
    } finally {
        hideLoading('dashboard-content');
    }
}

function renderDashboard(products) {
    const dashboardContent = document.getElementById('dashboard-content');
    
    if (products.length === 0) {
        dashboardContent.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <h3>Товары не найдены</h3>
                <p>Добавьте первый товар для начала работы</p>
                <button class="btn btn-primary" onclick="showSection('products')">
                    Добавить товар
                </button>
            </div>
        `;
        return;
    }
    
    // Calculate stats
    const totalProducts = products.length;
    const avgPrice = (products.reduce((sum, p) => sum + (p.current_price || 0), 0) / totalProducts).toFixed(0);
    const totalRevenue = products.reduce((sum, p) => sum + ((p.current_price || 0) * (p.sales_per_day || 0) * 30), 0);
    
    dashboardContent.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Всего товаров</h3>
                <div class="value">${totalProducts}</div>
            </div>
            <div class="stat-card">
                <h3>Средняя цена</h3>
                <div class="value">${avgPrice} ₽</div>
            </div>
            <div class="stat-card">
                <h3>Прогноз выручки/мес</h3>
                <div class="value">${formatNumber(totalRevenue)} ₽</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Ваши товары</h2>
            </div>
            <div class="card-body">
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Артикул WB</th>
                                <th>Категория</th>
                                <th>Текущая цена</th>
                                <th>Себестоимость</th>
                                <th>Добавлен</th>
                                <th>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${products.map(p => `
                                <tr>
                                    <td><strong>${p.nm_id}</strong></td>
                                    <td>${p.category || 'Не указано'}</td>
                                    <td><strong>${p.current_price} ₽</strong></td>
                                    <td>${p.cost} ₽</td>
                                    <td>${new Date(p.created_at).toLocaleDateString('ru-RU')}</td>
                                    <td>
                                        <button class="btn btn-sm btn-primary" onclick="optimizeProduct(${p.nm_id})">
                                            Оптимизировать
                                        </button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    `;
}

// Products Management
async function loadProducts() {
    console.log('📦 Loading products...');
    const productsListDiv = document.getElementById('productsList');
    showLoading('productsList');
    
    try {
        const response = await fetch(`${API_BASE_URL}/products/`);
        if (!response.ok) throw new Error('Failed to load products');
        
        const products = await response.json();
        state.products = products;
        
        if (products.length === 0) {
            productsListDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📦</div>
                    <h3>Список пуст</h3>
                    <p>Добавьте первый товар используя форму выше</p>
                </div>
            `;
            return;
        }
        
        productsListDiv.innerHTML = `
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Артикул WB</th>
                            <th>Категория</th>
                            <th>Размер</th>
                            <th>Текущая цена</th>
                            <th>Себестоимость</th>
                            <th>Маржа</th>
                            <th>Добавлен</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${products.map(p => {
                            const margin = ((p.current_price - p.cost) / p.current_price * 100).toFixed(1);
                            return `
                                <tr>
                                    <td><strong>${p.nm_id}</strong></td>
                                    <td>${p.category || 'Не указано'}</td>
                                    <td>${p.size || 'Не указано'}</td>
                                    <td><strong>${p.current_price} ₽</strong></td>
                                    <td>${p.cost} ₽</td>
                                    <td>
                                        <span class="badge ${margin > 30 ? 'badge-success' : margin > 15 ? 'badge-warning' : 'badge-danger'}">
                                            ${margin}%
                                        </span>
                                    </td>
                                    <td>${new Date(p.created_at).toLocaleDateString('ru-RU')}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (error) {
        console.error('❌ Products error:', error);
        showError('productsList', 'Не удалось загрузить список товаров');
    } finally {
        hideLoading('productsList');
    }
}

async function handleAddProduct(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const productData = {
        nm_id: parseInt(formData.get('nm_id')),
        current_price: parseFloat(formData.get('current_price')),
        cost: parseFloat(formData.get('cost')),
        category: formData.get('category'),
        size: formData.get('size')
    };
    
    console.log('➕ Adding product:', productData);
    showLoading('productsList');
    
    try {
        const response = await fetch(`${API_BASE_URL}/products/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(productData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add product');
        }
        
        const result = await response.json();
        console.log('✅ Product added:', result);
        
        showToast('Товар успешно добавлен!', 'success');
        event.target.reset();
        await loadProducts();
    } catch (error) {
        console.error('❌ Add product error:', error);
        showToast(`Ошибка: ${error.message}`, 'error');
    } finally {
        hideLoading('productsList');
    }
}

// Competitor Analysis
async function handleCompetitorAnalysis(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const nmId = parseInt(formData.get('nm_id'));
    const minReviews = parseInt(formData.get('min_reviews')) || 500;
    
    console.log('🔍 Analyzing competitors:', { nmId, minReviews });
    showLoading('competitorResults');
    
    try {
        const response = await fetch(`${API_BASE_URL}/competitors/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                nm_id: nmId,
                min_reviews: minReviews
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to analyze competitors');
        }
        
        const result = await response.json();
        state.competitorData = result;
        console.log('✅ Competitor analysis:', result);
        
        renderCompetitorResults(result);
    } catch (error) {
        console.error('❌ Competitor analysis error:', error);
        showError('competitorResults', `Ошибка анализа: ${error.message}`);
    } finally {
        hideLoading('competitorResults');
    }
}

function renderCompetitorResults(data) {
    const resultsDiv = document.getElementById('competitorResults');
    
    if (!data.competitors || data.competitors.length === 0) {
        resultsDiv.innerHTML = `
            <div class="alert alert-warning">
                <strong>Конкуренты не найдены</strong><br>
                Попробуйте уменьшить минимальное количество отзывов
            </div>
        `;
        return;
    }
    
    const stats = data.market_stats;
    const competitors = data.competitors;
    
    resultsDiv.innerHTML = `
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Статистика рынка</h2>
            </div>
            <div class="card-body">
                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>Конкурентов найдено</h3>
                        <div class="value">${stats.total_competitors}</div>
                    </div>
                    <div class="stat-card">
                        <h3>Средняя цена</h3>
                        <div class="value">${stats.average_price.toFixed(0)} ₽</div>
                    </div>
                    <div class="stat-card">
                        <h3>Медианная цена</h3>
                        <div class="value">${stats.median_price.toFixed(0)} ₽</div>
                    </div>
                    <div class="stat-card">
                        <h3>Диапазон цен</h3>
                        <div class="value">${stats.min_price} - ${stats.max_price} ₽</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <h2 class="card-title">Топ конкурентов</h2>
            </div>
            <div class="card-body">
                <div class="competitor-grid">
                    ${competitors.slice(0, 6).map(comp => `
                        <div class="competitor-card">
                            <div class="competitor-header">
                                <div>
                                    <div class="competitor-name">
                                        Артикул: ${comp.nm_id}
                                    </div>
                                    <span class="badge badge-info">${comp.reviews} отзывов</span>
                                </div>
                                <div class="price-item">
                                    <div class="value" style="font-size: 1.5em;">${comp.price} ₽</div>
                                </div>
                            </div>
                            <div class="competitor-metrics">
                                <div class="competitor-metric">
                                    <span>Рейтинг:</span>
                                    <strong>${comp.rating.toFixed(1)} ⭐</strong>
                                </div>
                                <div class="competitor-metric">
                                    <span>Продаж/день:</span>
                                    <strong>${comp.sales_per_day}</strong>
                                </div>
                                ${comp.in_stock !== undefined ? `
                                    <div class="competitor-metric">
                                        <span>В наличии:</span>
                                        <span class="badge ${comp.in_stock ? 'badge-success' : 'badge-danger'}">
                                            ${comp.in_stock ? 'Да' : 'Нет'}
                                        </span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
        
        <div class="alert alert-info">
            <strong>💡 Рекомендация:</strong><br>
            Оптимальная цена для конкуренции: ${stats.median_price.toFixed(0)} ₽<br>
            Средняя цена рынка: ${stats.average_price.toFixed(0)} ₽
        </div>
    `;
}

// Price Optimization
async function loadProductsForOptimization() {
    const select = document.getElementById('optimizeProductId');
    
    try {
        const response = await fetch(`${API_BASE_URL}/products/`);
        if (!response.ok) throw new Error('Failed to load products');
        
        const products = await response.json();
        
        select.innerHTML = '<option value="">Выберите товар...</option>' +
            products.map(p => `
                <option value="${p.nm_id}">
                    ${p.nm_id} - ${p.category || 'Товар'} (${p.current_price} ₽)
                </option>
            `).join('');
    } catch (error) {
        console.error('❌ Load products error:', error);
        select.innerHTML = '<option value="">Ошибка загрузки товаров</option>';
    }
}

async function handleOptimization(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const nmId = parseInt(formData.get('nm_id'));
    const optimizeFor = formData.get('optimize_for');
    const considerCompetitors = formData.get('consider_competitors') === 'on';
    
    console.log('🎯 Optimizing price:', { nmId, optimizeFor, considerCompetitors });
    showLoading('optimizationResults');
    
    try {
        const response = await fetch(`${API_BASE_URL}/optimize/${nmId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                optimize_for: optimizeFor,
                consider_competitors: considerCompetitors
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Optimization failed');
        }
        
        const result = await response.json();
        state.optimizationResult = result;
        console.log('✅ Optimization result:', result);
        
        renderOptimizationResults(result);
    } catch (error) {
        console.error('❌ Optimization error:', error);
        showError('optimizationResults', `Ошибка оптимизации: ${error.message}`);
    } finally {
        hideLoading('optimizationResults');
    }
}

function renderOptimizationResults(data) {
    const resultsDiv = document.getElementById('optimizationResults');
    
    const currentPrice = data.current_price;
    const optimalPrice = data.optimal_price;
    const priceChange = ((optimalPrice - currentPrice) / currentPrice * 100).toFixed(1);
    const priceChangeClass = priceChange > 0 ? 'positive' : 'negative';
    
    resultsDiv.innerHTML = `
        <div class="optimization-card">
            <h2 style="margin-bottom: 20px;">✨ Результаты оптимизации</h2>
            
            <div class="price-comparison">
                <div class="price-item">
                    <div class="label">Текущая цена</div>
                    <div class="value">${currentPrice} ₽</div>
                </div>
                <div class="price-item">
                    <div class="label">→</div>
                </div>
                <div class="price-item">
                    <div class="label">Оптимальная цена</div>
                    <div class="value" style="color: var(--success-color);">${optimalPrice} ₽</div>
                    <div class="price-change ${priceChangeClass}">
                        ${priceChange > 0 ? '↑' : '↓'} ${Math.abs(priceChange)}%
                    </div>
                </div>
            </div>
            
            <div class="metric-row">
                <span class="metric-label">Прогноз продаж в день:</span>
                <span class="metric-value">${data.estimated_sales_per_day} шт</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Прогноз выручки в месяц:</span>
                <span class="metric-value">${formatNumber(data.estimated_revenue_per_month)} ₽</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Прогноз прибыли в месяц:</span>
                <span class="metric-value">${formatNumber(data.estimated_profit_per_month)} ₽</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Эластичность спроса:</span>
                <span class="metric-value">${data.elasticity.toFixed(2)}</span>
            </div>
            
            ${data.ai_reasoning ? `
                <div class="alert alert-info" style="margin-top: 20px;">
                    <strong>🤖 AI Рекомендация:</strong><br>
                    ${data.ai_reasoning}
                </div>
            ` : ''}
            
            ${data.competitor_context ? `
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <strong>📊 Контекст конкурентов:</strong><br>
                    ${data.competitor_context}
                </div>
            ` : ''}
        </div>
        
        ${renderScenarioComparison(data)}
        
        <div class="card">
            <div class="card-header">
                <h3>Применить оптимальную цену</h3>
            </div>
            <div class="card-body">
                <p>Внимание: Ваш API ключ имеет права только на чтение. Для автоматического изменения цен создайте новый токен с правами "Цены и скидки".</p>
                <button class="btn btn-success" disabled>
                    Применить цену ${optimalPrice} ₽ (требуется токен с правами)
                </button>
            </div>
        </div>
    `;
}

function renderScenarioComparison(data) {
    if (!data.scenarios || data.scenarios.length === 0) {
        return '';
    }
    
    return `
        <div class="card" style="margin-top: 20px;">
            <div class="card-header">
                <h3>Сравнение сценариев</h3>
            </div>
            <div class="card-body">
                <div class="scenario-grid">
                    ${data.scenarios.map(scenario => `
                        <div class="scenario-card ${scenario.is_recommended ? 'recommended' : ''}">
                            <div class="scenario-title">
                                ${scenario.name}
                                ${scenario.is_recommended ? '<span class="badge badge-success">Рекомендуется</span>' : ''}
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Цена:</span>
                                <span class="metric-value">${scenario.price} ₽</span>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Продажи/день:</span>
                                <span class="metric-value">${scenario.sales_per_day} шт</span>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Выручка/мес:</span>
                                <span class="metric-value">${formatNumber(scenario.revenue_per_month)} ₽</span>
                            </div>
                            <div class="metric-row">
                                <span class="metric-label">Прибыль/мес:</span>
                                <span class="metric-value">${formatNumber(scenario.profit_per_month)} ₽</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;
}

// Quick Optimization from Dashboard
async function optimizeProduct(nmId) {
    console.log('🚀 Quick optimize:', nmId);
    showSection('optimize');
    
    // Wait for section to load
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const select = document.getElementById('optimizeProductId');
    if (select) {
        select.value = nmId;
    }
}

// Utility Functions
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div style="text-align: center; padding: 40px;">
                <div class="loading"></div>
                <p style="margin-top: 15px; color: var(--text-secondary);">Загрузка...</p>
            </div>
        `;
    }
}

function hideLoading(elementId) {
    // Loading is replaced by actual content
}

function showError(elementId, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div class="alert alert-danger">
                <strong>Ошибка!</strong><br>
                ${message}
            </div>
        `;
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast alert-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function formatNumber(num) {
    return new Intl.NumberFormat('ru-RU').format(Math.round(num));
}

function refreshDashboard() {
    loadDashboard();
    showToast('Дашборд обновлён', 'success');
}

// Health Check
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        console.log('💚 Health check:', data);
        return data.status === 'healthy';
    } catch (error) {
        console.error('❌ Health check failed:', error);
        return false;
    }
}

// Initial health check
checkHealth().then(healthy => {
    if (healthy) {
        console.log('✅ Backend is healthy');
    } else {
        console.warn('⚠️ Backend health check failed');
    }
});