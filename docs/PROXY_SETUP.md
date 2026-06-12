# Proxy-oppsett

Når du er klar til å skalere over ~500 creators/dag (typisk etter at Instagram-kontoen har vært aktiv i ~1 måned), legg til en proxy. Koden er allerede klargjort for det — du trenger bare å fylle inn `"proxy"`-feltet i `config.json`.

## Hva en proxy gjør

Hver gang systemet kontakter Instagram, sender det i dag pakker direkte fra din IP. Instagram teller alle pakker fra samme IP-adresse. Over en viss terskel (typisk 500–800 kall/dag) flagger de IP-en og blokkerer kontoen.

En proxy er en mellomtjener som videresender pakker for deg. Instagram ser proxyens IP, ikke din. Med proxy-rotasjon kan du gjøre 1 000–2 000 kall/dag fra én Instagram-konto trygt.

## Hva som passer for deg

| Volum-mål | Type | Pris | Anbefaling |
|---|---|---|---|
| 500–2 000/dag | Datacenter-proxy med roterende IP-er | $3–10/mnd | 👈 **start her** |
| 2 000–5 000/dag | Residential proxy med sticky sessions | $15–30/mnd | Senere |
| 5 000+/dag | Mobile proxy | $50+/mnd | Bare hvis du skalerer eksplosivt |

## Konkrete leverandører (juni 2026)

Disse har proxyer som fungerer for Instagram-scraping. **Velg én**:

### Webshare ($2.99/mnd, 10 datacenter-IP-er) — Enklest å starte med
1. Gå til `webshare.io`
2. Sign up med din e-post
3. Velg «Free plan» (10 proxyer, 1 GB/mnd) eller «Proxy Server» ($2.99/mnd, 100 GB/mnd)
4. Etter kjøp, gå til **Proxy → Proxy List**
5. Velg ett proxy i listen, klikk «Direct Connection»
6. Du får ut et string i formatet:
   ```
   http://brukernavn:passord@p.webshare.io:80
   ```
   (eller en spesifikk port som `9999`)
7. Kopier denne strengen
8. Lim inn i `config.json` under `"proxy"`:
   ```json
   "proxy": "http://brukernavn:passord@p.webshare.io:80",
   ```
9. Lagre filen. Neste sesjon bruker proxyen automatisk.

### Smartproxy ($5/mnd, 100 MB datacenter)
1. `smartproxy.com` → Datacenter Proxies
2. Pay-as-you-go fra $5
3. Få endpoint i format `dc.smartproxy.com:10000` + brukernavn/passord
4. Bygg URL: `http://brukernavn:passord@dc.smartproxy.com:10000`

### Bright Data (større volum, $15+/mnd)
1. `brightdata.com` → Datacenter Proxies
2. Setup-prosedyre litt mer kompleks, men best kvalitet for høyt volum
3. Bedre å vente til 5 000+/dag

## Verifisering etter oppsett

Etter at du har fylt inn proxy-strengen:

```
python main.py --platforms instagram --max 1
```

I loggen vil du se:
```
[INFO] Bruker proxy for Instagram-sesjon
```

Hvis du i stedet får en feilmelding om at proxy ikke kan kobles til:
- Sjekk at strengen er nøyaktig kopiert (inkludert `http://`-prefixet)
- Sjekk at brukernavn/passord er riktige
- Noen leverandører krever at du whitelister din egen IP først — sjekk leverandørens dashboard

## Hvordan systemet bruker proxyen

Når `"proxy"`-feltet er satt, brukes den automatisk av:
- **Instagram-klienten** (`instagrapi`) — alle API-kall ruteres gjennom proxyen
- **TikTok-klienten** (`TikTokApi`) — samme
- **Social Blade-scraperen** (Playwright) — også samme (når SB-sjekken aktiveres senere, jfr. [SOCIALBLADE_PLAN.md](SOCIALBLADE_PLAN.md))

Du trenger ikke å konfigurere noe per klient. Én verdi i `config.json` styrer alt.

## Forventet volum-økning

| Setup | Trygg per dag | Trygg per time |
|---|---|---|
| Uten proxy, etablert konto (1+ mnd) | 500 | 50 |
| Med datacenter-proxy | 1 500–2 000 | 200 |
| Med residential proxy (rotert) | 5 000+ | 500+ |

Disse tallene forutsetter polite delays (2–8s mellom kall) — som er innebygd i koden allerede.

## Når bør du oppgradere til konto-pool?

Selv med proxy har én Instagram-konto teoretisk en grense. I praksis: hvis du oppdager at sesjoner begynner å feile med login-issues eller «challenge required», er det tegn på at IG er mistenksom. Da kan du:

1. **Senke volumet** (enkleste fix)
2. **Bytte til residential proxy** (neste trinn)
3. **Legge til en konto til** (krever kode-endring for konto-rotasjon)

Konto-pool-støtte er ikke implementert i koden nå, men kan legges til når du nærmer deg 5 000+/dag.
