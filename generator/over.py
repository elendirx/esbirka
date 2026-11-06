#!/usr/bin/env python3
"""Ověří vygenerovanou historii proti zdroji.

Použití: over.py sb/1999/106 [--web]

Kontroluje úplnost textu v každém tagu, hierarchii, to, že body novely v commitu
odpovídají změněným paragrafům, a s --web i shodu se znění na webu e-Sbírky.
"""
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from generuj import HISTORY_TAG, ROOT, Novel, attribution, clean, commit_message, load

REPO = ROOT.parent
WEB = "https://e-sbirka.gov.cz/sbr-cache/dokumenty-sbirky/"


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout


def law_text(rev, act):
    return git("show", f"{rev}:{act}.txt")


def units(text):
    """Rozdělí text na paragrafy podle prázdných řádků."""
    blocks = {}
    for block in text.split("\n\n"):
        match = re.match(r"§ (\d+[a-z]*)", block)
        if match:
            blocks[match[1]] = block
    return blocks


def check_text(act, slug, versions):
    bad = 0
    for v in versions:
        text = law_text(f"{slug}/{v['datum']}", act)
        body = Counter(line.strip() for line in text.splitlines() if line.strip())
        fragments = load(f"{slug}/fragmenty/{v['datum']}.json")
        missing = []
        for f in fragments:
            content = clean(f["text"])
            if not content:
                continue
            if f["typ"] in ("Cast", "Paragraf", "Nadpis_pod"):
                if content not in text:
                    missing.append(f["cesta"])
            elif body[content] > 0:
                body[content] -= 1
            else:
                missing.append(f["cesta"])
        extra = [k for k, c in body.items()
                 if c > 0 and not re.match(r"§ \d|ČÁST ", k)]
        if missing or extra:
            bad += 1
            print(f"  {v['datum']}: chybí {missing[:3]}, navíc {extra[:3]}")
    print(f"text: {len(versions) - bad}/{len(versions)} znění bez rozdílu")


def check_levels(act, slug, versions):
    wrong = Counter()
    lines = 0
    for v in versions:
        for line in law_text(f"{slug}/{v['datum']}", act).splitlines():
            if not line.startswith("\t"):
                continue
            lines += 1
            depth = len(line) - len(line.lstrip("\t"))
            content = line.strip()
            if re.match(r"\(\d+[a-z]?\) ", content) and depth != 1:
                wrong[("odstavec", content[:50])] += 1
            elif re.match(r"[a-z]\) ", content) and depth != 2:
                wrong[("písmeno", content[:50])] += 1
            elif re.match(r"\d+\. ", content) and depth < 2:
                wrong[("bod", content[:50])] += 1
    print(f"hierarchie: {lines} řádků, neočekávaná úroveň: {len(wrong)}")
    for key in list(wrong)[:8]:
        print("  ", key)


def novel_points(act, versions):
    """Vrátí {datum znění: text bodů novely}, zprávy commitů je neobsahují."""
    links, _ = attribution(act, versions)
    novels = {name: Novel(name) for items in links.values() for name in items}
    seen = set()
    points = {}
    for number, version in enumerate(versions):
        if version["datum"] in links:
            _, body, _, _ = commit_message(act, version, number, links[version["datum"]],
                                           seen, novels, lambda warning: None)
            points[version["datum"]] = body
    return points


def changed_units(commit, act):
    before = units(law_text(f"{commit}~1", act))
    after = units(law_text(commit, act))
    return [ref for ref in sorted(before.keys() | after.keys())
            if before.get(ref) != after.get(ref)]


def check_attribution(act, slug, points):
    commits = git("log", "--reverse", "--format=%H", HISTORY_TAG).split()
    total = covered = 0
    sources = Counter()
    for commit in commits[1:]:
        message = git("show", "-s", "--format=%B", commit)
        match = re.search(r"Účinnost-od: (\S+)", message)
        if match is None:
            continue
        date = match[1]
        for source in re.findall(r"Zdroj-bodů: (.+)", message):
            sources[source] += 1
        for ref in changed_units(commit, act):
            total += 1
            if re.search(rf"§ {ref}\b|§ {ref}[a-z]?\b|§§ ", points.get(date, "")):
                covered += 1
            else:
                print(f"  {date}: § {ref} změněn, v bodech novely nezmíněn")
    print(f"původ změn: {covered}/{total} změněných paragrafů je zmíněno v bodech novely")
    print(f"zdroje bodů: {dict(sources)}")


