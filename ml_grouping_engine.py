"""
WB Price Optimizer V3.0 - ML Grouping Engine
Автоматическое обучение и группировка товаров
"""

import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict
from typing import List, Dict, Tuple
import pickle


class MLGroupingEngine:
    """
    Движок машинного обучения для автоматической группировки товаров-конкурентов
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 3),
            analyzer='char_wb',
            lowercase=True
        )
        self.category_patterns = {}
        self.trained = False
        self.similarity_threshold = 0.75  # Порог схожести 75%
        
    def extract_features(self, product: Dict) -> str:
        """
        Извлечение признаков из товара для векторизации
        """
        # Основные поля
        name = product.get('name', '').lower()
        category = product.get('category', '').lower()
        
        # Извлекаем ключевые характеристики из названия
        size = self._extract_size(name)
        material = self._extract_material(name)
        color = self._extract_color(name)
        type_info = self._extract_type(name)
        
        # Комбинируем все признаки
        features = f"{category} {type_info} {material} {size} {color} {name}"
        
        return features.strip()
    
    def _extract_size(self, text: str) -> str:
        """Извлечение размера из текста"""
        # Паттерны: 150х250, 150x250, 150*250, 150 х 250 см
        patterns = [
            r'(\d{2,4})\s*[xх*×]\s*(\d{2,4})',  # 150х250
            r'(\d{2,4})\s*см\s*[xх*×]\s*(\d{2,4})\s*см',  # 150 см х 250 см
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return f"{match.group(1)}x{match.group(2)}"
        
        return ""
    
    def _extract_material(self, text: str) -> str:
        """Извлечение материала из текста"""
        materials = [
            'блэкаут', 'blackout', 'блекаут',
            'канвас', 'canvas',
            'бархат', 'велюр',
            'лен', 'льняной',
            'хлопок', 'cotton',
            'полиэстер', 'polyester',
            'шелк', 'silk',
            'тюль', 'органза', 'вуаль',
            'жаккард',
            'однотон', 'однотонный',
            'алюминий', 'алюминиевый',
            'пластик', 'пластиковый',
            'металл', 'металлический',
            'дерево', 'деревянный',
            'ковка', 'кованый'
        ]
        
        text_lower = text.lower()
        found = []
        for material in materials:
            if material in text_lower:
                found.append(material)
        
        return ' '.join(found)
    
    def _extract_color(self, text: str) -> str:
        """Извлечение цвета из текста"""
        colors = [
            'белый', 'черный', 'серый', 'бежевый',
            'коричневый', 'синий', 'голубой', 'зеленый',
            'красный', 'розовый', 'желтый', 'оранжевый',
            'фиолетовый', 'золотой', 'серебряный',
            'бронзовый', 'медный'
        ]
        
        text_lower = text.lower()
        found = []
        for color in colors:
            if color in text_lower:
                found.append(color)
        
        return ' '.join(found)
    
    def _extract_type(self, text: str) -> str:
        """Извлечение типа товара из текста"""
        types = {
            'карнизы': ['карниз', 'штанга', 'труба'],
            'шторы': ['штор', 'занавес', 'портьер'],
            'тюль': ['тюль', 'вуаль', 'органза'],
            'рулонные': ['рулонн', 'рольштор', 'ролет'],
            'жалюзи': ['жалюзи', 'ламел'],
            'римские': ['римск'],
        }
        
        text_lower = text.lower()
        for type_name, keywords in types.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return type_name
        
        return ""
    
    def train_from_excel_data(self, products: List[Dict]) -> Dict:
        """
        Обучение на данных из Excel
        
        Args:
            products: Список товаров с полями:
                - nm_id, name, category, group_id, price
        
        Returns:
            Статистика обучения
        """
        print("🎓 Начало обучения на Excel данных...")
        
        # Группируем товары по group_id из Excel
        groups = defaultdict(list)
        for product in products:
            group_id = product.get('group_id') or product.get('ID склейки')
            if group_id and group_id != 'nan' and str(group_id).strip():
                groups[str(group_id)].append(product)
        
        # Извлекаем признаки для всех товаров
        all_features = []
        all_products = []
        
        for group_id, group_products in groups.items():
            if len(group_products) < 2:  # Группа должна содержать минимум 2 товара
                continue
            
            for product in group_products:
                features = self.extract_features(product)
                all_features.append(features)
                all_products.append(product)
        
        # Обучаем векторизатор
        if len(all_features) > 0:
            self.vectorizer.fit(all_features)
            self.trained = True
        
        # Анализируем паттерны категорий
        for group_id, group_products in groups.items():
            categories = set(p.get('category', '') for p in group_products if p.get('category'))
            materials = set()
            sizes = set()
            
            for product in group_products:
                name = product.get('name', '')
                materials.add(self._extract_material(name))
                sizes.add(self._extract_size(name))
            
            if categories:
                main_category = list(categories)[0]
                if main_category not in self.category_patterns:
                    self.category_patterns[main_category] = {
                        'materials': set(),
                        'sizes': set(),
                        'groups': []
                    }
                
                self.category_patterns[main_category]['materials'].update(
                    m for m in materials if m
                )
                self.category_patterns[main_category]['sizes'].update(
                    s for s in sizes if s
                )
                self.category_patterns[main_category]['groups'].append(group_id)
        
        stats = {
            'total_products': len(all_products),
            'total_groups': len(groups),
            'categories': len(self.category_patterns),
            'trained': self.trained,
            'avg_group_size': np.mean([len(g) for g in groups.values()]) if groups else 0
        }
        
        print(f"✅ Обучение завершено!")
        print(f"   - Товаров обработано: {stats['total_products']}")
        print(f"   - Групп найдено: {stats['total_groups']}")
        print(f"   - Категорий: {stats['categories']}")
        print(f"   - Средний размер группы: {stats['avg_group_size']:.1f}")
        
        return stats
    
    def find_similar_products(self, target_product: Dict, candidate_products: List[Dict], 
                             top_k: int = 20) -> List[Tuple[Dict, float]]:
        """
        Находит похожие товары для целевого товара
        
        Args:
            target_product: Целевой товар
            candidate_products: Список товаров-кандидатов
            top_k: Количество топ результатов
        
        Returns:
            Список кортежей (товар, схожесть)
        """
        if not self.trained:
            raise ValueError("Модель не обучена! Вызовите train_from_excel_data() сначала")
        
        # Извлекаем признаки целевого товара
        target_features = self.extract_features(target_product)
        target_vector = self.vectorizer.transform([target_features])
        
        # Фильтруем кандидатов по категории
        target_category = target_product.get('category', '')
        filtered_candidates = [
            p for p in candidate_products 
            if p.get('category', '') == target_category
            and p.get('nm_id') != target_product.get('nm_id')
        ]
        
        if not filtered_candidates:
            return []
        
        # Векторизуем кандидатов
        candidate_features = [self.extract_features(p) for p in filtered_candidates]
        candidate_vectors = self.vectorizer.transform(candidate_features)
        
        # Вычисляем схожесть
        similarities = cosine_similarity(target_vector, candidate_vectors)[0]
        
        # Дополнительные правила схожести
        adjusted_similarities = []
        for i, (product, sim) in enumerate(zip(filtered_candidates, similarities)):
            adjusted_sim = sim
            
            # Бонус за схожий размер
            target_size = self._extract_size(target_product.get('name', ''))
            candidate_size = self._extract_size(product.get('name', ''))
            if target_size and candidate_size and target_size == candidate_size:
                adjusted_sim += 0.1
            
            # Бонус за схожий материал
            target_material = self._extract_material(target_product.get('name', ''))
            candidate_material = self._extract_material(product.get('name', ''))
            if target_material and candidate_material:
                common_materials = set(target_material.split()) & set(candidate_material.split())
                if common_materials:
                    adjusted_sim += 0.15
            
            # Штраф за сильное отличие в цене (>2x разница)
            target_price = target_product.get('price', 0) or target_product.get('current_price', 0)
            candidate_price = product.get('price', 0) or product.get('current_price', 0)
            
            if target_price > 0 and candidate_price > 0:
                price_ratio = max(target_price, candidate_price) / min(target_price, candidate_price)
                if price_ratio > 2.0:
                    adjusted_sim *= 0.7
            
            adjusted_similarities.append(adjusted_sim)
        
        # Сортируем по схожести
        similarities_array = np.array(adjusted_similarities)
        top_indices = np.argsort(similarities_array)[::-1][:top_k]
        
        # Фильтруем по порогу схожести
        results = []
        for idx in top_indices:
            if similarities_array[idx] >= self.similarity_threshold:
                results.append((filtered_candidates[idx], float(similarities_array[idx])))
        
        return results
    
    def auto_group_new_product(self, new_product: Dict, existing_products: List[Dict]) -> Dict:
        """
        Автоматически определяет группу для нового товара
        
        Args:
            new_product: Новый товар из WB API
            existing_products: Существующие товары в базе
        
        Returns:
            Результат группировки с конкурентами
        """
        similar = self.find_similar_products(new_product, existing_products, top_k=20)
        
        return {
            'product': new_product,
            'competitors': [
                {
                    'nm_id': p.get('nm_id'),
                    'name': p.get('name'),
                    'price': p.get('price') or p.get('current_price'),
                    'category': p.get('category'),
                    'similarity': sim,
                    'confidence': 'high' if sim >= 0.85 else 'medium' if sim >= 0.75 else 'low'
                }
                for p, sim in similar
            ],
            'total_competitors': len(similar),
            'avg_similarity': np.mean([sim for _, sim in similar]) if similar else 0.0
        }
    
    def save_model(self, filepath: str):
        """Сохранение обученной модели"""
        model_data = {
            'vectorizer': self.vectorizer,
            'category_patterns': {
                k: {
                    'materials': list(v['materials']),
                    'sizes': list(v['sizes']),
                    'groups': v['groups']
                }
                for k, v in self.category_patterns.items()
            },
            'trained': self.trained,
            'similarity_threshold': self.similarity_threshold
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"💾 Модель сохранена: {filepath}")
    
    def load_model(self, filepath: str):
        """Загрузка обученной модели"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.vectorizer = model_data['vectorizer']
        self.category_patterns = {
            k: {
                'materials': set(v['materials']),
                'sizes': set(v['sizes']),
                'groups': v['groups']
            }
            for k, v in model_data['category_patterns'].items()
        }
        self.trained = model_data['trained']
        self.similarity_threshold = model_data.get('similarity_threshold', 0.75)
        
        print(f"📂 Модель загружена: {filepath}")


