// WB Price Optimizer V2.0 - Client Application (FIXED)

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

    // Загрузка статистики (ИСПРАВЛЕНО)
    async loadStats() {
        try {
            const response = await fetch(`${this.apiBase}/categories/stats`);
            const data = await response.json();
            
            // Подсчёт категорий из statistics
            let totalCategories = 0;
            if (data.statistics) {
                totalCategories = Object.keys(data.statistics).length;
            }
            
            document.getElementById('totalProducts').textContent = 
                this.formatNumber(data.total_products || 0);
            document.getElementById('totalCategories').textContent = 
                this.formatNumber(totalCategories);
            document.getElementById('totalGroups').textContent = 
                this.formatNumber(data.total_groups || 0);
        } catch (error) {
            console.error('Ошибка загрузки статистики:', error);
        }
    }

    // Анализ товара (ИСПРАВЛЕНО для реальной структуры API)
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
                throw new Error(`Товар не найден (код: ${response.status})`);
            }

            const data = await response.json();
            this.displayResults(data);
        } catch (error) {
            this.showError(`${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    // Отображение результатов (АДАПТИРОВАНО под реальную структуру API)
    displayResults(data) {
        // Информация о товаре
        this.displayProductInfo(data);
        
        // Оптимизация цены
        this.displayPriceOptimization(data);
        
        // Эластичность
        this.displayElasticity(data.demand_analysis);
        
        // Сезонность
        this.displaySeasonality(data.seasonality);
        
        // Конкуренты
        this.displayCompetitors(data.competitor_analysis);
        
        // Рекомендации
        this.displayRecommendations(data.recommendation);
        
        // Показать результаты
        this.showResults();
    }

    displayProductInfo(data) {
        const html = `
            <div class="product-info-grid">
                <div class="info-item">
                    <div class="info-label">Артикул WB</div>
                    <div class="info-value">${data.nm_id}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Тип товара</div>
                    <div class="info-value">${data.product_type || 'Не указан'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Категория</div>
                    <div class="info-value">${data.category || 'Не указана'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Текущая цена</div>
                    <div class="info-value">${this.formatPrice(data.current_price)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Себестоимость</div>
                    <div class="info-value">${this.formatPrice(data.cost)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Маржа</div>
                    <div class="info-value">${((data.current_price - data.cost) / data.current_price * 100).toFixed(1)}%</div>
                </div>
            </div>
        `;
        document.getElementById('productInfo').innerHTML = html;
    }

    displayPriceOptimization(data) {
        const currentPrice = data.current_price;
        const optimalPrice = data.price_optimization?.optimal_price || currentPrice;
        const change = ((optimalPrice - currentPrice) / currentPrice * 100).toFixed(1);
        const changeClass = change >= 0 ? 'positive' : 'negative';
        const changeSign = change >= 0 ? '+' : '';
        
        const priceRange = data.price_optimization?.price_range || {};

        const html = `
            <div class="price-comparison">
                <div class="price-box price-box-current">
                    <div class="price-label">Текущая цена</div>
                    <div class="price-amount">${this.formatPrice(currentPrice)}</div>
                </div>
                <div class="price-box price-box-optimal">
                    <div class="price-label">🎯 Оптимальная цена</div>
                    <div class="price-amount">${this.formatPrice(optimalPrice)}</div>
                    <div class="price-change ${changeClass}">
                        ${changeSign}${change}%
                    </div>
                </div>
                <div class="price-box price-box-competitor">
                    <div class="price-label">Диапазон рынка</div>
                    <div class="price-amount">
                        ${this.formatPrice(priceRange.min || 0)} - ${this.formatPrice(priceRange.max || 0)}
                    </div>
                    <div style="font-size: 0.85em; color: #666;">
                        Медиана: ${this.formatPrice(priceRange.median || 0)}
                    </div>
                </div>
            </div>
        `;
        document.getElementById('priceOptimization').innerHTML = html;
    }

    displayElasticity(elasticity) {
        if (!elasticity) {
            document.getElementById('elasticityAnalysis').innerHTML = 
                '<p style="color: #999;">Данные об эластичности недоступны</p>';
            return;
        }

        const html = `
            <div class="elasticity-grid">
                <div class="elasticity-item">
                    <strong>Коэффициент эластичности</strong>
                    <span style="font-size: 1.5em; color: #667eea;">${elasticity.elasticity?.toFixed(2) || 'N/A'}</span>
                </div>
                <div class="elasticity-item">
                    <strong>Интерпретация</strong>
                    <span>${elasticity.interpretation || 'N/A'}</span>
                </div>
                <div class="elasticity-item">
                    <strong>Период анализа</strong>
                    <span>${elasticity.period_days || 0} дней (${elasticity.data_points || 0} точек)</span>
                </div>
                <div class="elasticity-item">
                    <strong>Лучший день продаж</strong>
                    <span>${elasticity.best_sales_day?.sales || 0} шт по ${this.formatPrice(elasticity.best_sales_day?.price || 0)}</span>
                </div>
            </div>
            <div style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 10px;">
                <p style="font-size: 14px; color: #666;">
                    <strong>💡 Что это значит:</strong> 
                    ${this.interpretElasticity(elasticity.elasticity)}
                </p>
            </div>
        `;
        document.getElementById('elasticityAnalysis').innerHTML = html;
    }

    displaySeasonality(seasonality) {
        if (!seasonality) {
            document.getElementById('seasonalityInfo').innerHTML = 
                '<p style="color: #999;">Данные о сезонности недоступны</p>';
            return;
        }

        const index = seasonality.seasonality_index || 1.0;
        const adjustment = ((index - 1) * 100).toFixed(1);
        const adjustmentSign = adjustment >= 0 ? '+' : '';

        const html = `
            <div class="seasonality-info">
                <p><strong>Текущий месяц:</strong> ${seasonality.current_month || 'N/A'}</p>
                <p><strong>Индекс сезонности:</strong> ${index.toFixed(2)} (${adjustmentSign}${adjustment}%)</p>
                <p><strong>Статус:</strong> ${seasonality.interpretation || 'Нормальный сезон'}</p>
                <p><strong>Источник:</strong> ${seasonality.source || 'WB API'}</p>
            </div>
        `;
        document.getElementById('seasonalityInfo').innerHTML = html;
    }

    displayCompetitors(competitorAnalysis) {
        if (!competitorAnalysis || !competitorAnalysis.top_sellers || competitorAnalysis.top_sellers.length === 0) {
            document.getElementById('topCompetitors').innerHTML = 
                `<p style="color: #999;">Конкуренты не найдены. ${competitorAnalysis?.category_note || ''}</p>`;
            return;
        }

        const rows = competitorAnalysis.top_sellers.map((comp, index) => {
            const rankClass = index < 3 ? 'top3' : '';
            return `
                <tr>
                    <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
                    <td>${comp.nm_id}</td>
                    <td>${this.truncate(comp.name || 'Неизвестно', 40)}</td>
                    <td>${comp.category || 'N/A'}</td>
                    <td><strong>${this.formatPrice(comp.price)}</strong></td>
                    <td>${this.formatNumber(comp.sales_7d || 0)} шт/нед</td>
                    <td>${this.formatPrice(comp.revenue_7d || 0)}</td>
                </tr>
            `;
        }).join('');

        const html = `
            <div style="margin-bottom: 15px; padding: 10px; background: #f0f0f0; border-radius: 8px;">
                <p><strong>Проанализировано:</strong> ${competitorAnalysis.total_analyzed || 0} конкурентов</p>
                <p style="font-size: 0.9em; color: #666;">${competitorAnalysis.category_note || ''}</p>
            </div>
            <div class="competitors-table">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Артикул</th>
                            <th>Название</th>
                            <th>Категория</th>
                            <th>Цена</th>
                            <th>Продажи (7 дней)</th>
                            <th>Выручка (7 дней)</th>
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

    displayRecommendations(recommendation) {
        if (!recommendation) {
            document.getElementById('recommendations').innerHTML = 
                '<p style="color: #999;">Рекомендации недоступны</p>';
            return;
        }

        const html = `
            <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 12px; font-size: 1.1em; line-height: 1.6;">
                ${recommendation}
            </div>
        `;
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
        if (abs < 0.5) return 'Спрос неэластичный - покупатели не чувствительны к цене, можно повышать';
        if (abs < 1.5) return 'Спрос умеренно эластичный - изменение цены влияет на продажи пропорционально';
        return 'Спрос высоко эластичный - снижение цены значительно увеличит продажи';
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
