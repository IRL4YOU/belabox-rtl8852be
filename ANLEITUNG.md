# Anleitung: neuer WLAN-Treiber und Bluetooth für die ROCK 5B Plus

Diese Anleitung ist für die **Radxa ROCK 5B Plus** mit BELABOX-Image. Du brauchst keine Linux-Kenntnisse, nur ein Terminal und etwas Zeit
(gut eine halbe Stunde, davon die meiste Zeit Warten auf den Bau). **Die Software ist eine Vorabversion.** Lies bitte auch die Hinweise am Ende.

Englisch: [ANLEITUNG.en.md](ANLEITUNG.en.md)

## Was du vorher wissen musst

- Es ändert nur den Treiber für den WLAN- und Bluetooth-Chip auf dem Board. Dein Sendeaufbau, die BELABOX-Software und deine Einstellungen bleiben unberührt.
- Du brauchst einen **LAN-Anschluss** an der Box. Das WLAN wird getauscht, der Zugang soll nicht davon abhängen.
- Die Box darf **nicht senden**, solange du das machst (zwischendurch ist ein Neustart nötig).
- Alles lässt sich rückgängig machen (Abschnitt 6). Bis zum Neustart läuft dein bisheriger Treiber unverändert weiter.

## 1. Prüfen, ob dein Gerät passt

Verbinde dich per SSH mit der Box (Benutzer `user`, `BOX-IP` ist die Adresse der Box im Netzwerk). Dann:

```sh
ssh user@BOX-IP
cat /proc/device-tree/model; echo; uname -r
```

Es muss `Radxa ROCK 5B Plus` und `5.10.160-belabox` erscheinen. Bei anderen Werten **nicht weitermachen**, das Paket ist dafür nicht gedacht.
Hast du gerade ein BELABOX-Kernel-Update eingespielt, starte die Box einmal neu, bevor du anfängst.

## 2. Paket herunterladen und prüfen

Auf der Box (nach `sudo -i` bist du root, das Passwort ist das von `user`):

```sh
sudo -i
cd /root
wget https://github.com/IRL4YOU/belabox-rtl8852be/releases/download/0.1.0-test1/belabox-rtw89-0.1.0-test1.tar.gz
wget https://github.com/IRL4YOU/belabox-rtl8852be/releases/download/0.1.0-test1/belabox-rtw89-0.1.0-test1.tar.gz.sha256
sha256sum -c belabox-rtw89-0.1.0-test1.tar.gz.sha256
```

Es muss `belabox-rtw89-0.1.0-test1.tar.gz: OK` erscheinen. Bei einer Abweichung nicht installieren, neu laden.

```sh
tar -xzf belabox-rtw89-0.1.0-test1.tar.gz
cd belabox-rtw89
```

## 3. Voraussetzungen prüfen

```sh
python3 rtw89ctl.py check
```

Erwartet: `KOMPATIBEL. Keine Änderungen.` Bei `ABBRUCH` steht der Grund dabei (falscher Kernel, Chip nicht gefunden, Baudateien fehlen).
Dann nicht weitermachen und die Meldung bei einem Issue angeben (Abschnitt 8).

## 4. Bauen (ändert nichts am laufenden System)

```sh
python3 rtw89ctl.py build --output /var/tmp/belabox-rtw89-build-1
```

Das dauert einige Minuten. Erwartet: `BUILD GEPRÜFT. Noch NICHT installiert oder geladen.` und vier Modulnamen mit Prüfsummen.
Das Protokoll liegt in `/var/tmp/belabox-rtw89-build-1/build.log`. Bei einem zweiten Versuch einen neuen Ordnernamen nehmen (`-2`), alte Ordner werden nicht überschrieben.

## 5. Installieren und neu starten

```sh
python3 rtw89ctl.py install --build-dir /var/tmp/belabox-rtw89-build-1 --accept-experimental
```

Erwartet: `INSTALLIERT FÜR DEN NÄCHSTEN START.` und darunter `BLUETOOTH EINGERICHTET.` Der laufende Treiber bleibt noch unverändert.
Nur WLAN ohne Bluetooth-Anpassung: zusätzlich `--no-bluetooth` anhängen.

