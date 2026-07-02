from __future__ import annotations

from .config import Settings
from .indexer import search_index
from .llm import OpenAICompatibleLLM
from .models import RetrievedDocument, Scope


ANSWER_SYSTEM_PROMPT = """You answer questions from an LLM Wiki.
Use only the retrieved wiki documents.
Separate stable knowledge from draft knowledge when needed.
If evidence is insufficient, say so clearly.
Always cite page titles in the answer."""


def render_context(documents: list[RetrievedDocument]) -> str:
    blocks = []
    for doc in documents:
        blocks.append(
            f"Title: {doc.title}\n"
            f"Status: {doc.status}\n"
            f"Page Type: {doc.page_type}\n"
            f"Source Type: {doc.source_type}\n"
            f"Excerpt:\n{doc.excerpt}\n"
        )
    return "\n---\n".join(blocks)


def deterministic_answer(question: str, documents: list[RetrievedDocument], scope: Scope) -> str:
    if not documents:
        return f"未检索到与问题相关的 wiki 内容。当前范围：{scope.value}。"
    lines = [f"问题：{question}", "", "检索结论："]
    for index, doc in enumerate(documents, start=1):
        lines.append(f"{index}. {doc.title} [{doc.status}/{doc.page_type}]")
        lines.append(f"   摘要：{doc.excerpt.strip()}")
    lines.append("")
    lines.append("说明：这是无模型模式下的摘录式回答，请根据引用页面继续确认。")
    return "\n".join(lines)


def answer_question(settings: Settings, question: str, scope: Scope, limit: int = 5) -> str:
    documents = search_index(settings, question, scope, limit=limit)
    llm = OpenAICompatibleLLM(settings)
    if not llm.available:
        return deterministic_answer(question, documents, scope)

    context = render_context(documents)
    prompt = f"Question:\n{question}\n\nScope: {scope.value}\n\nRetrieved wiki context:\n{context}"
    return llm.complete_text(ANSWER_SYSTEM_PROMPT, prompt)
