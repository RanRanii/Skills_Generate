import random


def split(samples: list[str]) -> tuple[list[str], list[str]]:
    shuffled = list(samples)
    random.Random(42).shuffle(shuffled)
    cutoff = int(len(shuffled) * 0.8)
    return shuffled[:cutoff], shuffled[cutoff:]