```sh
reboot
```

Nach etwa einer Minute meldest du dich wieder an und prüfst:

```sh
ssh user@BOX-IP
sudo -i
cd /root/belabox-rtw89 && python3 rtw89ctl.py status
```

Erwartet: `Treiber am WLAN-Chip: rtw89_8852be_git` und `Eingebauter Treiber gesperrt: ja`.

**WLAN:** Der neue Treiber nennt die Schnittstelle `wlan0` (vorher `wlan1`). Verbindungen, die fest an `wlan1` gebunden waren, legst du neu an,
in der BELABOX-Oberfläche oder so:

```sh
nmcli dev wifi list
nmcli dev wifi connect "NETZNAME" ifname wlan0 --ask
```

**Bluetooth testen:**

```sh
bluetoothctl --timeout 15 scan on
bluetoothctl devices
```

Es sollten Geräte in der Umgebung auftauchen (vorher: keines). In der IRL4YOU BOX erkennt die Software den Adapter von selbst.

## 6. Rückgängig machen

```sh
cd /root/belabox-rtw89
python3 rtw89ctl.py uninstall
reboot
```

Entfernt Treiber, Sperre, Dienste und die Bluetooth-Anpassung. Danach läuft wieder der eingebaute Treiber. Reicht der Zugang nicht mehr (kein WLAN, kein SSH),
meldest du dich über das LAN-Kabel an, oder mit Bildschirm und Tastatur direkt an der Box.

## 7. Was passiert bei Updates?

- **BELABOX-Kernel-Update (gleiche Versionsnummer, neuer Bau):** Der eingebaute Treiber wird beim nächsten Start wieder freigegeben, das WLAN läuft also.
  Nach 90 Sekunden baut die Box den neuen Treiber im Hintergrund neu. **Nach dem nächsten Neustart** gilt er wieder. Du musst nichts tun.
  Fortschritt: `journalctl -u belabox-rtw89-rebuild`.
- **Kernel mit anderer Versionsnummer:** Das Paket ist dafür nicht geprüft und baut nicht. Es bleibt der eingebaute Treiber.
- **IRL4YOU-Updates** ändern dieses Paket nicht.

## 8. Wenn etwas nicht klappt

| Problem | Was tun |
|---|---|
| `check` meldet `ABBRUCH` | Meldung lesen. Falscher Kernel oder Board: nicht weitermachen. Baudateien fehlen: erst das BELABOX-Update vollständig einspielen. |
| `build` scheitert | `tail -n 40 /var/tmp/belabox-rtw89-build-1/build.log` und bei einem Issue anhängen. |
| Nach dem Neustart kein WLAN | Per LAN anmelden, `python3 rtw89ctl.py status`, dann `python3 rtw89ctl.py uninstall` und neu starten. |
| Bluetooth findet nichts | `dmesg \| grep rtk_btusb` und `systemctl status belabox-rtw89-bt`. Ausgabe bei einem Issue anhängen. |
| WLAN nur auf 2,4 GHz sichtbar | Länderkennung prüfen: `apt-get install -y iw`, dann `iw reg get`. Es sollte `country DE` (oder dein Land) stehen. |

Hilfe gibt es als Issue im Repository <https://github.com/IRL4YOU/belabox-rtl8852be/issues>. Bitte angeben: Ausgabe von `uname -a`,
`python3 rtw89ctl.py status`, `python3 rtw89ctl.py --version` und die Meldung, die du gesehen hast. **Keine Passwörter oder WLAN-Namen** posten.

## Hinweise zur Vorabversion

Geprüft sind Bau, Laden, Verbindung auf 5 GHz, Bluetooth-Suche und der Neustart. **Nicht geprüft** sind Dauerbetrieb, Kameras und Sendung über WLAN
sowie Hotspot-Betrieb. Siehe [TESTSTAND.md](TESTSTAND.md). Nutze es nicht kurz vor einer wichtigen Sendung.
