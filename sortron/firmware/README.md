# Sortron – getrennte Steuerungsarchitektur

Die Website und die Arduino-Firmware sind zwei getrennte Programme.

- `software.html` enthält Oberfläche, Kamera und Teachable-Machine-Erkennung.
- `js/sortron-ble.js` enthält ausschließlich die Bluetooth-Verbindung und das Senden der Sortierbefehle.
- Die Mini-R4-Firmware bleibt auf dem Board und verarbeitet die Befehle.

## BLE-Protokoll (V6, unverändert)

- Gerätename: `MiniR4 Sorter`
- Service: `19b10000-e8f2-537e-4f6c-d104768a1214`
- Characteristic: `19b10001-e8f2-537e-4f6c-d104768a1214`
- Gesendet wird genau ein ASCII-Byte über `BLEByteCharacteristic`.

| Byte | Klasse |
|---|---|
| `'0'` | kein Sortierbefehl / Ausgangszustand |
| `'1'` | Papier |
| `'2'` | Plastik |
| `'3'` | Bio |
| `'4'` | Restmüll |

Die bestehende V6-Firmware wird durch diese Website-Änderung nicht überschrieben oder verändert.

## Browserhinweis

Die Browser-API Web Bluetooth ist nicht in jedem Browser verfügbar. Insbesondere iPad-Safari stellt sie nicht bereit. Die Website zeigt dafür eine verständliche Fehlermeldung, statt eine erfolgreiche Verbindung vorzutäuschen.
