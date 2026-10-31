import re
from langchain_core.documents import Document

def calculate_confidence_score(query: str, retrieved_docs: list[Document], answer: str) -> dict:
    """
    Evaluates confidence score (FR-08) based on retrieval relevance, 
    presence of explicit citations, and fallback triggers.
    """
    score = 100.0
    reasons = []

    # 1. Check for fallback trigger phrase
    if "I could not find this information in the authorised documentation sources" in answer:
        return {
            "confidence_score": 0.0,
            "confidence_level": "None (Fallback Triggered)",
            "reasons": ["The model could not find matching evidence in the context."]
        }

    # 2. Check if documents were retrieved
    if not retrieved_docs:
        return {
            "confidence_score": 10.0,
            "confidence_level": "Very Low",
            "reasons": ["No source documents were retrieved for this query."]
        }

    # 3. Citation Check (FR-06 / FR-08)
    # Checks if the generated answer references source tags like 'Source:' or page numbers
    has_citations = bool(re.search(r"Source:|page|section", answer, re.IGNORECASE))
    if not has_citations:
        score -= 25.0
        reasons.append("Answer lacks explicit document source references.")
    else:
        reasons.append("Explicit source citations detected.")

    # 4. Keyword Overlap Heuristic between query and retrieved context
    query_tokens = set(re.findall(r"\w+", query.lower()))
    context_text = " ".join([doc.page_content.lower() for doc in retrieved_docs])
    context_tokens = set(re.findall(r"\w+", context_text))
    
    overlap = query_tokens.intersection(context_tokens)
    if query_tokens:
        overlap_ratio = len(overlap) / len(query_tokens)
        if overlap_ratio < 0.3:
            score -= 30.0
            reasons.append(f"Low keyword overlap ({int(overlap_ratio * 100)}%) between query and context.")
        else:
            reasons.append(f"Strong keyword overlap ({int(overlap_ratio * 100)}%) with retrieved chunks.")

    # Bound score between 0 and 100
    final_score = max(0.0, min(100.0, score))

    # Categorize Confidence Level
    if final_score >= 80:
        level = "High"
    elif final_score >= 50:
        level = "Moderate"
    else:
        level = "Low"

    return {
        "confidence_score": round(final_score, 1),
        "confidence_level": level,
        "reasons": reasons
    }