def demo_training():
    """Демонстрация обучения модели"""
    # Пример данных из Excel
    excel_products = [
        {'nm_id': '123', 'name': 'Шторы блэкаут 2 шт 150х250 см', 'category': 'Портьеры', 'group_id': 'G001', 'price': 1500},
        {'nm_id': '124', 'name': 'Портьеры блэкаут 150x250', 'category': 'Портьеры', 'group_id': 'G001', 'price': 1600},
        {'nm_id': '125', 'name': 'Занавески blackout 150*250 см', 'category': 'Портьеры', 'group_id': 'G001', 'price': 1450},
        
        {'nm_id': '201', 'name': 'Шторы однотон 2 шт 150х250 см', 'category': 'Портьеры', 'group_id': 'G002', 'price': 850},
        {'nm_id': '202', 'name': 'Портьеры однотонные 150x250', 'category': 'Портьеры', 'group_id': 'G002', 'price': 900},
        
        {'nm_id': '301', 'name': 'Карниз алюминиевый 200 см', 'category': 'Карнизы', 'group_id': 'G003', 'price': 1200},
        {'nm_id': '302', 'name': 'Штанга алюминий 2 метра', 'category': 'Карнизы', 'group_id': 'G003', 'price': 1150},
    ]
    
    # Обучение
    engine = MLGroupingEngine()
    stats = engine.train_from_excel_data(excel_products)
    
    # Тест: новый товар
    new_product = {
        'nm_id': '999',
        'name': 'Шторы блэкаут 150х250 см комплект',
        'category': 'Портьеры',
        'price': 1550
    }
    
    result = engine.auto_group_new_product(new_product, excel_products)
    
    print("\n" + "="*60)
    print(f"🆕 Новый товар: {new_product['name']}")
    print(f"✅ Найдено конкурентов: {result['total_competitors']}")
    print(f"📊 Средняя схожесть: {result['avg_similarity']:.2%}")
    print("\nТОП конкуренты:")
    for comp in result['competitors'][:5]:
        print(f"  - {comp['name']} | Схожесть: {comp['similarity']:.2%} | {comp['confidence'].upper()}")
    
    return engine


if __name__ == '__main__':
    demo_training()
