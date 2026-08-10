"""Command-line interface for the debate-analysis pipeline.

Phase 1: ingest, transcribe. Phase 2 adds: extract, verify, assemble, run.
"""

from __future__ import annotations

import argparse
import sys

from debatt.config import Config


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", help="Katalog för debattdata (default: debatt/data)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debatt",
        description="Sanningsmätaren: pipeline för faktagranskning av politiska debatter.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ladda ner video och extrahera ljud")
    p_ingest.add_argument("url", help="URL till debatten (svtplay.se/riksdagen.se), eller '-' med --file")
    p_ingest.add_argument("--id", required=True, dest="debate_id", help="Debatt-id (kebab-case)")
    p_ingest.add_argument(
        "--kind",
        choices=["svtplay", "riksdagen", "file"],
        default="svtplay",
        help="Källtyp (default: svtplay)",
    )
    p_ingest.add_argument("--file", help="Lokal videofil (när --kind file)")
    _add_common(p_ingest)

    p_transcribe = sub.add_parser(
        "transcribe", help="Transkribera med Azure Speech och mappa talare"
    )
    p_transcribe.add_argument("debate_id", help="Debatt-id")
    p_transcribe.add_argument(
        "--max-speakers", type=int, default=12, help="Max antal talare för diarisering"
    )
    p_transcribe.add_argument(
        "--skip-mapping", action="store_true", help="Hoppa över AI-mappning av talare"
    )
    _add_common(p_transcribe)

    p_extract = sub.add_parser("extract", help="Extrahera kontrollerbara påståenden")
    p_extract.add_argument("debate_id", help="Debatt-id")
    _add_common(p_extract)

    p_verify = sub.add_parser(
        "verify", help="Verifiera påståenden med webbsökning + adversarial granskning"
    )
    p_verify.add_argument("debate_id", help="Debatt-id")
    p_verify.add_argument(
        "--skip-review", action="store_true", help="Hoppa över adversarial granskning"
    )
    _add_common(p_verify)

    p_assemble = sub.add_parser("assemble", help="Bygg publicerbar timeline.json")
    p_assemble.add_argument("debate_id", help="Debatt-id")
    p_assemble.add_argument(
        "--skip-summary", action="store_true", help="Hoppa över AI-sammanfattning"
    )
    _add_common(p_assemble)

    p_analyze = sub.add_parser(
        "analyze", help="Kör extract + verify + assemble i följd"
    )
    p_analyze.add_argument("debate_id", help="Debatt-id")
    p_analyze.add_argument("--skip-review", action="store_true")
    p_analyze.add_argument("--skip-summary", action="store_true")
    _add_common(p_analyze)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Config.from_env(data_dir=args.data_dir)

    try:
        if args.command == "ingest":
            from debatt.ingest import ingest

            ingest(
                url=args.url,
                debate_id=args.debate_id,
                debate_dir=config.debate_dir(args.debate_id),
                kind=args.kind,
                video_file=args.file,
            )
        elif args.command == "transcribe":
            from debatt.transcribe import transcribe

            transcribe(
                args.debate_id,
                config,
                max_speakers=args.max_speakers,
                skip_mapping=args.skip_mapping,
            )
        elif args.command == "extract":
            from debatt.extract import extract

            extract(args.debate_id, config)
        elif args.command == "verify":
            from debatt.verify import verify

            verify(args.debate_id, config, skip_review=args.skip_review)
        elif args.command == "assemble":
            from debatt.assemble import assemble

            assemble(args.debate_id, config, skip_summary=args.skip_summary)
        elif args.command == "analyze":
            from debatt.assemble import assemble
            from debatt.extract import extract
            from debatt.verify import verify

            extract(args.debate_id, config)
            verify(args.debate_id, config, skip_review=args.skip_review)
            assemble(args.debate_id, config, skip_summary=args.skip_summary)
    except Exception as exc:  # surfaced as a clean CLI error, not a traceback
        print(f"FEL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
