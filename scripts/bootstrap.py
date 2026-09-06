import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse

from app.db.schema import ensure_schema, reset_schema
from app.db.seed import seed_data
from scripts.embed_knowledge import embed_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the local SupportPilot V2 PostgreSQL database."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and recreate SupportPilot project tables before seeding.",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Generate missing Gemini embeddings after seeding.",
    )
    parser.add_argument(
        "--force-embed",
        action="store_true",
        help="Regenerate all knowledge embeddings.",
    )
    args = parser.parse_args()

    if args.reset:
        reset_schema()
    else:
        ensure_schema()

    seed_data()

    if args.embed or args.force_embed:
        embed_knowledge(force=args.force_embed)

    print("SupportPilot V2 bootstrap complete.")


if __name__ == "__main__":
    main()
