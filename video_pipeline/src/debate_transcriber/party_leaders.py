from __future__ import annotations

from dataclasses import dataclass


PARTY_LEADER_ROSTER_VERSION = "2026-08-10-v2"


@dataclass(frozen=True, slots=True)
class PartyLeader:
    name: str
    party: str
    official_url: str
    aliases: tuple[str, ...] = ()
    official_image_urls: tuple[str, ...] = ()


# Partiledare/språkrör verifierade mot respektive partis officiella webbplats.
# Versionsnumret ovan gör att ett redan hämtat register uppdateras när listan ändras.
CURRENT_PARTY_LEADERS: tuple[PartyLeader, ...] = (
    PartyLeader(
        "Magdalena Andersson",
        "S",
        "https://www.socialdemokraterna.se/magdalenaandersson",
    ),
    PartyLeader(
        "Ulf Kristersson",
        "M",
        "https://moderaterna.se/",
    ),
    PartyLeader(
        "Jimmie Åkesson",
        "SD",
        "https://www.sd.se/jimmie/",
        ("Jimmy Åkesson",),
    ),
    PartyLeader(
        "Elisabeth Thand Ringqvist",
        "C",
        "https://www.centerpartiet.se/om-centerpartiet/kontakta-centerpartiet/"
        "riksorganisationen/partistyrelsen",
        ("Elisabeth Thand", "Elisabeth Ringqvist"),
    ),
    PartyLeader(
        "Nooshi Dadgostar",
        "V",
        "https://www.vansterpartiet.se/nooshi-dadgostar/",
    ),
    PartyLeader(
        "Ebba Busch",
        "KD",
        "https://kristdemokraterna.se/ebba",
        ("Ebba Busch Thor",),
    ),
    PartyLeader(
        "Simona Mohamsson",
        "L",
        "https://www.liberalerna.se/liberaler/simona-mohamsson",
        official_image_urls=(
            "https://www.liberalerna.se/wp-content/uploads/"
            "omslag-hemsida-10-e1759413341362-720x344.jpg",
        ),
    ),
    PartyLeader(
        "Amanda Lind",
        "MP",
        "https://www.mp.se/om/sprakror/",
    ),
    PartyLeader(
        "Daniel Helldén",
        "MP",
        "https://www.mp.se/om/sprakror/",
        ("Daniel Hellden",),
    ),
)
