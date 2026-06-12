# Creator Qualification — Steg 1

Automatisert creator-discovery for Abahne AS. Finner og kvalifiserer creators på Instagram og TikTok mot 11 objektive kriterier, og eksporterer godkjente kandidater til Google Sheets.

Steg 1 i Abahnes outreach-pipeline. Volum og hastighet — ingen kvalitativ vurdering her. Godkjente creators går videre til Steg 2 (Prospect List i Flozy).

## Oppsett

1. Opprett `config.json` fra `config.example.json` og fyll inn:
   - Instagram-credentials (dedikert konto)
   - TikTok msToken
   - Sti til Google service account JSON
   - Google Sheets ID
2. Installer avhengigheter:
   ```
   pip install instagrapi TikTokApi playwright langdetect gspread google-auth
   python -m playwright install chromium
   ```

## Status

Bygges stegvis etter Discovery Spec v1.2 — seksjon 0.9 byggerekkefølge.

| # | Modul | Status |
|---|---|---|
| 1 | Instagram-innlogging (instagrapi) | Kode klar — venter live-validering |
| 2 | Hent siste 20 poster | — |
| 3 | Early exit-filter (11 kriterier) | — |
| 4 | SQLite deduplication | — |
| 5 | Google Sheets-eksport | — |
| 6 | Discovery: keyword-søk | — |
| 7 | Discovery: seed-profiler | — |
| 8 | Discovery: hashtag-søk | — |
| 9 | Social Blade fake-follower-sjekk | — |
| 10 | TikTok-integrasjon | — |
| 11 | Frontend | — |

## Hemmeligheter

`config.json`, service account JSON, persisterte sesjoner og SQLite-databasen er gitignored. Push aldri disse til remote.
