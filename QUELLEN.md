# Herkunft und Lizenzen

## WLAN-Treiber (`src/`)

- Realtek `rtw89` (Linux-Kernel-Treiber für RTL8851BE/8852AE/8852BE/8852CE), im Quelltext mit
  `SPDX-License-Identifier: GPL-2.0 OR BSD-3-Clause`.
- Genauer Stand: Repository `a5a5aa555oo/rtw89`, Branch `6.6-lts`, Commit
  `2310939e2002117cd2b223c6d4f997e537142b78` (20. Juli 2025, „Revert rtw89: 8852b: update fw to v0.29.128.0").
  Das ist exakt der Stand, den Radxa im Paket `radxa-pkg/rtw89` (Version `6.6.95+git20250721.2310939-1`) eingebunden hat.
- Weg dorthin: Linux-Kernel `rtw89` (Realtek, Ping-Ke Shih und andere) → `lwfinger/rtw89` (Larry Finger) → `a5a5aa555oo/rtw89` → Radxa.
- Unsere Änderungen: `patches/belabox-5.10-compat.patch` (Makefile, `compat.h`, `core.c`, `mac80211.c`, `sar.c`, `sar.h`).
  Der Patch auf den Originalstand ergibt `src/` byte-genau, abzüglich des Ordners `firmware/` des Originals (Firmware-Dateien, brauchen wir nicht,
  die Box bringt ihre eigene mit). Wir haben keine Funktionen ergänzt, nur fehlende Kernel-Schnittstellen
  von 5.10 überbrückt (`compat.h`) und die SAR-Begrenzung abgeschaltet.
- Die Firmware (`rtw89/rtw8852b_fw-1.bin`) liefert das BELABOX-Image (linux-firmware). Sie ist nicht Teil dieses Pakets.

## Bluetooth

- Es wird nichts nachgebaut. Der Realtek-Herstellertreiber `rtk_btusb` (Version 3.1.6) und die Firmware `rtl_bt/rtl8852bu_fw.bin`
  sind im BELABOX-Image vorhanden. Dieses Paket stellt nur die Zuordnung her (Treiber umhängen, Firmware-Verknüpfungen anlegen).

## Lizenz

- Treiberquelle: Dual `GPL-2.0 OR BSD-3-Clause` nach dem Kopf der einzelnen Dateien.
- Eigene Werkzeuge (`rtw89ctl.py`, `make_release.py`, Dienstdateien, Tests): `GPL-2.0-only`, siehe `LICENSE`.
