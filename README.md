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

Bygget stegvis etter Discovery Spec v1.2 — seksjon 0.9 byggerekkefølge.

| # | Modul | Status |
|---|---|---|
| 1 | Instagram-innlogging (instagrapi) | Kode klar — venter live-validering |
| 2 | Hent siste 20 poster | Kode klar — venter live-validering |
| 3 | Early exit-filter (11 kriterier) | ✅ Validert (11 enhetstester) |
| 4 | SQLite deduplication | ✅ Validert (9 enhetstester) |
| 5 | Google Sheets-eksport | ✅ Live-testet mot eget ark |
| 6 | Discovery: keyword-søk | Kode klar — venter live-validering |
| 7 | Discovery: seed-profiler | Kode klar — trenger seed-handles i config |
| 8 | Discovery: hashtag-søk | Kode klar — venter live-validering |
| 9 | Social Blade fake-follower-sjekk | ⚠️ Hoppes over for IG (SB krever nå login) |
| 10 | TikTok-integrasjon | Kode klar — venter live-validering |
| 11 | Frontend (Flask) | ✅ Imports + endepunkter validert |

## Kjøring

CLI:
```
python main.py                  # full sesjon, alle nisjer, eksport til Sheets
python main.py --max 20         # bare prosesser 20 handles
python main.py --no-sheets      # hopp over Sheets
python main.py --stats-only     # vis database-statistikk
```

Nettside:
```
python web/app.py               # åpne http://127.0.0.1:5000 i nettleser
```

## Validering før produksjon

Skript som validerer hvert lag live (kjøres manuelt når Instagram-kontoen er moden):
```
python -m scripts.test_instagram_login natgeo    # Byggesteg 1+2
python -m scripts.test_tiktok mrbeast            # Byggesteg 10
```

## Skalering

Volum-tak per oppsett:

| Setup | Trygg per dag |
|---|---|
| Ny konto, uke 1 | 50–100 |
| Ny konto, uke 2–4 | 200–300 |
| Etablert konto (1+ mnd) | 500 |
| + datacenter-proxy | 1 500–2 000 |
| + residential proxy | 5 000+ |

Proxy-støtte er allerede bygd inn i alle klienter. Fyll inn `"proxy"`-feltet i `config.json` når du er klar. Se [docs/PROXY_SETUP.md](docs/PROXY_SETUP.md) for kjøpesteder og konfigurasjon.

Social Blade fake-follower-sjekk for Instagram er midlertidig hoppet over (specens kriterium 11). Plan for senere aktivering: [docs/SOCIALBLADE_PLAN.md](docs/SOCIALBLADE_PLAN.md).

## Hemmeligheter

`config.json`, service account JSON, persisterte sesjoner og SQLite-databasen er gitignored. Push aldri disse til remote.
