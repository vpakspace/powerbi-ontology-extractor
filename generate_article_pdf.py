#!/usr/bin/env python3
"""
Генерация PDF статьи о проекте PowerBI Ontology Extractor
"""

from fpdf import FPDF
from datetime import datetime


class ArticlePDF(FPDF):
    """PDF документ со статьёй"""

    def __init__(self):
        super().__init__()
        # Добавляем шрифт с поддержкой кириллицы
        self.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
        self.add_font('DejaVu', 'B', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        self.add_font('DejaVu', 'I', '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf')  # Using Serif for italic style
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font('DejaVu', 'I', 9)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'PowerBI Ontology Extractor — Техническая статья', align='C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Страница {self.page_no()}', align='C')

    def title_page(self, title, subtitle, author, date):
        """Титульная страница"""
        self.add_page()
        self.ln(60)

        # Заголовок
        self.set_font('DejaVu', 'B', 28)
        self.set_text_color(0, 51, 102)
        self.multi_cell(0, 15, title, align='C')

        self.ln(10)

        # Подзаголовок
        self.set_font('DejaVu', 'I', 14)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 10, subtitle, align='C')

        self.ln(40)

        # Автор и дата
        self.set_font('DejaVu', '', 12)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, f'Автор: {author}', align='C')
        self.ln(8)
        self.cell(0, 10, f'Дата: {date}', align='C')

    def chapter_title(self, title):
        """Заголовок главы"""
        self.set_font('DejaVu', 'B', 16)
        self.set_text_color(0, 51, 102)
        self.ln(10)
        self.cell(0, 10, title)
        self.ln(8)
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)

    def section_title(self, title):
        """Заголовок раздела"""
        self.set_font('DejaVu', 'B', 12)
        self.set_text_color(51, 51, 51)
        self.ln(5)
        self.cell(0, 8, title)
        self.ln(6)

    def body_text(self, text):
        """Основной текст"""
        self.set_font('DejaVu', '', 11)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullet_point(self, text):
        """Пункт списка"""
        self.set_font('DejaVu', '', 11)
        self.set_text_color(0, 0, 0)
        x = self.get_x()
        self.cell(8, 6, '  •  ', new_x="RIGHT", new_y="TOP")
        self.multi_cell(0, 6, text)
        self.set_x(x)  # Reset X position

    def code_block(self, code):
        """Блок кода"""
        self.set_font('DejaVu', '', 9)
        self.set_fill_color(245, 245, 245)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 5, code, fill=True)
        self.ln(3)


