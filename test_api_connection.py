"""
Тест подключения к API Wildberries
"""
import asyncio
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("WB_API_KEY")


async def test_api_connection():
    """Тест подключения к API Wildberries"""
    print("=" * 60)
    print("  ТЕСТ ПОДКЛЮЧЕНИЯ К API WILDBERRIES")
    print("=" * 60)
    
    if not API_KEY:
        print("❌ API ключ не найден в .env файле")
        return False
    
    print(f"\n✅ API ключ загружен")
    print(f"   Длина: {len(API_KEY)} символов")
    print(f"   Начало: {API_KEY[:20]}...")
    
    # Тест 1: Проверка доступности API
    print("\n📡 Тест 1: Проверка доступности API...")
    
    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Пробуем получить информацию о контенте
            url = "https://suppliers-api.wildberries.ru/content/v2/get/cards/list"
            
            response = await client.post(
                url,
                headers=headers,
                json={
                    "settings": {
                        "cursor": {
                            "limit": 1
                        }
                    }
                },
                timeout=30.0
            )
            
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ API доступен и работает корректно")
                data = response.json()
                
                if "cards" in data:
                    print(f"   ✅ Найдено товаров в каталоге: {len(data['cards'])}")
                    
                    if data['cards']:
                        card = data['cards'][0]
                        print(f"\n   Пример товара:")
                        print(f"   - ID: {card.get('nmID', 'N/A')}")
                        print(f"   - Артикул поставщика: {card.get('vendorCode', 'N/A')}")
                
                return True
            
            elif response.status_code == 401:
                print("   ❌ Ошибка авторизации - проверьте API ключ")
                return False
            
            elif response.status_code == 403:
                print("   ❌ Доступ запрещен - проверьте права API ключа")
                return False
            
            else:
                print(f"   ⚠️  Неожиданный статус: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
                return False
    
    except httpx.ConnectError:
        print("   ❌ Ошибка подключения к API")
        return False
    
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_public_api():
    """Тест публичного API (для поиска конкурентов)"""
    print("\n📡 Тест 2: Проверка публичного API (для конкурентов)...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Тестовый запрос к публичному API
            url = "https://search.wb.ru/exactmatch/ru/common/v4/search"
            
            params = {
                "appType": 1,
                "curr": "rub",
                "dest": -1257786,
                "query": "футболка",
                "resultset": "catalog",
                "sort": "popular",
                "spp": 30,
                "suppressSpellcheck": False
            }
            
            response = await client.get(url, params=params, timeout=30.0)
            
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ Публичный API доступен")
                data = response.json()
                
                if "data" in data and "products" in data["data"]:
                    products = data["data"]["products"]
                    print(f"   ✅ Найдено товаров: {len(products)}")
                    
                    if products:
                        product = products[0]
                        print(f"\n   Пример товара конкурента:")
                        print(f"   - ID: {product.get('id', 'N/A')}")
                        print(f"   - Название: {product.get('name', 'N/A')[:50]}...")
                        print(f"   - Цена со скидкой: {product.get('salePriceU', 0) / 100} руб")
                        print(f"   - Отзывов: {product.get('feedbacks', 0)}")
                
                return True
            else:
                print(f"   ⚠️  Статус: {response.status_code}")
                return False
    
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_card_api():
    """Тест API карточек товаров"""
    print("\n📡 Тест 3: Проверка API карточек товаров...")
    
    try:
        async with httpx.AsyncClient() as client:
            # Тестовый популярный товар
            test_nm_id = 171144489  # Популярный товар на WB
            
            url = f"https://card.wb.ru/cards/v1/detail"
            params = {
                "appType": 1,
                "curr": "rub",
                "dest": -1257786,
                "spp": 30,
                "nm": test_nm_id
            }
            
            response = await client.get(url, params=params, timeout=30.0)
            
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ API карточек доступен")
                data = response.json()
                
                if "data" in data and "products" in data["data"]:
                    products = data["data"]["products"]
                    if products:
                        product = products[0]
                        print(f"\n   Информация о товаре:")
                        print(f"   - ID: {product.get('id', 'N/A')}")
                        print(f"   - Название: {product.get('name', 'N/A')[:50]}...")
                        print(f"   - Цена со скидкой: {product.get('salePriceU', 0) / 100} руб")
                        print(f"   - Рейтинг: {product.get('rating', 0)}")
                        print(f"   - Отзывов: {product.get('feedbacks', 0)}")
                
                return True
            else:
                print(f"   ⚠️  Статус: {response.status_code}")
                return False
    
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def main():
    """Запуск всех тестов"""
    
    test1 = await test_api_connection()
    test2 = await test_public_api()
    test3 = await test_card_api()
    
    print("\n" + "=" * 60)
    print("  РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    print(f"\n✅ API Wildberries (ваши товары): {'РАБОТАЕТ' if test1 else 'ОШИБКА'}")
    print(f"✅ Публичный API (поиск): {'РАБОТАЕТ' if test2 else 'ОШИБКА'}")
    print(f"✅ API карточек (детали): {'РАБОТАЕТ' if test3 else 'ОШИБКА'}")
    
    if test1 and test2 and test3:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Приложение готово к работе.")
        print("\n📌 Следующие шаги:")
        print("   1. Запустите приложение: python main.py")
        print("   2. Откройте документацию: http://localhost:8000/docs")
        print("   3. Добавьте ваши товары через API")
    else:
        print("\n⚠️  ЕСТЬ ПРОБЛЕМЫ. Проверьте:")
        if not test1:
            print("   - API ключ Wildberries (права доступа)")
        if not test2 or not test3:
            print("   - Подключение к интернету")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