def check_quotes(act, slug, points):
    """Text v uvozovkách, který novela vkládá, musí po commitu v zákoně existovat."""
    found = missing = 0
    for commit in git("log", "--reverse", "--format=%H", HISTORY_TAG).split()[1:]:
        message = git("show", "-s", "--format=%B", commit)
        match = re.search(r"Účinnost-od: (\S+)", message)
        if match is None:
            continue
        date = match[1]
        body = points.get(date, "")
        plain = re.sub(r"\s+", " ", law_text(commit, act))
        for quote in re.findall(r"(?:vkládá|vkládají|nahrazuje|nahrazují|doplňuje|doplňují)[^„\n]*(?:slov[oay]|text|číslo)[^„\n]*„([^“\n]{4,})“", body):
            if re.sub(r"\s+", " ", quote).strip() in plain:
                found += 1
            else:
                missing += 1
                print(f"  {date}: nenalezeno „{quote[:70]}“")
    print(f"vložený text: {found} nalezeno, {missing} nenalezeno")


def check_novels(act, slug, versions):
    links, _ = attribution(act, versions)
    first = {}
    for version in versions:
        for name in links.get(version["datum"], {}):
            first.setdefault(name, version["datum"])
    bad = 0
    for name, date in first.items():
        revisions = git("log", "--format=%H", HISTORY_TAG, "--", f"{name}.txt").split()
        insertion = revisions[-1]
        changed = git("show", "--format=", "--name-only", insertion).split()
        commit_date = git("log", "-1", "--format=%ad", "--date=short", insertion).strip()
        fragments = load(f"novely/{name.replace('/', '-')}.json")
        text = law_text(f"{slug}/{date}", name)
        missing = [f["cesta"] for f in fragments
                   if clean(f["text"]) and clean(f["text"]) not in text]
        if (changed != [f"{name}.txt"] or commit_date != Novel(name).published
                or missing or len(revisions) != 1):
            bad += 1
            print(f"  {name}: změněno {changed[:3]}, datum {commit_date}, "
                  f"chybí {missing[:2]}, verzí {len(revisions)}")
    print(f"novely: {len(first) - bad}/{len(first)} vložené samostatně k datu vyhlášení, text úplný")


def check_links(act, slug, versions):
    """Každá změna znění musí mít svou novelu vloženou dřív nebo ve stejný den."""
    links, _ = attribution(act, versions)
    bad = 0
    for date, items in links.items():
        tag = f"{slug}/{date}"
        for name in items:
            _, year, number = name.split("/")
            found = git("log", "--format=%h", tag, "--fixed-strings",
                        f"--grep=Novela: {number}/{year} Sb.").split()
            if len(found) < 2:
                bad += 1
                print(f"  {date} {name}: nalezeno {found}")
    print(f"vazby: {bad} změn bez dohledatelné novely")


def check_order():
    dates = git("log", "--reverse", "--format=%ad", "--date=short", HISTORY_TAG).split()
    print(f"chronologie: {len(dates)} commitů, " + ("seřazeno" if dates == sorted(dates) else "NESEŘAZENO"))


def check_web(slug, act, versions):
    same = different = 0
    for v in versions:
        if v["datum"] == "0000-00-00":
            continue
        url = WEB + urllib.parse.quote(f"/{act}/{v['datum']}", safe="") + "/fragmenty?cisloStranky=0"
        out = subprocess.run(["curl", "-sS", "-m", "60", url], capture_output=True, text=True, check=True)
        web = Counter(clean(f.get("xhtml")) for f in json.loads(out.stdout)["seznam"])
        ours = Counter(clean(f["text"]) for f in load(f"{slug}/fragmenty/{v['datum']}.json"))
        web.pop("", None)
        ours.pop("", None)
        if web == ours:
            same += 1
        else:
            different += 1
            print(f"  {v['datum']}: rozdíl {list((web - ours))[:2]} / {list((ours - web))[:2]}")
    print(f"web: {same} znění shodných, {different} rozdílných")


def main():
    act = sys.argv[1]
    slug = act.replace("/", "-")
    versions = load(f"{slug}/zneni.json")
    check_text(act, slug, versions)
    check_levels(act, slug, versions)
    points = novel_points(act, versions)
    check_attribution(act, slug, points)
    check_quotes(act, slug, points)
    check_novels(act, slug, versions)
    check_links(act, slug, versions)
    check_order()
    if "--web" in sys.argv:
        check_web(slug, act, versions)


if __name__ == "__main__":
    main()