def create_article():
    """Создание статьи"""
    pdf = ArticlePDF()

    # Титульная страница
    pdf.title_page(
        title="PowerBI Ontology Extractor",
        subtitle="Инструмент для извлечения и управления\nонтологиями из моделей данных Power BI",
        author="vladspace_ubuntu24",
        date=datetime.now().strftime("%d %B %Y")
    )

    # Аннотация
    pdf.add_page()
    pdf.chapter_title("Аннотация")
    pdf.body_text(
        "В данной статье представлен инструмент PowerBI Ontology Extractor — программное "
        "решение для автоматического извлечения семантических метаданных из моделей данных "
        "Power BI и их преобразования в формат OWL-онтологий. Инструмент решает задачу "
        "формализации бизнес-знаний, заложенных в аналитических моделях, делая их доступными "
        "для семантического анализа, валидации и интеграции с системами искусственного интеллекта."
    )

    # Введение
    pdf.chapter_title("1. Введение")

    pdf.section_title("1.1 Проблематика")
    pdf.body_text(
        "Современные организации накапливают значительный объём бизнес-знаний в своих "
        "аналитических платформах. Power BI, будучи одной из ведущих платформ бизнес-аналитики, "
        "содержит в своих моделях данных ценную семантическую информацию: структуру сущностей, "
        "связи между ними, бизнес-метрики и правила расчёта показателей."
    )
    pdf.body_text(
        "Однако эта информация остаётся «замкнутой» внутри инструмента и недоступна для:"
    )
    pdf.bullet_point("Семантического анализа и рассуждений")
    pdf.bullet_point("Интеграции с системами управления знаниями")
    pdf.bullet_point("Валидации действий AI-агентов")
    pdf.bullet_point("Автоматизированной проверки соответствия бизнес-правилам")

    pdf.section_title("1.2 Предлагаемое решение")
    pdf.body_text(
        "PowerBI Ontology Extractor автоматически извлекает метаданные из различных форматов "
        "Power BI моделей (PBIP/TMDL, BIM, VPAX) и генерирует формальные OWL-онтологии, "
        "которые могут быть использованы в системах семантического веба, knowledge graphs "
        "и AI-приложениях."
    )

    # Архитектура
    pdf.chapter_title("2. Архитектура системы")

    pdf.section_title("2.1 Ключевые компоненты")
    pdf.body_text("Система состоит из четырёх основных компонентов:")
    pdf.ln(3)

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "Power BI Model Parser")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.body_text(
        "Модуль парсинга поддерживает три формата моделей Power BI: PBIP/TMDL (новый формат "
        "с разделением на файлы), BIM (JSON-представление табличной модели) и VPAX "
        "(XML-экспорт из DAX Studio). Парсер извлекает таблицы, колонки, меры, связи "
        "и иерархии из модели."
    )

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "OWL Ontology Generator")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.body_text(
        "Генератор преобразует извлечённые метаданные в OWL-онтологию с использованием "
        "библиотеки RDFLib. Сущности моделируются как OWL-классы с аннотациями типов данных, "
        "связи — как ObjectProperty, меры — как DatatypeProperty с формулами в rdfs:comment."
    )

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "Business Rules Engine")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.body_text(
        "Модуль позволяет определять бизнес-правила в формате OWL-ограничений и SWRL-правил. "
        "Поддерживаются ограничения кардинальности, допустимых значений, а также ролевые "
        "ограничения доступа для интеграции с системами безопасности."
    )

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "Ontology Chat (AI Q&A)")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.body_text(
        "Интеллектуальный чат-интерфейс на базе OpenAI GPT-4o-mini, позволяющий задавать "
        "вопросы об онтологии на естественном языке. Поддерживает русский и английский языки, "
        "учитывает роль пользователя (Admin, Analyst, Viewer) при формировании ответов."
    )

    pdf.section_title("2.2 Технологический стек")
    pdf.bullet_point("Python 3.10+ — основной язык разработки")
    pdf.bullet_point("Streamlit — веб-интерфейс с 8 вкладками")
    pdf.bullet_point("RDFLib — работа с RDF/OWL онтологиями")
    pdf.bullet_point("OpenAI API — AI-функциональность чата")
    pdf.bullet_point("Pydantic — валидация данных")

    # Функциональные возможности
    pdf.add_page()
    pdf.chapter_title("3. Функциональные возможности")

    pdf.section_title("3.1 Извлечение онтологий")
    pdf.body_text("Система поддерживает автоматическое извлечение следующих элементов:")
    pdf.bullet_point("Entities (сущности) — таблицы модели с типами колонок и описаниями")
    pdf.bullet_point("Relationships (связи) — foreign key связи между таблицами")
    pdf.bullet_point("Measures (меры) — DAX-формулы с метаданными форматирования")
    pdf.bullet_point("Hierarchies (иерархии) — аналитические иерархии для drill-down")

    pdf.section_title("3.2 Управление онтологиями")
    pdf.body_text("Веб-интерфейс предоставляет полный набор инструментов:")
    pdf.bullet_point("Создание и редактирование сущностей с атрибутами")
    pdf.bullet_point("Визуальное управление связями между сущностями")
    pdf.bullet_point("Настройка ролевых разрешений (CRUD per entity)")
    pdf.bullet_point("Редактор бизнес-правил с SWRL-синтаксисом")
    pdf.bullet_point("Предпросмотр OWL в форматах RDF/XML, Turtle, N-Triples")
    pdf.bullet_point("Сравнение и слияние версий онтологий (Diff & Merge)")

    pdf.section_title("3.3 AI-функциональность")
    pdf.body_text(
        "Ontology Chat позволяет пользователям взаимодействовать с онтологией через "
        "естественный язык. Примеры запросов:"
    )
    pdf.bullet_point("«Какие сущности есть в онтологии?» — список всех entities")
    pdf.bullet_point("«Покажи связи между таблицами» — таблица relationships")
    pdf.bullet_point("«Опиши структуру модели данных» — развёрнутое описание архитектуры")
    pdf.bullet_point("«Какие меры связаны с продажами?» — фильтрация по контексту")

    # Интеграции
    pdf.chapter_title("4. Интеграции")

    pdf.section_title("4.1 OntoGuard AI")
    pdf.body_text(
        "Проект интегрируется с OntoGuard AI — семантическим файрволом для AI-агентов. "
        "Сгенерированные онтологии могут использоваться для валидации действий агентов "
        "на основе OWL-правил. Например, правило «только Admin может удалять записи» "
        "будет автоматически проверяться при каждом запросе агента."
    )

    pdf.section_title("4.2 Universal Agent Connector")
    pdf.body_text(
        "Онтологии могут экспортироваться для использования в Universal Agent Connector — "
        "платформе для подключения AI-агентов к корпоративным базам данных. "
        "Это обеспечивает семантическую валидацию SQL-запросов и естественно-языковых "
        "команд на уровне бизнес-правил."
    )

    pdf.section_title("4.3 Knowledge Graphs")
    pdf.body_text(
        "Экспортированные OWL-онтологии совместимы со стандартами семантического веба "
        "и могут загружаться в графовые базы данных (Neo4j, Amazon Neptune) для "
        "построения корпоративных knowledge graphs."
    )

    # Результаты
    pdf.add_page()
    pdf.chapter_title("5. Результаты и тестирование")

    pdf.section_title("5.1 Статистика проекта")
    pdf.bullet_point("14 реализованных задач (Tasks) — 100% completion")
    pdf.bullet_point("~3000 строк Python кода")
    pdf.bullet_point("10 ключевых функций")
    pdf.bullet_point("8 вкладок пользовательского интерфейса")
    pdf.bullet_point("Поддержка 3 форматов Power BI моделей")

    pdf.section_title("5.2 Тестирование")
    pdf.body_text("Система протестирована на реальных моделях Power BI:")
    pdf.ln(3)

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "Sales Returns Sample")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.bullet_point("15 сущностей (таблиц)")
    pdf.bullet_point("9 связей между таблицами")
    pdf.bullet_point("Успешная генерация OWL-онтологии")
    pdf.bullet_point("AI-чат отвечает на вопросы корректно")
    pdf.ln(3)

    pdf.set_font('DejaVu', 'B', 11)
    pdf.cell(0, 6, "Adventure Works DW 2020")
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 11)
    pdf.bullet_point("11 сущностей")
    pdf.bullet_point("13 связей")
    pdf.bullet_point("Сложная star schema корректно преобразована")
    pdf.bullet_point("Описание модели данных на английском языке")

    pdf.section_title("5.3 Тестирование с Playwright MCP")
    pdf.body_text(
        "Функциональное тестирование выполнено с использованием Playwright MCP — "
        "инструмента браузерной автоматизации от Microsoft. Все 8 вкладок интерфейса "
        "проверены, AI-чат протестирован на различных типах запросов (списки, таблицы, "
        "развёрнутые описания) на русском и английском языках."
    )

    # Заключение
    pdf.chapter_title("6. Заключение")
    pdf.body_text(
        "PowerBI Ontology Extractor решает актуальную задачу извлечения семантических знаний "
        "из аналитических моделей и их формализации в виде OWL-онтологий. Инструмент "
        "обеспечивает мост между миром бизнес-аналитики и семантическими технологиями, "
        "открывая возможности для:"
    )
    pdf.bullet_point("Построения корпоративных knowledge graphs на основе BI-моделей")
    pdf.bullet_point("Семантической валидации действий AI-агентов")
    pdf.bullet_point("Автоматизированной проверки соответствия бизнес-правилам")
    pdf.bullet_point("Интеграции аналитических метаданных в системы управления знаниями")

    pdf.ln(5)
    pdf.body_text(
        "Проект имеет открытый исходный код и доступен на GitHub. Дальнейшее развитие "
        "предполагает расширение поддержки форматов (Azure Analysis Services, SSAS), "
        "улучшение AI-функциональности и интеграцию с большим количеством семантических "
        "платформ."
    )

    # Ссылки
    pdf.chapter_title("Ссылки")
    pdf.bullet_point("GitHub: https://github.com/vpakspace/powerbi-ontology-extractor")
    pdf.bullet_point("OntoGuard AI: https://github.com/vpakspace/ontoguard-ai")
    pdf.bullet_point("Universal Agent Connector: https://github.com/vpakspace/universal-agent-connector")
    pdf.bullet_point("OWL Web Ontology Language: https://www.w3.org/OWL/")
    pdf.bullet_point("RDFLib Documentation: https://rdflib.readthedocs.io/")

    return pdf


if __name__ == "__main__":
    pdf = create_article()
    output_path = "/home/vladspace_ubuntu24/powerbi-ontology-extractor/PowerBI_Ontology_Extractor_Article.pdf"
    pdf.output(output_path)
    print(f"PDF статья сохранена: {output_path}")
