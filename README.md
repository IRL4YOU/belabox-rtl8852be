# BELABOX RTL8852BE: neuer WLAN-Treiber und Bluetooth

**0.1.0-test1 · Experimentelle Vorabversion · Keine Produktivfreigabe**

Ein Nachrüstpaket von IRL4YOU für die **ROCK 5B Plus** mit BELABOX-Kernel `5.10.160-belabox`. Es ersetzt den eingebauten
Realtek-Herstellertreiber (Stand Mai 2022) für den WLAN-Chip RTL8852BE durch den neueren Linux-Treiber **rtw89**
(Stand Juli 2025) und macht den **Bluetooth-Teil desselben Chips** nutzbar. Beides in einer Installation.
Kein offizielles Produkt von BELABOX, Radxa oder Realtek.

## Was wird behoben?

1. **WLAN:** Der eingebaute Treiber ist alt. Der neuere `rtw89`-Treiber ist für Kernel ab 5.15 geschrieben und lässt sich
   auf 5.10 nicht unverändert bauen. Dieses Paket enthält ihn mit sechs kleinen Anpassungen (`patches/belabox-5.10-compat.patch`).
2. **Bluetooth:** Auf dem Board meldet sich der Bluetooth-Chip am allgemeinen Kerneltreiber `btusb` an. Der lädt für diesen Chip
   keine Firmware, der Controller zeigt `UP RUNNING`, empfängt aber nichts (Scan findet 0 Geräte). Das Paket hängt den Chip beim
   Start an den Realtek-Herstellertreiber `rtk_btusb`, der im BELABOX-Kernel schon vorhanden ist, und legt die Firmware-Verknüpfungen an,
   die er erwartet. Danach findet derselbe Scan viele Geräte.
3. **Kernel-Updates:** Nach einem Kernel-Update baut ein Start-Dienst den Treiber automatisch neu. Bis dahin läuft der eingebaute Treiber,
   sodass das WLAN nicht ausfällt.

## Voraussetzungen

- Radxa ROCK 5B Plus mit internem RTL8852BE (PCI `10ec:b852` oder `10ec:b85b`).
- Kernel genau `5.10.160-belabox` mit den Kernel-Baudateien unter `/lib/modules/5.10.160-belabox/build`.
- Firmware `rtw89/rtw8852b_fw-1.bin` und `rtl_bt/rtl8852bu_fw.bin` (liegen im BELABOX-Image).
- Werkzeuge: Python 3, make, gcc, ld, depmod, modinfo. Mindestens 1 GiB frei unter `/var/tmp`.
- LAN-Verbindung (der Zugang soll nicht vom WLAN abhängen) und die Möglichkeit, die Box neu zu starten.

Andere Kernel und andere Boards sind **nicht freigegeben**; das Paket lehnt sie ab.

## Installation

**Ausführliche Schritt-für-Schritt-Anleitung:** [ANLEITUNG.md](ANLEITUNG.md) (English: [ANLEITUNG.en.md](ANLEITUNG.en.md)). Kurzfassung:

Als root auf der Box, Paket entpacken und in den Ordner `belabox-rtw89` wechseln:

```sh
python3 rtw89ctl.py check
python3 rtw89ctl.py build --output /var/tmp/belabox-rtw89-build-1
python3 rtw89ctl.py install --build-dir /var/tmp/belabox-rtw89-build-1 --accept-experimental
reboot
```

- `check` prüft nur. `build` dauert einige Minuten und ändert nichts am laufenden System.
- `install` kopiert die vier Module, trägt sie ein, sperrt den eingebauten Treiber `8852be` und richtet den Bluetooth-Teil ein.
  Der laufende Treiber bleibt bis zum Neustart unverändert. Nur WLAN: `--no-bluetooth` anhängen.
- Nach dem Neustart: `python3 rtw89ctl.py status` zeigt den Zustand. Der WLAN-Chip hängt dann an `rtw89_8852be_git`,
  Bluetooth an `rtk_btusb`.

**WLAN-Schnittstelle:** Der neue Treiber legt eine Schnittstelle `wlan0` an (der alte `wlan1` und `wlan2`).
Gespeicherte Verbindungen, die fest an `wlan1` gebunden sind, müssen neu angelegt werden.

## Rückweg

```sh
python3 rtw89ctl.py uninstall
reboot
```

Entfernt Module, Sperre, Start-Dienste und die Bluetooth-Anpassung. Danach läuft wieder der eingebaute Treiber.
Ohne Installation genügt auch ein Neustart: Alles, was nicht installiert wurde, ist nach einem Neustart weg.

## Verhalten bei Kernel-Updates

Beim Start vergleicht ein Dienst die Kernel-Baukennung (`uname -v`) mit dem Bau. Passt sie nicht (neuer Kernelbau oder geänderte Quellen),
wird der eingebaute Treiber freigegeben, veraltete Module werden entfernt, und ein Neubau startet nach 90 Sekunden mit niedriger Priorität.
Nach dem Neubau gilt der neue Treiber **ab dem nächsten Neustart**. Es gibt keinen automatischen Neustart.
Ein Kernel-Update mit anderer Versionsnummer wird nicht neu gebaut, dann bleibt der eingebaute Treiber aktiv.

## Bekannte Einschränkungen

- Die SAR-Sendeleistungsbegrenzung des Treibers ist abgeschaltet (die Schnittstelle gibt es erst ab Kernel 5.11).
- Hotspot-/Access-Point-Betrieb, WLAN-Ausgabe der Sendung, Kameras über WLAN und Langzeitbetrieb sind **nicht geprüft**.
- Durchsatz im Vergleichstest etwa wie der alte Treiber (Download rund 8 % niedriger, Upload etwas höher). Die Messung war klein, siehe `TESTSTAND.md`.
- Der Bluetooth-Teil gilt nur für den Chip `13d3:3572`. Weitere Kennungen kommen mit Rückmeldung dazu.
- Nicht zusammen mit dem WLAN-Fix für den alten Treiber (`belabox-wlan-fix`) verwenden. Dieses Paket sperrt den alten Treiber.

## Dateien

- `rtw89ctl.py`: Prüfen, Bauen, Installieren, Rückweg, Start-Dienste. `systemd/`: Dienstdateien.
- `src/`: Treiberquelle mit den Anpassungen (ohne den Firmware-Ordner des Originals). `patches/belabox-5.10-compat.patch`: nur die Änderungen gegenüber dem Original.
- `ANLEITUNG.md`, `ANLEITUNG.en.md`: Anleitung für Anwender.
- `tests/`: automatische Tests (23), sie ändern nichts am System. `QUELLEN.md`: Herkunft und Lizenzen. `TESTSTAND.md`: was geprüft wurde.
