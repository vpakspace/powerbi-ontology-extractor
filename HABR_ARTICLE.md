# Как мы извлекаем скрытые онтологии из 20 миллионов Power BI дашбордов и делаем их доступными для AI-агентов

> **TL;DR**: Мы создали open-source инструмент, который автоматически извлекает семантические модели из .pbix файлов Power BI и превращает их в формальные OWL-онтологии. Это позволяет AI-агентам безопасно работать с корпоративными данными, понимая бизнес-правила, связи и ограничения доступа. `pip install powerbi-ontology-extractor` — и через 10 минут у вас есть онтология.

---

## Проблема: $4.6M из-за переименованной колонки

В 2024 году крупная логистическая компания потеряла $4.6M за одну ночь. Причина оказалась до абсурдного простой: администратор базы данных переименовал колонку `Warehouse_Location` в `FacilityID`. AI-агент, управлявший маршрутизацией, не знал о переименовании и начал отправлять грузы по случайным адресам.

Этот случай — не исключение, а симптом системной проблемы. В мире существует **более 20 миллионов** Power BI дашбордов (данные Microsoft, 2024). Каждый из них содержит семантическую модель — таблицы, связи, меры, правила безопасности. По сути, каждый Power BI дашборд — это **неформальная онтология**, заточенная внутри проприетарного .pbix файла.

AI-агенты не умеют читать .pbix файлы. Они не знают, что `Revenue` в отделе продаж и `Revenue` в финансовом отделе — это разные метрики с разными формулами. Они не понимают, что аналитик имеет право только на чтение, а удалять записи может только администратор. Без этих знаний AI-агент — это слепой робот с доступом к продакшн-базе.

### Масштаб проблемы

| Метрика | Значение |
|---------|----------|
| Power BI дашбордов в мире | 20+ млн |
| Средняя стоимость ручного создания онтологии | $50K–$200K |
| Процент онтологии, который можно извлечь автоматически | ~70% |
| Процент, требующий ручной работы бизнес-аналитика | ~30% |

Ручное создание онтологий — это месяцы работы дорогих специалистов. При этом 70% работы — механическое извлечение того, что уже описано в Power BI: таблицы превращаются в сущности, колонки — в свойства, foreign keys — в связи, DAX-формулы — в бизнес-правила.

---

## Решение: 30 минут вместо 3 месяцев

Мы создали **PowerBI Ontology Extractor** — open-source Python-инструмент, который автоматизирует эти 70% и даёт визуальный редактор для оставшихся 30%.

Архитектура решения:

```
Power BI (.pbix)  →  Ontology Extractor  →  OntoGuard  →  AI Agent
     10 мин              10 мин             5 мин          5 мин
```

Что происходит на каждом этапе:

1. **Extraction** (10 мин): Бинарный .pbix файл распаковывается, парсится DataModel (через PBIXRay), извлекаются таблицы, колонки, типы данных, связи, DAX-меры, RLS-правила
2. **Generation** (10 мин): Сырые данные превращаются в формальную онтологию — классы, свойства, связи с кардинальностью, бизнес-правила из DAX, ограничения
3. **Validation** (5 мин): Онтология проходит через OntoGuard (семантический файрвол), который проверяет role-based access control по OWL-правилам
4. **Deployment** (5 мин): AI-агент получает онтологию как контракт — и теперь знает, что может делать, а что нет

### Установка

```bash
pip install powerbi-ontology-extractor
```

Всё. Ни Docker, ни конфигурации серверов, ни платных API (кроме опционального OpenAI для чата). Одна команда — и у вас есть CLI, Python API и Streamlit UI.

### Идейная основа

