def parse(text):
    """Sum plus-separated integers; this starter has a trailing-operator bug."""
    return sum(int(part) for part in text.split('+') if part.strip())
