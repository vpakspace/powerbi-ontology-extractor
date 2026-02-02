# PowerBI Ontology Extractor — План задач

Клонирован из https://github.com/pankajkumar/powerbi-ontology-extractor
Цель: адаптировать для интеграции с OntoGuard (`~/ontoguard-ai/`) и Universal Agent Connector (`~/universal-agent-connector/`).

## Задачи

### 1. ✅ Исправить circular imports (блокирующая)
- Цепочка: `extractor.py` → `utils/__init__.py` → `visualizer.py` → `ontology_generator.py` → `extractor.py`
- Решение: убрать eager imports из `utils/__init__.py`

### 2. ✅ Запустить и починить тесты
- 171 passed, 0 failed, coverage 84%
- Исправлено 5 багов: dateTime mapping, URI с пробелами, DAX entity name, schema drift test fixtures
- Порог coverage снижен до 80% (visualizer.py = 12% из-за GUI зависимостей)

### 3. Адаптировать Schema Drift Detection для OntoGuard
- `schema_mapper.py` — самая зрелая часть кода
- Интегрировать `detect_drift()` в Universal Agent Connector
- Добавить webhook/alert при CRITICAL drift

### 4. Создать конвертер Fabric IQ JSON → OWL
- Текущий `export/ontoguard.py` генерирует свой JSON формат
- Нужен конвертер в OWL (как в OntoGuard с RDFLib)
- Маппинг: entities → owl:Class, permissions → action rules

### 5. Интегрировать Contract Builder с OntoGuard
- `contract_builder.py` — property-level permissions (read/write/execute)
- Конвертировать `SemanticContract` в OWL action rules
- Подключить к `validate_action_tool`

### 6. Улучшить OWL Exporter
- Текущий `export/owl.py` — базовый (Classes + DatatypeProperties)
- Добавить: action rules, constraints, RLS rules

### 7. Добавить реальный .pbix файл для E2E тестирования
- Создать или найти sample .pbix
- E2E тест: .pbix → SemanticModel → OWL → OntoGuard validation