PowerBI Ontology Extractor переводит семантическую модель Power BI в явный онтологический артефакт — то, что можно запрашивать, валидировать, версионировать и использовать как «семантический контракт» для AI-агентов. Отправная идея здесь — линия статей [Pankaj Kumar](#ссылки): в корпоративном масштабе BI-модели фактически являются неформальными онтологиями, которые можно формализовать и превратить в инфраструктурный актив.

Практическая ценность — в надёжности. Когда смысл вынесен наружу, становятся возможны проверки «по смыслу», а не только «по схеме»: например, контроль бизнес-логики и более безопасные изменения модели при дрейфе полей и имён. Это хорошо стыкуется с идеями Kumar про семантическую валидацию ([OntoGuard](https://github.com/vpakspace/ontoguard-ai)) и прод-инфраструктуру для агентов на стыке MCP и онтологий ([Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector)).

---

## Что под капотом

### Парсинг .pbix файлов

Power BI хранит данные в бинарном формате. Мы используем библиотеку [PBIXRay](https://github.com/pankajkumar/pbixray) для чтения DataModel, а затем извлекаем:

```python
from powerbi_ontology import PowerBIExtractor

extractor = PowerBIExtractor("sales_dashboard.pbix")
model = extractor.extract()

print(f"Таблицы: {len(model.entities)}")
print(f"Связи:   {len(model.relationships)}")
print(f"Меры:    {len(model.measures)}")
print(f"RLS:     {len(model.rls_rules)}")
```

Для реального файла Sales_Returns_Sample.pbix от Microsoft это даёт:

```
Таблицы: 15
Связи:   9
Меры:    58
RLS:     0
```

Каждая таблица становится `Entity` с типизированными свойствами, каждая связь — `Relationship` с кардинальностью (one-to-many, many-to-many) и направлением кросс-фильтрации.

### DAX → Бизнес-правила

Самая интересная часть — автоматический парсинг DAX-формул. DAX — это язык запросов Power BI, в котором закодирована бизнес-логика:

```dax
Total Revenue = SUMX(Sales, Sales[Quantity] * Sales[Unit Price])

Revenue YoY% =
DIVIDE(
    [Total Revenue] - CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Date'[Date])),
    CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Date'[Date]))
)
```

Наш DAX-парсер распознаёт:
- **Агрегации**: SUM, AVERAGE, COUNT, SUMX — превращаются в правила вычислений
- **Условную логику**: IF, SWITCH, CALCULATE с фильтрами — превращаются в бизнес-правила
- **Time Intelligence**: SAMEPERIODLASTYEAR, DATEADD — помечаются как временные метрики
- **Зависимости**: Какие таблицы и колонки использует каждая мера

Это критически важно: AI-агент, который знает формулу Revenue, не станет суммировать колонку `Price` напрямую — он будет использовать правильную метрику.

### Генерация OWL-онтологии

Извлечённая модель трансформируется в формальную OWL-онтологию:

```python
from powerbi_ontology import OntologyGenerator
from powerbi_ontology.export.owl import OWLExporter

# Генерируем онтологию
ontology = OntologyGenerator(model).generate()

# Экспортируем в OWL
exporter = OWLExporter(
    ontology,
    default_roles=["Admin", "Analyst", "Viewer"]
)
exporter.save("sales_ontology.owl")

summary = exporter.get_export_summary()
print(f"OWL классы:     {summary['classes']}")
print(f"Свойства:       {summary['datatype_properties']}")
print(f"Action Rules:   {summary['action_rules']}")
```

OWL-файл содержит:
- **owl:Class** для каждой сущности (Customer, Sales, Product)
- **owl:DatatypeProperty** для каждого свойства с типами XSD
- **owl:ObjectProperty** для связей между сущностями
- **Action Rules** — кто (роль) что (create/read/update/delete) может делать с какой сущностью
- **Бизнес-правила** из DAX-мер (в формате OWL-аннотаций)
- **Ограничения** (required, unique, range, enum)

Для Sales_Returns_Sample это генерирует **1,734 RDF-триплета** — полное формальное описание семантики дашборда.

---

## В чём новизна

### 1. Автоматическое извлечение, а не ручное создание

Существующие инструменты (Protege, WebVOWL, TopBraid) предполагают, что вы **вручную** создаёте онтологию. Это дорого ($50K+) и долго (месяцы). Мы извлекаем 70% онтологии **автоматически** из того, что уже существует в Power BI.

### 2. DAX → Бизнес-правила (не просто схема)

Инструменты типа `pbi-tools` или `Tabular Editor` умеют экспортировать схему Power BI. Но схема — это не онтология. Мы идём дальше: парсим DAX-формулы и превращаем их в семантические бизнес-правила. AI-агент получает не просто "таблица Sales с колонкой Revenue", а "Revenue вычисляется как SUMX(Sales, Quantity * UnitPrice) и доступна ролям Admin и Analyst для чтения".

### 3. Мост между BI и AI

Power BI — инструмент для людей. OWL — стандарт для машин. Наш экстрактор — это мост: человек работает в привычном Power BI, а AI-агент получает формальную онтологию с правилами доступа.

### 4. Schema Drift Detection

Помните историю с $4.6M? Мы решаем эту проблему через Schema Drift Detection:

```python
from powerbi_ontology import SchemaMapper

mapper = SchemaMapper()
# Привязка онтологии к реальной схеме БД
drift = mapper.check_drift(ontology, actual_schema)

for issue in drift:
    print(f"[{issue.severity}] {issue.entity}: {issue.description}")
    # [CRITICAL] Sales: Column 'Warehouse_Location' not found (renamed to 'FacilityID'?)
```

Система нормализует типы (`varchar(255)` → `text`, `int` → `integer`), обнаруживает переименования через similarity matching (>70% совпадения), и классифицирует проблемы по severity: CRITICAL блокирует агента, WARNING логирует, INFO информирует.

### 5. Semantic Debt Analysis

Когда в организации 50+ дашбордов, неизбежно возникает "семантический долг" — одна и та же метрика определена по-разному в разных дашбордах:

```python
from powerbi_ontology import analyze_ontologies

report = analyze_ontologies([
    "sales_ontology.json",
    "finance_ontology.json",
    "marketing_ontology.json"
])

for conflict in report.conflicts:
    print(f"Конфликт: {conflict.entity}.{conflict.property}")
    print(f"  Dashboard A: {conflict.definition_a}")
    print(f"  Dashboard B: {conflict.definition_b}")
    # Конфликт: Revenue
    #   Sales dashboard: SUMX(Sales, Quantity * UnitPrice)
    #   Finance dashboard: SUM(Invoices[Amount]) - SUM(Refunds[Amount])
```

Это позволяет обнаружить конфликты **до** того, как AI-агент начнёт использовать противоречивые данные.

---

## Как пользоваться

### Вариант 1: Python API (для разработчиков)

```bash
pip install powerbi-ontology-extractor
```

```python
from powerbi_ontology import PowerBIExtractor, OntologyGenerator
from powerbi_ontology.export.owl import OWLExporter

# 1. Извлекаем модель из .pbix
extractor = PowerBIExtractor("my_dashboard.pbix")
model = extractor.extract()

# 2. Генерируем онтологию
ontology = OntologyGenerator(model).generate()

# 3. Экспортируем
# В OWL (для OntoGuard / triple stores)
OWLExporter(ontology).save("ontology.owl")

# В JSON (для API / AI-агентов)
import json
with open("ontology.json", "w") as f:
    json.dump(ontology.to_dict(), f, indent=2)
```

### Вариант 2: CLI (для DevOps и автоматизации)

```bash
# Извлечь один файл
pbix2owl extract -i dashboard.pbix -o ontology.owl

# Пакетная обработка директории (8 параллельных воркеров)
pbix2owl batch -i ./dashboards/ -o ./ontologies/ -w 8 --recursive

# Анализ семантического долга
pbix2owl analyze -i ./ontologies/ -o report.md

# Сравнение версий
pbix2owl diff -s v1.json -t v2.json -o changelog.md
```

### Вариант 3: Streamlit UI (для бизнес-аналитиков)

```bash
pip install powerbi-ontology-extractor streamlit
streamlit run ontology_editor.py --server.port 8503
```

Визуальный редактор с 8 вкладками:

| Вкладка | Что делает |
|---------|------------|
| Load/Create | Загрузка .pbix или создание с нуля |
| Entities | Редактирование сущностей и свойств |
| Relationships | Управление связями |
| Permissions | RBAC-матрица (роль × сущность × действие) |
| Business Rules | Бизнес-правила с классификацией |
| OWL Preview | Предпросмотр и экспорт OWL |
| Diff & Merge | Сравнение и слияние версий |
| AI Chat | Вопросы об онтологии на естественном языке |

Аналитик может загрузить .pbix файл, отредактировать автоматически извлечённую онтологию (те самые 30%), задать вопрос AI ("Какие сущности связаны с Customer?") и экспортировать результат — всё без единой строки кода.

### Вариант 4: MCP Server (для Claude Code)

PowerBI Ontology Extractor работает как MCP-сервер, который можно подключить к Claude Code:

```json
// ~/.claude.json
{
  "mcpServers": {
    "powerbi-ontology": {
      "command": "python",
      "args": ["-m", "powerbi_ontology.mcp_server"]
    }
  }
}
```

После этого в Claude Code доступны 8 инструментов: `pbix_extract`, `ontology_generate`, `export_owl`, `export_json`, `analyze_debt`, `ontology_diff`, `ontology_merge`, `ontology_chat_ask`.

Можно просто сказать Claude: *"Извлеки онтологию из sales.pbix и экспортируй в OWL"* — и он это сделает.

---

## Интеграция с экосистемой

PowerBI Ontology Extractor — это первый элемент в цепочке безопасной работы AI-агентов с данными:

```
┌──────────────────────┐     ┌──────────────────────┐     ┌────────────────────────────┐
│  Ontology Extractor  │────▶│      OntoGuard       │────▶│ Universal Agent Connector  │
│  (этот проект)       │     │  Semantic Firewall   │     │    MCP Infrastructure     │
│  Извлечение          │     │  Валидация           │     │    Подключение агентов     │
└──────────────────────┘     └──────────────────────┘     └────────────────────────────┘
```

- **[OntoGuard](https://github.com/vpakspace/ontoguard-ai)** — семантический файрвол. Принимает OWL-онтологию, извлечённую нашим экстрактором, и проверяет каждое действие AI-агента: "Может ли роль Analyst удалить запись в таблице Patients?" Если OWL-правило запрещает — действие блокируется ещё до обращения к БД.

- **[Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector)** — MCP-инфраструктура для подключения AI-агентов к базам данных. Использует OntoGuard как middleware: NL-запрос → SQL → проверка OntoGuard → выполнение.

Вместе они реализуют **семантический контракт**: AI-агент получает не просто доступ к данным, а доступ с пониманием того, что эти данные значат, как они связаны и что с ними можно делать.

---

## Тестирование и безопасность

### 370 тестов, 81% покрытие

```bash
$ pytest
========================= 370 passed in 4.56s =========================
```

Мы тестируем на реальных .pbix файлах от Microsoft (Sales_Returns_Sample, Adventure_Works_DW_2020), а не на синтетических данных.

### Security Hardening (v0.1.1)

В версии 0.1.1 исправлены 14 security issues, обнаруженных при code review:

| Severity | Кол-во | Примеры |
|----------|--------|---------|
| CRITICAL | 3 | Path traversal при записи файлов, XSS в чате, unsafe YAML |
| HIGH | 2 | Валидация API-ключа, ограничение размера upload (50 MB) |
| MEDIUM | 4 | Audit logging, hardening DAX-парсера, ограничение истории чата |
| LOW | 5 | Type hints, детерминистичное хеширование, rate limiting |

Все мутирующие операции (загрузка файлов, экспорт, редактирование) логируются в `data/audit.log`.

---

## Об авторстве и Roadmap

Фреймворк сильно переработан архитектурно относительно оригинальной концепции Kumar, но названия сущностей и смысловых блоков я осознанно оставил «как у автора» — чтобы читателю было проще сопоставлять с первоисточниками и не терять нить контекста.

Проект активно развивается. Ближайшие шаги:

- **Извлечение более богатых ограничений** — в духе SHACL-валидаций, чтобы выразить не только типы, но и бизнес-инварианты (диапазоны, зависимости между полями)
- **Анализ влияния изменений** — diff между версиями моделей с оценкой того, какие агенты и пайплайны затронуты
- **Стандартизация упаковки онтологий** — для рантаймов агентных систем (MCP-совместимый формат, версионирование артефактов)
- **v0.2.0**: Поддержка Power BI Semantic Link (прямое подключение к Fabric)
- **v0.3.0**: Автоматическая генерация Semantic Contract с property-level permissions
- **v1.0.0**: Production-ready с CI/CD, Docker image, Helm chart

---

## Попробовать прямо сейчас

```bash
# Установка
pip install powerbi-ontology-extractor

# CLI
pbix2owl extract -i your_dashboard.pbix -o ontology.owl

# Или визуальный редактор
pip install streamlit
streamlit run ontology_editor.py
```

- **PyPI**: [powerbi-ontology-extractor](https://pypi.org/project/powerbi-ontology-extractor/)
- **GitHub**: [vpakspace/powerbi-ontology-extractor](https://github.com/vpakspace/powerbi-ontology-extractor)
- **Релиз**: [v0.1.1](https://github.com/vpakspace/powerbi-ontology-extractor/releases/tag/v0.1.1)
- **Лицензия**: MIT

---

*Если проект полезен — поставьте звезду на GitHub. Если есть вопросы или идеи — открывайте Issues, мы отвечаем.*

---

## Ссылки

### Серия статей Pankaj Kumar (идейная основа)

1. [Microsoft vs Palantir: Two Paths to Enterprise Ontology](https://medium.com/@cloudpankaj/microsoft-vs-palantir-two-paths-to-enterprise-ontology-and-why-microsofts-bet-on-semantic-6e72265dce21)
2. [The Power BI Ontology Paradox](https://medium.com/@cloudpankaj/the-power-bi-ontology-paradox-how-20-million-dashboards-became-microsofts-secret-weapon-for-5585e7d18c01)
3. [From Power BI Dashboard to AI Agent in 30 Minutes](https://medium.com/@cloudpankaj/from-power-bi-dashboard-to-ai-agent-in-30-minutes-i-built-the-tool-that-unlocks-20-million-hidden-500e59bd91df)
4. [Universal Agent Connector: MCP + Ontology](https://medium.com/@cloudpankaj/universal-agent-connector-mcp-ontology-production-ready-ai-infrastructure-0b4e35f22942)
5. [OntoGuard: Ontology Firewall for AI Agents](https://medium.com/@cloudpankaj/ontoguard-i-built-an-ontology-firewall-for-ai-agents-in-48-hours-using-cursor-ai-be4208c405e7)

### Проекты

- [PowerBI Ontology Extractor](https://github.com/vpakspace/powerbi-ontology-extractor) — этот проект
- [OntoGuard AI](https://github.com/vpakspace/ontoguard-ai) — семантический файрвол для AI-агентов
- [Universal Agent Connector](https://github.com/vpakspace/universal-agent-connector) — MCP-инфраструктура для подключения агентов к БД
