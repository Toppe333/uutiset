# Uutiset

Oma kevyt uutislistaus puhelimeen (PWA): **https://toppe333.github.io/uutiset/**

GitHub Actions hakee RSS-syötteet 20 minuutin välein, rakentaa `docs/news.json`-tiedoston ja
julkaisee `docs/`-kansion suoraan GitHub Pagesiin. Ei palvelinta, ei riippuvuuksia, ei kuluja.

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

Jutut säilyvät 48 tuntia: jokainen ajo lukee edellisen tilan julkaistulta sivulta, lisää uudet
jutut ja poistaa yli 48 tuntia vanhat. `news.json` ei tallennu repoon, joten poistetut jutut
eivät jää julkiseen versiohistoriaan.

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

Repo: https://github.com/Toppe333/uutiset. Pages on asetettu julkaisemaan GitHub Actionsista
(**Settings → Pages → Source: GitHub Actions**). Työnkulku *Hae ja julkaise uutiset* ajetaan
ajastetusti, jokaisen `main`-haaran pushin jälkeen ja käsin *Actions*-välilehdeltä.

GitHub sammuttaa ajastetut työnkulut, jos repoon ei tule committeja 60 päivään. Siksi työnkulussa
on *keepalive*-työ, joka kerran päivässä ottaa työnkulun uudelleen käyttöön API:lla. Tämä nollaa
laskurin ilman committeja.

Puhelimeen: avaa osoite ja lisää kotivalikkoon (iPhone: Jaa → Lisää Koti-valikkoon;
Android: valikko → Asenna sovellus).

**Huom:** julkaistu `news.json` sisältää juttujen koko tekstit, ja GitHub Pages -sivu on kenen
tahansa luettavissa, joka tietää osoitteen.

## Paikallinen ajo

```bash
python3 scripts/fetch_news.py
```

```bash
python3 -m http.server 8765 --directory docs
```
