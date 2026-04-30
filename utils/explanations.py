def explanation_for(question) -> str:
    text = (question.explanation or "").strip()
    if text:
        return text
    if question.is_real:
        if question.source_date and question.source_date != "generated":
            return f"Real {question.format} by {question.persona} ({question.source_date})."
        return f"Real post by {question.persona}."
    return "AI-generated. The voice was close but the specifics didn't ring true."
