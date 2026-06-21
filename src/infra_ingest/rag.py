"""Question answering over the local research library."""

import re

from .llm_client import build_llm_config_from_env, call_llm_api
from .library import retrieve_context


RAG_SYSTEM_PROMPT = """
你是研究库问答助手。请只基于提供的检索片段回答问题。

要求：
1. 如果检索片段不足以回答，直接说明“资料库中没有足够证据”。
2. 回答中的关键结论必须标注来源编号，例如 [S1]。
3. 不要引入外部知识，不要猜测。
4. 最后列出“引用来源”，包含编号、标题和路径。
""".strip()


def answer_question(db_path, question, **filters):
    """Answer a question with retrieved source snippets and an LLM."""
    llm_config = build_llm_config_from_env()
    if not llm_config.get("api_key"):
        raise RuntimeError("RAG 问答需要配置 LLM_API_KEY 或 OPENAI_API_KEY。")

    context = retrieve_context(db_path, question, **filters)
    if not context:
        return "资料库中没有足够证据回答这个问题。"

    context_text = "\n\n".join(
        f"[{item['ref']}] 标题：{item['title']}\n路径：{item['path']}\n来源：{item.get('source') or '未知'}\n片段：{item['snippet']}"
        for item in context
    )
    payload = f"问题：{question}\n\n检索片段：\n{context_text}"
    answer = call_llm_api(payload, RAG_SYSTEM_PROMPT, llm_config)
    return validate_rag_answer(answer, context)


def validate_rag_answer(answer, context):
    """Append a warning when an answer cites no retrieved source."""
    valid_refs = {item["ref"] for item in context}
    used_refs = set(re.findall(r"\[(S\d+)\]", answer or ""))
    invalid_refs = used_refs - valid_refs
    if not used_refs:
        return f"{answer}\n\n> 可信度提示：回答没有标注任何检索来源，请回到原文核对。"
    if invalid_refs:
        invalid = ", ".join(sorted(invalid_refs))
        return f"{answer}\n\n> 可信度提示：回答引用了不存在的来源编号：{invalid}。"
    return answer
