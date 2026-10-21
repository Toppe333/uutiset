#!/usr/bin/env python3
"""Hakee uutisotsikot RSS-syötteistä ja kirjoittaa ne tiedostoon docs/news.json.

Pelkkä Python-standardikirjasto, ei riippuvuuksia. Aiemmat jutut säilyvät
KEEP_HOURS tuntia, joten lyhyetkään syötteet (Yle: 20 juttua) eivät hukkaa
juttuja ajojen välissä; vanhemmat poistetaan jokaisella ajolla. Videot ja maksulliset jutut suodatetaan pois,
ja jokaisesta jutusta haetaan koko teksti juttusivulta.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "news.json"

KEEP_HOURS = 48
MAX_ITEMS = 800
USER_AGENT = "Mozilla/5.0 (compatible; oma-uutislukija/1.0)"

# Ylen jokainen syöte palauttaa vain 20 juttua, ja "Tuoreimmat" jättää pois esim. vähemmän
# tärkeiksi merkityt ja alueelliset jutut. Aihesyötteet täydentävät sitä.
YLE_TOPICS = {
    "kotimaa": "18-34837", "ulkomaat": "18-34953", "talous": "18-19274", "politiikka": "18-38033",
    "tiede": "18-819", "kulttuuri": "18-150067", "luonto": "18-35354", "terveys": "18-35138",
    "urheilu": "18-220090",
}

# recheck: lähteen jutut tarkistetaan joka ajolla uudelleen (KL:n juttu voi muuttua
# ilmaisesta maksulliseksi muutamassa tunnissa).
SOURCES = [
    {"id": "yle", "name": "Yle",
     "urls": ["https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"]
             + [f"https://yle.fi/rss/t/{topic_id}/fi" for topic_id in YLE_TOPICS.values()]},
    {"id": "hs", "name": "HS", "urls": ["https://www.hs.fi/rss/tuoreimmat.xml"]},
    {"id": "kl", "name": "Kauppalehti", "recheck": True,
     "urls": ["https://feeds.kauppalehti.fi/rss/main", "https://feeds.kauppalehti.fi/rss/klnyt"]},
    {"id": "al", "name": "Aamulehti", "urls": ["https://www.aamulehti.fi/rss/uutiset.xml"]},
    {"id": "hasa", "name": "Hämeen Sanomat", "urls": ["https://www.hameensanomat.fi/feed/rss/"]},
]

# Videotunnistus. Syötteissä ei ole yhtenäistä videomerkintää, joten säännöt
# yhdistävät otsikon, osoitteen, kategorian ja juttusivun tiedot.
VIDEO_TITLE = re.compile(r"^\s*(video|videot|katso video|live|suora|suora lähetys|hs-tv)\s*[|:–-]", re.I)
VIDEO_CATEGORIES = {"video", "videot", "talousaamu"}  # Talousaamu = Kauppalehden videolähetys
VIDEO_URL = re.compile(r"(areena\.yle\.fi|/videot?/|/video-)", re.I)
YLE_VIDEO_MAX_CHARS = 600  # Ylen juttu, jonka päämedia on video ja tekstiä vähän
KL_VIDEO_MAX_WORDS = 80

# Maksullisuus: HS ja Aamulehti merkitsevät syötteeseen kategorian "Tilaajille"
# (varmistetaan vielä juttusivulta), KL:n ja Hämeen Sanomien tieto luetaan juttusivulta.
PAYWALL_CATEGORIES = {"tilaajille"}
# Yhteinen aihejako sivun aihesuodattimille. Lehtien kategoriat nimetään eri tavoin,
# joten ne yhdistetään tässä. Järjestys on sama kuin sivulla.
TOPICS = [
    ("kotimaa", "Kotimaa"), ("paikalliset", "Paikalliset"), ("ulkomaat", "Ulkomaat"),
    ("politiikka", "Politiikka"), ("talous", "Talous"), ("urheilu", "Urheilu"),
    ("kulttuuri", "Kulttuuri ja viihde"), ("tiede", "Tiede ja terveys"),
    ("mielipide", "Mielipiteet"), ("muut", "Muut"),
]
YLE_REGIONS = {
    "uusimaa", "varsinais-suomi", "satakunta", "kanta-häme", "pirkanmaa", "päijät-häme", "kymenlaakso",
    "etelä-karjala", "etelä-savo", "pohjois-savo", "pohjois-karjala", "keski-suomi", "etelä-pohjanmaa",
    "pohjanmaa", "keski-pohjanmaa", "pohjois-pohjanmaa", "kainuu", "lappi", "ahvenanmaa",
}
CATEGORY_TOPICS = {
    "kotimaa": {"kotimaa", "suomi", "uutiset", "rikos", "rikosepäilyt", "rikokset", "sää", "uutissuomalainen",
                "onnettomuudet", "turvallisuus"} | YLE_REGIONS,
    "paikalliset": {"paikalliset", "helsinki", "pk-seutu", "tampere", "pirkanmaa"},
    "ulkomaat": {"ulkomaat", "maailma", "kirjeenvaihtajat", "venäjän hyökkäys"},
    "politiikka": {"politiikka", "puolueiden kannatus", "eduskunta", "eduskuntavaalit"},
    "talous": {"talous", "hs visio", "yritykset", "sijoittaminen", "työelämä", "työmarkkinat", "työllisyys",
               "verotus", "digitalous", "muutosneuvottelut", "asuminen"},
    "urheilu": {"urheilu", "liiga", "nhl", "jääkiekko", "jalkapallo", "hiihto", "koripallo", "urheilutapahtumat",
                "maailmancupit", "yleisurheilu", "formula 1", "salibandy", "lentopallo", "ravit"},
    "kulttuuri": {"kulttuuri", "popkulttuuri", "viihde", "teatteri", "musiikki", "kirjat", "elokuvat",
                  "televisio", "kuvataide", "pelit", "moro"},
    "tiede": {"tiede", "tiede ja teknologia", "terveys", "luonto", "ilmasto", "ympäristö", "eläimet", "hyvinvointi"},
    "mielipide": {"mielipide", "pääkirjoitus", "kolumnit", "lukijalta"},
}
TOPIC_OF_CATEGORY = {c: t for t, cats in CATEGORY_TOPICS.items() for c in cats}
# Osastotason kategoriat ratkaisevat ennen tarkempia tunnisteita (Ylellä osasto voi olla
# listan alussa tai lopussa, ja tunnisteissa on esim. maa "Suomi").
SECTION_CATEGORIES = {"kotimaa", "ulkomaat", "urheilu", "talous", "politiikka", "kulttuuri", "viihde",
                      "tiede", "terveys", "luonto"}
# Pirkanmaa on Aamulehdellä paikallisuutinen mutta Ylellä alueuutinen (kotimaa).
SOURCE_TOPIC_OVERRIDES = {"al": {"pirkanmaa": "paikalliset"}, "yle": {"pirkanmaa": "kotimaa"}}
SOURCE_DEFAULT_TOPIC = {"kl": "talous"}

# Henkirikosuutiset saavat oman merkinnän (sivulla oletuksena piilossa). Haetaan vain
# otsikosta, ingressistä ja kategorioista: leipätekstissä sanat esiintyvät usein sivumennen
# ("tappouhkauksia", "sudet tappoivat lampaita").
HOMICIDE = re.compile(
    # yhdyssanat (sarjamurhaaja, perhesurma) sallitaan, itsemurha ei ole henkirikos
    r"\w*(henkirik\w*|(?<!itse)murh[ai]\w*|surm\w*)"
    r"|\b(tappo(?!uhk)\w*|tapo(n|ksi|sta|ssa|t|ista)\b|tappa(ja\w*|nut\w*|neen\w*|mis\w*)|kuoliaaksi"
    r"|kuolemaan johtan\w* (pahoinpitel|väkival)\w*)",
    re.I,
)

TRACKING_PARAMS = {"origin", "utm_source", "utm_medium", "utm_campaign", "utm_content"}


def fetch(url, timeout=20):
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def clean_url(url):
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("­", "")  # tavutusvihjeet (HS, Yle)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s):
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def thumbnail(url):
    """Pienentää kuvan listan pikkukuvaksi lähteen kuvapalvelun omilla kokoversioilla."""
    if not url:
        return None
    url = re.sub(r"(images\.sanoma-sndp\.fi/[0-9a-f]+)/normal/\d+\.jpg", r"\1/square/300.jpg", url)
    url = url.replace("/alternates/LANDSCAPE_960/", "/alternates/LANDSCAPE_480/")
    url = re.sub(r"crop_fill,w_\d+,h_\d+", "crop_fill,w_300,h_300", url)  # Yle
    url = re.sub(r",\d+x/", ",300x/", url)  # Kauppalehti
    return url


def parse_feed(source, xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for el in root.iter("item"):
        link = clean_url(el.findtext("link") or "")
        title = clean_text(el.findtext("title"))
        if not link or not title:
            continue
        published = parse_date(el.findtext("pubDate"))
        categories = [clean_text(c.text) for c in el.findall("category") if c.text]
        enclosure = el.find("enclosure")
        enclosure_type = enclosure.get("type", "") if enclosure is not None else ""
        image = enclosure.get("url") if enclosure is not None and enclosure_type.startswith("image") else None
        media_video = any(
            (m.get("medium") == "video" or m.get("type", "").startswith("video"))
            for m in el.iter("{http://search.yahoo.com/mrss/}content")
        )
        guid = (el.findtext("guid") or link).strip()
        items.append({
            "id": f"{source['id']}:{guid}",
            "source": source["id"],
            "title": title,
            "link": link,
            "published": (published or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
            "summary": clean_text(el.findtext("description")),
            "categories": [c for c in categories if c.lower() not in PAYWALL_CATEGORIES],
            "image": thumbnail(image),
            "_paywall": any(c.lower() in PAYWALL_CATEGORIES for c in categories),
            "_video_hint": enclosure_type.startswith("video") or media_video,
        })
    return items


def feed_reason(item):
    """Syy suodattaa juttu pelkän syötteen perusteella, tai None."""
    paywall = item.pop("_paywall", False)
    video_hint = item.pop("_video_hint", False)
    if video_hint:
        return "video: media-tyyppi"
    if VIDEO_TITLE.search(item["title"]):
        return "video: otsikko"
    if VIDEO_URL.search(item["link"]):
        return "video: osoite"
    if any(c.lower() in VIDEO_CATEGORIES for c in item["categories"]):
        return "video: kategoria"
    if paywall:
        return "maksullinen"
    return None


def topic_of(item):
    """Valitsee aiheen: ensin osastotason kategoria, sitten muut kategoriat lopusta alkaen."""
    overrides = SOURCE_TOPIC_OVERRIDES.get(item["source"], {})
    categories = [c.lower() for c in reversed(item.get("categories") or [])]
    sections = [c for c in categories if c in SECTION_CATEGORIES]
    sections.sort(key=lambda c: c == "kotimaa")  # tarkempi osasto (esim. kulttuuri) voittaa kotimaan
    for key in sections + categories:
        topic = overrides.get(key) or TOPIC_OF_CATEGORY.get(key)
        if topic:
            return topic
    return SOURCE_DEFAULT_TOPIC.get(item["source"], "muut")


def is_homicide(item):
    return bool(HOMICIDE.search(" ".join([item["title"], item["summary"], *(item.get("categories") or [])])))


# --- Juttusivut: koko teksti, isompi kuva, video- ja maksullisuustarkistus ----
#
# Teksti tallennetaan kappalelistana kevyttä markdownia: **lihavointi**, *kursiivi*,
# [linkki](url) ja "## " väliotsikon alussa. Upotetut videot, kuvat ja mainokset jätetään pois.

def json_after(html, marker):
    m = re.search(re.escape(marker) + r"\s*=\s*", html)
    if not m:
        return None
    obj, _ = json.JSONDecoder().raw_decode(html[m.end():])
    return obj


def og_image(html):
    m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


def soft(text):
    return text.replace("­", "").strip()


def drop_lead(paragraphs, summary):
    """Ensimmäinen kappale on usein ingressi, joka näytetään jo erikseen."""
    if paragraphs and clean_text(re.sub(r"\*+", "", paragraphs[0])) == summary:
        return paragraphs[1:]
    return paragraphs


def enrich_yle(item):
    html = fetch(item["link"])
    state = json_after(html, "window.__INITIAL__STATE__")
    article = (state or {}).get("pageData", {}).get("article") or {}
    if not article:
        return None
    main_media = [m.get("type") for m in article.get("mainMedia", [])]
    body_chars = article.get("meta", {}).get("characterCount", {}).get("body", 10**6)
    if article.get("meta", {}).get("analytics", {}).get("yle_contenttype", "article") != "article":
        return "video: Ylen sisältötyyppi"
    if main_media[:1] == ["video"] and body_chars < YLE_VIDEO_MAX_CHARS:
        return "video: Ylen videojuttu (päämedia video, vähän tekstiä)"
    if main_media:  # ilman päämediaa og:image on Ylen yleislogo
        item["hero"] = og_image(html)
        item["image"] = item["image"] or thumbnail(item["hero"])

    paragraphs = []
    for block in article.get("content", []):
        kind = block.get("type")
        if kind == "text" and block.get("text"):
            paragraphs.append(soft(block["text"]))
        elif kind == "heading" and block.get("level", 1) >= 2 and block.get("text"):
            paragraphs.append("## " + soft(block["text"]))
    item["content"] = drop_lead(paragraphs, item["summary"])
    return None


def kl_text(node):
    if node.get("name") == "text":
        return node.get("value", "")
    inner = "".join(kl_text(c) for c in node.get("children", []))
    href = node.get("attributes", {}).get("href")
    return f"[{inner}]({href})" if node.get("name") == "x-im/link" and href and inner else inner


def enrich_kl(item):
    html = fetch(item["link"])
    state = json_after(html, "window.__PRELOADED_STATE__") or {}
    uuid = item["id"].split(":", 1)[1]
    data = state.get("article", {}).get(uuid, {}).get("data") or {}
    if not data:
        return None
    body = data.get("body") or []
    has_video = any(n.get("name") == "alma/jw-video" for n in body)
    if data.get("isVideoOnly"):
        return "video: KL isVideoOnly"
    if (data.get("primaryCategory") or {}).get("slug", "").lower() in VIDEO_CATEGORIES:
        return "video: kategoria"
    if has_video and (data.get("wordCount") or 0) < KL_VIDEO_MAX_WORDS:
        return "video: KL videojuttu (vähän tekstiä)"
    if not data.get("freeArticle", False):
        return "maksullinen"

    item["hero"] = og_image(html)
    item["image"] = item["image"] or thumbnail(item["hero"])
    paragraphs = []
    for node in body:
        kind = node.get("attributes", {}).get("type")
        text = soft(kl_text(node))
        if not text:
            continue
        if kind == "body":
            paragraphs.append(text)
        elif kind in ("subheadline", "subheadline1", "subheadline2"):
            paragraphs.append("## " + text)
    item["content"] = paragraphs
    return None


SANOMA_MARKS = {"strong": "**", "leadin": "**", "em": "*", "endnote": "*"}


def sanoma_crumbs(crumbs):
    out = []
    for c in crumbs:
        text = c.get("content") or ""
        if not text.strip():
            out.append(text)
            continue
        if c.get("type") == "externalLink" and c.get("href"):
            text = f"[{text}]({c['href']})"
        for mark in c.get("marks", []):
            wrap = SANOMA_MARKS.get(mark)
            if wrap:
                lead = text[: len(text) - len(text.lstrip())]
                trail = text[len(text.rstrip()):]
                text = f"{lead}{wrap}{text.strip()}{wrap}{trail}"
        out.append(text)
    return soft("".join(out))


def enrich_sanoma(item):
    """HS ja Aamulehti (sama Sanoman julkaisualusta)."""
    html = fetch(item["link"])
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    asset = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("page", {}).get("assetData") or {}
    if asset.get("showPaywall") or asset.get("paidType") == "paid":
        return "maksullinen"
    if "video" in (asset.get("template") or "").lower() or asset.get("resourceType", "Article") != "Article":
        return "video: Sanoman sisältötyyppi"

    if item["image"] or asset.get("mainPicture"):  # muuten og:image on lehden logo
        item["hero"] = og_image(html)
        item["image"] = item["image"] or thumbnail(item["hero"])
    paragraphs = []
    for block in asset.get("splitBody", []):
        kind = block.get("type")
        if kind == "heading" and block.get("content"):
            paragraphs.append("## " + soft(block["content"]))
        elif kind == "paragraph":
            crumbs = block.get("crumbs", [])
            if crumbs and all("location" in c.get("marks", []) for c in crumbs):
                continue  # paikkakuntarivi ("Aamulehti")
            text = sanoma_crumbs(crumbs)
            if text:
                paragraphs.append(text)
    item["content"] = drop_lead(paragraphs, item["summary"])
    return None


class HasaParser(HTMLParser):
    """Poimii Hämeen Sanomien juttusivulta leipätekstin (div.diks-article__storyline)."""

    INLINE = {"strong": "**", "b": "**", "em": "*", "i": "*"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0          # div-syvyys storylinen sisällä, 0 = ulkona
        self.skip = 0           # script/style/mainos-syvyys
        self.block = None       # meneillään oleva p/h2/h3
        self.buf = []
        self.href = None
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if self.depth == 0:
            if tag == "div" and "diks-article__storyline" in cls:
                self.depth = 1
            return
        if tag == "div":
            self.depth += 1
            if self.skip or "ad" in cls.split("-") or "diks-display-ad" in cls:
                self.skip += 1
            return
        if tag in ("script", "style", "figure", "aside"):
            self.skip += 1
        if self.skip:
            return
        if tag in ("p", "h2", "h3"):
            self.block, self.buf = tag, []
        elif self.block and tag in self.INLINE:
            self.buf.append(self.INLINE[tag])
        elif self.block and tag == "a" and a.get("href", "").startswith("http"):
            self.href = a["href"]
            self.buf.append("[")

    def handle_endtag(self, tag):
        if self.depth == 0:
            return
        if tag == "div":
            if self.skip:
                self.skip -= 1
            self.depth -= 1
            return
        if tag in ("script", "style", "figure", "aside"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or not self.block:
            return
        if tag in self.INLINE:
            self.buf.append(self.INLINE[tag])
        elif tag == "a" and self.href:
            self.buf.append(f"]({self.href})")
            self.href = None
        elif tag == self.block:
            text = soft(re.sub(r"\s+", " ", "".join(self.buf)).replace("** **", " ").replace("****", ""))
            if text:
                self.paragraphs.append(("## " if tag != "p" else "") + text)
            self.block = None

    def handle_data(self, data):
        if self.depth and not self.skip and self.block:
            self.buf.append(data)


def enrich_hasa(item):
    html = fetch(item["link"])
    m = re.search(r'"isAccessibleForFree"\s*:\s*"?(true|false)', html, re.I)
    if m and m.group(1).lower() == "false":
        return "maksullinen"
    # og:image-kuvassa on lehden logo päällä, joten käytetään syötteen kuvaa isompana.
    item["hero"] = item["image"].replace("/LANDSCAPE_480/", "/LANDSCAPE_960/") if item["image"] else None
    parser = HasaParser()
    parser.feed(html)
    item["content"] = drop_lead(parser.paragraphs, item["summary"])
    return None


ENRICHERS = {"yle": enrich_yle, "kl": enrich_kl, "hs": enrich_sanoma, "al": enrich_sanoma, "hasa": enrich_hasa}


def enrich(item):
    fn = ENRICHERS.get(item["source"])
    if not fn:
        return None
    try:
        return fn(item)
    except Exception as e:  # juttusivun muutos ei saa kaataa koko ajoa
        print(f"  ! {item['link']}: {e}", file=sys.stderr)
        return None


# --- Pääohjelma -------------------------------------------------------------

def load_previous():
    """Edellinen tila: GitHub Actionsissa julkaistulta sivulta (PREVIOUS_URL), paikallisesti tiedostosta.

    news.json ei ole repossa, jotta poistetut jutut eivät jää julkiseen versiohistoriaan.
    """
    url = os.environ.get("PREVIOUS_URL")
    try:
        text = fetch(url) if url else OUT.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception as e:
        print(f"Ei edellistä tilaa ({e}), aloitetaan tyhjästä", file=sys.stderr)
        return {}


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=KEEP_HOURS)
    prev = load_previous()
    items = {i["id"]: i for i in prev.get("items", [])}
    excluded = dict(prev.get("excluded", {}))  # id -> {"reason", "title", "published"}

    def exclude(item, reason):
        items.pop(item["id"], None)
        excluded[item["id"]] = {"reason": reason, "title": item["title"], "published": item["published"]}

    new_items = []
    status = {}
    for source in SOURCES:
        feed_items = {}
        errors = []
        for url in source["urls"]:
            try:
                for item in parse_feed(source, fetch(url)):
                    feed_items.setdefault(item["id"], item)
            except Exception as e:
                print(f"! {source['name']} {url}: {e}", file=sys.stderr)
                errors.append(str(e)[:200])
        status[source["id"]] = {"ok": not errors, "count": len(feed_items)}
        if errors:
            status[source["id"]]["error"] = "; ".join(errors)

        for item in feed_items.values():
            if datetime.fromisoformat(item["published"]) < cutoff:
                continue  # aihesyötteissä on viikkojen takaisia juttuja
            if not source.get("recheck"):
                if item["id"] in excluded:
                    continue
                if item["id"] in items:
                    # Päivitä otsikko ja ingressi (voivat muuttua), säilytä muut tiedot.
                    old = items[item["id"]]
                    old.update(title=item["title"], summary=item["summary"], image=item["image"] or old.get("image"))
                    continue
            reason = feed_reason(item)
            if reason:
                exclude(item, reason)
                continue
            new_items.append(item)

    with ThreadPoolExecutor(max_workers=8) as pool:
        reasons = list(pool.map(enrich, new_items))
    for item, reason in zip(new_items, reasons):
        if reason:
            exclude(item, reason)
        else:
            excluded.pop(item["id"], None)
            items[item["id"]] = item

    def fresh(published):
        return datetime.fromisoformat(published) >= cutoff

    kept = sorted((i for i in items.values() if fresh(i["published"])), key=lambda i: i["published"], reverse=True)
    kept = kept[:MAX_ITEMS]
    for item in kept:  # lasketaan joka ajolla, jotta sääntöjen muutokset koskevat myös vanhoja juttuja
        item["topic"] = topic_of(item)
        item["homicide"] = is_homicide(item)
    excluded = {k: v for k, v in excluded.items() if fresh(v["published"])}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": now.isoformat(timespec="seconds"),
        "sources": [{"id": s["id"], "name": s["name"]} for s in SOURCES],
        "topics": [{"id": t, "name": n} for t, n in TOPICS],
        "status": status,
        "items": kept,
        "excluded": excluded,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    reasons = {}
    for v in excluded.values():
        key = v["reason"].split(":")[0]
        reasons[key] = reasons.get(key, 0) + 1
    print(f"{len(new_items)} tarkistettu, {len(kept)} juttua, suodatettu: {reasons}")
    for s in SOURCES:
        print(f"  {s['name']}: {status[s['id']]}, näytetään {sum(1 for i in kept if i['source'] == s['id'])}")


if __name__ == "__main__":
    main()
