"""Which endpoint the Voyage key belongs to (T5.5), with one one-word embedding per endpoint tried.

Voyage's own platform (api.voyageai.com) and MongoDB Atlas (ai.mongodb.com) issue separate keys, each
accepted only by its own endpoint; which one the key is decides the training opt-out the user must check
(T5.5). Each request embeds the single word "test" with voyage-law-2 (a few tokens, well under a cent at
$0.12 per million). It stops at the first endpoint that accepts the key. Prints the endpoint, the outcome
and the tokens billed; never the key. Not retried.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.errors import ServiceError  # noqa: E402
from api.search.voyage import HttpVoyageClient  # noqa: E402
from scripts.embed_corpus import read_key  # noqa: E402

ENDPOINTS = ("https://api.voyageai.com/v1", "https://ai.mongodb.com/v1")


async def main() -> int:
    key = read_key(ROOT / ".env")
    for base in ENDPOINTS:
        client = HttpVoyageClient(base_url=base, api_key=key)
        try:
            vectors, usage = await client.embed(["test"], "query")
        except ServiceError as e:
            print(f"{base}: refused ({e.kind}, status {e.status})")
            if e.kind != "auth":
                return 2
            continue
        print(f"{base}: accepted; {len(vectors[0])} dimensions; {usage.input_tokens} tokens billed")
        return 0
    print("no endpoint accepted the key")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
