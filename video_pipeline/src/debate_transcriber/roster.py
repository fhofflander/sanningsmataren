from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .party_leaders import CURRENT_PARTY_LEADERS, PARTY_LEADER_ROSTER_VERSION, PartyLeader

RIKSDAGEN_API = "https://data.riksdagen.se/personlista/?utformat=json"
SOURCE_ATTRIBUTION = "Sveriges riksdag, Riksdagens öppna data"
MIN_PARTY_LEADER_CANDIDATES = 1


@dataclass(slots=True)
class RosterPerson:
    id: str
    name: str
    party: str | None
    image_url: str
    image_path: str
    source: str
    aliases: list[str]
    image_urls: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    reference_sources: list[dict[str, str]] = field(default_factory=list)
    is_party_leader: bool = False
    official_url: str | None = None

    def all_image_paths(self) -> list[str]:
        return list(dict.fromkeys([self.image_path, *self.image_paths]))


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
            people = [RosterPerson(**person) for person in cached.get("people", [])]
            if limit is not None or _party_leader_cache_is_current(
                roster_dir, cached, people
            ):
                return people
            people, leader_failures = _enrich_with_party_leaders(
                roster_dir, people, force=False
            )
            cached["people"] = [asdict(person) for person in people]
            cached["party_leader_roster_version"] = PARTY_LEADER_ROSTER_VERSION
            cached["party_leader_download_failures"] = leader_failures
            _write_json_atomic(metadata_path, cached)
            return people

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

    leader_failures: list[str] = []
    if limit is None:
        people, leader_failures = _enrich_with_party_leaders(
            roster_dir, people, force=force
        )

    document = {
        "source": SOURCE_ATTRIBUTION,
        "source_url": url,
        "people": [asdict(person) for person in people],
        "download_failures": failures,
        "party_leader_roster_version": PARTY_LEADER_ROSTER_VERSION,
        "party_leader_download_failures": leader_failures,
    }
    _write_json_atomic(metadata_path, document)
    return people


def _party_leader_cache_is_current(
    roster_dir: Path, document: dict[str, Any], people: list[RosterPerson]
) -> bool:
    if document.get("party_leader_roster_version") != PARTY_LEADER_ROSTER_VERSION:
        return False
    by_key = {(_normalize(person.name), person.party): person for person in people}
    for leader in CURRENT_PARTY_LEADERS:
        person = by_key.get((_normalize(leader.name), leader.party))
        if person is None or not person.is_party_leader:
            return False
        if len(person.image_paths) < MIN_PARTY_LEADER_CANDIDATES:
            return False
        if not all((roster_dir / path).is_file() for path in person.all_image_paths()):
            return False
    return True


