from services.query_router import detect_intent


def test_detect_intent_uses_canonical_disease_for_long_target_prompt():
    query = (
        "Prioritize targets for non-small cell lung cancer using genetics, pathway centrality, "
        "literature support, safety, novelty, tractability, and East Asian evidence where "
        "available, then explain every score component, surface contradictions, and show which "
        "targets are robust versus speculative."
    )

    intent, search_term, method = detect_intent(query)

    assert intent == "disease"
    assert search_term == "non-small cell lung cancer"
    assert method == "keyword"


def test_detect_intent_does_not_match_gene_inside_genetics_word():
    query = "Summarize genetics evidence for glioblastoma and flag the strongest contradictions."

    intent, search_term, _ = detect_intent(query)

    assert intent == "disease"
    assert search_term == "glioblastoma"


def test_detect_intent_keeps_explicit_gene_queries_precise():
    intent, search_term, method = detect_intent("Find EGFR inhibitors")

    assert intent == "protein"
    assert search_term == "EGFR"
    assert method == "keyword"