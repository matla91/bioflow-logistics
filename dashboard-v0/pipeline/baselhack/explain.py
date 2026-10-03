"""Only word existing decision evidence. No LLM credentials or network required."""


def explain(decision):
    # Optional LLM integration deliberately unimplemented: the safe default cannot add facts.
    return (
        decision["headline"] + ". " + " ".join(r["text"] for r in decision["reasons"])
    )