def _enrich_with_party_leaders(
    roster_dir: Path, people: list[RosterPerson], *, force: bool
) -> tuple[list[RosterPerson], list[str]]:
    """Komplettera Riksdagens aktuella lista med alla partiledare och fria bilder."""
    by_key = {(_normalize(person.name), person.party): person for person in people}
    missing_by_party: dict[str, list[PartyLeader]] = {}
    for leader in CURRENT_PARTY_LEADERS:
        if (_normalize(leader.name), leader.party) not in by_key:
            missing_by_party.setdefault(leader.party, []).append(leader)

    # Ministrar och frånvarande ledamöter saknas i standardlistan. Hämta därför
    # partiets historiska lista enbart för de partier där en ledare saknas.
    for party, missing in missing_by_party.items():
        party_url = (
            f"{RIKSDAGEN_API}&parti={urllib.parse.quote(party)}&rdlstatus=alla"
        )
        try:
            payload = _read_json(party_url)
        except Exception:
            continue
        raw_people = payload.get("personlista", {}).get("person", [])
        if isinstance(raw_people, dict):
            raw_people = [raw_people]
        wanted = {(_normalize(leader.name), leader.party): leader for leader in missing}
        for raw in raw_people:
            first_name = str(raw.get("tilltalsnamn") or "").strip()
            last_name = str(raw.get("efternamn") or "").strip()
            name = f"{first_name} {last_name}".strip()
            raw_party = str(raw.get("parti") or "").strip() or None
            key = (_normalize(name), raw_party)
            if key not in wanted or key in by_key:
                continue
            person = _person_from_riksdagen(raw, roster_dir)
            if person is not None:
                by_key[key] = person

    failures: list[str] = []
    leaders_dir = roster_dir / "party_leaders"
    leaders_dir.mkdir(parents=True, exist_ok=True)
    leader_people: list[tuple[PartyLeader, RosterPerson]] = []
    for leader in CURRENT_PARTY_LEADERS:
        key = (_normalize(leader.name), leader.party)
        person = by_key.get(key)
        if person is None:
            failures.append(f"{leader.name}:ingen_riksdagsbild")
            continue

        try:
            _download(person.image_url, roster_dir / person.image_path, force)
        except Exception:
            failures.append(f"{leader.name}:riksdagsbild")
            continue

        person.is_party_leader = True
        person.official_url = leader.official_url
        person.aliases = list(dict.fromkeys([*person.aliases, *leader.aliases]))
        leader_people.append((leader, person))

    candidates_by_person: dict[str, list[dict[str, str]]] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_leader = {
            executor.submit(_commons_image_candidates, leader, limit=6): (leader, person)
            for leader, person in leader_people
        }
        for future in as_completed(future_to_leader):
            leader, person = future_to_leader[future]
            try:
                candidates_by_person[person.id] = future.result()
            except Exception:
                candidates_by_person[person.id] = []
                failures.append(f"{leader.name}:commons_sökning")

    # Om Commons begränsar en parallell API-fråga görs ett enda lugnt försök
    # för just den personen. Bildhämtningen nedan är fortfarande parallell.
    for leader, person in leader_people:
        if not candidates_by_person.get(person.id):
            candidates_by_person[person.id] = _commons_image_candidates(
                leader, limit=6
            )
        official_candidates = [
            {
                "url": image_url,
                "original_url": image_url,
                "size": "0",
                "page_url": leader.official_url,
                "license": "Officiell partisida; endast lokal analys",
                "license_url": leader.official_url,
                "kind": "official",
                "mime": (
                    "image/png"
                    if image_url.casefold().endswith(".png")
                    else "image/jpeg"
                ),
            }
            for image_url in leader.official_image_urls
        ]
        candidates_by_person[person.id] = [
            *official_candidates,
            *candidates_by_person.get(person.id, []),
        ]

    download_tasks: list[
        tuple[PartyLeader, RosterPerson, int, dict[str, str], Path]
    ] = []
    for leader, person in leader_people:
        person_dir = leaders_dir / safe_filename(person.id)
        person_dir.mkdir(parents=True, exist_ok=True)
        kind_counts: dict[str, int] = {}
        for candidate in candidates_by_person.get(person.id, []):
            kind = candidate.get("kind") or "commons"
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
            index = kind_counts[kind]
            suffix = ".png" if candidate["mime"] == "image/png" else ".jpg"
            target = person_dir / f"{kind}_{index:02d}{suffix}"
            download_tasks.append((leader, person, index, candidate, target))

    successful: dict[
        str, list[tuple[int, dict[str, str], Path]]
    ] = {person.id: [] for _, person in leader_people}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_task = {
            executor.submit(_download_reference, candidate, target, force): task
            for task in download_tasks
            for _, _, _, candidate, target in [task]
        }
        for future in as_completed(future_to_task):
            leader, person, index, candidate, target = future_to_task[future]
            try:
                future.result()
            except Exception:
                failures.append(
                    f"{leader.name}:{candidate.get('kind', 'commons')}_{index}"
                )
                continue
            successful[person.id].append((index, candidate, target))

    for _, person in leader_people:
        records = sorted(successful[person.id], key=lambda item: item[0])
        person.image_urls = [candidate["url"] for _, candidate, _ in records]
        person.image_paths = [
            str(target.relative_to(roster_dir)) for _, _, target in records
        ]
        person.reference_sources = [
            {
                "page_url": candidate["page_url"],
                "license": candidate["license"],
                "license_url": candidate["license_url"],
            }
            for _, candidate, _ in records
        ]

    merged = sorted(by_key.values(), key=lambda person: person.name.casefold())
    return merged, failures


def _person_from_riksdagen(
    raw: dict[str, Any], roster_dir: Path
) -> RosterPerson | None:
    person_id = str(raw.get("sourceid") or raw.get("intressent_id") or "")
    first_name = str(raw.get("tilltalsnamn") or "").strip()
    last_name = str(raw.get("efternamn") or "").strip()
    image_url = str(raw.get("bild_url_max") or raw.get("bild_url_192") or "")
    if not person_id or not first_name or not last_name or not image_url:
        return None
    suffix = Path(image_url.split("?", 1)[0]).suffix or ".jpg"
    image_path = roster_dir / "images" / f"{safe_filename(person_id)}{suffix}"
    return RosterPerson(
        id=person_id,
        name=f"{first_name} {last_name}",
        party=str(raw.get("parti") or "").strip() or None,
        image_url=image_url,
        image_path=str(image_path.relative_to(roster_dir)),
        source=SOURCE_ATTRIBUTION,
        aliases=[],
    )


