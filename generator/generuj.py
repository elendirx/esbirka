#!/usr/bin/env python3
"""Z dat v .cache/ vygeneruje git repozitář s historií předpisu.

Použití: generuj.py sb/1999/106

Historii předpisů postaví v dočasném repozitáři a podloží ji pod commity s kódem
na větvi main. Tag zakony-konec označuje poslední commit historie předpisů.

Formát souborů popisuje README.md ve vygenerovaném repozitáři.
"""
import datetime
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
AUTHOR = ("Sbírka zákonů", "sbirka@example.invalid")
HISTORY_TAG = "zakony-konec"
NEW_HISTORY = "refs/generator/nova-historie"
STRUCTURE_TYPES = {"Cast", "Hlava", "Dil", "Oddil", "Pododdil"}
README = """# Sbírka zákonů v gitu

Pilotní převod předpisů z [otevřených dat e-Sbírky](https://e-sbirka.gov.cz/open-data)
do gitu. Každý commit odpovídá jednomu znění k datu účinnosti.

Znění je převzaté z e-Sbírky a má informativní povahu; právně závazný je text
vyhlášený ve Sbírce zákonů.

## Formát

- `sb/<rok>/<číslo>.md` je celý předpis v Markdownu v pořadí ze zdroje.
- Části jsou nadpisy `##`, paragrafy nadpisy `###` s číslem a případným názvem.
- Jeden fragment je jedna položka seznamu. Hierarchii určují tabulátory relativně k paragrafu.
- Odkaz na poznámku pod čarou je zapsaný jako `[12]`.

## Procházení

```bash
git log --format='%ad %s' --date=short -- sb
git log -p --word-diff sb/1999/106.md
git log -L '/^### § 11 /,/^$/:sb/1999/106.md'
git blame sb/1999/106.md
```

Datum commitu je datum účinnosti. Tagy mají tvar `sb-1999-106/2025-08-19`.
"""


def clean(text):
    text = text or ""
    text = re.sub(r"<sup>([^<]+)</sup>\)", r"[\1]", text)
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def load(name):
    return json.loads((CACHE / name).read_text())


def ancestors(fragment, by_path):
    parent = by_path.get(fragment["predek"])
    while parent is not None:
        yield parent
        parent = by_path.get(parent["predek"])


def render(fragments):
    """Vrátí text jednoho znění a seznam varování."""
    by_path = {f["cesta"]: f for f in fragments}
    lines = []
    warnings = []
    section = None
    heading_target = None

    def add(line, gap=False):
        if gap and lines and lines[-1]:
            lines.append("")
        lines.append(line)

    for f in fragments:
        text = clean(f["text"])
        if not text:
            continue
        kind = f["typ"]
        current = "prefix" if kind.startswith("Prefix") else kind if kind in ("Postfix", "PPC") else "norma"
        new_section = current != section
        section = current
        if kind == "PPC":
            add("- " + text, gap=new_section)
        elif current != "norma":
            add(text, gap=True)
            lines.append("")
        elif kind in STRUCTURE_TYPES or kind in ("Paragraf", "Clanek"):
            add(("## " if kind in STRUCTURE_TYPES else "### ") + text, gap=True)
            heading_target = f["cesta"]
        elif kind == "Nadpis_pod" and f["predek"] == heading_target:
            lines[-1] += " " + text
            heading_target = None
        else:
            chain = list(ancestors(f, by_path))
            unit = next((a for a in chain if a["typ"] in ("Paragraf", "Clanek")), None)
            heading_target = None
            if unit is None:
                if kind != "Nadpis_pod":
                    warnings.append(f"fragment mimo paragraf: {kind} {f['cesta']}")
                add("## " + text, gap=True)
                continue
            if kind == "Nadpis_pod":
                warnings.append(f"nadpis uvnitř paragrafu: {f['cesta']}")
            depth = sum(1 for a in chain[:chain.index(unit)] if clean(a["text"]))
            add("\t" * depth + "- " + text)
    return "\n".join(lines).rstrip("\n") + "\n", warnings


