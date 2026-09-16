class Model:
    def __init__(self, config, attention_factory):
        self.use_attention = config["use_attention"]
        self.attention = attention_factory()

    def forward(self, features):
        return self.attention(features)