def _commons_image_candidates(
    leader: PartyLeader, *, limit: int
) -> list[dict[str, str]]:
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f'"{leader.name}"',
        "gsrnamespace": "6",
        "gsrlimit": str(min(20, max(limit, 1) * 2)),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        # 320 px är en förgenererad Commons-storlek och undviker att deras
        # bildserver behöver skapa många nya miniatyrer (HTTP 429). Ankaret är
        # fortfarande Riksdagens högupplösta porträtt.
        "iiurlwidth": "320",
        "format": "json",
        "origin": "*",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    try:
        payload = _read_json(url)
    except Exception:
        return []
    pages = payload.get("query", {}).get("pages", {}).values()
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    normalized_name = _normalize(leader.name)
    for page in pages:
        image_info = (page.get("imageinfo") or [{}])[0]
        mime = str(image_info.get("mime") or "")
        if mime not in {"image/jpeg", "image/png"}:
            continue
        metadata = image_info.get("extmetadata") or {}
        license_name = str((metadata.get("LicenseShortName") or {}).get("value") or "")
        license_url = str((metadata.get("LicenseUrl") or {}).get("value") or "")
        searchable = " ".join(
            [
                str(page.get("title") or ""),
                str((metadata.get("ImageDescription") or {}).get("value") or ""),
                str((metadata.get("Categories") or {}).get("value") or ""),
            ]
        )
        if not license_name or normalized_name not in _normalize(searchable):
            continue
        image_url = str(image_info.get("thumburl") or image_info.get("url") or "")
        original_url = str(image_info.get("url") or "")
        page_url = str(image_info.get("descriptionurl") or "")
        if not image_url or image_url in seen:
            continue
        seen.add(image_url)
        result.append(
            {
                "url": image_url,
                "original_url": original_url,
                "size": str(image_info.get("size") or "0"),
                "page_url": page_url,
                "license": license_name,
                "license_url": license_url,
                "mime": mime,
                "kind": "commons",
            }
        )
        if len(result) >= limit:
            break
    return result


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
        raw_urls = entry.get("image_urls") or []
        if not isinstance(raw_urls, list):
            raise ValueError("Fältet 'image_urls' måste vara en lista.")
        urls = list(
            dict.fromkeys(
                [str(entry.get("image_url") or ""), *[str(url) for url in raw_urls]]
            )
        )
        urls = [url for url in urls if url]
        if not urls:
            raise ValueError(f"Referensbilder saknas för {entry.get('name', person_id)}.")
        image_url = urls[0]
        suffix = Path(image_url.split("?", 1)[0]).suffix or ".jpg"
        image_path = image_dir / f"extra_{safe_filename(person_id)}{suffix}"
        _download(image_url, image_path, True)
        extra_urls: list[str] = []
        extra_paths: list[str] = []
        for index, extra_url in enumerate(urls[1:], start=1):
            extra_suffix = Path(extra_url.split("?", 1)[0]).suffix or ".jpg"
            extra_path = (
                image_dir
                / f"extra_{safe_filename(person_id)}_{index:02d}{extra_suffix}"
            )
            _download(extra_url, extra_path, True)
            extra_urls.append(extra_url)
            extra_paths.append(str(extra_path.relative_to(roster_dir)))
        by_id[person_id] = RosterPerson(
            id=person_id,
            name=str(entry["name"]),
            party=str(entry.get("party") or "").strip() or None,
            image_url=image_url,
            image_path=str(image_path.relative_to(roster_dir)),
            source=str(entry.get("source") or "Eget talarregister"),
            aliases=[str(alias) for alias in entry.get("aliases", [])],
            image_urls=extra_urls,
            image_paths=extra_paths,
        )

    merged = sorted(by_id.values(), key=lambda person: person.name.casefold())
    _write_json_atomic(
        metadata_path,
        {
            "source": "Sammanslaget talarregister",
            "source_url": RIKSDAGEN_API,
            "people": [asdict(person) for person in merged],
            "download_failures": [],
            "party_leader_roster_version": PARTY_LEADER_ROSTER_VERSION,
        },
    )
    return merged


def load_roster(metadata_path: Path) -> list[RosterPerson]:
    document = json.loads(metadata_path.read_text(encoding="utf-8"))
    return [RosterPerson(**person) for person in document.get("people", [])]


def safe_filename(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    without_markup = re.sub(r"<[^>]+>", " ", without_marks)
    return re.sub(r"[^a-z0-9]+", " ", without_markup.casefold()).strip()


def _read_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def _download(url: str, target: Path, force: bool) -> None:
    if target.is_file() and target.stat().st_size > 0 and not force:
        return
    temporary = target.with_suffix(target.suffix + ".tmp")
    for attempt in range(3):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Sanningsmataren-debate-transcriber/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                temporary.write_bytes(response.read())
            temporary.replace(target)
            return
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry_after = error.headers.get("Retry-After")
            try:
                requested_delay = float(retry_after)
            except (TypeError, ValueError):
                requested_delay = 1.0 + attempt
            if requested_delay > 30:
                raise
            delay = min(5.0, max(0.5, requested_delay))
            time.sleep(delay)


def _download_reference(
    candidate: dict[str, str], target: Path, force: bool
) -> None:
    try:
        _download(candidate["url"], target, force)
        return
    except urllib.error.HTTPError as error:
        # 330 px är normalfallet. Vissa äldre Commons-filer har bara en redan
        # cachad 250 px-version och svarar annars med en lång 429-spärr.
        smaller_url = candidate["url"].split("?", 1)[0].replace(
            "/330px-", "/250px-"
        )
        if error.code == 429 and smaller_url != candidate["url"].split("?", 1)[0]:
            try:
                _download(smaller_url, target, force)
                return
            except Exception:
                pass
        original_url = candidate.get("original_url") or ""
        try:
            original_size = int(candidate.get("size") or 0)
        except ValueError:
            original_size = 0
        if (
            error.code != 429
            or not original_url
            or original_url == candidate["url"]
            or original_size > 2 * 1024 * 1024
        ):
            raise
    _download(original_url, target, force)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
