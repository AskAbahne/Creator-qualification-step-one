# Social Blade fake-follower-sjekk — implementeringsplan

**Status (2026-06-12):** Hoppet over for Instagram. Specens kriterium 11 deaktiveres for IG-creators. Skal implementeres senere — denne planen beskriver hvordan.

---

## 1. Bakgrunn og problemet

Discovery Spec v1.2 seksjon 4 + 7.3.9 sier at vi skal:
- Hente ukentlige follower-snapshots fra Social Blade
- Avvise creators der vekstspikes på +5 000 følgere på én uke ikke er forklart av en video med ≥10× snittvisninger samme uke

Da systemet ble bygget 2026-06-12 oppdaget vi at **Social Blade endret tilgangsmodell**: for Instagram-statistikk kreves nå innlogging. Uten login får vi kun 14-dagers tabell, ikke specens ukentlige historikk.

Filteret er allerede satt opp til å håndtere fraværet av Social Blade-data: hvis `socialblade=None` sendes til `check_creator()`, hoppes kriterium 11 over uten å avvise creatoren. Det betyr at vi kan slå dette på senere uten å endre filterhjernen.

## 2. Foretrukne alternativer

To realistiske veier å gå (Ask valgte midlertidig å hoppe over begge — denne planen er for å gjenoppta arbeidet senere):

### Alternativ A: Social Blade-konto + Playwright med login

**Hva:** Opprett en gratis Social Blade-konto. Lagre brukernavn/passord i `config.json`. Endre `src/socialblade.py` til å logge inn først, deretter scrape.

**Pros:** Full historisk data (12+ uker), gratis.
**Cons:** Login-flyt er skjør (captcha, session-expirering, layoutendringer). Krever vedlikehold.

**Implementeringssteg:**
1. Manuelt: Opprett konto på `socialblade.com/signup`. Bruk dedikert e-post (gjerne samme som IG-kontoen). 2FA av.
2. Legg til i `config.json`:
   ```json
   "socialblade_username": "...",
   "socialblade_password": "..."
   ```
3. I `config.example.json`: legg til de samme nøklene som plassholdere.
4. I `src/socialblade.py`:
   - Ny funksjon `_login_socialblade(page, username, password)` som navigerer til `socialblade.com/login`, fyller inn skjemaet, og venter på redirect.
   - Persister cookies til `sessions/socialblade_cookies.json` så vi ikke logger inn hver gang.
   - I `scrape_weekly_growth()`: last cookies hvis de finnes, ellers logg inn. Hvis siden fortsatt viser «You must be logged in», forsøk re-login én gang.
5. Sjekk DOM-selektorer på den innloggede siden. Tabellen med ukentlig data finnes typisk under `.YouTubeUserTopInfoBlock` eller liknende tabellselektor.
6. Test mot en kjent IG-konto (f.eks. `garyvee`). Forventet: ≥12 ukentlige snapshots med dato og delta.

**Anti-deteksjon (viktig):**
- Headless Chromium med realistisk User-Agent
- 3–7 sek tilfeldig delay mellom kall (allerede i koden)
- Maksimalt 1 SB-oppslag per creator, og kun for creators som har passert alle andre 10 kriterier (begrenser volum drastisk)
- Vurder å persistere browser-context på tvers av sesjoner (gjør oss mer «menneskelig»)

### Alternativ D: Betalt Social Blade API

**Hva:** Kjøp `Social Blade Business`-plan ($10–25/mnd avhengig av volum). Bruk deres offisielle API.

**Pros:** Pålitelig, rask, ingen scraping-bro å vedlikeholde, JSON-respons.
**Cons:** Månedlig kostnad.

**Implementeringssteg:**
1. Manuelt: Kjøp abonnement på `business.socialblade.com`. Få API-nøkkel.
2. Legg til i `config.json`:
   ```json
   "socialblade_api_key": "..."
   ```
