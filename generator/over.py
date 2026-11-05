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
from generuj import HISTORY_TAG, ROOT, clean, load

REPO = ROOT.parent
WEB = "https://e-sbirka.gov.cz/sbr-cache/dokumenty-sbirky/"


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout


def tree_text(tag, act):
    names = git("ls-tree", "-r", "--name-only", tag, act).split()
    return {n.rsplit("/", 1)[1]: git("show", f"{tag}:{n}") for n in names}


def check_text(act, slug, versions):
    bad = 0
    for v in versions:
        tag = f"{slug}/{v['datum']}"
        files = tree_text(tag, act)
        body = Counter()
        for name, text in files.items():
            if name == "_osnova.txt":
                continue
            for i, line in enumerate(text.splitlines()):
                body[line.strip()] += 1
        missing = []
        for f in load(f"{slug}/fragmenty/{v['datum']}.json"):
            text = clean(f["text"])
            if not text or f["typ"] in ("Cast", "Paragraf", "Nadpis_pod"):
                continue
            if body[text] > 0:
                body[text] -= 1
            else:
                missing.append(f["cesta"])
        headings = [clean(f["text"]) for f in load(f"{slug}/fragmenty/{v['datum']}.json")
                    if f["typ"] == "Nadpis_pod"]
        everything = "\n".join(files.values())
        missing += [h for h in headings if h not in everything]
        extra = [k for k, c in body.items() if c > 0 and not re.match(r"§ \d", k)]
        if missing or extra:
            bad += 1
            print(f"  {v['datum']}: chybí {missing[:3]}, navíc {extra[:3]}")
    print(f"text: {len(versions) - bad}/{len(versions)} znění bez rozdílu")


def check_levels(act, slug, versions):
    wrong = Counter()
    lines = 0
    for v in versions:
        for name, text in tree_text(f"{slug}/{v['datum']}", act).items():
            if not name.startswith("par-"):
                continue
            for line in text.splitlines()[1:]:
                lines += 1
                depth = len(line) - len(line.lstrip("\t"))
                content = line.strip()
                if re.match(r"\(\d+[a-z]?\) ", content) and depth != 1:
                    wrong[("odstavec", name, content[:50])] += 1
                elif re.match(r"[a-z]\) ", content) and depth != 2:
                    wrong[("písmeno", name, content[:50])] += 1
                elif re.match(r"\d+\. ", content) and depth < 2:
                    wrong[("bod", name, content[:50])] += 1
    print(f"hierarchie: {lines} řádků, neočekávaná úroveň: {len(wrong)}")
    for key in list(wrong)[:8]:
        print("  ", key)


def changed_units(commit):
    out = git("show", "--format=", "--name-only", commit)
    return [n.rsplit("/", 1)[1] for n in out.split() if "/par-" in n]


def check_attribution(act, slug):
    commits = git("log", "--reverse", "--format=%H", HISTORY_TAG).split()
    total = covered = 0
    sources = Counter()
    for commit in commits[1:]:
        message = git("show", "-s", "--format=%B", commit)
        date = re.search(r"Účinnost-od: (\S+)", message)[1]
        for source in re.findall(r"Zdroj-bodů: (.+)", message):
            sources[source] += 1
        for unit in changed_units(commit):
            total += 1
            match = re.match(r"par-0*(\d+)([a-z]*)\.txt", unit)
            ref = f"{match[1]}{match[2]}"
            if re.search(rf"§ {ref}\b|§ {ref}[a-z]?\b|§§ ", message):
                covered += 1
            else:
                print(f"  {date}: {unit} změněn, v bodech novely nezmíněn")
    print(f"původ změn: {covered}/{total} změněných paragrafů je zmíněno v bodech novely")
    print(f"zdroje bodů: {dict(sources)}")


def check_quotes(act, slug):
    """Text v uvozovkách, který novela vkládá, musí po commitu v zákoně existovat."""
    found = missing = 0
    for commit in git("log", "--reverse", "--format=%H", HISTORY_TAG).split()[1:]:
        message = git("show", "-s", "--format=%B", commit)
        date = re.search(r"Účinnost-od: (\S+)", message)[1]
        body = message.split("Přechodná ustanovení:")[0]
        tree = "\n".join(tree_text(commit, act).values())
        plain = re.sub(r"\s+", " ", tree)
        for quote in re.findall(r"(?:vkládá|vkládají|nahrazuje|nahrazují|doplňuje|doplňují)[^„\n]*(?:slov[oay]|text|číslo)[^„\n]*„([^“\n]{4,})“", body):
            if re.sub(r"\s+", " ", quote).strip() in plain:
                found += 1
            else:
                missing += 1
                print(f"  {date}: nenalezeno „{quote[:70]}“")
    print(f"vložený text: {found} nalezeno, {missing} nenalezeno")


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
    check_attribution(act, slug)
    check_quotes(act, slug)
    if "--web" in sys.argv:
        check_web(slug, act, versions)


if __name__ == "__main__":
    main()
