#!/usr/bin/env python3
"""Met à jour veille.json : veille uniquement sur les sauvegardes informatiques.
Bibliothèque standard uniquement."""
import json, re, sys, html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

OUT = "veille.json"
MAX_ITEMS = 60

# (nom affiché, URL du flux RSS). Un flux en panne est simplement ignoré.
FEEDS = [
    ("CERT-FR", "https://www.cert.ssi.gouv.fr/avis/feed/"),
    ("CERT-FR", "https://www.cert.ssi.gouv.fr/alerte/feed/"),
    ("IT-Connect", "https://www.it-connect.fr/feed/"),
    ("LeMagIT", "https://www.lemagit.fr/rss/ALL.xml"),
    ("Le Monde Informatique", "https://www.lemondeinformatique.fr/flux-rss/thematique/toutes-les-actualites/rss.xml"),
    ("Vladan", "https://www.vladan.fr/feed/"),
]

# Un article n'est gardé que s'il parle de sauvegarde (termes + éditeurs de logiciels de sauvegarde)
KEYWORDS = [
    "sauvegarde", "backup", "3-2-1", "immuable", "plan de reprise", "pra ",
    "veeam", "commvault", "veritas", "netbackup", "backup exec", "acronis", "cohesity",
    "rubrik", "nakivo", "arcserve", "bacula", "bareos", "duplicati", "active backup",
]

def is_backup(text):
    t = text.lower()
    return any(k in t for k in KEYWORDS)

def clean(s, n=220):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"

def to_date(s):
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s.strip())
        return m.group(1) if m else ""

def parse(xml_bytes, source):
    root = ET.fromstring(xml_bytes)
    out = []
    atom = "{http://www.w3.org/2005/Atom}"
    for it in list(root.iter("item")) + list(root.iter(atom + "entry")):
        def g(tag):
            e = it.find(tag)
            return e if e is not None else it.find(atom + tag)
        t, l, d, p = g("title"), g("link"), g("description"), g("pubDate")
        if d is None: d = g("summary")
        if p is None: p = g("updated")
        title = clean(t.text if t is not None else "", 160)
        link = ((l.text or l.get("href") or "").strip()) if l is not None else ""
        summary = clean(d.text if d is not None else "")
        if not title or not link.startswith("http") or not is_backup(title + " " + summary):
            continue
        out.append({"category": "Sauvegardes", "title": title, "summary": summary, "link": link,
                    "date": to_date(p.text if p is not None else ""), "source": source})
    return out

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "veille-portfolio/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def main():
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("items", [])
    except Exception:
        old = []
    # on garde l'historique, mais uniquement ce qui parle de sauvegarde
    old = [o for o in old if is_backup(o.get("title", "") + " " + o.get("summary", ""))]
    new = []
    for source, url in FEEDS:
        try:
            got = parse(fetch(url), source)
            print(f"[ok] {source} ({url}) : {len(got)} article(s) sur les sauvegardes")
            new += got
        except Exception as e:           # un flux en panne ne bloque pas les autres
            print(f"[ignoré] {source} ({url}) : {e}", file=sys.stderr)
    seen, items = set(), []
    for it in new + old:
        if it["link"] in seen:
            continue
        seen.add(it["link"]); items.append(it)
    items.sort(key=lambda x: x.get("date") or "0000", reverse=True)
    dates = [i["date"] for i in items if i.get("date")]
    data = {"updated": max(dates) if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "items": items[:MAX_ITEMS]}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(new)} nouveau(x) lu(s), {len(data['items'])} conservé(s)")

if __name__ == "__main__":
    main()
