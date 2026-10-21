# Uutiset

Oma kevyt uutislistaus puhelimeen (PWA). GitHub Actions hakee RSS-syötteet 20 minuutin välein
tiedostoon `docs/news.json`, ja GitHub Pages näyttää staattisen sivun `docs/`-kansiosta.
Ei palvelinta, ei riippuvuuksia, ei kuluja.

Listassa näkyvät vain **ilmaiset** jutut, eikä videoita. Napautus avaa jutun **koko tekstin
sovelluksessa** julkaisijan tyylillä: otsikko, pääkuva, ingressi, leipäteksti ja väliotsikot.
Upotetut videot, kuvagalleriat ja mainokset jätetään pois. Alkuperäinen juttu on linkkinä lopussa.

## Lähteet

| Lähde | Syöte |
|---|---|
| Yle Uutiset | `https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET` (20 juttua) |
| Helsingin Sanomat | `https://www.hs.fi/rss/tuoreimmat.xml` |
| Kauppalehti | `https://feeds.kauppalehti.fi/rss/main` ja `https://feeds.kauppalehti.fi/rss/klnyt` |
| Aamulehti | `https://www.aamulehti.fi/rss/uutiset.xml` |
| Hämeen Sanomat | `https://www.hameensanomat.fi/feed/rss/` |

Jutut säilyvät `news.json`:ssa 3 päivää, joten Ylen lyhyt syöte ei hukkaa juttuja ajojen välissä.

Koko teksti luetaan juttusivun sisältämästä datasta: Yle `window.__INITIAL__STATE__`,
HS ja Aamulehti `__NEXT_DATA__` (`splitBody`), Kauppalehti `window.__PRELOADED_STATE__` ja
Hämeen Sanomat sivun HTML (`div.diks-article__storyline`).

## Maksullisten juttujen suodatus

- **HS ja Aamulehti:** syötteen kategoria *Tilaajille*, varmistetaan juttusivun `paidType`/`showPaywall`-tiedosta.
- **Kauppalehti:** juttusivun `freeArticle`-lippu. Lähes kaikki KL:n jutut ovat maksullisia, joten
  KL:ltä näkyy usein nolla juttua. KL:n juttu voi myös muuttua ilmaisesta maksulliseksi, joten
  sen jutut tarkistetaan joka ajolla uudelleen.
- **Hämeen Sanomat:** juttusivun `isAccessibleForFree`. Paikallisuutiset ovat yleensä maksullisia.
- **Yle:** kaikki ilmaisia.

## Videoiden suodatus

Syötteissä ei ole yhtenäistä videomerkintää, joten säännöt ovat lähdekohtaisia:

- **Kaikki lähteet:** otsikon alkusana *Video*, *Live*, *Suora lähetys* tai *HS-TV* (HS ja Aamulehti
  merkitsevät suorat lähetykset muodossa `Live | …`), osoitteessa `/video/` tai `areena.yle.fi`,
  kategoria *Video* tai *Talousaamu* (Kauppalehden videolähetys), tai video-enclosure.
- **Yle:** päämedia on video ja leipätekstiä alle 600 merkkiä. Ylen tavallisissa jutuissa on usein
  upotettuja videoita, joten pelkkä videon olemassaolo ei riitä.
- **Kauppalehti:** juttusivun `isVideoOnly`-lippu tai video ja alle 80 sanaa tekstiä.

Suodatetut jutut ja syy tallentuvat `news.json`:n `excluded`-osioon.

## Ulkoasu

Jokainen kortti noudattaa julkaisijansa tyyliä: logo, tunnusväri ja otsikkofontti. Julkaisijoiden
omat fontit ovat lisensoituja, joten tilalla ovat lähimmät avoimet Google Fonts -vastineet:

| Lähde | Alkuperäinen | Tässä |
|---|---|---|
| Yle | Yle Next | Open Sans (Ylen oma varafontti) |
| HS | Sanomat News Headline / Helsingin | Source Serif 4 / Source Sans 3 |
| Kauppalehti | Guardian Egyptian / Guardian Sans | Zilla Slab / Hanken Grotesk |
| Aamulehti | Lyon Display / Metric | Newsreader / Inter |
| Hämeen Sanomat | Majrit / Caslon Doric | Literata / Archivo |

Logot (`docs/logos/`) ovat julkaisijoiden omia favicon-tiedostoja.

## Käyttöönotto

1. Luo GitHubiin uusi repo ja vie tämä kansio sinne.
2. **Settings → Pages:** Source *Deploy from a branch*, branch `main`, kansio `/docs`.
3. **Actions**-välilehdeltä aja *Hae uutiset* kerran käsin (*Run workflow*). Jatkossa se ajautuu itsestään.
4. Avaa `https://<käyttäjä>.github.io/<repo>/` puhelimella ja lisää kotivalikkoon
   (iPhone: Jaa → Lisää Koti-valikkoon; Android: valikko → Asenna sovellus).

Julkisessa repossa Actions-minuutit ovat ilmaisia.

**Huom:** `news.json` sisältää juttujen koko tekstit, ja GitHub Pages -sivu on kenen tahansa
luettavissa, joka tietää osoitteen (myös yksityisestä reposta). Jos sivun pitää näkyä vain sinulle,
julkaise `docs/` esimerkiksi Cloudflare Pagesiin ja suojaa se Cloudflare Accessilla (ilmainen).

## Paikallinen ajo

```bash
python3 scripts/fetch_news.py
```

```bash
python3 -m http.server 8765 --directory docs
```
