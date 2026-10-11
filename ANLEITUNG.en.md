# Guide: new Wi-Fi driver and Bluetooth for the ROCK 5B Plus

This guide is for the **Radxa ROCK 5B Plus** running the BELABOX image. You do not need Linux experience, only a terminal and some time
(about half an hour, mostly waiting for the build). **This is a pre-release.** Please also read the notes at the end.

German: [ANLEITUNG.md](ANLEITUNG.md)

## Before you start

- It only changes the driver for the Wi-Fi and Bluetooth chip on the board. Your streaming setup, BELABOX software and settings stay as they are.
- You need a **LAN cable** connected to the box. The Wi-Fi driver is swapped, so your access must not depend on it.
- Do **not stream** while doing this (one reboot is needed).
- Everything can be undone (section 6). Until the reboot your current driver keeps running unchanged.

## 1. Check that your device matches

Connect to the box via SSH (user `user`, `BOX-IP` is the box's address on your network):

```sh
ssh user@BOX-IP
cat /proc/device-tree/model; echo; uname -r
```

It must show `Radxa ROCK 5B Plus` and `5.10.160-belabox`. If not, **stop**; this package is not meant for that device.
If you just installed a BELABOX kernel update, reboot once before you start.

## 2. Download and verify the package

On the box (`sudo -i` makes you root, the password is the one of `user`):

```sh
sudo -i
cd /root
wget https://github.com/IRL4YOU/belabox-rtl8852be/releases/download/0.1.0-test1/belabox-rtw89-0.1.0-test1.tar.gz
wget https://github.com/IRL4YOU/belabox-rtl8852be/releases/download/0.1.0-test1/belabox-rtw89-0.1.0-test1.tar.gz.sha256
sha256sum -c belabox-rtw89-0.1.0-test1.tar.gz.sha256
```

It must print `belabox-rtw89-0.1.0-test1.tar.gz: OK`. If it does not, do not install; download again.

```sh
tar -xzf belabox-rtw89-0.1.0-test1.tar.gz
cd belabox-rtw89
```

## 3. Check the requirements

```sh
python3 rtw89ctl.py check
```

Expected: `KOMPATIBEL. Keine Änderungen.` (compatible, no changes). On `ABBRUCH` (abort) the reason is printed (wrong kernel, chip not found, kernel build files missing).
Do not continue then; include the message in an issue (section 8).

## 4. Build (changes nothing on the running system)

```sh
python3 rtw89ctl.py build --output /var/tmp/belabox-rtw89-build-1
```

This takes a few minutes. Expected: `BUILD GEPRÜFT. Noch NICHT installiert oder geladen.` (build verified, not installed yet) and four module names with checksums.
The log is `/var/tmp/belabox-rtw89-build-1/build.log`. For a second attempt use a new folder name (`-2`); old folders are never overwritten.

## 5. Install and reboot

```sh
python3 rtw89ctl.py install --build-dir /var/tmp/belabox-rtw89-build-1 --accept-experimental
```

Expected: `INSTALLIERT FÜR DEN NÄCHSTEN START.` (installed for the next start) followed by `BLUETOOTH EINGERICHTET.` (Bluetooth set up).
The running driver is not changed yet. Wi-Fi only, without the Bluetooth part: add `--no-bluetooth`.

```sh
reboot
```

After about a minute log in again and check:

```sh
ssh user@BOX-IP
sudo -i
cd /root/belabox-rtw89 && python3 rtw89ctl.py status
```

Expected: `Treiber am WLAN-Chip: rtw89_8852be_git` and `Eingebauter Treiber gesperrt: ja` (built-in driver blocked: yes).

**Wi-Fi:** The new driver names the interface `wlan0` (formerly `wlan1`). Connections that were bound to `wlan1` must be created again,
in the BELABOX UI or with:

```sh
nmcli dev wifi list
nmcli dev wifi connect "NETWORK" ifname wlan0 --ask
```

**Test Bluetooth:**

```sh
bluetoothctl --timeout 15 scan on
bluetoothctl devices
```

Devices around you should show up (before: none). The IRL4YOU BOX software detects the adapter on its own.

## 6. Undo

```sh
cd /root/belabox-rtw89
python3 rtw89ctl.py uninstall
reboot
```

Removes the driver, the block on the built-in driver, the services and the Bluetooth change. The built-in driver runs again afterwards.
If you lose access (no Wi-Fi, no SSH), log in over the LAN cable, or with a screen and keyboard directly on the box.

## 7. What happens on updates?

- **BELABOX kernel update (same version number, new build):** At the next start the built-in driver is released again, so Wi-Fi works.
  After 90 seconds the box rebuilds the new driver in the background. It takes effect **after the next reboot**. You do not need to do anything.
  Progress: `journalctl -u belabox-rtw89-rebuild`.
- **Kernel with a different version number:** The package is not tested for it and does not build. The built-in driver stays.
- **IRL4YOU updates** do not change this package.

## 8. If something goes wrong

| Problem | What to do |
|---|---|
| `check` says `ABBRUCH` | Read the message. Wrong kernel or board: stop. Build files missing: install the full BELABOX update first. |
| `build` fails | `tail -n 40 /var/tmp/belabox-rtw89-build-1/build.log` and attach it to an issue. |
| No Wi-Fi after reboot | Log in via LAN, `python3 rtw89ctl.py status`, then `python3 rtw89ctl.py uninstall` and reboot. |
| Bluetooth finds nothing | `dmesg \| grep rtk_btusb` and `systemctl status belabox-rtw89-bt`. Attach the output to an issue. |
| Only 2.4 GHz visible | Check the country code: `apt-get install -y iw`, then `iw reg get`. It should show `country DE` (or your country). |

Help is available as an issue at <https://github.com/IRL4YOU/belabox-rtl8852be/issues>. Please include the output of `uname -a`,
`python3 rtw89ctl.py status`, `python3 rtw89ctl.py --version` and the message you saw. **Do not post passwords or Wi-Fi names.**

## Notes on the pre-release

Tested: build, loading, connection on 5 GHz, Bluetooth scan and reboot. **Not tested:** long-term use, cameras and streaming over Wi-Fi, hotspot mode.
See [TESTSTAND.md](TESTSTAND.md). Do not use it right before an important stream.
