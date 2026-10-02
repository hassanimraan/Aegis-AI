import json
from pathlib import Path


KNOWLEDGE_BASE_FILE = (
    Path(__file__).parent.parent
    / "knowledge_base"
    / "policy_embeddings.json"
)


def load_knowledge_base():

    with open(
        KNOWLEDGE_BASE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)
