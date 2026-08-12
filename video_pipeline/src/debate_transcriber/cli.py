from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .face_index import build_face_index
from .paths import default_cache_dir
from .pipeline import analyze_debate
from .roster import merge_extra_roster, sync_riksdag_roster
from .transcription import LocalTranscriber, OpenAIDiarizedTranscriber


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="debate-transcriber",
        description="Skapa tidsstämplad JSON med identifierade talare från en debattvideo.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=default_cache_dir(),
        help="Cache för talarregister och ansiktsindex.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analysera en videofil eller URL.")
    analyze.add_argument("source", help="Lokal videofil eller http(s)-URL.")
    analyze.add_argument("--output", "-o", type=Path, default=Path("debate.json"))
    analyze.add_argument("--transcriber", choices=("openai", "local"), default="openai")
    analyze.add_argument("--language", default="sv")
    analyze.add_argument("--whisper-model", default="small")
    analyze.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    analyze.add_argument("--compute-type", default="int8")
    analyze.add_argument("--min-speakers", type=int)
    analyze.add_argument("--max-speakers", type=int)
    analyze.add_argument("--no-identity", action="store_true")
    analyze.add_argument(
        "--require-identity",
        action="store_true",
        help="Avbryt i stället för att skriva null när bildidentifieringen misslyckas.",
    )
    analyze.add_argument("--no-ocr", action="store_true")
    analyze.add_argument("--include-former", action="store_true")
    analyze.add_argument(
        "--extra-roster",
        type=Path,
        help="JSON med extra politiker/moderatorer och referensbilder.",
    )

    roster_sync = subparsers.add_parser(
        "roster-sync", help="Hämta Riksdagens öppna talarregister."
    )
    roster_sync.add_argument(
        "--all", action="store_true", help="Ta med tidigare ledamöter."
    )
    roster_sync.add_argument("--force", action="store_true")
    roster_sync.add_argument("--limit", type=int, help=argparse.SUPPRESS)
    roster_sync.add_argument("--extra", type=Path)

    subparsers.add_parser(
        "roster-index", help="Bygg lokala ansiktsvektorer från talarregistret."
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    cache_dir = args.cache_dir.expanduser().resolve()
    roster_dir = cache_dir / "roster"

    try:
        if args.command == "roster-sync":
            people = sync_riksdag_roster(
                roster_dir,
                include_former=args.all,
                force=args.force,
                limit=args.limit,
            )
            if args.extra:
                people = merge_extra_roster(roster_dir, args.extra.resolve())
            print(f"Talarregister klart: {len(people)} personer i {roster_dir}")
            return

        if args.command == "roster-index":
            count, failures = build_face_index(roster_dir)
            print(
                f"Ansiktsindex klart: {count} referensansikten, "
                f"{len(failures)} bilder avvisades."
            )
            return

        transcriber = _make_transcriber(args, cache_dir)
        output = args.output.expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix="debate-transcriber-") as temporary:
            analyze_debate(
                args.source,
                output=output,
                workdir=Path(temporary),
                cache_dir=cache_dir,
                transcriber=transcriber,
                identify_speakers=not args.no_identity,
                require_identity=args.require_identity,
                use_ocr=not args.no_ocr,
                extra_roster=args.extra_roster.resolve() if args.extra_roster else None,
                include_former=args.include_former,
                progress=lambda message: print(message, file=sys.stderr),
            )
    except KeyboardInterrupt:
        parser.exit(130, "Avbrutet.\n")
    except Exception as error:
        parser.exit(1, f"Fel: {error}\n")


def _make_transcriber(args: argparse.Namespace, cache_dir: Path):
    if args.transcriber == "local":
        return LocalTranscriber(
            language=args.language,
            whisper_model=args.whisper_model,
            device=args.device,
            compute_type=args.compute_type,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
            cache_dir=cache_dir,
        )
    return OpenAIDiarizedTranscriber(language=args.language)
