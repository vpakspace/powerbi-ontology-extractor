# PowerBI Ontology Extractor — Руководство пользователя

Инструмент для извлечения семантических моделей из Power BI и генерации OWL-онтологий.

---

## Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Установка MCP сервера](#установка-mcp-сервера)
3. [Способы использования](#способы-использования)
4. [Streamlit UI](#streamlit-ui)
5. [MCP Tools (Claude Code)](#mcp-tools-claude-code)
6. [Примеры использования](#примеры-использования)
7. [Форматы файлов](#форматы-файлов)
8. [FAQ](#faq)

---

## Быстрый старт

### Требования

- Python 3.10+
- Streamlit (для веб-интерфейса)
- Claude Code 2.0+ (для MCP интеграции)
- OpenAI API key (для AI-чата, опционально)

### Установка

**Вариант 1: Через PyPI (рекомендуется)**

```bash
pip install powerbi-ontology-extractor
```

**Вариант 2: Из исходников**

```bash
git clone https://github.com/vpakspace/powerbi-ontology-extractor.git
cd powerbi-ontology-extractor
pip install -e .
```

---

## Установка MCP сервера

MCP (Model Context Protocol) позволяет использовать инструменты напрямую в Claude Code.

### Шаг 1: Установка пакета

```bash
# Вариант 1: Через PyPI (рекомендуется)
pip install powerbi-ontology-extractor

# Вариант 2: Из исходников
git clone https://github.com/vpakspace/powerbi-ontology-extractor.git
cd powerbi-ontology-extractor
pip install -e .
```

### Шаг 2: Настройка Claude Code

Откройте файл `~/.claude.json` в текстовом редакторе:

```bash
# Linux/macOS
nano ~/.claude.json

# Или через код
code ~/.claude.json
```

Добавьте секцию `powerbi-ontology` в `mcpServers`:

```json
{
  "mcpServers": {
    "powerbi-ontology": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "powerbi_ontology.mcp_server"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

**Примечание:** Если у вас уже есть другие MCP серверы, просто добавьте `"powerbi-ontology": {...}` внутрь существующего `mcpServers`.

**Пример с несколькими серверами:**

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "powerbi-ontology": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "powerbi_ontology.mcp_server"],
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}"
      }
    }
  }
}
```

### Шаг 3: Перезапуск Claude Code

```bash
# Закройте текущую сессию
exit

# Запустите снова
claude
```

### Шаг 4: Проверка работы

В Claude Code выполните:

```
Проверь что powerbi-ontology MCP работает
```

Или используйте любой из tools:

```
Сгенерируй тестовую онтологию с таблицами Sales и Products
```

### Альтернатива: Ручная регистрация через CLI

```bash
claude mcp add powerbi-ontology -s user -- python -m powerbi_ontology.mcp_server
```

### Настройка OpenAI API (для AI-чата)

Если вы хотите использовать `ontology_chat_ask`:

```bash
# Добавьте в ~/.bashrc или ~/.zshrc
export OPENAI_API_KEY="sk-your-api-key-here"
```

Или добавьте в `~/.claude.json`:

```json
{
  "mcpServers": {
    "powerbi-ontology": {
      "env": {
        "OPENAI_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

### Проверка статуса MCP серверов

```bash
claude mcp list
```

Должен отобразиться `powerbi-ontology` в списке активных серверов.

### Troubleshooting

**Проблема: MCP сервер не подключается**

1. Проверьте путь в `cwd`:
   ```bash
   ls /path/to/powerbi-ontology-extractor/powerbi_ontology/mcp_server.py
   ```

2. Проверьте установку пакета:
   ```bash
   python -c "from powerbi_ontology import mcp_server; print('OK')"
   ```

3. Проверьте логи:
   ```bash
   python -m powerbi_ontology.mcp_server
   # Должен запуститься без ошибок
   ```

**Проблема: Tools не отображаются**

Перезапустите Claude Code и подождите 10-15 секунд для инициализации MCP серверов.

**Проблема: ontology_chat_ask не работает**

Убедитесь, что `OPENAI_API_KEY` установлен корректно:
```bash
echo $OPENAI_API_KEY
```

### Запуск веб-интерфейса

```bash
streamlit run ontology_editor.py
```

Откроется браузер на `http://localhost:8501`

---

## Способы использования

### 1. Streamlit UI (рекомендуется для начинающих)

Веб-интерфейс с 8 вкладками:
- **Load/Create** — загрузка Power BI моделей или создание вручную
- **Entities** — управление сущностями
- **Relationships** — управление связями
- **Permissions** — настройка прав доступа
- **Rules** — бизнес-правила
- **OWL Preview** — предпросмотр OWL
- **Diff & Merge** — сравнение и слияние онтологий
- **Chat** — AI-ассистент для вопросов по онтологии

### 2. MCP Tools (для Claude Code)

Интеграция с Claude Code через MCP протокол. Все команды доступны прямо в чате.

### 3. Python API

```python
from powerbi_ontology import PowerBIParser, OntologyGenerator

parser = PowerBIParser()
model = parser.parse_pbix("model.pbix")

generator = OntologyGenerator()
ontology = generator.generate(model)
```

---

## Streamlit UI

### Вкладка 1: Load/Create

**Загрузка Power BI модели:**
1. Выберите формат файла (PBIX, BIM, VPAX, PBIP/TMDL)
2. Загрузите файл через drag-and-drop
3. Нажмите "Parse Model"

**Создание вручную:**
1. Введите название онтологии
2. Добавьте сущности и колонки
3. Нажмите "Create Ontology"

### Вкладка 2: Entities

Управление сущностями (таблицами):
- Добавление новых сущностей
- Редактирование свойств (колонок)
- Установка типа сущности (standard, dimension, fact)
- Добавление ограничений (constraints)

### Вкладка 3: Relationships

Управление связями между сущностями:
- Создание связей (one-to-many, many-to-one, many-to-many)
- Указание ключевых колонок
- Описание связей

### Вкладка 4: Permissions

Настройка прав доступа по ролям:

| Роль | Описание |
|------|----------|
| Admin | Полный доступ (CRUD) |
| Analyst | Чтение, создание, обновление |
| Viewer | Только чтение |

Для каждой сущности можно настроить:
- Какие роли имеют доступ
- Какие действия разрешены (read, create, update, delete)

### Вкладка 5: Rules

Бизнес-правила в формате:
- **Текстовые правила** — описание на естественном языке
- **SWRL правила** — логические правила для reasoning

Пример:
```
IF Sales.Amount > 10000 THEN Sales.RequiresApproval = true
```

### Вкладка 6: OWL Preview

Предпросмотр сгенерированного OWL:
- Формат: RDF/XML или Turtle
- Статистика: количество классов, свойств, правил
- Кнопка "Download OWL"

### Вкладка 7: Diff & Merge

Сравнение двух онтологий:
1. Загрузите базовую онтологию
2. Загрузите сравниваемую онтологию
3. Просмотрите различия (added, removed, modified)
4. Выберите изменения для слияния

### Вкладка 8: Chat

AI-ассистент для вопросов:
- "Какие сущности есть в модели?"
- "Покажи связи таблицы Sales"
- "Объясни структуру данных"

Требует `OPENAI_API_KEY` в environment.

---

## MCP Tools (Claude Code)

В Claude Code доступны следующие команды:

### pbix_extract — Извлечение из Power BI

```
Извлеки модель из файла sales_model.pbix
```

Параметры:
- `pbix_path` — путь к файлу
- `include_measures` — включать меры (по умолчанию: true)
- `include_security` — включать RLS (по умолчанию: true)

### ontology_generate — Генерация онтологии

```
Сгенерируй онтологию из модели с таблицами Sales и Products
```

Параметры:
- `model_data` — данные модели (entities, relationships)
- `detect_patterns` — определять паттерны (по умолчанию: true)

### export_owl — Экспорт в OWL

```
Экспортируй онтологию в OWL формат
```

Параметры:
- `ontology_data` — данные онтологии
- `format` — формат (xml, turtle)
- `include_action_rules` — включать правила доступа

### export_json — Экспорт в JSON

```
Сохрани онтологию в JSON файл
```

### ontology_diff — Сравнение онтологий

```
Сравни две онтологии и покажи различия
```

### ontology_merge — Слияние онтологий

```
Объедини онтологии sales и products
```

### analyze_debt — Анализ семантического долга

```
Проанализируй качество онтологий и найди проблемы
```

### ontology_chat_ask — AI-вопросы

```
Спроси у онтологии: какие таблицы связаны с Sales?
```

---

## Примеры использования

### Пример 1: Создание онтологии из Power BI

**Через Streamlit:**
1. Откройте `http://localhost:8501`
2. Вкладка "Load/Create" → загрузите `.pbix` файл
3. Вкладка "OWL Preview" → скачайте результат

**Через Claude Code:**
```
Извлеки модель из ~/models/sales.pbix и сгенерируй OWL онтологию
```

### Пример 2: Ручное создание онтологии

```python
model_data = {
    "entities": [
        {"name": "Customers", "columns": ["CustomerID", "Name", "Email"]},
        {"name": "Orders", "columns": ["OrderID", "CustomerID", "Amount", "Date"]}
    ],
    "relationships": [
        {
            "from_entity": "Orders",
            "to_entity": "Customers",
            "from_column": "CustomerID",
            "to_column": "CustomerID"
        }
    ]
}
```

### Пример 3: Настройка прав доступа

В OWL генерируются action rules:

```xml
<rdf:Description rdf:about="#read_Customers_Viewer">
    <rdf:type rdf:resource="#ReadAction"/>
    <ont:appliesTo rdf:resource="#Customers"/>
    <ont:requiresRole rdf:resource="#Viewer"/>
    <ont:allowsAction>read</ont:allowsAction>
</rdf:Description>
```

Это означает: роль Viewer может читать сущность Customers.

### Пример 4: Интеграция с OntoGuard

Сгенерированные OWL-онтологии совместимы с OntoGuard:

```bash
# Скопировать онтологию
cp ontologies/sales.owl ~/ontoguard-ai/ontologies/

# Обновить конфиг OntoGuard
# ontology: ontologies/sales.owl
```

---

## Форматы файлов

### Поддерживаемые входные форматы

| Формат | Расширение | Описание |
|--------|------------|----------|
| PBIX | `.pbix` | Power BI Desktop файл |
| BIM | `.bim` | Tabular Model JSON |
| VPAX | `.vpax` | VertiPaq Analyzer export |
| PBIP/TMDL | папка | Power BI Project (новый формат) |

### Выходные форматы

| Формат | Описание |
|--------|----------|
| OWL/XML | W3C OWL 2 в RDF/XML синтаксисе |
| Turtle | Компактный RDF формат |
| JSON | Внутренний формат для редактирования |

---

## FAQ

### Q: Какие версии Power BI поддерживаются?

A: Все версии Power BI Desktop. Для PBIP формата требуется Power BI Desktop 2023+.

### Q: Как добавить свои роли?

A: В Streamlit UI → вкладка "Permissions" → кнопка "Add Role". Или в JSON:
```json
{
    "roles": ["Admin", "Analyst", "Viewer", "CustomRole"]
}
```

### Q: Можно ли редактировать OWL напрямую?

A: Да, OWL файлы — это стандартный RDF/XML. Можно редактировать в Protégé или текстовом редакторе.

### Q: Как использовать с OntoGuard?

A:
1. Экспортируйте онтологию в OWL
2. Скопируйте в `~/ontoguard-ai/ontologies/`
3. Укажите путь в `config.yaml`

### Q: Где хранятся созданные онтологии?

A: По умолчанию в `~/powerbi-ontology-extractor/ontologies/`

### Q: Как получить AI-чат?

A: Установите `OPENAI_API_KEY`:
```bash
export OPENAI_API_KEY="sk-..."
```

### Q: Нужно ли регистрировать MCP сервер где-то?

A: Нет, регистрация не требуется. MCP сервер работает локально. Для использования:
1. Клонируйте репозиторий
2. Установите зависимости (`pip install -r requirements.txt`)
3. Добавьте конфигурацию в `~/.claude.json`
4. Перезапустите Claude Code

### Q: Можно ли установить через pip?

A: Да! Пакет опубликован на PyPI:
```bash
pip install powerbi-ontology-extractor
```

Страница проекта: https://pypi.org/project/powerbi-ontology-extractor/

### Q: Как обновить MCP сервер?

A:
```bash
cd ~/powerbi-ontology-extractor
git pull
pip install -e .
# Перезапустите Claude Code
```

### Q: Работает ли в Windows/macOS?

A: Да, проект кроссплатформенный. Пути в `~/.claude.json` нужно указывать для вашей ОС:
- **Linux/macOS**: `/home/user/powerbi-ontology-extractor`
- **Windows**: `C:\\Users\\user\\powerbi-ontology-extractor`

---

## Поддержка

- **GitHub Issues**: [powerbi-ontology-extractor/issues](https://github.com/vpakspace/powerbi-ontology-extractor/issues)
- **Документация**: Эта страница
- **Примеры**: папка `examples/` в репозитории

---

## Roadmap

- [x] ~~Публикация на PyPI~~ ✅ `pip install powerbi-ontology-extractor`
- [ ] Публикация на npm (`npx powerbi-ontology-mcp`)
- [ ] Docker образ для изолированного запуска
- [ ] Интеграция с Microsoft Fabric

---

**Версия**: 1.0.0
**Дата**: 2026-02-05
**GitHub**: https://github.com/vpakspace/powerbi-ontology-extractor
