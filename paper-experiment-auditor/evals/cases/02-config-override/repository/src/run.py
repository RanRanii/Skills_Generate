import json


def effective_config(path="configs/train.json"):
    with open(path, encoding="utf-8") as handle:
        config = json.load(handle)
    config["learning_rate"] = 0.01
    return config


def train(config):
    return {"optimizer": config["optimizer"], "lr": config["learning_rate"]}

