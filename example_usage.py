"""
Примеры использования API оптимизатора цен Wildberries
"""
import httpx
import asyncio
import json


BASE_URL = "http://localhost:8000"


async def example_1_add_product():
    """Пример 1: Добавление товара"""
    print("\n=== Пример 1: Добавление товара ===")
    
    product_data = {
        "nm_id": 123456789,
        "name": "Футболка мужская хлопок",
        "category": "Мужская одежда",
        "current_price": 1500,  # Цена со скидкой!
        "cost_price": 800
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/products",
            json=product_data,
            timeout=30.0
        )
        
        if response.status_code == 201:
            print("✅ Товар успешно добавлен:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def example_2_analyze_competitors():
    """Пример 2: Анализ конкурентов"""
    print("\n=== Пример 2: Анализ конкурентов ===")
    
    request_data = {
        "nm_id": 123456789,
        "min_reviews": 500  # Минимум 500 отзывов
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/competitors/analyze",
            json=request_data,
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Анализ конкурентов завершен:")
            print(f"\nНаш товар:")
            print(f"  - Цена со скидкой: {data['our_product']['price_with_discount']} руб")
            print(f"  - Отзывов: {data['our_product']['reviews_count']}")
            
            print(f"\nНайдено конкурентов: {data['total_competitors']}")
            
            if data.get('analysis'):
                analysis = data['analysis']
                print(f"\nЦены конкурентов:")
                print(f"  - Минимальная: {analysis['min_price']} руб")
                print(f"  - Средняя: {analysis['avg_price']} руб")
                print(f"  - Медианная: {analysis['median_price']} руб")
                print(f"  - Максимальная: {analysis['max_price']} руб")
                
                position = analysis['our_position']
                print(f"\nВаша позиция:")
                print(f"  - Процентиль: {position['percentile']}%")
                print(f"  - {position['position_description']}")
                
                print(f"\nОптимальный диапазон:")
                optimal = analysis['optimal_range']
                print(f"  - От {optimal['low']} до {optimal['high']} руб")
                
                print(f"\nТоп-5 конкурентов:")
                for i, comp in enumerate(analysis['top_competitors'][:5], 1):
                    print(f"  {i}. {comp['name']}")
                    print(f"     Цена: {comp['price_with_discount']} руб, "
                          f"Отзывов: {comp['reviews_count']}, "
                          f"Рейтинг: {comp['rating']}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def example_3_optimize_with_competitors():
    """Пример 3: Оптимизация цены с учетом конкурентов"""
    print("\n=== Пример 3: Оптимизация с учетом конкурентов ===")
    
    nm_id = 123456789
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/optimize/{nm_id}",
            params={
                "optimize_for": "profit",  # profit, revenue, или balanced
                "consider_competitors": True
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Оптимизация завершена:")
            
            print(f"\nТекущая ситуация:")
            print(f"  - Товар: {data['product_name']}")
            print(f"  - Текущая цена: {data['current_price']} руб")
            print(f"  - Текущие продажи: {data['current_daily_sales']} шт/день")
            print(f"  - Текущая прибыль: {data['current_daily_profit']:.2f} руб/день")
            
            print(f"\nОптимальная цена: {data['optimal_price']} руб")
            print(f"Изменение: {data['price_change_percent']:+.1f}%")
            
            print(f"\nПрогнозы:")
            print(f"  - Продажи: {data['predicted_daily_sales']} шт/день")
            print(f"  - Выручка: {data['predicted_daily_revenue']:.2f} руб/день")
            print(f"  - Прибыль: {data['predicted_daily_profit']:.2f} руб/день")
            
            profit_increase = data['predicted_daily_profit'] - data['current_daily_profit']
            print(f"\n💰 Прирост прибыли: {profit_increase:+.2f} руб/день "
                  f"({(profit_increase/data['current_daily_profit']*100):+.1f}%)")
            
            elasticity = data['elasticity']
            print(f"\nЭластичность спроса:")
            print(f"  - Коэффициент: {elasticity['elasticity_coefficient']:.2f}")
            print(f"  - Тип: {'Эластичный' if elasticity['is_elastic'] else 'Неэластичный'}")
            print(f"  - Уверенность: {elasticity['confidence']:.1%}")
            
            print(f"\nРиск: {data['risk_level'].upper()}")
            print(f"\nРекомендация AI:")
            print(f"  {data['recommendation']}")
            
            if data.get('competitor_analysis'):
                comp = data['competitor_analysis']
                if comp.get('analysis'):
                    analysis = comp['analysis']
                    print(f"\nАнализ конкурентов:")
                    print(f"  - Найдено: {comp['total_competitors']} конкурентов")
                    print(f"  - Медиана рынка: {analysis['median_price']} руб")
                    print(f"  - Ваша позиция: {analysis['our_position']['position_description']}")
            
            print(f"\nАльтернативные сценарии:")
            for scenario in data['alternative_scenarios']:
                print(f"\n  {scenario['name']}:")
                print(f"    - Цена: {scenario['price']} руб")
                print(f"    - Прогноз продаж: {scenario.get('predicted_sales', 'N/A')} шт")
                print(f"    - Прогноз прибыли: {scenario.get('predicted_profit', 'N/A')} руб")
                print(f"    - Описание: {scenario['description']}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def example_4_bulk_optimization():
    """Пример 4: Массовая оптимизация"""
    print("\n=== Пример 4: Массовая оптимизация ===")
    
    request_data = {
        "optimize_for": "balanced",
        "min_confidence": 0.7,
        "consider_competitors": True
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/optimize/bulk",
            json=request_data,
            timeout=300.0  # 5 минут
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Массовая оптимизация завершена:")
            print(f"\nОбработано товаров: {data['total_products']}")
            print(f"Оптимизировано: {data['optimized_products']}")
            print(f"\nПотенциальный прирост:")
            print(f"  - Прибыль: +{data['total_potential_profit_increase']:.2f} руб/день")
            print(f"  - Выручка: +{data['total_potential_revenue_increase']:.2f} руб/день")
            
            print(f"\nТоп-3 рекомендации:")
            for i, rec in enumerate(data['recommendations'][:3], 1):
                profit_increase = rec['predicted_daily_profit'] - rec['current_daily_profit']
                print(f"\n  {i}. {rec['product_name']} (#{rec['nm_id']})")
                print(f"     Цена: {rec['current_price']} → {rec['optimal_price']} руб "
                      f"({rec['price_change_percent']:+.1f}%)")
                print(f"     Прирост прибыли: +{profit_increase:.2f} руб/день")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def example_5_apply_price():
    """Пример 5: Применение оптимальной цены"""
    print("\n=== Пример 5: Применение оптимальной цены ===")
    
    nm_id = 123456789
    
    # Подтверждение от пользователя
    print(f"⚠️  Внимание! Цена товара {nm_id} будет обновлена на Wildberries.")
    confirm = input("Продолжить? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("❌ Отменено пользователем")
        return
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/apply-price/{nm_id}",
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data['message']}")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def example_6_get_analytics():
    """Пример 6: Получение аналитики"""
    print("\n=== Пример 6: Аналитика товара ===")
    
    nm_id = 123456789
    days = 30
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/analytics/{nm_id}",
            params={"days": days},
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Аналитика за {days} дней:")
            
            price = data['price']
            print(f"\nЦены (со скидкой):")
            print(f"  - Текущая: {price['current']} руб")
            print(f"  - Средняя: {price['avg']} руб")
            print(f"  - Диапазон: {price['min']} - {price['max']} руб")
            
            sales = data['sales']
            print(f"\nПродажи:")
            print(f"  - Всего: {sales['total']} шт")
            print(f"  - В среднем: {sales['avg_daily']} шт/день")
            print(f"  - Диапазон: {sales['min_daily']} - {sales['max_daily']} шт/день")
            
            revenue = data['revenue']
            print(f"\nВыручка:")
            print(f"  - Всего: {revenue['total']:.2f} руб")
            print(f"  - В среднем: {revenue['avg_daily']:.2f} руб/день")
        else:
            print(f"❌ Ошибка: {response.status_code}")
            print(response.text)


async def main():
    """Запуск всех примеров"""
    print("=" * 60)
    print("  ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ WILDBERRIES PRICE OPTIMIZER")
    print("=" * 60)
    
    try:
        # Проверка доступности API
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if response.status_code != 200:
                print("❌ API недоступен. Запустите сервер: python main.py")
                return
        
        # Запуск примеров
        await example_1_add_product()
        await asyncio.sleep(1)
        
        await example_2_analyze_competitors()
        await asyncio.sleep(1)
        
        await example_3_optimize_with_competitors()
        await asyncio.sleep(1)
        
        await example_4_bulk_optimization()
        await asyncio.sleep(1)
        
        await example_6_get_analytics()
        await asyncio.sleep(1)
        
        # Пример применения цены (требует подтверждения)
        # await example_5_apply_price()
        
        print("\n" + "=" * 60)
        print("  ✅ ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
        print("=" * 60)
        
    except httpx.ConnectError:
        print("\n❌ Не удается подключиться к API.")
        print("Убедитесь, что сервер запущен: python main.py")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
