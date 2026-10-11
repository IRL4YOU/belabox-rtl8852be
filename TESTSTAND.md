# Geprüfter Stand

Stand: 11. Oktober 2026. Paket `0.1.0-test1`. Keine allgemeine Stabilitäts- oder Produktivfreigabe.

## Prüfumgebung

- Radxa ROCK 5B Plus, interner RTL8852BE, WLAN PCI `10ec:b852`, Bluetooth USB `13d3:3572`.
- Ubuntu 22.04.5, Kernel `5.10.160-belabox #168` (8. September 2026), Kernelpaket `belabox-linux-rk3588=20261010-2`, GCC 11.4.0.
- Quellstand `rtw89` 6.6-lts, Commit `2310939e` (20. Juli 2025), siehe `QUELLEN.md`.

## Geprüft

1. **Bau** auf der Box: null Fehler, null Warnungen, vier Module mit Kernelkennung `5.10.160-belabox`, keine fehlenden Kernel-Symbole.
2. **Laden und Scan:** Firmware `rtw8852b_fw-1.bin` (Version 0.29.29.5) geladen, Scan findet Netze auf 2,4 und 5 GHz bis Kanal 104.
3. **Verbindung:** 5 GHz, Kanal 44, WLAN 6 (HE-MCS 11, zwei Datenströme), TX bis 287 Mbit/s.
4. **Pakettest:** 100 von 100 Paketen über das WLAN, Mittel 9,8 ms (alter Treiber: 100 von 100, 16,1 ms).
5. **Durchsatz** (Box ↔ Mac im selben Router-Funk, jeweils 25 bis 30 s): Download 86, 90, 82 Mbit/s (alter Treiber 93, 98, 92),
   Upload 99 und 89 Mbit/s (alter Treiber 84). Beide Geräte hingen am selben Funk, die Werte sind keine Obergrenze und nur zum Vergleich geeignet.
6. **Installation und Neustart:** Module installiert, eingebauter Treiber gesperrt, Start-Dienst läuft. Nach dem Neustart hängt der Chip an
   `rtw89_8852be_git`, das WLAN verbindet sich von selbst.
7. **Bluetooth:** Ohne Fix: Controller `UP RUNNING`, Scan findet 0 Geräte (Chip am `btusb` ohne Firmware). Mit Fix (Herstellertreiber
   `rtk_btusb` plus Firmware-Verknüpfungen): Firmware geladen, Scan findet 38 bis 43 Geräte in 15 bis 20 s. Dauerhaft über Neustart bestätigt.
   Die Oberfläche der IRL4YOU BOX erkennt den Adapter (`adapter_info`: Realtek, `13d3:3572`, keine Probleme).
8. **Automatische Tests:** 23 Tests (Start-Abgleich, Kernel-Update-Fall, Installation, Rückweg, Bluetooth-Umstellung), sie ändern nichts am System.

## Nicht geprüft

- Dauerbetrieb über Stunden und Tage, Kameraempfang und Sendeausgabe über WLAN.
- Hotspot-/Access-Point-Betrieb und die WLAN-Funktionen der BELABOX-Oberfläche über diesen Treiber.
- Ein echtes Kernel-Update (der Abgleich ist in den Tests simuliert, nicht mit einem neuen Kernelpaket durchgespielt).
- Suspend/Resume, andere Boards, andere Kernel, andere Bluetooth-Kennungen.
- Eine DJI-Kamerasuche über den Board-Bluetooth-Chip in der Oberfläche (nur Erkennung und Scan geprüft).
