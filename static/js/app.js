// WB Price Optimizer V2.0 - Client Application (FIXED)

class PriceOptimizerApp {
    constructor() {
        this.apiBase = window.location.origin;
        this.init();
    }

    init() {
        // Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ¸ Ð¿Ñ€Ð¸ ÑÑ‚Ð°Ñ€Ñ‚Ðµ
        this.loadStats();
        
        // ÐžÐ±Ñ€Ð°Ð±Ð¾Ñ‚Ñ‡Ð¸ÐºÐ¸ ÑÐ¾Ð±Ñ‹Ñ‚Ð¸Ð¹
        document.getElementById('analyzeBtn').addEventListener('click', () => this.analyze());
        document.getElementById('exportExcelBtn').addEventListener('click', () => this.exportExcel());
        
        // Enter Ð´Ð»Ñ Ð¿Ð¾Ð¸ÑÐºÐ°
        document.getElementById('nmIdInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.analyze();
        });
    }

    // Ð—Ð°Ð³Ñ€ÑƒÐ·ÐºÐ° ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ¸ (Ð˜Ð¡ÐŸÐ ÐÐ’Ð›Ð•ÐÐž)
    async loadStats() {
        try {
            const response = await fetch(`${this.apiBase}/categories/stats`);
            const data = await response.json();
            
            // ÐŸÐ¾Ð´ÑÑ‡Ñ‘Ñ‚ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ð¹ Ð¸Ð· statistics
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
            console.error('ÐžÑˆÐ¸Ð±ÐºÐ° Ð·Ð°Ð³Ñ€ÑƒÐ·ÐºÐ¸ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ¸:', error);
        }
    }

    // ÐÐ½Ð°Ð»Ð¸Ð· Ñ‚Ð¾Ð²Ð°Ñ€Ð° (Ð˜Ð¡ÐŸÐ ÐÐ’Ð›Ð•ÐÐž Ð´Ð»Ñ Ñ€ÐµÐ°Ð»ÑŒÐ½Ð¾Ð¹ ÑÑ‚Ñ€ÑƒÐºÑ‚ÑƒÑ€Ñ‹ API)
    async analyze() {
        const nmId = document.getElementById('nmIdInput').value.trim();
        
        if (!nmId) {
            this.showError('ÐŸÐ¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð°, Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð°Ñ€Ñ‚Ð¸ÐºÑƒÐ» WB');
            return;
        }

        this.showLoading(true);
        this.hideError();
        this.hideResults();

        try {
            const response = await fetch(`${this.apiBase}/analyze/full/${nmId}`);
            
            if (!response.ok) {
                throw new Error(`Ð¢Ð¾Ð²Ð°Ñ€ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½ (ÐºÐ¾Ð´: ${response.status})`);
            }

            const data = await response.json();
            this.displayResults(data);
        } catch (error) {
            this.showError(`${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    // ÐžÑ‚Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ðµ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ð¾Ð² (ÐÐ”ÐÐŸÐ¢Ð˜Ð ÐžÐ’ÐÐÐž Ð¿Ð¾Ð´ Ñ€ÐµÐ°Ð»ÑŒÐ½ÑƒÑŽ ÑÑ‚Ñ€ÑƒÐºÑ‚ÑƒÑ€Ñƒ API)
    displayResults(data) {
        // Ð˜Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ñ Ð¾ Ñ‚Ð¾Ð²Ð°Ñ€Ðµ
        this.displayProductInfo(data);
        
        // ÐžÐ¿Ñ‚Ð¸Ð¼Ð¸Ð·Ð°Ñ†Ð¸Ñ Ñ†ÐµÐ½Ñ‹
        this.displayPriceOptimization(data);
        
        // Ð­Ð»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ð¾ÑÑ‚ÑŒ
        this.displayElasticity(data.demand_analysis);
        
        // Ð¡ÐµÐ·Ð¾Ð½Ð½Ð¾ÑÑ‚ÑŒ
        this.displaySeasonality(data.seasonality);
        
        // ÐšÐ¾Ð½ÐºÑƒÑ€ÐµÐ½Ñ‚Ñ‹
        this.displayCompetitors(data.competitor_analysis);
        
        // Ð ÐµÐºÐ¾Ð¼ÐµÐ½Ð´Ð°Ñ†Ð¸Ð¸
        this.displayRecommendations(data.recommendation);
        
        // ÐŸÐ¾ÐºÐ°Ð·Ð°Ñ‚ÑŒ Ñ€ÐµÐ·ÑƒÐ»ÑŒÑ‚Ð°Ñ‚Ñ‹
        this.showResults();
    }

    displayProductInfo(data) {
        const html = `
            <div class="product-info-grid">
                <div class="info-item">
                    <div class="info-label">ÐÑ€Ñ‚Ð¸ÐºÑƒÐ» WB</div>
                    <div class="info-value">${data.nm_id}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Ð¢Ð¸Ð¿ Ñ‚Ð¾Ð²Ð°Ñ€Ð°</div>
                    <div class="info-value">${data.product_type || 'ÐÐµ ÑƒÐºÐ°Ð·Ð°Ð½'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ</div>
                    <div class="info-value">${data.category || 'ÐÐµ ÑƒÐºÐ°Ð·Ð°Ð½Ð°'}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Ð¢ÐµÐºÑƒÑ‰Ð°Ñ Ñ†ÐµÐ½Ð°</div>
                    <div class="info-value">${this.formatPrice(data.current_price)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Ð¡ÐµÐ±ÐµÑÑ‚Ð¾Ð¸Ð¼Ð¾ÑÑ‚ÑŒ</div>
                    <div class="info-value">${this.formatPrice(data.cost)}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">ÐœÐ°Ñ€Ð¶Ð°</div>
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
                    <div class="price-label">Ð¢ÐµÐºÑƒÑ‰Ð°Ñ Ñ†ÐµÐ½Ð°</div>
                    <div class="price-amount">${this.formatPrice(currentPrice)}</div>
                </div>
                <div class="price-box price-box-optimal">
                    <div class="price-label">ðŸŽ¯ ÐžÐ¿Ñ‚Ð¸Ð¼Ð°Ð»ÑŒÐ½Ð°Ñ Ñ†ÐµÐ½Ð°</div>
                    <div class="price-amount">${this.formatPrice(optimalPrice)}</div>
                    <div class="price-change ${changeClass}">
                        ${changeSign}${change}%
                    </div>
                </div>
                <div class="price-box price-box-competitor">
                    <div class="price-label">Ð”Ð¸Ð°Ð¿Ð°Ð·Ð¾Ð½ Ñ€Ñ‹Ð½ÐºÐ°</div>
                    <div class="price-amount">
                        ${this.formatPrice(priceRange.min || 0)} - ${this.formatPrice(priceRange.max || 0)}
                    </div>
                    <div style="font-size: 0.85em; color: #666;">
                        ÐœÐµÐ´Ð¸Ð°Ð½Ð°: ${this.formatPrice(priceRange.median || 0)}
                    </div>
                </div>
            </div>
        `;
        document.getElementById('priceOptimization').innerHTML = html;
    }

    displayElasticity(elasticity) {
        if (!elasticity) {
            document.getElementById('elasticityAnalysis').innerHTML = 
                '<p style="color: #999;">Ð”Ð°Ð½Ð½Ñ‹Ðµ Ð¾Ð± ÑÐ»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ð¾ÑÑ‚Ð¸ Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ñ‹</p>';
            return;
        }

        const html = `
            <div class="elasticity-grid">
                <div class="elasticity-item">
                    <strong>ÐšÐ¾ÑÑ„Ñ„Ð¸Ñ†Ð¸ÐµÐ½Ñ‚ ÑÐ»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ð¾ÑÑ‚Ð¸</strong>
                    <span style="font-size: 1.5em; color: #667eea;">${elasticity.elasticity?.toFixed(2) || 'N/A'}</span>
                </div>
                <div class="elasticity-item">
                    <strong>Ð˜Ð½Ñ‚ÐµÑ€Ð¿Ñ€ÐµÑ‚Ð°Ñ†Ð¸Ñ</strong>
                    <span>${elasticity.interpretation || 'N/A'}</span>
                </div>
                <div class="elasticity-item">
                    <strong>ÐŸÐµÑ€Ð¸Ð¾Ð´ Ð°Ð½Ð°Ð»Ð¸Ð·Ð°</strong>
                    <span>${elasticity.period_days || 0} Ð´Ð½ÐµÐ¹ (${elasticity.data_points || 0} Ñ‚Ð¾Ñ‡ÐµÐº)</span>
                </div>
                <div class="elasticity-item">
                    <strong>Ð›ÑƒÑ‡ÑˆÐ¸Ð¹ Ð´ÐµÐ½ÑŒ Ð¿Ñ€Ð¾Ð´Ð°Ð¶</strong>
                    <span>${elasticity.best_sales_day?.sales || 0} ÑˆÑ‚ Ð¿Ð¾ ${this.formatPrice(elasticity.best_sales_day?.price || 0)}</span>
                </div>
            </div>
            <div style="margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 10px;">
                <p style="font-size: 14px; color: #666;">
                    <strong>ðŸ’¡ Ð§Ñ‚Ð¾ ÑÑ‚Ð¾ Ð·Ð½Ð°Ñ‡Ð¸Ñ‚:</strong> 
                    ${this.interpretElasticity(elasticity.elasticity)}
                </p>
            </div>
        `;
        document.getElementById('elasticityAnalysis').innerHTML = html;
    }

    displaySeasonality(seasonality) {
        if (!seasonality) {
            document.getElementById('seasonalityInfo').innerHTML = 
                '<p style="color: #999;">Ð”Ð°Ð½Ð½Ñ‹Ðµ Ð¾ ÑÐµÐ·Ð¾Ð½Ð½Ð¾ÑÑ‚Ð¸ Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ñ‹</p>';
            return;
        }

        const index = seasonality.seasonality_index || 1.0;
        const adjustment = ((index - 1) * 100).toFixed(1);
        const adjustmentSign = adjustment >= 0 ? '+' : '';

        const html = `
            <div class="seasonality-info">
                <p><strong>Ð¢ÐµÐºÑƒÑ‰Ð¸Ð¹ Ð¼ÐµÑÑÑ†:</strong> ${seasonality.current_month || 'N/A'}</p>
                <p><strong>Ð˜Ð½Ð´ÐµÐºÑ ÑÐµÐ·Ð¾Ð½Ð½Ð¾ÑÑ‚Ð¸:</strong> ${index.toFixed(2)} (${adjustmentSign}${adjustment}%)</p>
                <p><strong>Ð¡Ñ‚Ð°Ñ‚ÑƒÑ:</strong> ${seasonality.interpretation || 'ÐÐ¾Ñ€Ð¼Ð°Ð»ÑŒÐ½Ñ‹Ð¹ ÑÐµÐ·Ð¾Ð½'}</p>
                <p><strong>Ð˜ÑÑ‚Ð¾Ñ‡Ð½Ð¸Ðº:</strong> ${seasonality.source || 'WB API'}</p>
            </div>
        `;
        document.getElementById('seasonalityInfo').innerHTML = html;
    }

    displayCompetitors(competitorAnalysis) {
        if (!competitorAnalysis || !competitorAnalysis.top_sellers || competitorAnalysis.top_sellers.length === 0) {
            document.getElementById('topCompetitors').innerHTML = 
                `<p style="color: #999;">ÐšÐ¾Ð½ÐºÑƒÑ€ÐµÐ½Ñ‚Ñ‹ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ñ‹. ${competitorAnalysis?.category_note || ''}</p>`;
            return;
        }

        const rows = competitorAnalysis.top_sellers.map((comp, index) => {
            const rankClass = index < 3 ? 'top3' : '';
            return `
                <tr>
                    <td><span class="rank-badge ${rankClass}">${index + 1}</span></td>
                    <td>${comp.nm_id}</td>
                    <td>${this.truncate(comp.name || 'ÐÐµÐ¸Ð·Ð²ÐµÑÑ‚Ð½Ð¾', 40)}</td>
                    <td>${comp.category || 'N/A'}</td>
                    <td><strong>${this.formatPrice(comp.price)}</strong></td>
                    <td>${this.formatNumber(comp.sales_7d || 0)} ÑˆÑ‚/Ð½ÐµÐ´</td>
                    <td>${this.formatPrice(comp.revenue_7d || 0)}</td>
                </tr>
            `;
        }).join('');

        const html = `
            <div style="margin-bottom: 15px; padding: 10px; background: #f0f0f0; border-radius: 8px;">
                <p><strong>ÐŸÑ€Ð¾Ð°Ð½Ð°Ð»Ð¸Ð·Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¾:</strong> ${competitorAnalysis.total_analyzed || 0} ÐºÐ¾Ð½ÐºÑƒÑ€ÐµÐ½Ñ‚Ð¾Ð²</p>
                <p style="font-size: 0.9em; color: #666;">${competitorAnalysis.category_note || ''}</p>
            </div>
            <div class="competitors-table">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>ÐÑ€Ñ‚Ð¸ÐºÑƒÐ»</th>
                            <th>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ</th>
                            <th>ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ</th>
                            <th>Ð¦ÐµÐ½Ð°</th>
                            <th>ÐŸÑ€Ð¾Ð´Ð°Ð¶Ð¸ (7 Ð´Ð½ÐµÐ¹)</th>
                            <th>Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ° (7 Ð´Ð½ÐµÐ¹)</th>
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
                '<p style="color: #999;">Ð ÐµÐºÐ¾Ð¼ÐµÐ½Ð´Ð°Ñ†Ð¸Ð¸ Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ñ‹</p>';
            return;
        }

        const html = `
            <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 12px; font-size: 1.1em; line-height: 1.6;">
                ${recommendation}
            </div>
        `;
        document.getElementById('recommendations').innerHTML = html;
    }

    // Ð­ÐºÑÐ¿Ð¾Ñ€Ñ‚ Ð² Excel
    async exportExcel() {
        this.showLoading(true);
        this.hideError();

        try {
            const response = await fetch(`${this.apiBase}/export/excel`);
            
            if (!response.ok) {
                throw new Error(`ÐžÑˆÐ¸Ð±ÐºÐ° ÑÐºÑÐ¿Ð¾Ñ€Ñ‚Ð°: ${response.status}`);
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

            alert('âœ… ÐžÑ‚Ñ‡ÐµÑ‚ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ ÑÐºÐ°Ñ‡Ð°Ð½!');
        } catch (error) {
            this.showError(`ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ ÑÐºÑÐ¿Ð¾Ñ€Ñ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    // Ð’ÑÐ¿Ð¾Ð¼Ð¾Ð³Ð°Ñ‚ÐµÐ»ÑŒÐ½Ñ‹Ðµ Ñ„ÑƒÐ½ÐºÑ†Ð¸Ð¸
    interpretElasticity(e) {
        if (!e) return 'ÐÐµÑ‚ Ð´Ð°Ð½Ð½Ñ‹Ñ…';
        const abs = Math.abs(e);
        if (abs < 0.5) return 'Ð¡Ð¿Ñ€Ð¾Ñ Ð½ÐµÑÐ»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ñ‹Ð¹ - Ð¿Ð¾ÐºÑƒÐ¿Ð°Ñ‚ÐµÐ»Ð¸ Ð½Ðµ Ñ‡ÑƒÐ²ÑÑ‚Ð²Ð¸Ñ‚ÐµÐ»ÑŒÐ½Ñ‹ Ðº Ñ†ÐµÐ½Ðµ, Ð¼Ð¾Ð¶Ð½Ð¾ Ð¿Ð¾Ð²Ñ‹ÑˆÐ°Ñ‚ÑŒ';
        if (abs < 1.5) return 'Ð¡Ð¿Ñ€Ð¾Ñ ÑƒÐ¼ÐµÑ€ÐµÐ½Ð½Ð¾ ÑÐ»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ñ‹Ð¹ - Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ðµ Ñ†ÐµÐ½Ñ‹ Ð²Ð»Ð¸ÑÐµÑ‚ Ð½Ð° Ð¿Ñ€Ð¾Ð´Ð°Ð¶Ð¸ Ð¿Ñ€Ð¾Ð¿Ð¾Ñ€Ñ†Ð¸Ð¾Ð½Ð°Ð»ÑŒÐ½Ð¾';
        return 'Ð¡Ð¿Ñ€Ð¾Ñ Ð²Ñ‹ÑÐ¾ÐºÐ¾ ÑÐ»Ð°ÑÑ‚Ð¸Ñ‡Ð½Ñ‹Ð¹ - ÑÐ½Ð¸Ð¶ÐµÐ½Ð¸Ðµ Ñ†ÐµÐ½Ñ‹ Ð·Ð½Ð°Ñ‡Ð¸Ñ‚ÐµÐ»ÑŒÐ½Ð¾ ÑƒÐ²ÐµÐ»Ð¸Ñ‡Ð¸Ñ‚ Ð¿Ñ€Ð¾Ð´Ð°Ð¶Ð¸';
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
        el.textContent = 'âŒ ' + message;
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

// Ð˜Ð½Ð¸Ñ†Ð¸Ð°Ð»Ð¸Ð·Ð°Ñ†Ð¸Ñ Ð¿Ñ€Ð¸Ð»Ð¾Ð¶ÐµÐ½Ð¸Ñ
document.addEventListener('DOMContentLoaded', () => {
    new PriceOptimizerApp();
});
