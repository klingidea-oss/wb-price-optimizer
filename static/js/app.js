// WB Price Optimizer V2.0 - Client Application

class PriceOptimizerApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.init();
    }

    init() {
        // Загрузка статистики при старте
        this.loadStats();
        
        // Обработчики событий
        document.getElementById('analyzeBtn').addEventListener('click', () => this.analyze());
        document.getElementById('exportExcelBtn').addEventListener('click', () => this.exportExcel());
        
        // Enter для поиска
        document.getElementById('nmIdInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.analyze();
        });
    }

    // Загрузка статистики
    async loadStats() {
        try {
            const response = await fetch(`${this.apiBase}/categories/stats`);
            const data = await response.json();
            
            document.getElementById('totalProducts').textContent = 
                this.formatNumber(data.total_products || 0);
            document.getElementById('totalCategories').textContent = 
                this.formatNumber(data.total_categories || 0);
            document.getElementById('totalGroups').textContent = 
                this.formatNumber(data.total_groups || 0);
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
    }

    // Анализ товара
    async analyze() {
        const nmId = document.getElementById('nmIdInput').value.trim();
        
        if (!nmId) {
            this.showError('Пожалуйста, введите артикул WB');
            return;
        }

        this.showLoading(true);
        this.hideError();
        this.hideResults();

        try {
            const response = await fetch(`${this.apiBase}/analyze/full/${nmId}`);
            
            if (!response.ok) {
                throw new Error(`Ошибка анализа: ${response.status}`);
            }

            const data = await response.json();
            this.displayResults(data);
        } catch (error) {
            this.showError(`Не удалось выполнить анализ: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    // Отображение результатов
    displayResults(data) {
        // Информация о товаре
        this.displayProductInfo(data.product);
        
        // Оптимизация цены
        this.displayPriceOptimization(data.optimization);
        
        // Эластичность
        this.displayElasticity(data.elasticity);
        
        // Сезонность
        this.displaySeasonality(data.seasonality);
        
        // Конкуренты
        this.displayCompetitors(data.competitors);
        
        // Рекомендации
        this.displayRecommendations(data.recommendations);
        
        // Показать результаты
        this.showResults();
    }

    displayProductInfo(product) {
        const html = `
            <div class="product-info-grid">
                <div class="info-item">
                    <div class="info-label">Артикул WB</div>
                    <div class="info-value">${product.nm_id}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Название</div>
                    <div class="info-value">${this.truncate(product.name, 40)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Категория</div>
                    <div class="info-value">${product.category || 'Не указана'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Текущая цена</div>
                    <div class="info-value">${this.formatPrice(product.current_price)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Себестоимость</div>
                    <div class="info-value">${this.formatPrice(product.cost)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Группа конкурентов</div>
                    <div class="info-value">${product.group_id || 'Нет данных'}</div>
                </div>
            </div>
        `;
        document.getElementById('productInfo').innerHTML = html;
    }

    displayPriceOptimization(opt) {
        const currentPrice = opt.current_price;
        const optimalPrice = opt.optimal_price;
        const competitorAvg = opt.competitor_avg_price;
        const change = ((optimalPrice - currentPrice) / currentPrice * 100).toFixed(1);
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const changeSign = change >= 0 ? '+' : '';

        const html = `
            <div class="price-comparison">
                <div class="price-box price-box-current">
                    <div class="price-label">Текущая цена</div>
                    <div class="price-amount">${this.formatPrice(currentPrice)}</div>
                </div>
                <div class="price-box price-box-optimal">
                    <div class="price-label">Оптимальная цена</div>
                    <div class="price-amount">${this.formatPrice(optimalPrice)}</div>
                    <div class="price-change ${changeClass}">
                        ${changeSign}${change}% (${changeSign}${this.formatPrice(optimalPrice - currentPrice)})
                    </div>
                </div>
                <div class="price-box price-box-competitor">
                    <div class="price-label">Средняя у конкурентов</div>
                    <div class="price-amount">${this.formatPrice(competitorAvg)}</div>
                </div>
            </div>
            <div style="text-align: center; font-size: 16px; color: #666;">
                <p><strong>Прогноз продаж:</strong> ${opt.predicted_sales || 'Нет данных'} шт/мес</p>
                <p><strong>Прогноз выручки:</strong> ${this.formatPrice(opt.predicted_revenue || 0)}</p>
                <p><strong>Ожидаемая прибыль:</strong> ${this.formatPrice(opt.predicted_profit || 0)}</p>
            </div>
        `;
        document.getElementById('priceOptimization').innerHTML = html;
    }

    displayElasticity(elasticity) {
        const html = `
            <div class="elasticity-grid">
                <div class="elasticity-item">
                    <strong>Эластичность</strong>
                    <span>${elasticity.elasticity?.toFixed(2) || 'N/A'}</span>
                </div>
                <div class="elasticity-item">
                    <strong>Изменение цены</strong>
                    <span>${elasticity.price_change_pct?.toFixed(1) || 0}%</span>
                </div>
                <div class="elasticity-item">
                    <strong>Изменение спроса</strong>
                    <span>${elasticity.demand_change_pct?.toFixed(1) || 0}%</span>
                </div>
                <div class="elasticity-item">
                    <strong>Текущий спрос</strong>
                    <span>${elasticity.current_demand || 0} шт/мес</span>
                </div>
            </div>
            <div style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 10px;">
                <p style="font-size: 14px; color: #666;">
                    <strong>Интерпретация:</strong> 
                    ${this.interpretElasticity(elasticity.elasticity)}
                </p>
            </div>
        `;
        document.getElementById('elasticityAnalysis').innerHTML = html;
    }

    displaySeasonality(seasonality) {
        const factor = seasonality.seasonality_factor || 1.0;
        const trendText = this.getSeasonalityTrend(factor);
        const adjustment = ((factor - 1) * 100).toFixed(1);
        const adjustmentSign = adjustment >= 0 ? '+' : '';

        const html = `
            <div class="seasonality-info">
                <p><strong>Сезонный коэффициент:</strong> ${factor.toFixed(2)} (${adjustmentSign}${adjustment}%)</p>
                <p><strong>Тренд:</strong> ${trendText}</p>
                <p><strong>Рекомендация:</strong> ${seasonality.recommendation || 'Нет данных о сезонности'}</p>
                <p><strong>Источник данных:</strong> ${seasonality.data_source || 'Автоматический расчет'}</p>
            </div>
        `;
        document.getElementById('seasonalityInfo').innerHTML = html;
    }

    displayCompetitors(competitors) {
        if (!competitors || competitors.length === 0) {
            document.getElementById('topCompetitors').innerHTML = 
                '<p style="color: #999;">Конкуренты не найдены</p>';
            return;
        }

        const rows = competitors.slice(0, 20).map((comp, index) => {
            const rankClass = index < 3 ? 'top3' : '';
            return `
                <tr>
                    <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
                    <td>${comp.nm_id}</td>
                    <td>${this.truncate(comp.name, 50)}</td>
                    <td>${comp.category || 'N/A'}</td>
                    <td>${this.formatPrice(comp.price)}</td>
                    <td>${comp.brand || 'N/A'}</td>
                    <td>${this.formatNumber(comp.sales || 0)}</td>
                    <td>${this.formatNumber(comp.reviews || 0)}</td>
                    <td>${comp.rating?.toFixed(1) || 'N/A'}</td>
                </tr>
            `;
        }).join('');

        const html = `
            <div class="competitors-table">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Артикул</th>
                            <th>Название</th>
                            <th>Категория</th>
                            <th>Цена</th>
                            <th>Бренд</th>
                            <th>Продажи</th>
                            <th>Отзывы</th>
                            <th>Рейтинг</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
        document.getElementById('topCompetitors').innerHTML = html;
    }

    displayRecommendations(recommendations) {
        if (!recommendations || recommendations.length === 0) {
            document.getElementById('recommendations').innerHTML = 
                '<p style="color: #999;">Рекомендации недоступны</p>';
            return;
        }

        const items = recommendations.map(rec => 
            `<li>💡 ${rec}</li>`
        ).join('');

        const html = `<ul class="recommendations-list">${items}</ul>`;
        document.getElementById('recommendations').innerHTML = html;
    }

    // Экспорт в Excel
    async exportExcel() {
        this.showLoading(true);
        this.hideError();

        try {
            const response = await fetch(`${this.apiBase}/export/excel`);
            
            if (!response.ok) {
                throw new Error(`Ошибка экспорта: ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `price_optimization_${this.formatDate()}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            alert('✅ Отчет успешно скачан!');
        } catch (error) {
            this.showError(`Не удалось экспортировать: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    // Вспомогательные функции
    interpretElasticity(e) {
        if (!e) return 'Нет данных';
        const abs = Math.abs(e);
        if (abs < 0.5) return 'Спрос неэластичный - цену можно повышать';
        if (abs < 1.5) return 'Спрос умеренно эластичный - требуется осторожность';
        return 'Спрос высоко эластичный - снижение цены увеличит продажи';
    }

    getSeasonalityTrend(factor) {
        if (factor >= 1.15) return '🔥 Высокий спрос - можно повысить цену';
        if (factor >= 1.05) return '📈 Рост спроса - благоприятное время';
        if (factor >= 0.95) return '➡️ Стабильный спрос';
        if (factor >= 0.85) return '📉 Снижение спроса - рассмотрите скидки';
        return '❄️ Низкий спрос - возможно межсезонье';
    }

    formatPrice(price) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0
        }).format(price);
    }

    formatNumber(num) {
        return new Intl.NumberFormat('ru-RU').format(num);
    }

    formatDate() {
        const now = new Date();
        return now.toISOString().split('T')[0];
    }

    truncate(str, len) {
        if (!str) return 'N/A';
        return str.length > len ? str.substring(0, len) + '...' : str;
    }

    showLoading(show) {
        document.getElementById('loadingIndicator').style.display = show ? 'block' : 'none';
    }

    showError(message) {
        const el = document.getElementById('errorMessage');
        el.textContent = '❌ ' + message;
        el.style.display = 'block';
    }

    hideError() {
        document.getElementById('errorMessage').style.display = 'none';
    }

    showResults() {
        document.getElementById('resultsContainer').style.display = 'block';
    }

    hideResults() {
        document.getElementById('resultsContainer').style.display = 'none';
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', () => {
    new PriceOptimizerApp();
});
