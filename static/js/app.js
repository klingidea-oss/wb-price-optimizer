// WB Price Optimizer - Frontend Application (Bootstrap Compatible)
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
    loadDashboard();
    checkHealth();
});

// Navigation
function showSection(sectionName) {
    // Hide all sections
    const sections = ['dashboard', 'products', 'competitors', 'optimization'];
    sections.forEach(s => {
        const section = document.getElementById(`${s}-section`);
        if (section) section.style.display = 'none';
    });
    
    // Show target section
    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
        targetSection.style.display = 'block';
        
        // Load section data
        switch(sectionName) {
            case 'dashboard':
                loadDashboard();
                break;
            case 'products':
                loadProducts();
                break;
        }
    }
}

// Dashboard
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
    
    // Update stats
    const totalEl = document.getElementById('total-products');
    if (totalEl) totalEl.textContent = totalProducts;
    
    // Update API status
    const apiStatus = document.getElementById('api-status');
    if (apiStatus) {
        apiStatus.innerHTML = '<span class="badge bg-success">Активен</span>';
    }
}

// Products Management
async function loadProducts() {
    console.log('📦 Loading products...');
    const productsList = document.getElementById('products-list');
    if (!productsList) return;
    
    productsList.innerHTML = '<div class="text-center py-5">
