"""
Скрипт обучения ML модели на Excel данных
Запускается ОДИН РАЗ для создания обученной модели
"""

import pandas as pd
import json
import sys
from pathlib import Path
from ml_grouping_engine import MLGroupingEngine


def load_excel_data(file_path: str, max_rows: int = None):
    """Загрузка данных из Excel"""
    print(f"📂 Загрузка: {file_path}")
    
    try:
        # Читаем основной лист
        df = pd.read_excel(file_path, nrows=max_rows)
        
        # Стандартизация названий колонок
        df.columns = df.columns.str.strip()
        
        # Ищем нужные колонки
        name_col = None
        price_col = None
        category_col = None
        group_col = None
        sku_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'название' in col_lower or 'name' in col_lower:
                name_col = col
            elif 'цена' in col_lower or 'price' in col_lower:
                price_col = col
            elif ('категор' in col_lower or 'category' in col_lower) and 'тип карниза крупно' not in col_lower:
                if not category_col:
                    category_col = col
            elif 'склейки' in col_lower or 'group' in col_lower:
                group_col = col
            elif 'sku' in col_lower or 'артикул' in col_lower or 'nm_id' in col_lower or 'nm id' in col_lower:
                sku_col = col
        
        # Если не нашли группу, ищем "Тип карниза/аналог" или похожие
        if not group_col:
            for col in df.columns:
                if 'тип' in col.lower() and 'аналог' in col.lower():
                    group_col = col
                    break
        
        print(f"   Найдены колонки:")
        print(f"   - SKU: {sku_col}")
        print(f"   - Название: {name_col}")
        print(f"   - Цена: {price_col}")
        print(f"   - Категория: {category_col}")
        print(f"   - Группа: {group_col}")
        
        # Создаем структурированные данные
        products = []
        for idx, row in df.iterrows():
            try:
                product = {
                    'nm_id': str(row[sku_col]) if sku_col and pd.notna(row[sku_col]) else f"item_{idx}",
                    'name': str(row[name_col]) if name_col and pd.notna(row[name_col]) else '',
                    'price': float(row[price_col]) if price_col and pd.notna(row[price_col]) else 0,
                    'category': str(row[category_col]) if category_col and pd.notna(row[category_col]) else 'Unknown',
                    'group_id': str(row[group_col]) if group_col and pd.notna(row[group_col]) else None,
                }
                
                # Фильтруем пустые записи
                if product['name'] and product['group_id'] and product['group_id'] != 'nan':
                    products.append(product)
            except Exception as e:
                continue
        
        print(f"   ✅ Загружено товаров: {len(products)}")
        return products
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return []


def main():
    """Основная функция обучения"""
    print("="*70)
    print("🎓 ОБУЧЕНИЕ ML МОДЕЛИ НА EXCEL ДАННЫХ")
    print("="*70)
    print()
    
    # Файлы Excel
    excel_files = [
        'WB_Карнизы_24.11-07.12.25.xlsx',
        'WB_Портьеры_24.11-07.12.25.xlsx',
        'WB_РШ_24.11-07.12.25.xlsx'
    ]
    
    # Проверяем наличие файлов
    available_files = [f for f in excel_files if Path(f).exists()]
    
    if not available_files:
        print("❌ Excel файлы не найдены!")
        print("   Положите файлы в текущую папку:")
        for f in excel_files:
            print(f"   - {f}")
        print()
        print("Или укажите путь к папке с файлами:")
        folder = input("Путь к папке (Enter для текущей): ").strip()
        if folder:
            available_files = [str(Path(folder) / f) for f in excel_files if (Path(folder) / f).exists()]
    
    if not available_files:
        print("❌ Не найдено файлов для обучения!")
        sys.exit(1)
    
    print(f"📁 Найдено файлов: {len(available_files)}")
    print()
    
    # Спрашиваем про количество строк
    print("❓ Сколько строк загрузить из каждого файла?")
    print("   1. Все строки (может занять 5-10 минут)")
    print("   2. Первые 10,000 строк (быстро, ~1 минута)")
    print("   3. Первые 1,000 строк (для теста)")
    
    choice = input("Выбор (1/2/3): ").strip()
    
    max_rows = None
    if choice == '2':
        max_rows = 10000
    elif choice == '3':
        max_rows = 1000
    
    print()
    
    # Загружаем данные из всех файлов
    all_products = []
    
    for file_path in available_files:
        products = load_excel_data(file_path, max_rows=max_rows)
        all_products.extend(products)
        print()
    
    print(f"📊 Всего загружено товаров: {len(all_products)}")
    print()
    
    if len(all_products) == 0:
        print("❌ Нет данных для обучения!")
        sys.exit(1)
    
    # Создаем и обучаем ML движок
    print("🤖 Создание ML движка...")
    engine = MLGroupingEngine()
    
    print()
    stats = engine.train_from_excel_data(all_products)
    print()
    
    # Сохраняем модель
    model_path = 'ml_model.pkl'
    engine.save_model(model_path)
    print()
    
    # Сохраняем статистику
    stats_data = {
        'training_stats': stats,
        'source_files': available_files,
        'max_rows_per_file': max_rows,
        'total_products_loaded': len(all_products),
        'model_path': model_path
    }
    
    with open('ml_training_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)
    
    print("📊 Статистика сохранена: ml_training_stats.json")
    print()
    
    # Демонстрация
    print("="*70)
    print("🧪 ТЕСТИРОВАНИЕ МОДЕЛИ")
    print("="*70)
    print()
    
    if len(all_products) > 0:
        # Берем случайный товар для теста
        import random
        test_product = random.choice(all_products)
        
        print(f"🎯 Тестовый товар:")
        print(f"   Название: {test_product['name']}")
        print(f"   Категория: {test_product['category']}")
        print(f"   Цена: {test_product['price']}₽")
        print()
        
        result = engine.auto_group_new_product(test_product, all_products)
        
        print(f"✅ Найдено конкурентов: {result['total_competitors']}")
        print(f"📊 Средняя схожесть: {result['avg_similarity']:.1%}")
        print()
        
        if result['competitors']:
            print("ТОП-5 конкурентов:")
            for i, comp in enumerate(result['competitors'][:5], 1):
                print(f"   {i}. {comp['name'][:60]}")
                print(f"      Схожесть: {comp['similarity']:.1%} | Уверенность: {comp['confidence'].upper()}")
                print()
    
    print("="*70)
    print("✅ ОБУЧЕНИЕ ЗАВЕРШЕНО!")
    print("="*70)
    print()
    print(f"📦 Файлы для использования в приложении:")
    print(f"   1. {model_path} - Обученная ML модель")
    print(f"   2. ml_training_stats.json - Статистика обучения")
    print()
    print("🚀 Скопируйте эти файлы в репозиторий вместе с main.py")
    print()


if __name__ == '__main__':
    main()