3. Skriv om `src/socialblade.py` til å bruke `requests` mot:
   - `https://matrix.sbapis.com/b/instagram/statistics?query=<handle>&history=extended`
   - Send `query`-, `clientid`- og `token`-headere per deres dokumentasjon.
4. Mapp respons-feltet `weekly` (eller tilsvarende) til vårt eksisterende format `[{"date": datetime, "follower_delta": int}, ...]`.
5. Fjern Playwright-avhengigheten fra `socialblade.py` — den trengs ikke lenger. La Playwright fortsatt være installert (kan trenges for andre formål).

**Når dette lønner seg:** Hvis du oppdager at falske følgere er et reelt problem i Steg 2 (Flozy) — dvs. creators som ser bra ut i Steg 1 men viser seg å ha kjøpt vekst. $10–25/mnd er billig forsikring hvis det sparer deg én feilrekrutering i kvartalet.

## 3. Aktivering i pipelinen

Når enten A eller D er implementert:

1. I `main.py` → `_filter_instagram_handle()`:
   ```python
   from src.socialblade import scrape_weekly_growth
   sb_data = scrape_weekly_growth(handle, "instagram")
   return check_creator(profile, posts, platform="instagram", socialblade=sb_data)
   ```
2. SB-oppslag skjer kun for creators som har passert kriterium 1–10 (`check_creator` håndterer dette automatisk siden K11 er sist i kjeden).
3. Forventet tilleggstid per godkjent creator: 5–15 sekunder (login + parsing). Lite siden de fleste avvises før kriterium 11.

## 4. Testkriterier før produksjon

For å verifisere at implementeringen fungerer som spec'en krever:

- **Test 1 (positiv):** Kjør mot en kjent legitim creator (f.eks. `garyvee`). Forventet: ingen 5k+ uker uten viral content → kriterium 11 godkjent.
- **Test 2 (negativ):** Finn en kjent kjøpt-følger-konto (det finnes lister på `socialblade.com/instagram/top/100/most-followers` der noen åpenbart er mistenkelige). Kjør den gjennom. Forventet: kriterium 11 avviser.
- **Test 3 (edge):** En creator med en viralt video samme uke som en spike. Skal IKKE avvises (10×-regelen redder dem).

## 5. Cutover-plan

Når koden er klar:

1. Aktiver SB i en testkjøring med `--max 5` mot kjente kontoer. Verifiser at filteret oppfører seg riktig.
2. Sjekk databasen for nye `failed_at = "11_fake_followers"`-oppføringer. Hvis det er for mange (>30% av tidligere godkjente blir nå avvist) — vurder om terskelen er riktig kalibrert for vår nisjefolk.
3. Når du er trygg: kjør full sesjon med SB aktivt. Sammenlign output med Sheets-ark fra forrige sesjon — har antall godkjente falt med en rimelig prosent (10–25%)?

## 6. Estimerte timer

| Aktivitet | Alternativ A | Alternativ D |
|---|---|---|
| Manuell oppsett | 30 min (lage konto) | 60 min (kjøp + dokumentasjon) |
| Koding | 4–6 timer | 1–2 timer |
| Testing | 2 timer | 1 time |
| **Totalt** | **6.5–8.5 timer** | **3–4 timer** |

## 7. Sjekkliste når vi tar dette opp igjen

- [ ] Bestem A eller D
- [ ] Manuell oppsett (konto eller API-kjøp)
- [ ] Oppdater `config.json` og `config.example.json` med nye felt
- [ ] Skriv om `src/socialblade.py` per valgt alternativ
- [ ] Aktiver i `main.py` → `_filter_instagram_handle()`
- [ ] Live-test mot 3 kjente kontoer (legitim, kjøpt, viral)
- [ ] Test med `python main.py --platforms instagram --max 5`
- [ ] Push og oppdater README med SB-status

---

*Denne planen er holdt enkel med vilje — selve filtersjekken (kriterium 11) er allerede skrevet i `src/filters.py`. Det eneste som mangler er datainnhentingen.*
