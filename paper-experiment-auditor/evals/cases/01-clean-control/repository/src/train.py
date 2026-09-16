import json


def load_protocol(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def select_checkpoint(history):
    return max(history, key=lambda item: item["validation_score"])

