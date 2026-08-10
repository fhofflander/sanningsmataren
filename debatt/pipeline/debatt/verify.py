"""Stage 4: verify claims with web search, then adversarially review harsh verdicts.

Mirrors the main app's verification (Sonnet + provider web search, three
concurrent calls). New for the debate module: every FALSKT / MESTADELS FALSKT /
VILSELEDANDE verdict gets a second, adversarial pass instructed to refute it
before it can be published. The review can only confirm, soften or set
GÅR EJ ATT AVGÖRA (enforced in code, see debatt.verdict_rules).
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from anthropic import Anthropic, BadRequestError

from debatt import artifacts, llm, prompts
from debatt.config import Config
from debatt.verdict_rules import HARSH, VALID_OMDOMEN, resolve_review

CONCURRENCY = 3  # matches the extension's CONCURRENCY in src/App.tsx
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
WEB_SEARCH_TOOL_FALLBACK = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
MAX_PAUSE_CONTINUATIONS = 5


class VerifyError(RuntimeError):
    pass


def _search_call(client: Anthropic, model: str, system: str, user_message: str) -> str:
    """One web-search-enabled call, handling tool-version fallback and pause_turn."""
    messages = [{"role": "user", "content": user_message}]
    tool = WEB_SEARCH_TOOL
    for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=6000,
                system=system,
                tools=[tool],
                messages=messages,
            )
        except BadRequestError:
            if tool is WEB_SEARCH_TOOL:
                tool = WEB_SEARCH_TOOL_FALLBACK
                continue
            raise
        if response.stop_reason == "pause_turn":
            messages = [*messages, {"role": "assistant", "content": response.content}]
            continue
        return llm.response_text(response)
    raise VerifyError("Webbsökningen pausade för många gånger utan att bli klar.")


def _parse_verdict(text: str) -> dict:
    data = llm.parse_json_payload(text)
    if not isinstance(data, dict) or data.get("omdome") not in VALID_OMDOMEN:
        raise ValueError(f"Ogiltigt omdöme i svaret: {str(data)[:200]}")
    return {
        "omdome": data["omdome"],
        "motivering": str(data.get("motivering") or ""),
        "kallor": [
            {"titel": str(k.get("titel") or k.get("url", "")), "url": str(k["url"])}
            for k in data.get("kallor") or []
            if isinstance(k, dict) and k.get("url")
        ],
        "osakerhet": str(data.get("osakerhet") or ""),
    }


def _verify_one(client: Anthropic, config: Config, claim: dict, index: int, total: int) -> dict:
    label = f"[{index}/{total}] {claim['id']}"
    try:
        text = _search_call(
            client,
            config.verify_model,
            prompts.VERIFY_SYSTEM_PROMPT,
            prompts.verify_user_message(claim["pastaende"], claim.get("talare", ""), claim.get("citat", "")),
        )
        verdict = _parse_verdict(text)
        print(f"{label}: {verdict['omdome']}", file=sys.stderr)
    except Exception as exc:
        print(f"{label}: FEL ({exc}); markeras GÅR EJ ATT AVGÖRA", file=sys.stderr)
        verdict = {
            "omdome": "GÅR EJ ATT AVGÖRA",
            "motivering": "Verifieringen misslyckades tekniskt; påståendet har inte kunnat granskas.",
            "kallor": [],
            "osakerhet": f"Tekniskt fel: {exc}",
        }
    return {"claimId": claim["id"], **verdict}


def _review_one(client: Anthropic, config: Config, claim: dict, verdict: dict) -> dict:
    label = f"granskning {claim['id']} ({verdict['omdome']})"
    try:
        text = _search_call(
            client,
            config.verify_model,
            prompts.REVIEW_SYSTEM_PROMPT,
            prompts.review_user_message(claim, verdict),
        )
        review = llm.parse_json_payload(text)
        if not isinstance(review, dict):
            raise ValueError("granskningssvaret var inte ett JSON-objekt")
    except Exception as exc:
        print(f"{label}: FEL ({exc}); omdömet behålls omärkt granskat", file=sys.stderr)
        review = {"beslut": "bekräftad", "kommentar": f"Granskningen misslyckades tekniskt: {exc}"}
    resolved = resolve_review(verdict, review)
    outcome = resolved["granskning"]["beslut"]
    print(f"{label}: {outcome}" + (f" -> {resolved['omdome']}" if outcome == "ändrad" else ""), file=sys.stderr)
    return resolved


def verify(debate_id: str, config: Config, skip_review: bool = False) -> dict:
    debate_dir = config.debate_dir(debate_id)
    claims_doc = artifacts.load(debate_dir, artifacts.CLAIMS)
    claims = claims_doc["claims"]
    if not claims:
        raise VerifyError("claims.json innehåller inga påståenden.")
    client = llm.make_client(config.anthropic_api_key)

    print(f"Verifierar {len(claims)} påståenden (parallellitet {CONCURRENCY}) ...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        verdicts = list(
            pool.map(
                lambda pair: _verify_one(client, config, pair[1], pair[0] + 1, len(claims)),
                enumerate(claims),
            )
        )

    claims_by_id = {c["id"]: c for c in claims}
    if skip_review:
        print("Hoppar över adversarial granskning (--skip-review).", file=sys.stderr)
        verdicts = [
            {**v, "granskning": {"reviewed": False, "beslut": "bekräftad", "ursprungligtOmdome": None, "kommentar": ""}}
            for v in verdicts
        ]
    else:
        harsh = [v for v in verdicts if v["omdome"] in HARSH]
        print(f"Adversarial granskning av {len(harsh)} hårda omdömen ...", file=sys.stderr)
        reviewed: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for resolved in pool.map(
                lambda v: _review_one(client, config, claims_by_id[v["claimId"]], v), harsh
            ):
                reviewed[resolved["claimId"]] = resolved
        verdicts = [
            reviewed.get(
                v["claimId"],
                {**v, "granskning": {"reviewed": False, "beslut": "bekräftad", "ursprungligtOmdome": None, "kommentar": ""}},
            )
            for v in verdicts
        ]

    data = {
        "version": 1,
        "debateId": debate_id,
        "model": config.verify_model,
        "verifiedAt": artifacts.now_iso(),
        "verdicts": verdicts,
    }
    artifacts.save(debate_dir, artifacts.VERDICTS, data)
    print(f"Klart: {len(verdicts)} omdömen -> verdicts.json", file=sys.stderr)
    return data
