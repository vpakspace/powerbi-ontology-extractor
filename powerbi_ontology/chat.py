"""
Ontology Chat - AI-powered Q&A for Power BI ontologies.

Allows users to ask questions about loaded ontologies in natural language.
Uses OpenAI API (or compatible) to generate answers based on ontology context.
"""

import os
from typing import Optional, List, Dict
from dataclasses import dataclass, field
from datetime import datetime

from .ontology_generator import Ontology


@dataclass
class ChatMessage:
    """Represents a single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatSession:
    """Manages chat history for a session."""
    messages: List[ChatMessage] = field(default_factory=list)
    ontology_name: str = ""
    user_role: str = "Analyst"

    def add_message(self, role: str, content: str) -> ChatMessage:
        """Add a message to the chat history."""
        msg = ChatMessage(role=role, content=content)
        self.messages.append(msg)
        return msg

    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent chat history in OpenAI format."""
        recent = self.messages[-limit:] if limit else self.messages
        return [{"role": m.role, "content": m.content} for m in recent]

    def clear(self):
        """Clear chat history."""
        self.messages.clear()


class OntologyChat:
    """
    AI-powered chat for exploring Power BI ontologies.

    Uses OpenAI API to answer questions about ontology structure,
    entities, relationships, measures, and business rules.
    """

    SYSTEM_PROMPT = """Ты - эксперт по Power BI онтологиям и семантическим моделям данных.
Твоя задача - отвечать на вопросы пользователя о загруженной онтологии.

КОНТЕКСТ ОНТОЛОГИИ:
{ontology_context}

РОЛЬ ПОЛЬЗОВАТЕЛЯ: {user_role}

ИНСТРУКЦИИ:
1. Отвечай на русском языке, если вопрос на русском, иначе на английском
2. Используй ТОЛЬКО информацию из предоставленного контекста онтологии
3. Если информации недостаточно, честно скажи об этом
4. Форматируй ответы с использованием markdown (списки, таблицы, код)
5. Для DAX формул используй блоки кода
6. Будь кратким, но информативным
7. Если спрашивают о правах доступа, учитывай роль пользователя

ПРИМЕРЫ ВОПРОСОВ:
- "Какие entities есть в онтологии?"
- "Как связаны Customer и Sales?"
- "Покажи все DAX меры"
- "Какие бизнес-правила определены?"
- "Что может делать роль Analyst?"
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Ontology Chat.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (defaults to gpt-4o-mini)
            base_url: Custom API base URL (for Ollama or other providers)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        self._client = None
        self.session = ChatSession()

    def _get_client(self):
        """Lazy load OpenAI client."""
        if self._client is None:
            try:
                import openai

                if self.base_url:
                    # Local model (Ollama) or custom endpoint
                    self._client = openai.OpenAI(
                        base_url=self.base_url,
                        api_key=self.api_key or "not-needed",
                        timeout=60,
                    )
                else:
                    # Standard OpenAI
                    if not self.api_key:
                        raise ValueError(
                            "OPENAI_API_KEY not set. Please set it in .env file or environment."
                        )
                    self._client = openai.OpenAI(api_key=self.api_key)

            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )

        return self._client

    def build_context(self, ontology: Ontology) -> str:
        """
        Build context string from ontology for the system prompt.

        Args:
            ontology: The loaded ontology

        Returns:
            Formatted context string
        """
        lines = []

        # Basic info
        lines.append(f"ОНТОЛОГИЯ: {ontology.name} v{ontology.version}")
        lines.append(f"Источник: {ontology.source}")
        lines.append("")

        # Entities
        lines.append(f"ENTITIES ({len(ontology.entities)}):")
        for entity in ontology.entities:
            props = [p.name for p in entity.properties]
            props_str = ", ".join(props[:5])
            if len(props) > 5:
                props_str += f"... (+{len(props)-5})"
            lines.append(f"  - {entity.name} ({entity.entity_type}): {props_str}")
            if entity.description:
                lines.append(f"    Описание: {entity.description}")
        lines.append("")

        # Relationships
        lines.append(f"RELATIONSHIPS ({len(ontology.relationships)}):")
        for rel in ontology.relationships:
            lines.append(
                f"  - {rel.from_entity}.{rel.from_property} → "
                f"{rel.to_entity}.{rel.to_property} ({rel.relationship_type}, {rel.cardinality})"
            )
        lines.append("")

        # Business Rules (DAX measures)
        if ontology.business_rules:
            lines.append(f"BUSINESS RULES / DAX MEASURES ({len(ontology.business_rules)}):")
            for rule in ontology.business_rules[:20]:  # Limit to avoid context overflow
                lines.append(f"  - {rule.name} [{rule.classification}]")
                if rule.condition:
                    # Truncate long DAX formulas
                    cond = rule.condition[:100] + "..." if len(rule.condition) > 100 else rule.condition
                    lines.append(f"    Formula: {cond}")
            if len(ontology.business_rules) > 20:
                lines.append(f"  ... и ещё {len(ontology.business_rules) - 20} правил")
        lines.append("")

        # Metadata
        if ontology.metadata:
            lines.append("METADATA:")
            for key, value in list(ontology.metadata.items())[:5]:
                lines.append(f"  - {key}: {value}")

        return "\n".join(lines)

    def ask(
        self,
        question: str,
        ontology: Ontology,
        user_role: str = "Analyst",
        include_history: bool = True,
    ) -> str:
        """
        Ask a question about the ontology.

        Args:
            question: User's question in natural language
            ontology: The loaded ontology to query
            user_role: User's role for permission context
            include_history: Whether to include chat history

        Returns:
            AI-generated answer
        """
        client = self._get_client()

        # Update session
        self.session.ontology_name = ontology.name
        self.session.user_role = user_role

        # Build system prompt with context
        context = self.build_context(ontology)
        system_prompt = self.SYSTEM_PROMPT.format(
            ontology_context=context,
            user_role=user_role,
        )

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add history if requested
        if include_history and self.session.messages:
            messages.extend(self.session.get_history(limit=6))

        # Add current question
        messages.append({"role": "user", "content": question})

        try:
            # Call OpenAI API
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for more factual answers
                max_tokens=1000,
            )

            answer = response.choices[0].message.content or ""

            # Save to history
            self.session.add_message("user", question)
            self.session.add_message("assistant", answer)

            return answer

        except Exception as e:
            error_msg = f"Ошибка при обращении к API: {str(e)}"
            return error_msg

    def get_suggestions(self, ontology: Ontology) -> List[str]:
        """
        Get suggested questions based on ontology content.

        Args:
            ontology: The loaded ontology

        Returns:
            List of suggested questions
        """
        suggestions = [
            "Какие entities есть в онтологии?",
            "Покажи все relationships между entities",
        ]

        # Add entity-specific suggestions
        if ontology.entities:
            first_entity = ontology.entities[0].name
            suggestions.append(f"Расскажи подробнее о {first_entity}")

            if len(ontology.entities) > 1:
                second_entity = ontology.entities[1].name
                suggestions.append(f"Как связаны {first_entity} и {second_entity}?")

        # Add measure-specific suggestions
        if ontology.business_rules:
            suggestions.append("Какие DAX меры определены?")
            suggestions.append("Покажи формулы для расчёта продаж")

        # Add permission suggestions
        suggestions.append("Какие права доступа есть у роли Analyst?")

        return suggestions[:6]  # Limit to 6 suggestions

    def clear_history(self):
        """Clear chat history."""
        self.session.clear()


def create_chat(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> OntologyChat:
    """
    Factory function to create OntologyChat instance.

    Args:
        api_key: OpenAI API key (optional, uses env var if not provided)
        model: Model name (optional, defaults to gpt-4o-mini)

    Returns:
        Configured OntologyChat instance
    """
    return OntologyChat(api_key=api_key, model=model)
