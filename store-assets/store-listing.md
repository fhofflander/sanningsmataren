# Chrome Web Store listing - Sanningsmätaren

Everything needed to fill in the Web Store listing and the privacy/review form.
Copy is written for the **launched backend version** (free to use, Google
sign-in), since that is the version being submitted. Replace every `[BRACKET]`
placeholder before submitting.

## Basic information

| Field | Value |
| --- | --- |
| Item name | Sanningsmätaren |
| Default language | Swedish (Sweden) |
| Category | Productivity (alt: News & Weather) |
| Website | [PUBLIC SITE URL] |
| Support email | [SUPPORT EMAIL] |
| Privacy policy URL | [HOSTED URL of docs/privacy-policy.md] |

## Summary / short description (max 132 characters)

**Swedish (default):**
> Faktagranska svensk politik i webbläsaren. Markera en text och få källbelagda omdömen på påståendena. Gratis med inloggning.

**English (optional locale):**
> Fact-check Swedish politics in your browser. Select any text and get sourced verdicts on the claims it makes. Free with sign-in.

> Character counts are verified in the commit; both are under 132.

## Detailed description

**Swedish (default):**
```
Sanningsmätaren faktagranskar svensk politisk text direkt i webbläsaren.

Markera ett citat, ett inlägg eller ett debattutdrag, eller klistra in egen
text. Appen plockar ut de kontrollerbara faktapåståendena och ger varje
påstående ett källbelagt omdöme på en skala från FALSKT till SANT.

Så funkar det:
- Logga in och kom igång direkt. Ingen egen API-nyckel behövs.
- Markera text på en sida och granska den, eller skriv in den själv.
- Få ett omdöme per påstående, med en tydlig mätare och länkar till källorna.

Källor först. Granskningen prioriterar svenska primärkällor som riksdagen.se,
scb.se, bra.se och riksbank.se, och stämmer av mot etablerade faktagranskare.

Bra att veta:
- Omdömena är automatiska och inte auktoritativa. Klicka alltid vidare till
  källorna och bilda dig en egen uppfattning.
- Fungerar bäst med politikerns exakta ord. Omskrivningar sänker träffsäkerheten.
- Varje konto har en daglig gräns för antal granskningar.

Sanningsmätaren är ett samarbete mellan alt_ctrl_ och eghed.
```

**English (optional locale):**
```
Sanningsmätaren fact-checks Swedish political text right in your browser.

Select a quote, a post, or a debate excerpt, or paste your own text. The app
pulls out the checkable factual claims and gives each one a sourced verdict on a
scale from FALSE to TRUE.

How it works:
- Sign in and start right away. No API key of your own required.
- Select text on a page to review it, or type it in yourself.
- Get one verdict per claim, with a clear gauge and links to the sources.

Sources first. Verification prioritises Swedish primary sources such as
riksdagen.se, scb.se, bra.se, and riksbank.se, and cross-checks against
established fact-checkers.

Good to know:
- Verdicts are automated and not authoritative. Always follow the sources and
  judge for yourself.
- Works best with a politician's exact words. Paraphrasing reduces accuracy.
- Each account has a daily limit on the number of checks.

Sanningsmätaren is a collaboration between alt_ctrl_ and eghed.
```

## Single purpose (review form)

> Sanningsmätaren fact-checks Swedish political text. The user pastes or selects
> text and the extension returns sourced verdicts on the factual claims it
> contains. It runs in Chrome's side panel.

## Permission justifications (review form)

These assume the final backend manifest: the three provider host permissions are
replaced by a single backend-domain host permission, and the `identity`
permission is added for Google sign-in. Update the manifest to match before
submitting.

| Permission | Justification |
| --- | --- |
| `activeTab` | Lets the user review the page they are actively on. Access is granted only by an explicit user action (toolbar click or context menu) and only for that tab. |
| `contextMenus` | Adds a right-click item to fact-check the currently selected text. |
| `scripting` | Reads the selected text or page content from the active tab when the user clicks a review button. Injected on demand, never on a schedule. |
| `sidePanel` | The extension UI runs in Chrome's side panel. |
| `storage` | Stores user settings and passes temporary selected text between the page and the side panel. |
| `identity` | Google sign-in, used to authenticate the user and enforce a per-user daily request limit. |
| Host permission `[BACKEND DOMAIN]/*` | The extension sends fact-check requests to our backend, which performs the AI analysis and holds the API key. This is the only remote endpoint the extension calls. |
| Optional host `*://*/*` | Requested on demand the first time the user chooses to read the content of an arbitrary page they are viewing. Not requested at install. Needed because the user may review any page they choose. |

> Review-speed note: the optional `*://*/*` is the item most likely to draw
> reviewer questions. If the on-demand `activeTab` + `scripting` model can cover
> the "review whole page / selection" feature, dropping it will speed review.

## Privacy practices / data use disclosures (review form)

Data collected:
- **Personally identifiable information** - email address and account identifier, via Google sign-in.
- **Authentication information** - sign-in state.
- **Website content** - the text the user submits or selects for fact-checking, and the generated verdicts. May reveal political opinions (handled under explicit consent; see the privacy policy).

Required certifications:
- [x] We do **not** sell or transfer user data to third parties for purposes unrelated to the item's single purpose. (Data is shared with our processors - the AI/search providers and hosting - solely to provide the fact-checking function.)
- [x] We do **not** use or transfer user data for purposes unrelated to the item's single purpose.
- [x] We do **not** use or transfer user data to determine creditworthiness or for lending.

Privacy policy URL: **[HOSTED URL of docs/privacy-policy.md]** (required because we
collect personal data and sensitive content).

## Graphic assets

| Asset | Status | Spec |
| --- | --- | --- |
| Store icon | **Ready** - `store-assets/store-icon-128.png` | 128x128 PNG |
| Screenshot 1 (results) | **Ready** - `store-assets/screenshots/01-results-1280x800.png` | 1280x800, real verdicts, version-agnostic |
| Screenshots 2-5 | **To capture on the real build** (see shot list) | 1280x800 or 640x400 |
| Small promo tile | **Ready** - `store-assets/promo-tile-440x280.png` | 440x280 PNG |
| Marquee promo tile | Optional, not yet made | 1400x560 PNG |

## Screenshot shot list

Captured (this PR):
1. **Results view** - two claims with verdict gauges (FALSKT and VILSELEDANDE)
   and Swedish sources. Reusable as-is.

To capture against the backend MVP (these screens do not exist yet):
2. **Sign-in screen** - "Logga in med Google" entry point.
3. **Consent screen** - the Article 9 explicit-consent step before logging.
4. **Empty / input state** - the side panel with the textarea and example chips,
   without the old API-key bar (which is removed in the backend version).
5. **Selection flow** - text selected on a page plus the right-click
   "Granska markerad text med Sanningsmätaren" menu, or the in-panel
   "Granska hela sidan" button.

Suggested captions (Swedish):
- "Markera text och granska den direkt"
- "Ett källbelagt omdöme per påstående"
- "Logga in och kom igång - ingen egen nyckel behövs"

## Still to provide before submitting

- [ ] Host the privacy policy at a public URL and fill its placeholders (PR #12)
- [ ] Confirm publisher identity / account verification (#7)
- [ ] Real values for every `[BRACKET]` above
- [ ] Update the manifest to the backend permission set (see #9, #10)
- [ ] Capture screenshots 2-5 on the backend MVP
- [ ] Bump `manifest.json` version for the submitted build
