# Sbírka zákonů v gitu

Pilotní převod předpisů z [otevřených dat e-Sbírky](https://e-sbirka.gov.cz/open-data)
do gitu. Vyhlášení změnového předpisu a změny předpisu k datům účinnosti jsou samostatné commity.

Znění je převzaté z e-Sbírky a má informativní povahu; právně závazný je text
vyhlášený ve Sbírce zákonů.

## Formát

- `sb/<rok>/<číslo>.txt` je celý předpis v pořadí ze zdroje.
- Jeden fragment je jeden řádek. Hierarchii určují tabulátory relativně k paragrafu.
- První řádek paragrafu obsahuje jeho číslo a případný nadpis. Paragrafy odděluje prázdný řádek.
- Změnový předpis je uložený ve vyhlášeném znění. Přidává se k datu vyhlášení a dál se nemění.
  Se změnami předpisu k datům účinnosti ho spojuje řádek `Novela:` ve zprávě commitu.
- Odkaz na poznámku pod čarou je zapsaný jako `[12]`.
- Tabulka je zapsaná jako pole JSON odsazené mezerami. Má-li hlavičku, je řádek objektem
  s názvy sloupců, jinak polem. Buňka překrytá sloučenou buňkou má hodnotu `null`.

## Procházení

```bash
git log --format='%ad %s' --date=short -- sb
git log -p --word-diff sb/1999/106.txt
git log -L '/^§ 11 /,/^$/:sb/1999/106.txt'
git blame sb/1999/106.txt
```

Commity změnových předpisů mají datum vyhlášení, commity se změnou znění datum účinnosti.
Tagy znění mají tvar `sb-1999-106/2025-08-19`. Všechny commity jedné novely najde:

```bash
git log --grep='^Novela: 241/2022 Sb\.$'
```
