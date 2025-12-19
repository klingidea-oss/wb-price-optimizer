"""
Конфигурация приложения для оптимизации цен на Wildberries
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # API ключи
    WB_API_KEY = os.getenv("WB_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Настройки базы данных
    DATABASE_URL = "sqlite+aiosqlite:///./wb_optimizer.db"
    
    # Настройки анализа
    MIN_DATA_POINTS = 7  # Минимум точек данных для анализа эластичности
    ELASTICITY_WINDOW_DAYS = 30  # Окно анализа в днях
    
    # Границы оптимизации
    MIN_PRICE_CHANGE_PERCENT = -30  # Максимальное снижение цены
    MAX_PRICE_CHANGE_PERCENT = 50   # Максимальное повышение цены
    
    # Настройки AI агента
    AI_MODEL = "gpt-4"  # или "claude-3-opus-20240229"
    AI_TEMPERATURE = 0.3
    
    # Wildberries API endpoints
    WB_API_BASE_URL = "https://suppliers-api.wildberries.ru"
    WB_STATISTICS_URL = f"{WB_API_BASE_URL}/content/v1/analytics/nm-report/detail"
    WB_PRICES_URL = f"{WB_API_BASE_URL}/public/api/v1/prices"
