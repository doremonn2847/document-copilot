class DemoUnavailable(Exception):
    """Safe reason only; never retain raw driver or provider messages."""

    def __init__(self, reason: str = "unavailable"):
        self.reason = reason
        super().__init__(reason)


def demo_failure(error: BaseException) -> DemoUnavailable | None:
    """The OpenAI/PydanticAI clients wrap transport failures."""
    seen = set()
    pending = [error]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, DemoUnavailable):
            return current
        pending.extend(e for e in (current.__cause__, current.__context__) if e)
    return None
