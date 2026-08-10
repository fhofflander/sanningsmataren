from __future__ import annotations

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

RIKSDAGEN_API = "https://data.riksdagen.se/personlista/?utformat=json"
SOURCE_ATTRIBUTION = "Sveriges riksdag, Riksdagens öppna data"


@dataclass(slots=True)
class RosterPerson:
    id: str
    name: str
    party: str | None
    image_url: str
    image_path: str
    source: str
    aliases: list[str]


def sync_riksdag_roster(
    roster_dir: Path,
    *,
    include_former: bool = False,
    force: bool = False,
    limit: int | None = None,
) -> list[RosterPerson]:
    roster_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = roster_dir / "roster.json"
    url = RIKSDAGEN_API + ("&rdlstatus=alla" if include_former else "")
    if metadata_path.is_file() and not force:
        cached = json.loads(metadata_path.read_text(encoding="utf-8"))
        if cached.get("source_url") == url:
            return [RosterPerson(**person) for person in cached.get("people", [])]

    payload = _read_json(url)
    raw_people = payload.get("personlista", {}).get("person", [])
    if isinstance(raw_people, dict):
        raw_people = [raw_people]
    if limit is not None:
        raw_people = raw_people[:limit]

    image_dir = roster_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    people: list[RosterPerson] = []
    for raw in raw_people:
        person_id = str(raw.get("sourceid") or raw.get("intressent_id") or "")
        first_name = str(raw.get("tilltalsnamn") or "").strip()
        last_name = str(raw.get("efternamn") or "").strip()
        image_url = str(raw.get("bild_url_max") or raw.get("bild_url_192") or "")
        if not person_id or not first_name or not last_name or not image_url:
            continue
        suffix = Path(image_url.split("?", 1)[0]).suffix or ".jpg"
        image_path = image_dir / f"{safe_filename(person_id)}{suffix}"
        people.append(
            RosterPerson(
                id=person_id,
                name=f"{first_name} {last_name}",
                party=str(raw.get("parti") or "").strip() or None,
                image_url=image_url,
                image_path=str(image_path.relative_to(roster_dir)),
                source=SOURCE_ATTRIBUTION,
                aliases=[],
            )
        )

    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_person = {
            executor.submit(
                _download,
                person.image_url,
                roster_dir / person.image_path,
                force,
            ): person
            for person in people
        }
        for future in as_completed(future_to_person):
            person = future_to_person[future]
            try:
                future.result()
            except Exception:
                failures.append(person.id)

    if failures:
        failed_ids = set(failures)
        people = [person for person in people if person.id not in failed_ids]

    document = {
        "source": SOURCE_ATTRIBUTION,
        "source_url": url,
        "people": [asdict(person) for person in people],
        "download_failures": failures,
    }
    _write_json_atomic(metadata_path, document)
    return people


def merge_extra_roster(roster_dir: Path, extra_path: Path) -> list[RosterPerson]:
    """Lägg till moderatorer eller andra politiker via en liten egen JSON-lista."""
    metadata_path = roster_dir / "roster.json"
    people = load_roster(metadata_path) if metadata_path.is_file() else []
    raw = json.loads(extra_path.read_text(encoding="utf-8"))
    entries = raw.get("people", raw) if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError(
            "Extra talarregister måste vara en lista eller ha fältet 'people'."
        )

    image_dir = roster_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    by_id = {person.id: person for person in people}
    for entry in entries:
        person_id = str(entry["id"])
        image_url = str(entry["image_url"])
        suffix = Path(image_url.split("?", 1)[0]).suffix or ".jpg"
        image_path = image_dir / f"extra_{safe_filename(person_id)}{suffix}"
        _download(image_url, image_path, True)
        by_id[person_id] = RosterPerson(
            id=person_id,
            name=str(entry["name"]),
            party=str(entry.get("party") or "").strip() or None,
            image_url=image_url,
            image_path=str(image_path.relative_to(roster_dir)),
            source=str(entry.get("source") or "Eget talarregister"),
            aliases=[str(alias) for alias in entry.get("aliases", [])],
        )

    merged = sorted(by_id.values(), key=lambda person: person.name.casefold())
    _write_json_atomic(
        metadata_path,
        {
            "source": "Sammanslaget talarregister",
            "source_url": RIKSDAGEN_API,
            "people": [asdict(person) for person in merged],
            "download_failures": [],
        },
    )
    return merged


def load_roster(metadata_path: Path) -> list[RosterPerson]:
    document = json.loads(metadata_path.read_text(encoding="utf-8"))
    return [RosterPerson(**person) for person in document.get("people", [])]


def safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def _read_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def _download(url: str, target: Path, force: bool) -> None:
    if target.is_file() and target.stat().st_size > 0 and not force:
        return
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"},
    )
    temporary = target.with_suffix(target.suffix + ".tmp")
    with urllib.request.urlopen(request, timeout=30) as response:
        temporary.write_bytes(response.read())
    temporary.replace(target)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
