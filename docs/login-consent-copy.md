# Login and consent UI copy (Swedish)

Ready-to-use Swedish copy for the screens Fredrik builds in #10 (sign-in) and
#11 (consent + logging). Two screens plus a few states. The consent wording is
drafted for **Article 9 explicit consent** and still needs the legal review
noted in `docs/gdpr-policy.md`.

## 1. Sign-in screen (#10)

> **Rubrik:** Logga in för att börja granska
>
> **Brödtext:** Sanningsmätaren är gratis att använda. Du loggar in så att vi kan
> ge varje konto en rättvis daglig gräns och hålla tjänsten igång utan att du
> behöver en egen API-nyckel.
>
> **Knapp:** Logga in med Google
>
> **Finstilt:** Genom att logga in godkänner du vår
> [integritetspolicy]([PRIVACY URL]).

## 2. Consent screen (#11) - shown once after first sign-in, before any logging

> **Rubrik:** Innan vi börjar
>
> **Brödtext:** För att förbättra Sanningsmätaren vill vi spara de frågor du
> ställer och de svar du får. Texten du granskar kan avslöja politiska åsikter,
> som räknas som känsliga personuppgifter. Därför ber vi om ditt uttryckliga
> samtycke först.
>
> **Kryssruta:** Jag samtycker till att mina frågor och svar sparas för att
> förbättra tjänsten. Jag förstår att texten kan avslöja politiska åsikter
> (känsliga personuppgifter enligt artikel 9 i GDPR).
>
> **Primär knapp:** Jag samtycker och fortsätter
> **Sekundär knapp:** Inte nu
>
> **Finstilt:** Du kan när som helst återkalla ditt samtycke i inställningarna.
> Läs mer i vår [integritetspolicy]([PRIVACY URL]).

GDPR notes for the implementation:
- The checkbox must be **unchecked by default** (consent is an active choice).
- "Inte nu" must let the user continue without consenting; logging then stays
  off for that user. Decide whether the rest of the app is usable without
  consent (recommended: yes, just without logging).
- Withdrawal must be as easy as giving consent (see settings copy below).

## 3. Settings / account states

> **Inloggad som:** {email}
> **Knapp:** Logga ut
>
> **Samtycke till loggning:** {På / Av}
> **Knapp (på):** Återkalla samtycke
> **Knapp (av):** Ge samtycke
>
> När samtycke återkallas: "Ditt samtycke har återkallats. Vi sparar inga nya
> frågor eller svar. Vill du även radera det som redan sparats? [Radera mina
> data]"

## 4. Quota reached (429 from the API)

> **Rubrik:** Dagens gräns är nådd
> **Brödtext:** Du har använt dina {limit} granskningar för idag. Gränsen
> återställs vid midnatt. Välkommen tillbaka då!

## 5. Other small strings

> **Laddar (inloggning):** Loggar in...
> **Inloggning misslyckades:** Inloggningen gick inte att slutföra. Försök igen.
> **Utloggad/empty:** Logga in för att granska politisk text.

## Placeholders to fill

- `[PRIVACY URL]` - the hosted privacy policy (PR #12)
- `{limit}` - the daily limit `[X]` from #10
- `{email}` - signed-in user's email from `GET /v1/me`
