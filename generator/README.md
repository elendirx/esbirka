# Generátor historie předpisů

Převádí předpisy z otevřených dat e-Sbírky do historie tohoto repozitáře. Vše je na větvi
`main`: nejdřív commity předpisů s daty účinnosti, nad nimi commity s kódem a daty.
Tag `zakony-konec` označuje poslední commit historie předpisů.

```bash
python3 stahni.py sb/1999/106
python3 generuj.py sb/1999/106
python3 over.py sb/1999/106 --web
```

- `stahni.py` stáhne data ze SPARQL endpointu do `.cache/`, která je součástí repozitáře.
- `generuj.py` z cache znovu vytvoří historii předpisů a přenese nad ni commity s kódem.
  Mění tím hashe, takže po změně historie je potřeba force push. Před spuštěním musí být
  všechny změny commitnuté.
  Stejná data dají stejné hashe commitů.
- `over.py` ověří výsledek proti zdroji. Volba `--web` navíc porovná text s webem e-Sbírky.
- `doplneni.json` obsahuje ručně ověřené novely pro znění, u kterých v datech chybí
  konsolidační vazby. Commity z něj mají `Zdroj-bodů: ručně ověřené doplnění`.
