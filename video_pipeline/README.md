# Debatt-transkriberaren

Ett körbart MVP som tar en lokal videofil eller en video-URL och skriver en
UTF-8-kodad JSON med talare, tidsintervall och svensk transkribering.
Varje post i `segments` innehåller högst en mening. Talar-ID, talarnamn och
tidsmetadata följer med varje mening; lokalläget använder ordens exakta tider.

## Windows-GUI – enklaste vägen

Dubbelklicka på **`run-gui.bat`**. Första gången startas installationen
automatiskt. Installationsprogrammet kan installera Python 3.12 och FFmpeg via
`winget` om de saknas, skapar en isolerad `.venv` och lägger en genväg på
skrivbordet. Det frågar innan systemprogram installeras.

GUI:t innehåller filväljare/URL-fält, val av transkriberingsläge,
talaridentifiering, ett maskerat API-fält för det valfria OpenAI-läget,
körlogg, avbrottsknapp och knappar för att öppna resultatet. Under
transkriberingen visas procent, avverkad videotid och en beräknad återstående
tid. I lokalläget behövs inga API-nycklar.

- `install-gui.bat` installerar det rekommenderade OpenAI-läget och lokal
  bildidentifiering.
- `install-local-gui.bat` installerar dessutom de betydligt större lokala
  Whisper- och sherpa-onnx-paketen.
- `run-gui.bat` startar programmet efter installationen.

### Kontrollera personer före transkriberingen

I lokalläget är ordningen nu uttryckligen bild först och Whisper sist:

1. Hela filmen skannas och ett avduplicerat persongalleri byggs.
2. Oidentifierade personer visas med en bild från filmen. I den redigerbara
   vallistan kan användaren välja en person som redan hittats, skriva ett nytt
   namn eller markera **Ej relevant**. Mushjulet rullar hela listan. Därefter
   visas återstående personer sorterade efter namn i en avduplicerad
   sammanställning; redan irrelevanta personer visas inte igen.
3. Ljudet delas upp i röstkluster utan att någon text ännu skapas.
4. Röstklustren kopplas till de kontrollerade personerna. Endast eventuella
   återstående okända röster behöver en extra manuell kontroll.
5. Först när namn och relevans är fastställda startar Whisper och skapar texten.

Personer med samma normaliserade namn slås ihop. Alla segment från personer som
markerats som ej relevanta tas bort innan JSON-filen skapas; tiderna för övriga
segment behåller sina ursprungliga positioner i filmen.

### Skapa en faktagranskad film

Klicka på **Skapa faktagranskad film …** i huvudfönstret och välj:

1. originalvideon eller dess URL,
2. faktagranskningsfilen i JSON-format, och
3. var den nya MP4-filen ska sparas.

Programmet kontrollerar JSON-strukturen, videolängden och SHA-256-värdet innan
renderingen startar. Resultatet blir en 1920×1080-film med originalvideon till
vänster och en permanent faktapanel till höger. Panelen visar tid, påstående,
gradering, kommentar och källnamn. Överlappande granskningar sidväxlas.
NVIDIA-kodning används automatiskt när den är tillgänglig, annars används CPU.
All bearbetning sker lokalt. Det formella indataformatet finns i
[`schema/fact-check.schema.json`](schema/fact-check.schema.json).

```powershell
debate-transcriber analyze "https://…/debatt" --output debatt.json
debate-transcriber analyze C:\video\debatt.mp4 --output debatt.json
```

## Den billiga identifieringsstrategin

Omvänd bildsökning för varje bildruta skulle både kosta mer, läcka fler bilder
till tredje part och ge svårreproducerbara resultat. Programmet gör i stället:

1. Hela filmen samplas först varannan sekund. Alla tillräckligt tydliga ansikten
   grupperas lokalt till ett persongalleri; personer som syns samtidigt kan
   aldrig slås ihop.
2. Varje unik galleri-person jämförs mot det lokala SFace-indexet. Namn kräver
   minst tre samstämmiga bilder över tid, tydlig marginal till näst bästa träff
   och både stark median- och centroidlikhet.
3. Användaren kontrollerar persongalleriet före texttranskriberingen och kan
   namnge eller utesluta personer.
4. Sherpa delar därefter upp ljudet i röstintervall utan att köra Whisper. Den
   lokala klustertröskeln är kalibrerad för debattljud för att undvika hundratals
   falska röstkluster.