class Novel:
    def __init__(self, act):
        slug = act.replace("/", "-")
        self.act = act
        self.fragments = load(f"novely/{slug}.json")
        self.by_path = {f["cesta"]: f for f in self.fragments}
        self.published = load(f"novely/{slug}.info.json")[0]["od"]
        _, year, number = act.split("/")
        self.code = f"{number}/{year} Sb."

    def _prefix(self, kind):
        return next((clean(f["text"]) for f in self.fragments if f["typ"] == kind), "")

    @property
    def title(self):
        kind = self._prefix("Prefix_Type").capitalize()
        author = self._prefix("Prefix_Author")
        name = self._prefix("Prefix_Title")
        head = " ".join(filter(None, [kind, author]))
        return f"{head} č. {self.code}" + (f", {name}" if name else "")

    def locate(self, path):
        """Zúží cestu z vazby na bod novely nebo nejbližší existující fragment."""
        match = re.match(r"(.*/bod_\d+[a-z]*)", path)
        if match and match[1] in self.by_path:
            return match[1]
        if path in self.by_path:
            return path
        parent = re.sub(r"/frag_\d+$", "", path)
        return parent if parent in self.by_path else None

    def text_of(self, path):
        lines = []
        root = self.by_path[path]
        for f in self.fragments:
            if f is root and f["typ"] in ("Clanek", "Paragraf"):
                continue
            if f is root or any(a is root for a in ancestors(f, self.by_path)):
                text = clean(f["text"])
                if text:
                    lines.append("    " + text)
        label = root["citace"] or "Text"
        return label, lines

    def transitional(self, paths):
        """Přechodná ustanovení ze stejné části novely jako její body."""
        parts = {m[1] for p in paths if (m := re.match(r"(novela/cast_\d+)/", p))}
        lines = []
        for f in self.fragments:
            if f["typ"] != "Nadpis_pod" or "řechodn" not in clean(f["text"]):
                continue
            if not any(f["cesta"].startswith(part + "/") for part in parts):
                continue
            article = self.by_path.get(f["predek"])
            if article is None:
                continue
            for child in self.fragments:
                if child is f or not any(a is article for a in ancestors(child, self.by_path)):
                    continue
                text = clean(child["text"])
                if text:
                    lines.append("    " + text)
        return lines


def attribution(act, versions):
    """Vrátí {datum znění: [(novela, [cesty], zdroj)]}."""
    slug = act.replace("/", "-")
    dates = {v["datum"] for v in versions}
    result, warnings = {}, []
    for link in load(f"{slug}/vazby.json"):
        match = re.match(r"eli/cz/(sb/\d+/\d+)/[^/]+/dokument/(.*)$", link["novela"])
        novel, path = match[1], match[2]
        if link["od"] not in dates:
            warnings.append(f"vazba bez znění: {link['od']} {link['novela']}")
            continue
        entry = result.setdefault(link["od"], {}).setdefault(novel, ([], "konsolidační vazby"))
        if path not in entry[0]:
            entry[0].append(path)
    supplement = json.loads((ROOT / "doplneni.json").read_text()).get(act, {})
    for date, items in supplement.items():
        for item in items:
            if date in result:
                warnings.append(f"doplnění přepisuje vazby: {date}")
            result.setdefault(date, {})[item["novela"]] = (item["cesty"], "ručně ověřené doplnění")
    return result, warnings


def commit_message(act, version, number, novels_here, seen_transitional, novels, note):
    parts = []
    trailers = [f"Účinnost-od: {version['ucinnost_od']}"]
    for act_novel, (paths, source) in novels_here.items():
        novel = novels[act_novel]
        located = []
        for path in paths:
            place = novel.locate(path)
            if place is None:
                note(f"bod nenalezen: {act_novel} {path}")
            elif place not in located:
                located.append(place)
        located.sort(key=lambda p: novel.by_path[p]["poradi"])
        located = [p for p in located
                   if not any(a["cesta"] in located
                              for a in ancestors(novel.by_path[p], novel.by_path))]
        blocks = []
        for place in located:
            label, lines = novel.text_of(place)
            blocks.append(f"{label}:\n" + "\n".join(lines))
        transitional = []
        if act_novel not in seen_transitional:
            seen_transitional.add(act_novel)
            transitional = novel.transitional(located)
        parts.append((novel, "\n\n".join(blocks), transitional))
        trailers += [f"Novela: {novel.code}", f"Vyhlášeno: {novel.published}",
                     f"Zdroj-bodů: {source}"]
    subject = "; ".join(novel.title for novel, _, _ in parts)
    points = "\n\n".join(body for _, body, _ in parts)
    notes = []
    for novel, _, transitional in parts:
        if transitional:
            suffix = f" ({novel.code})" if len(parts) > 1 else ""
            notes.append(f"Přechodná ustanovení{suffix}:\n" + "\n".join(transitional))
    trailers += [f"Znění: {number}", f"ELI: /eli/cz/{act}/{version['datum']}"]
    return subject, points, "\n\n".join(notes), trailers


