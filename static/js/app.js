// WB Price Optimizer - Frontend (Bootstrap Compatible)
const API_BASE_URL = window.location.origin;
const state = {products: [], currentProduct: null, competitorData: null, optimizationResult: null};

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 WB Price Optimizer initialized');
    loadDashboard();
    checkHealth();
});

function showSection(sectionName) {
    const sections = ['dashboard', 'products', 'competitors', 'optimization'];
    sections.forEach(s => {
        const section = document.getElementById(`${s}-section`);
        if (section) section.style.display = 'none';
    });
    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
        targetSection.style.display = 'block';
        if (sectionName === 'dashboard') loadDashboard();
        if (sectionName === 'products') loadProducts();
    }
}

async function loadDashboard() {
    console.log('📊 Loading dashboard...');
    try {
        const response = await fetch(`${API_BASE_URL}/products/`);
        if (!response.ok) throw new Error('Failed to load products');
        const products = await response.json();
        state.products = products;
        updateDashboardStats(products);
    } catch (error) {
        console.error('❌ Dashboard error:', error);
    }
}

function updateDashboardStats(products) {
    const totalProducts = products.length;
    const totalEl = document.getElementById('total-products');
    if (totalEl) totalEl.textContent = totalProducts;
    const apiStatus = document.getElementById('api-status');
    if (apiStatus) apiStatus.innerHTML = '<span class="badge bg-success">Активен</span>';
}

async function loadProducts() {
    console.log('📦 Loading products...');
    const productsList = document.getElementById('products-list');
    if (!productsList) return;
    productsList.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
    try {
        const response = await fetch(`${API_BASE_URL}/products/`);
        if (!response.ok) throw new Error('Failed to load products');
        const products = await response.json();
        state.products = products;
        if (products.length === 0) {
            productsList.innerHTML = '<div class="text-center py-5"><h3>📦 Список пуст</h3></div>';
            return;
        }
        productsList.innerHTML = `<table class="table table-hover"><thead><tr><th>Артикул</th><th>Название</th><th>Цена</th><th>Себестоимость</th><th>Маржа</th></tr></thead><tbody>${products.map(p => {
            const margin = ((p.current_price - p.cost) / p.current_price * 100).toFixed(1);
            const badgeClass = margin > 30 ? 'success' : margin > 15 ? 'warning' : 'danger';
            return `<tr><td><strong>${p.nm_id}</strong></td><td>${p.name || 'Без названия'}</td><td><strong>${p.current_price} ₽</strong></td><td>${p.cost} ₽</td><td><span class="badge bg-${badgeClass}">${margin}%</span></td></tr>`;
        }).join('')}</tbody></table>`;
    } catch (error) {
        console.error('❌ Products error:', error);
        productsList.innerHTML = '<div class="alert alert-danger">Ошибка загрузки</div>';
    }
}

