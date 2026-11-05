#!/usr/bin/env python3
"""Stáhne znění předpisu, jeho konsolidační vazby a novely z SPARQL open dat e-Sbírky.

Použití: stahni.py sb/1999/106

Výsledek ukládá do .cache/, generuj.py už pak síť nepotřebuje.
"""
import json
import pathlib
import re
import subprocess
import sys

ENDPOINT = "https://opendata.eselpoint.gov.cz/sparql"
BASE = "https://opendata.eselpoint.gov.cz/esel-esb/"
PREFIX = "PREFIX s: <https://slovník.gov.cz/datový/sbírka/pojem/>\n"
ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / ".cache"


def sparql(query):
    # curl místo urllib: urllib na tomto endpointu končí chybou IncompleteRead
    out = subprocess.run(
        ["curl", "-sS", "-m", "180", "-G", ENDPOINT,
         "--data-urlencode", "query=" + PREFIX + query,
         "-H", "Accept: application/sparql-results+json"],
        capture_output=True, text=True, check=True)
    rows = json.loads(out.stdout)["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def short(iri):
    return iri.removeprefix(BASE)


def cached(name, fetch):
    path = CACHE / name
    if path.exists():
        return json.loads(path.read_text())
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=0))
    return data


def fetch_versions(act):
    rows = sparql(f"""SELECT ?z ?od ?typ WHERE {{
      <{BASE}eli/cz/{act}> s:má-znění ?z .
      ?z s:účinnost-znění-od ?od ; s:má-typ-znění-právního-aktu ?typ .
    }}""")
    return sorted(
        ({"datum": short(r["z"]).rsplit("/", 1)[1], "ucinnost_od": r["od"],
          "typ": r["typ"].rsplit("/", 1)[1]} for r in rows),
        key=lambda v: v["datum"])


def fetch_fragments(act, date):
    rows = sparql(f"""SELECT ?f ?poradi ?citace ?predek ?typ ?text WHERE {{
      <{BASE}eli/cz/{act}/{date}> s:má-fragment-znění ?f .
      ?f s:pořadí-fragmentu-znění-právního-aktu ?poradi ;
         s:obsahuje-fragment ?pf .
      ?pf s:má-typ-fragmentu ?typ .
      OPTIONAL {{ ?f s:citace-označení-fragmentu-znění-právního-aktu ?citace }}
      OPTIONAL {{ ?f s:má-předka ?predek }}
      OPTIONAL {{ ?pf s:text-fragmentu ?text }}
    }}""")
    prefix = f"eli/cz/{act}/{date}/dokument"
    fragments = []
    for r in rows:
        fragments.append({
            "cesta": short(r["f"]).removeprefix(prefix).lstrip("/"),
            "poradi": r["poradi"],
            "typ": r["typ"].rsplit("/", 1)[1],
            "citace": r.get("citace"),
            "predek": short(r["predek"]).removeprefix(prefix).lstrip("/") if "predek" in r else None,
            "text": r.get("text"),
        })
    return sorted(fragments, key=lambda f: f["poradi"])


def fetch_links(act):
    links = {}
    for role in ("má-cíl", "má-zdroj"):
        rows = sparql(f"""SELECT ?v ?novela ?instrukce ?od ?f WHERE {{
          <{BASE}eli/cz/{act}> s:má-znění ?z .
          ?z s:má-fragment-znění ?f .
          ?v s:{role} ?f ; s:má-fragment-novely ?novela ;
             s:má-typ-novelizační-instrukce ?instrukce ;
             s:má-účinnost-konsolidační-vazby-od ?od .
        }}""")
        for r in rows:
            link = links.setdefault(r["v"], {
                "novela": short(r["novela"]),
                "instrukce": r["instrukce"].rsplit("/", 1)[1],
                "od": r["od"],
            })
            link["cil" if role == "má-cíl" else "zdroj"] = short(r["f"])
    return sorted(links.values(), key=lambda l: (l["od"], l["novela"]))


def main():
    act = sys.argv[1]
    slug = act.replace("/", "-")
    versions = cached(f"{slug}/zneni.json", lambda: fetch_versions(act))
    print(f"{act}: {len(versions)} znění")
    for v in versions:
        cached(f"{slug}/fragmenty/{v['datum']}.json",
               lambda: fetch_fragments(act, v["datum"]))
    links = cached(f"{slug}/vazby.json", lambda: fetch_links(act))
    print(f"vazby: {len(links)}")

    supplement = json.loads((ROOT / "doplneni.json").read_text()).get(act, {})
    novels = {re.match(r"eli/cz/(sb/\d+/\d+)/", l["novela"]).group(1) for l in links}
    novels |= {item["novela"] for items in supplement.values() for item in items}
    for novel in sorted(novels):
        fragments = cached(f"novely/{novel.replace('/', '-')}.json",
                           lambda: fetch_fragments(novel, "0000-00-00"))
        info = cached(f"novely/{novel.replace('/', '-')}.info.json",
                      lambda: sparql(f"""SELECT ?od WHERE {{
                        <{BASE}eli/cz/{novel}/0000-00-00> s:účinnost-znění-od ?od }}"""))
        print(f"{novel}: {len(fragments)} fragmentů, vyhlášeno {info[0]['od'] if info else '?'}")


if __name__ == "__main__":
    main()