5. När flera ansikten syns under ett talavsnitt mäts rörelse i munområdet. Ett
   centralt eller stort ansikte räknas inte automatiskt som talare.
6. Det aktiva ansiktet kopplas endast till en redan etablerad person i galleriet.
   Namn och porträtt kommer därför alltid från samma personpost. Referensbilder
   för riksdagsledamöter hämtas kostnadsfritt från
   [Riksdagens öppna data](https://www.riksdagen.se/sv/dokument-och-lagar/riksdagens-oppna-data/).
7. Flera röstobservationer måste peka på samma galleri-person. Vid låg säkerhet
   lämnas personen namnlös för den manuella kontrollen – systemet chansar inte.
8. Whisper körs sist och orden märks med de redan fastställda talarna.

Detta hanterar också en vanlig tv-fälla: kameran kan visa en åhörare medan någon
annan talar. Spridda felbilder röstar då normalt inte ned de konsekventa bilderna
av den riktiga talaren.

## Kostnadslägen

| Läge | Kontant marginalkostnad | Passar bäst för |
| --- | --- | --- |
| `openai` (standard) | API-kostnad för ett komprimerat ljudspår | MVP och låg/ojämn volym |
| `local` | Ingen avgift per minut; egen CPU/GPU och el | Stor eller regelbunden volym |

OpenAI-läget använder den specialiserade modellen
[`gpt-4o-transcribe-diarize`](https://developers.openai.com/api/docs/models/gpt-4o-transcribe-diarize).
API:t kräver `diarized_json` för talaretiketter och har en filgräns på 25 MB.
Programmet extraherar därför 16 kHz mono i 32 kbit/s och delar automatiskt långa
inspelningar i 45-minutersdelar. Aktuell prissättning finns på modellens sida.

Lokalläget använder `faster-whisper` för svensk text och `sherpa-onnx` för att
skilja rösterna åt. Inget konto, token eller API-anrop krävs. Första körningen
hämtar öppna modellfiler; därefter kan bearbetningen köras utan internet.
Långa inspelningar behandlas i tiominutersdelar med sammanhängande tidsstämplar.
De native CUDA- och ONNX-modellerna körs i en separat process, så att ett
modellfel kan visas i GUI:t utan att hela fönstret stängs.
Segmenteringsmodellen är MIT-licensierad och 3D-Speaker-modellen kommer från ett
Apache 2.0-projekt. Modellversionerna är låsta och SHA-256-verifieras.

## Installation på Windows

Förutsättningar: Python 3.11 eller 3.12 och FFmpeg/FFprobe i `PATH`.

```powershell
cd video_pipeline
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[vision]"
```

För OpenAI-läget:

```powershell
$env:OPENAI_API_KEY = "din-nyckel"
debate-transcriber analyze C:\video\debatt.mp4 -o C:\video\debatt.json
```

För helt lokal transkribering:

```powershell
pip install -e ".[vision,local]"
debate-transcriber analyze C:\video\debatt.mp4 -o C:\video\debatt.json `
  --transcriber local --whisper-model small
```

`small` + CPU `int8` håller nere hårdvarukravet. En större Whisper-modell ger
ofta bättre svensk text men kräver mer minne och tar längre tid. CUDA kan
aktiveras med `--device cuda --compute-type int8`. Windows-installationen för
lokalläget installerar en versionslåst kombination av CTranslate2 4.4, CUDA
12.2-cuBLAS och cuDNN 8.9 i programmets egen `.venv`. CUDA 13 och andra programs
GPU-miljöer påverkas därför inte. CUDA-biblioteken kräver ungefär 1,2 GB extra
nedladdning och en kompatibel NVIDIA-drivrutin.

Lokalläget är lokalt i betydelsen att själva analysen inte skickar video, ljud,
bilder eller text till en molntjänst. Internet behövs fortfarande första gången
för modell- och talarregisterhämtning samt när källan är en URL.

Första identifieringen hämtar ledamotsbilder, ett särskilt register över samtliga
aktuella partiledare/språkrör och flera fria Wikimedia Commons-bilder per ledare.
Varje extra bild jämförs först med Riksdagens betrodda porträtt; bilder som inte
föreställer samma person tas inte med i indexet. Därefter bygger programmet ett
lokalt index med OpenCV-modellerna SFace och YuNet. Det är ett engångsarbete.
Modellversionerna är
låsta och deras SHA-256-kontrollsummor verifieras vid hämtning. YuNet-modellen är
MIT-licensierad och [SFace-modellen är Apache 2.0-licensierad](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE).
För att göra indexeringen uttryckligen:

```powershell
debate-transcriber roster-sync
debate-transcriber roster-index
```

Talarregister och ansiktsindex lagras normalt under
`%LOCALAPPDATA%\Sanningsmataren\debate-transcriber`. Sätt
`DEBATE_TRANSCRIBER_CACHE` för en annan plats.

## Moderatorer och äldre politiker

Aktuella riksdagsledamöter och samtliga aktuella partiledare/språkrör är standard.
Tidigare ledamöter kan tas med med `--include-former` eller `roster-sync --all`.
Lägg hellre till debattens faktiska moderatorer och gäster via ett eget, litet
register:

```powershell
debate-transcriber analyze debatt.mp4 --extra-roster extra-roster.example.json
```

Varje post behöver ett stabilt id, namn och minst en direktlänk till en tydlig
porträttbild. Fältet `image_urls` kan innehålla flera oberoende referensbilder;
den första bilden i `image_url` är ankaret som övriga automatiskt jämförs med.
Ange bildkälla och kontrollera att bilderna får återanvändas.

## Exempel på resultat

```json
{
  "schema_version": "1.0",
  "source": {
    "input": "debatt.mp4",
    "kind": "file",
    "filename": "debatt.mp4",
    "duration_seconds": 5421.2,
    "sha256": "…"
  },
  "language": "sv",
  "transcription_backend": "openai:gpt-4o-transcribe-diarize",
  "speakers": [
    {
      "id": "person:012345",
      "name": "Exempel Person",
      "party": "S",
      "confidence": 0.91,
      "identification_method": "active_face+lower_third_ocr",
      "diarization_labels": ["A"],
      "reference_id": "012345",
      "evidence_count": 6,
      "alternatives": []
    }
  ],
  "segments": [
    {
      "id": "seg_00001",
      "start": 12.4,
      "end": 18.7,
      "speaker_id": "person:012345",
      "speaker_name": "Exempel Person",
      "text": "Det här är ett exempel.",
      "start_timecode": "00:00:12.400",
      "end_timecode": "00:00:18.700"
    }
  ],
  "warnings": []
}
```

Det fullständiga maskinläsbara schemat finns i
[`schema/debate-transcript.schema.json`](schema/debate-transcript.schema.json).

## Användbara flaggor

```text
--no-identity       transkribera och diariserar, men kör ingen bildanalys
--require-identity  avbryt om identifieringen inte kan köras
--no-ocr            använd bara ansikte/läppaktivitet
--min-speakers N    sätt samma N som max för exakt talarantal i lokalläge
--max-speakers N    sätt samma N som min för exakt talarantal i lokalläge
--include-former    bygg registret med tidigare riksdagsledamöter
```

## Integritet och kvalitet

- Tillfälligt nedladdad video, extraherat ljud och bildfönster raderas när
  körningen avslutas. Referensbilder och ansiktsvektorer ligger kvar lokalt i
  cachen för att slippa återkommande kostnad.
- I OpenAI-läget skickas det extraherade ljudet, men inte videobilderna eller
  ansiktsvektorerna, till transkriberings-API:t.
- Ansiktsvektorer är känslig behandling av personuppgifter. En produktionsdrift
  behöver rättslig bedömning, gallringsregler, åtkomstkontroll och uppdaterad
  DPIA/integritetstext.
- Resultatet är probabilistiskt. `confidence`, `alternatives` och `warnings`
  ska visas i ett granskningsgränssnitt; publicera inte en osäker identifiering
  som ett faktum.
- Läppheuristiken är inte full aktiv-talar-detektion. Bild-i-bild, dubbning,
  mycket små ansikten, munskydd och långa klippbilder kan ge `null`.

## Tester

```powershell
python -m unittest discover -s tests -v
```

En riktig end-to-end-körning kräver FFmpeg och nedladdade modeller samt, endast
för OpenAI-läget, en API-nyckel. Den ingår därför inte i de snabba enhetstesterna.
