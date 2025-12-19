"""
AI агент для анализа и рекомендаций по ценообразованию
"""
import json
from typing import Dict, List, Optional
import logging

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from config import Config
from models import ElasticityAnalysis, OptimalPriceRecommendation

logger = logging.getLogger(__name__)


class PricingAIAgent:
    """AI агент для интеллектуального анализа ценообразования"""
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "openai"):
        """
        Инициализация AI агента
        
        Args:
            api_key: API ключ для выбранного провайдера
            provider: Провайдер AI (openai или anthropic)
        """
        self.provider = provider
        
        if provider == "openai" and OPENAI_AVAILABLE:
            self.client = AsyncOpenAI(api_key=api_key or Config.OPENAI_API_KEY)
            self.model = Config.AI_MODEL
        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            self.client = AsyncAnthropic(api_key=api_key or Config.ANTHROPIC_API_KEY)
            self.model = "claude-3-opus-20240229"
        else:
            logger.warning("AI провайдер недоступен, используется базовый анализ")
            self.client = None
    
    async def analyze_pricing_strategy(
        self,
        product_data: Dict,
        elasticity: ElasticityAnalysis,
        optimal_price: float,
        current_price: float,
        market_context: Optional[Dict] = None
    ) -> Dict:
        """
        Глубокий анализ ценовой стратегии с помощью AI
        
        Args:
            product_data: Данные о товаре
            elasticity: Анализ эластичности
            optimal_price: Оптимальная цена
            current_price: Текущая цена
            market_context: Контекст рынка
        
        Returns:
            Словарь с insights и рекомендациями
        """
        if not self.client:
            return self._basic_analysis(product_data, elasticity, optimal_price, current_price)
        
        # Подготовка данных для анализа
        analysis_prompt = self._build_analysis_prompt(
            product_data, elasticity, optimal_price, current_price, market_context
        )
        
        try:
            if self.provider == "openai":
                response = await self._query_openai(analysis_prompt)
            else:
                response = await self._query_anthropic(analysis_prompt)
            
            return self._parse_ai_response(response)
        
        except Exception as e:
            logger.error(f"Ошибка AI анализа: {e}")
            return self._basic_analysis(product_data, elasticity, optimal_price, current_price)
    
    def _build_analysis_prompt(
        self,
        product_data: Dict,
        elasticity: ElasticityAnalysis,
        optimal_price: float,
        current_price: float,
        market_context: Optional[Dict]
    ) -> str:
        """Построить промпт для AI анализа"""
        
        price_change = ((optimal_price - current_price) / current_price) * 100
        
        prompt = f"""
Ты - эксперт по ценообразованию и анализу эластичности спроса на маркетплейсах.

ДАННЫЕ О ТОВАРЕ:
- Название: {product_data.get('name', 'N/A')}
- Категория: {product_data.get('category', 'N/A')}
- Текущая цена: {current_price:.2f} руб.
- Оптимальная цена: {optimal_price:.2f} руб.
- Изменение цены: {price_change:+.1f}%
- Себестоимость: {product_data.get('cost_price', 0):.2f} руб.

АНАЛИЗ ЭЛАСТИЧНОСТИ:
- Коэффициент эластичности: {elasticity.elasticity_coefficient:.2f}
- Тип спроса: {"Эластичный" if elasticity.is_elastic else "Неэластичный"}
- Уверенность анализа: {elasticity.confidence:.1%}
- Точек данных: {elasticity.data_points}

ПРОГНОЗЫ:
- Текущие продажи: {product_data.get('current_sales', 0)} шт/день
- Прогноз продаж: {product_data.get('predicted_sales', 0)} шт/день
- Текущая прибыль: {product_data.get('current_profit', 0):.2f} руб/день
- Прогноз прибыли: {product_data.get('predicted_profit', 0):.2f} руб/день

Проанализируй ситуацию и предоставь:

1. ОЦЕНКУ РИСКА (низкий/средний/высокий):
   - Оцени риски изменения цены
   - Учти эластичность спроса и размер изменения

2. СТРАТЕГИЧЕСКИЕ РЕКОМЕНДАЦИИ:
   - Стоит ли менять цену сейчас?
   - Как лучше внедрить изменение? (постепенно/сразу)
   - Какие факторы учесть?

3. АЛЬТЕРНАТИВНЫЕ СЦЕНАРИИ:
   - Предложи 2-3 альтернативных ценовых стратегии
   - Для каждой укажи плюсы и минусы

4. МОНИТОРИНГ:
   - Какие метрики отслеживать?
   - Когда пересмотреть цену?

Ответь в формате JSON:
{{
    "risk_level": "low|medium|high",
    "recommendation": "подробная рекомендация",
    "implementation_strategy": "как внедрить",
    "key_factors": ["фактор1", "фактор2"],
    "alternative_scenarios": [
        {{"price": цена, "strategy": "описание", "pros": ["плюс1"], "cons": ["минус1"]}}
    ],
    "monitoring_metrics": ["метрика1", "метрика2"],
    "review_period_days": число_дней
}}
"""
        return prompt
    
    async def _query_openai(self, prompt: str) -> str:
        """Запрос к OpenAI API"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты эксперт по ценообразованию на маркетплейсах. Отвечай только в формате JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=Config.AI_TEMPERATURE,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    
    async def _query_anthropic(self, prompt: str) -> str:
        """Запрос к Anthropic API"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=Config.AI_TEMPERATURE,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    
    def _parse_ai_response(self, response: str) -> Dict:
        """Парсинг ответа AI"""
        try:
            # Попытка извлечь JSON из ответа
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Ошибка парсинга AI ответа: {e}")
            return {
                "risk_level": "medium",
                "recommendation": "Требуется дополнительный анализ",
                "implementation_strategy": "Постепенное изменение цены",
                "key_factors": ["Мониторинг конкурентов", "Отслеживание продаж"],
                "alternative_scenarios": [],
                "monitoring_metrics": ["Продажи", "Конверсия", "Позиция в поиске"],
                "review_period_days": 7
            }
    
    def _basic_analysis(
        self,
        product_data: Dict,
        elasticity: ElasticityAnalysis,
        optimal_price: float,
        current_price: float
    ) -> Dict:
        """Базовый анализ без AI"""
        
        price_change_pct = abs((optimal_price - current_price) / current_price)
        
        # Определение уровня риска
        if price_change_pct > 0.20 or elasticity.confidence < 0.6:
            risk_level = "high"
        elif price_change_pct > 0.10 or elasticity.confidence < 0.75:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Рекомендация
        if elasticity.is_elastic:
            recommendation = (
                f"Спрос эластичный (коэф. {elasticity.elasticity_coefficient:.2f}). "
                f"{'Снижение' if optimal_price < current_price else 'Повышение'} цены "
                f"приведет к {'значительному росту' if optimal_price < current_price else 'снижению'} продаж."
            )
        else:
            recommendation = (
                f"Спрос неэластичный (коэф. {elasticity.elasticity_coefficient:.2f}). "
                f"Изменение цены не сильно повлияет на объем продаж."
            )
        
        return {
            "risk_level": risk_level,
            "recommendation": recommendation,
            "implementation_strategy": "Постепенное изменение с мониторингом результатов",
            "key_factors": [
                "Эластичность спроса",
                "Конкурентное окружение",
                "Сезонность"
            ],
            "alternative_scenarios": [],
            "monitoring_metrics": [
                "Ежедневные продажи",
                "Конверсия",
                "Средний чек",
                "Позиция в категории"
            ],
            "review_period_days": 7
        }
