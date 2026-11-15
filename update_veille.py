#!/usr/bin/env python3
"""Met à jour veille.json à partir de flux RSS (bibliothèque standard uniquement)."""
import json, re, sys, html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

OUT = "veille.json"
MAX_ITEMS = 60

# (nom affiché, URL du flux, catégorie fixe ou None = classement par mots-clés)
FEEDS = [
    ("CERT-FR", "https://www.cert.ssi.gouv.fr/alerte/feed/", "Alertes CERT-FR"),
    ("IT-Connect", "https://www.it-connect.fr/feed/", None),
    ("ZATAZ", "https://www.zataz.com/feed/", None),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", None),
]

KEYWORDS = [
    ("Sauvegardes", ["sauvegarde", "backup", "restauration", "immuable", "3-2-1", "pra ", "plan de reprise"]),
    ("Ransomwares", ["ransomware", "rançongiciel", "rancongiciel", "lockbit", "qilin", "akira", "ransomhub", "double extorsion"]),
    ("Réglementation", ["nis2", "nis 2", "dora", "rgpd", "cyber resilience act", "loi de programmation"]),
]

def classify(text):
    t = text.lower()
    for cat, words in KEYWORDS:
        if any(w in t for w in words):
            return cat
    return None

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

def parse(xml_bytes, source, fixed_cat):
    root = ET.fromstring(xml_bytes)
    out = []
    for it in list(root.iter("item")) + list(root.iter("{http://www.w3.org/2005/Atom}entry")):
        def g(tag):
            e = it.find(tag)
            if e is None:
                e = it.find("{http://www.w3.org/2005/Atom}" + tag)
            return e
        t, l, d, p = g("title"), g("link"), g("description"), g("pubDate")
        if d is None: d = g("summary")
        if p is None: p = g("updated")
        title = clean(t.text if t is not None else "", 160)
        link = (l.text or l.get("href") or "").strip() if l is not None else ""
        summary = clean(d.text if d is not None else "")
        if not title or not link.startswith("http"):
            continue
        cat = fixed_cat or classify(title + " " + summary)
        if not cat:
            continue
        out.append({"category": cat, "title": title, "summary": summary, "link": link,
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
    new = []
    for source, url, cat in FEEDS:
        try:
            new += parse(fetch(url), source, cat)
        except Exception as e:           # un flux en panne ne bloque pas les autres
            print(f"[ignoré] {source}: {e}", file=sys.stderr)
    seen, items = set(), []
    for it in new + old:                 # les nouveaux d'abord, on garde l'historique
        if it["link"] in seen:
            continue
        seen.add(it["link"]); items.append(it)
    items.sort(key=lambda x: x.get("date") or "0000", reverse=True)
    data = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "items": items[:MAX_ITEMS]}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(new)} article(s) lus, {len(data['items'])} conservé(s)")

if __name__ == "__main__":
    main()
