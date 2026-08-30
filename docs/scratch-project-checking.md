# Scratch-Projektpruefung

## Entscheidung

ScratchLab prueft Scratch-Aufgaben ueber hochgeladene `.sb3`-Dateien. Dadurch muessen keine Scratch-Logins, Scratch-Passwoerter oder privaten Scratch-Kontodaten gespeichert werden.

## Technischer Hintergrund

Eine `.sb3`-Datei ist ein ZIP-Archiv mit einer `project.json`. Die Scratch-VM repraesentiert Programme intern ueber Blockdaten mit `opcode`, Feldern, Inputs und Target-Strukturen. Der Scratch-Parser stellt Schema-Definitionen fuer Scratch-3-Projekte bereit.

## MVP-Pruefung

Die API `/api/projects/check` nimmt eine Base64-codierte `.sb3`-Datei entgegen, analysiert:

- verwendete Block-OpCodes
- Variablen
- Listen
- Broadcasts
- Anzahl Targets/Figuren

Danach vergleicht sie die gefundenen OpCodes mit den `required_opcodes` der jeweiligen Lektion.

Beispiel-Ergebnis:

```text
2 von 2 Anforderungen erfuellt.
```

## Grenzen

Diese Pruefung erkennt wichtige Strukturmerkmale, aber noch nicht jedes Verhalten zur Laufzeit. Spaeter kann ScratchLab die Analyse erweitern, zum Beispiel um Blockketten, Werte in Feldern, Reihenfolge von Skripten und einfache Simulationen.

## Quellen

- Scratch VM: https://github.com/scratchfoundation/scratch-vm
- Scratch Parser: https://github.com/scratchfoundation/scratch-parser