def git(repo, *args, env=None):
    subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   cwd=repo, check=True, capture_output=True, text=True,
                   env={**os.environ, **(env or {})})


def write_version(repo, act, text):
    path = repo / f"{act}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def publish(build):
    """Nahradí historii předpisů novou a přenese nad ni commity s kódem."""
    project = ROOT.parent
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=project, check=True,
                           capture_output=True, text=True).stdout
    if dirty:
        sys.exit("Repozitář obsahuje necommitnuté změny, nejdřív je commitněte.")
    git(project, "fetch", str(build), f"+main:{NEW_HISTORY}", "+refs/tags/*:refs/tags/*")
    git(project, "rebase", "--onto", NEW_HISTORY, HISTORY_TAG, "main")
    git(project, "tag", "-f", HISTORY_TAG, NEW_HISTORY)
    git(project, "update-ref", "-d", NEW_HISTORY)


def main():
    with tempfile.TemporaryDirectory() as build:
        generate(sys.argv[1], pathlib.Path(build))
        publish(build)


def generate(act, repo):
    slug = act.replace("/", "-")
    today = datetime.date.today().isoformat()
    versions = [v for v in load(f"{slug}/zneni.json") if v["ucinnost_od"] <= today]
    links, warnings = attribution(act, versions)
    novels = {name: Novel(name) for items in links.values() for name in items}
    _, year, number = act.split("/")
    code = f"{number}/{year} Sb."

    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", AUTHOR[0])
    git(repo, "config", "user.email", AUTHOR[1])
    (repo / "README.md").write_text(README)

    previous, previous_date, skipped = None, None, 0
    seen_transitional = set()
    version_number = 0
    fragments_first = load(f"{slug}/fragmenty/{versions[0]['datum']}.json")
    prefix = {f["typ"]: clean(f["text"]) for f in fragments_first}
    original_title = f"{prefix.get('Prefix_Type', '').capitalize()} č. {code}, {prefix.get('Prefix_Title', '')}"
    started = False

    for version in versions:
        fragments = load(f"{slug}/fragmenty/{version['datum']}.json")
        text, render_warnings = render(fragments)
        warnings += [f"{version['datum']}: {w}" for w in render_warnings]
        if version["typ"] == "KONSOL":
            version_number += 1
        novels_here = links.get(version["datum"], {})
        date = version["ucinnost_od"]
        tag = f"{slug}/{version['datum']}"
        notes = ""

        if version["typ"] == "VYHLZNE":
            subject = f"{original_title} (vyhlášené znění)"
            trailers = [f"Vyhlášeno: {date}", f"ELI: /eli/cz/{act}"]
        elif not novels_here and text == previous and date == previous_date:
            skipped += 1
            git(repo, "tag", tag)
            continue
        elif not novels_here and text == previous and not started:
            started = True
            subject = f"Nabytí účinnosti zákona č. {code}"
            trailers = [f"Účinnost-od: {date}", f"Znění: {version_number}",
                        f"ELI: /eli/cz/{act}/{version['datum']}"]
        elif not novels_here:
            warnings.append(f"{version['datum']}: změna bez dohledané novely")
            subject = f"Změna znění účinná od {date} (novela nedohledána)"
            trailers = [f"Účinnost-od: {date}", f"Znění: {version_number}",
                        f"ELI: /eli/cz/{act}/{version['datum']}"]
        else:
            subject, _, notes, trailers = commit_message(
                act, version, version_number, novels_here, seen_transitional, novels,
                lambda w: warnings.append(f"{version['datum']}: {w}"))
        if text == previous and novels_here:
            warnings.append(f"{version['datum']}: novela bez změny textu")

        write_version(repo, act, text)
        git(repo, "add", "-A")
        stamp = f"{date}T00:00:00+01:00"
        message = "\n\n".join(filter(None, [subject, notes, "\n".join(trailers)]))
        git(repo, "commit", "--allow-empty", "-m", message,
            env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
        git(repo, "tag", tag)
        previous, previous_date = text, date

    print(f"{act}: {len(versions)} znění, přeskočeno shodných {skipped}")
    for warning in warnings:
        print("VAROVÁNÍ:", warning)


if __name__ == "__main__":
    main()