async function addProduct(event) {
    event.preventDefault();
    const productData = {
        nm_id: parseInt(document.getElementById('product-nm-id').value),
        name: document.getElementById('product-name').value,
        category: document.getElementById('product-category').value,
        current_price: parseFloat(document.getElementById('product-price').value),
        cost: parseFloat(document.getElementById('product-cost').value)
    };
    console.log('➕ Adding product:', productData);
    try {
        const response = await fetch(`${API_BASE_URL}/products/add`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(productData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to add product');
        }
        const result = await response.json();
        console.log('✅ Product added:', result);
        const modal = bootstrap.Modal.getInstance(document.getElementById('addProductModal'));
        if (modal) modal.hide();
        event.target.reset();
        await loadProducts();
        showToast('Товар успешно добавлен!', 'success');
    } catch (error) {
        console.error('❌ Add product error:', error);
        showToast(`Ошибка: ${error.message}`, 'danger');
    }
}

async function searchCompetitors(event) {
    event.preventDefault();
    const nmId = parseInt(document.getElementById('competitor-nm-id').value);
    const minReviews = parseInt(document.getElementById('min-reviews').value) || 500;
    console.log('🔍 Analyzing competitors:', {nmId, minReviews});
    const resultsDiv = document.getElementById('competitors-results');
    if (!resultsDiv) return;
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
    try {
        const response = await fetch(`${API_BASE_URL}/competitors/analyze`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({nm_id: nmId, min_reviews: minReviews})
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to analyze');
        }
        const result = await response.json();
        console.log('✅ Competitor analysis:', result);
        renderCompetitorResults(result);
    } catch (error) {
        console.error('❌ Competitor error:', error);
        resultsDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
    }
}

function renderCompetitorResults(data) {
    const resultsDiv = document.getElementById('competitors-results');
    if (!resultsDiv) return;
    if (!data.competitors || data.competitors.length === 0) {
        resultsDiv.innerHTML = '<div class="alert alert-warning">Конкуренты не найдены</div>';
        return;
    }
    const stats = data.market_stats;
    const competitors = data.competitors;
    resultsDiv.innerHTML = `<div class="card mb-4"><div class="card-header"><h5>📊 Статистика рынка</h5></div><div class="card-body"><div class="row text-center"><div class="col-md-3"><h3>${stats.total_competitors}</h3><p class="text-muted">Конкурентов</p></div><div class="col-md-3"><h3>${stats.average_price.toFixed(0)} ₽</h3><p class="text-muted">Средняя</p></div><div class="col-md-3"><h3>${stats.median_price.toFixed(0)} ₽</h3><p class="text-muted">Медиана</p></div><div class="col-md-3"><h3>${stats.min_price}-${stats.max_price} ₽</h3><p class="text-muted">Диапазон</p></div></div></div></div><div class="card"><div class="card-header"><h5>🏆 Топ конкурентов</h5></div><div class="card-body"><table class="table table-hover"><thead><tr><th>Артикул</th><th>Цена</th><th>Рейтинг</th><th>Отзывы</th><th>Продаж/день</th></tr></thead><tbody>${competitors.slice(0,10).map(c => `<tr><td><strong>${c.nm_id}</strong></td><td><strong>${c.price} ₽</strong></td><td>${c.rating.toFixed(1)} ⭐</td><td><span class="badge bg-info">${c.reviews}</span></td><td>${c.sales_per_day}</td></tr>`).join('')}</tbody></table></div></div><div class="alert alert-info mt-3"><strong>💡 Рекомендация:</strong> Оптимальная цена: ${stats.median_price.toFixed(0)} ₽</div>`;
}

async function runOptimization(event) {
    event.preventDefault();
    const nmId = parseInt(document.getElementById('optimize-nm-id').value);
    const optimizeFor = document.getElementById('optimize-for').value;
    const considerCompetitors = document.getElementById('consider-competitors').value === 'true';
    console.log('🎯 Optimizing:', {nmId, optimizeFor, considerCompetitors});
    const resultsDiv = document.getElementById('optimization-results');
    if (!resultsDiv) return;
    resultsDiv.style.display = 'block';
    resultsDiv.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-success"></div></div>';
    try {
        const response = await fetch(`${API_BASE_URL}/optimize/${nmId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({optimize_for: optimizeFor, consider_competitors: considerCompetitors})
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Optimization failed');
        }
        const result = await response.json();
        console.log('✅ Optimization result:', result);
        renderOptimizationResults(result);
    } catch (error) {
        console.error('❌ Optimization error:', error);
        resultsDiv.innerHTML = `<div class="alert alert-danger">Ошибка: ${error.message}</div>`;
    }
}

function renderOptimizationResults(data) {
    const resultsDiv = document.getElementById('optimization-results');
    if (!resultsDiv) return;
    const priceChange = ((data.optimal_price - data.current_price) / data.current_price * 100).toFixed(1);
    const arrow = priceChange > 0 ? '↑' : '↓';
    const badgeClass = priceChange > 0 ? 'success' : 'danger';
    resultsDiv.innerHTML = `<div class="card border-success"><div class="card-header bg-success text-white"><h5>✨ Результаты оптимизации</h5></div><div class="card-body"><div class="row text-center mb-4"><div class="col-md-4"><h6 class="text-muted">Текущая</h6><h2>${data.current_price} ₽</h2></div><div class="col-md-4"><h6 class="text-muted">Оптимальная</h6><h2 class="text-success">${data.optimal_price} ₽</h2><span class="badge bg-${badgeClass}">${arrow}
