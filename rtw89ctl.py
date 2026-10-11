#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""BELABOX rtw89: zurückportierter RTL8852BE-Treiber (rtw89) für Kernel 5.10.160-belabox.

Baut, installiert und pflegt den Treiber. Nach einem Kernel-Update baut der Start-Dienst ihn
automatisch neu und fällt bis dahin auf den eingebauten Treiber zurück. Kein automatischer Neustart.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

VERSION = '0.1.0-test1'
KERNEL = '5.10.160-belabox'
PCI_VENDOR = '0x10ec'
PCI_DEVICES = ('0xb852', '0xb85b')
MODULES = ('rtw89_core_git', 'rtw89_pci_git', 'rtw89_8852b_git', 'rtw89_8852be_git')
OLD_DRIVER = '8852be'
FIRMWARE = ('rtw89/rtw8852b_fw-1.bin', 'rtw89/rtw8852b_fw.bin')
HERE = Path(__file__).resolve().parent

STATE_DIR = Path('/var/lib/belabox-rtw89')
SHARE_DIR = Path('/usr/local/share/belabox-rtw89')
SBIN = Path('/usr/local/sbin/rtw89ctl')
UNIT_DIR = Path('/etc/systemd/system')
BLACKLIST = Path('/etc/modprobe.d/belabox-rtw89.conf')
MODULE_ROOT = Path('/lib/modules')
SYS_PCI = Path('/sys/bus/pci/devices')
UNITS = ('belabox-rtw89-boot.service', 'belabox-rtw89-rebuild.service')

# Bluetooth-Teil des RTL8852BE (USB). Der allgemeine btusb-Treiber des Kernels 5.10 lädt für diesen Chip keine
# Firmware, der Chip bleibt dann taub. Der Realtek-Herstellertreiber rtk_btusb kann es, sucht die Firmware aber
# ohne Ordner und ohne ".bin" unter /lib/firmware.
BT_IDS = (('13d3', '3572'),)
BT_GENERIC = 'btusb'
BT_VENDOR = 'rtk_btusb'
BT_FW_LINKS = {'rtl8852bu_fw': 'rtl_bt/rtl8852bu_fw.bin', 'rtl8852bu_config': 'rtl_bt/rtl8852bu_config.bin'}
FIRMWARE_DIR = Path('/lib/firmware')
SYS_USB = Path('/sys/bus/usb')
BT_UNIT = 'belabox-rtw89-bt.service'


class Refused(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def run(*cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, **kw).stdout.strip()


def kernel_release():
    return platform.release()


def kernel_build():
    """Kennung des laufenden Kernelbaus, z. B. '#168 SMP Tue Sep 8 ...'. Ändert sich bei jedem neuen Kernelpaket."""
    return platform.version()


def source_hash(src):
    digest = hashlib.sha256()
    for path in sorted(Path(src).rglob('*')):
        if path.is_file() and (path.suffix in ('.c', '.h') or path.name == 'Makefile'):
            digest.update(path.relative_to(src).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_id(src):
    text = '\n'.join((kernel_release(), kernel_build(), source_hash(src)))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def read_state():
    path = STATE_DIR / 'state.json'
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_DIR / 'state.json.tmp'
    tmp.write_text(json.dumps(state, indent=1) + '\n')
    tmp.replace(STATE_DIR / 'state.json')


def module_dir(kernel=None):
    return MODULE_ROOT / (kernel or kernel_release()) / 'updates' / 'belabox-rtw89'


def has_device():
    for dev in SYS_PCI.glob('*'):
        try:
            if (dev / 'vendor').read_text().strip() == PCI_VENDOR and \
               (dev / 'device').read_text().strip() in PCI_DEVICES:
                return True
        except OSError:
            continue
    return False


def check(need_build=True):
    require(platform.system() == 'Linux' and platform.machine() == 'aarch64', 'Nur auf der aarch64-Linux-Box.')
    require(kernel_release() == KERNEL, 'Geprüft nur für Kernel %s, gefunden: %s' % (KERNEL, kernel_release()))
    require(has_device(), 'RTL8852BE-PCIe-Gerät (10ec:b852/b85b) nicht gefunden.')
    for name in FIRMWARE:
        require((Path('/lib/firmware') / name).is_file(), 'Firmware fehlt: ' + name)
    root = MODULE_ROOT / KERNEL
    require((root / 'kernel/net/mac80211/mac80211.ko').is_file(), 'mac80211 fehlt im Kernel.')
    if need_build:
        for tool in ('make', 'gcc', 'ld', 'depmod', 'modinfo'):
            require(shutil.which(tool), 'Programm fehlt: ' + tool)
        require((root / 'build/Makefile').is_file(), 'Kernel-Baudateien fehlen: %s' % (root / 'build'))


def build(output, src=None):
    check()
    src = Path(src or (SHARE_DIR / 'src' if (SHARE_DIR / 'src').is_dir() else HERE / 'src'))
    output = Path(output)
    require(not output.exists(), 'Ausgabeverzeichnis existiert schon: %s (neuen Namen wählen)' % output)
    shutil.copytree(src, output / 'src')
    log = output / 'build.log'
    jobs = str(max(1, (os.cpu_count() or 2) - 1))
    with log.open('w') as out:
        result = subprocess.run(['make', '-C', str(MODULE_ROOT / KERNEL / 'build'), 'M=' + str(output / 'src'),
                                 'CONFIG_PM=y', '-j' + jobs, 'modules'], stdout=out, stderr=subprocess.STDOUT)
    require(result.returncode == 0, 'Bau fehlgeschlagen, siehe %s' % log)
    info = {}
    for name in MODULES:
        ko = output / 'src' / (name + '.ko')
        require(ko.is_file(), 'Modul nicht gebaut: ' + name)
        vermagic = run('modinfo', '-F', 'vermagic', str(ko))
        require(vermagic.split()[0] == KERNEL, 'Falsche Kernelkennung in %s: %s' % (name, vermagic))
        info[name] = hashlib.sha256(ko.read_bytes()).hexdigest()
    (output / 'build-result.json').write_text(json.dumps(
        {'kernel': KERNEL, 'kernel_build': kernel_build(), 'build_id': build_id(output / 'src'),
         'modules': info, 'built_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, indent=1) + '\n')
    return info


def blacklist_text():
    return ('# BELABOX rtw89: eingebauten Treiber sperren, solange der zurückportierte zum Kernel passt.\n'
            'blacklist %s\n' % OLD_DRIVER)


def set_blacklist(on):
    if on:
        BLACKLIST.write_text(blacklist_text())
    elif BLACKLIST.exists():
        BLACKLIST.unlink()


def depmod_has_entry(kernel):
    dep = MODULE_ROOT / kernel / 'modules.dep'
    return dep.is_file() and 'rtw89_8852be_git' in dep.read_text()


def install_units(sbin=SBIN):
    # Beim Neubau aus dem Start-Dienst (HERE = /usr/local/sbin) sind Dienst und Programm schon an Ort und Stelle.
    if (HERE / 'systemd').is_dir():
        for name in UNITS:
            shutil.copy2(HERE / 'systemd' / name, UNIT_DIR / name)
        shutil.copy2(HERE / 'rtw89ctl.py', sbin)
        sbin.chmod(0o755)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'belabox-rtw89-boot.service')


def install(build_dir, bluetooth=True):
    build_dir = Path(build_dir)
    check(need_build=False)
    result = json.loads((build_dir / 'build-result.json').read_text())
    require(result.get('kernel') == KERNEL and result.get('kernel_build') == kernel_build(),
            'Der Bau gehört nicht zum laufenden Kernel. Neu bauen.')
    dest = module_dir()
    # Quellen für spätere Neubauten ablegen.
    if SHARE_DIR.exists():
        shutil.rmtree(SHARE_DIR)
    SHARE_DIR.mkdir(parents=True)
    shutil.copytree(build_dir / 'src', SHARE_DIR / 'src',
                    ignore=shutil.ignore_patterns('*.o', '*.ko', '*.mod*', '.*.cmd', 'Module.symvers', 'modules.order'))
    dest.mkdir(parents=True, exist_ok=True)
    for name in MODULES:
        ko = build_dir / 'src' / (name + '.ko')
        require(hashlib.sha256(ko.read_bytes()).hexdigest() == result['modules'][name], 'Prüfsumme weicht ab: ' + name)
        shutil.copy2(ko, dest / (name + '.ko'))
    run('depmod', '-a', KERNEL)
    require(depmod_has_entry(KERNEL), 'depmod hat die Module nicht eingetragen.')
    set_blacklist(True)
    write_state({'kernel': KERNEL, 'kernel_build': kernel_build(), 'build_id': build_id(SHARE_DIR / 'src'),
                 'installed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    install_units()
    print('INSTALLIERT FÜR DEN NÄCHSTEN START. Laufender Treiber unverändert.')
    # Bluetooth: nur bei der Erstinstallation (der Neubau nach einem Kernel-Update läuft aus /usr/local/sbin ohne Dienstdateien).
    if bluetooth and (HERE / 'systemd').is_dir():
        if bt_devices():
            bt_install()
        else:
            print('Hinweis: kein Bluetooth-Chip %s gefunden, Bluetooth-Teil übersprungen.' % ', '.join(':'.join(i) for i in BT_IDS))


def uninstall():
    set_blacklist(False)
    for name in UNITS:
        subprocess.run(['systemctl', 'disable', name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (UNIT_DIR / name).unlink(missing_ok=True)
    SBIN.unlink(missing_ok=True)
    for kernel in [p.name for p in MODULE_ROOT.glob('*') if (p / 'updates/belabox-rtw89').is_dir()]:
        shutil.rmtree(MODULE_ROOT / kernel / 'updates/belabox-rtw89')
        subprocess.run(['depmod', '-a', kernel], check=False)
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    shutil.rmtree(SHARE_DIR, ignore_errors=True)
    bt_uninstall()
    print('ENTFERNT. Nach einem Neustart läuft wieder der eingebaute Treiber (%s).' % OLD_DRIVER)


def boot():
    """Früh beim Start: passt der Bau zum Kernel, wird der eingebaute Treiber gesperrt, sonst nicht und der Neubau startet."""
    state = read_state()
    src = SHARE_DIR / 'src'
    ok = (state is not None and src.is_dir() and state.get('kernel') == kernel_release() and
          state.get('build_id') == build_id(src) and
          all((module_dir() / (n + '.ko')).is_file() for n in MODULES))
    if ok:
        if not depmod_has_entry(kernel_release()):
            run('depmod', '-a', kernel_release())
        set_blacklist(True)
        print('rtw89: Bau passt zum Kernel, zurückportierter Treiber wird verwendet.')
        return True
    set_blacklist(False)
    # Veraltete Module entfernen, damit nicht versehentlich ein nicht passender Bau geladen wird.
    stale = module_dir()
    if stale.is_dir():
        shutil.rmtree(stale)
        subprocess.run(['depmod', '-a', kernel_release()], check=False)
    print('rtw89: Bau passt nicht zum Kernel (oder fehlt): eingebauter Treiber bleibt aktiv, Neubau wird gestartet.')
    if state is not None and src.is_dir():
        subprocess.run(['systemctl', 'start', '--no-block', 'belabox-rtw89-rebuild.service'], check=False)
    return False


def rebuild():
    """Baut für den laufenden Kernel neu und stellt erst nach geprüftem Bau um. Wirksam nach dem nächsten Neustart."""
    state = read_state()
    require(state is not None and (SHARE_DIR / 'src').is_dir(), 'Nichts installiert, kein Neubau möglich.')
    out = Path('/var/tmp') / ('belabox-rtw89-build-' + time.strftime('%Y%m%d-%H%M%S'))
    build(out, SHARE_DIR / 'src')
    install(out, bluetooth=False)
    print('NEUBAU FERTIG. Wirksam nach dem nächsten Neustart.')


def status():
    state = read_state()
    print('Kernel:', kernel_release(), kernel_build())
    print('Installiert:', 'ja' if state else 'nein', json.dumps(state) if state else '')
    for dev in SYS_PCI.glob('*'):
        try:
            if (dev / 'vendor').read_text().strip() == PCI_VENDOR and (dev / 'device').read_text().strip() in PCI_DEVICES:
                drv = (dev / 'driver').resolve().name if (dev / 'driver').exists() else 'keiner'
                print('Treiber am WLAN-Chip:', drv)
        except OSError:
            pass
    print('Eingebauter Treiber gesperrt:', 'ja' if BLACKLIST.exists() else 'nein')


def write_sysfs(path, text):
    with open(path, 'w') as handle:
        handle.write(text)


def bt_devices():
    """Alle USB-Geräte mit einer der bekannten Kennungen: Liste von (Gerätename, Pfad)."""
    found = []
    for dev in sorted((SYS_USB / 'devices').glob('*')):
        try:
            ident = ((dev / 'idVendor').read_text().strip(), (dev / 'idProduct').read_text().strip())
        except OSError:
            continue
        if ident in BT_IDS:
            found.append((dev.name, dev))
    return found


def bt_links():
    """Firmware-Verknüpfungen anlegen; vorhandene Dateien anderer Herkunft bleiben unangetastet."""
    for name, target in BT_FW_LINKS.items():
        link = FIRMWARE_DIR / name
        if link.is_symlink() and os.readlink(link) == target:
            continue
        if link.exists() or link.is_symlink():
            if not link.is_symlink():
                continue
            link.unlink()
        require((FIRMWARE_DIR / target).exists(), 'Firmware fehlt: ' + target)
        link.symlink_to(target)


def bt_attach():
    """Schaltet den Bluetooth-Chip auf den Herstellertreiber um, falls er am allgemeinen hängt. Mehrfach ausführbar."""
    devices = bt_devices()
    if not devices:
        print('rtw89-bt: kein bekannter Bluetooth-Chip gefunden, nichts zu tun.')
        return False
    bt_links()
    subprocess.run(['modprobe', BT_VENDOR], check=False)
    vendor = SYS_USB / 'drivers' / BT_VENDOR
    generic = SYS_USB / 'drivers' / BT_GENERIC
    require(vendor.is_dir(), 'Herstellertreiber %s nicht verfügbar.' % BT_VENDOR)
    for name, dev in devices:
        interfaces = sorted(p.name for p in dev.glob(name + ':*'))
        for iface in interfaces:
            if (generic / iface).exists():
                write_sysfs(generic / 'unbind', iface)
        ident = '%s %s' % ((dev / 'idVendor').read_text().strip(), (dev / 'idProduct').read_text().strip())
        try:
            write_sysfs(vendor / 'new_id', ident)
        except OSError:
            pass  # Kennung ist dem Treiber schon bekannt
        for iface in interfaces:
            if not (vendor / iface).exists():
                try:
                    write_sysfs(vendor / 'bind', iface)
                except OSError:
                    pass  # new_id hat schon gebunden
        print('rtw89-bt: %s auf %s umgestellt.' % (name, BT_VENDOR))
    return True


def bt_install():
    require(shutil.which('modinfo') and run('modinfo', '-F', 'filename', BT_VENDOR), '%s fehlt im Kernel.' % BT_VENDOR)
    require(bt_devices(), 'Kein Bluetooth-Chip (%s) gefunden.' % ', '.join(':'.join(i) for i in BT_IDS))
    bt_links()
    shutil.copy2(HERE / 'systemd' / BT_UNIT, UNIT_DIR / BT_UNIT)
    shutil.copy2(HERE / 'rtw89ctl.py', SBIN)
    SBIN.chmod(0o755)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', BT_UNIT)
    bt_attach()
    print('BLUETOOTH EINGERICHTET. Gilt jetzt und nach jedem Start.')


def bt_uninstall():
    subprocess.run(['systemctl', 'disable', BT_UNIT], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (UNIT_DIR / BT_UNIT).unlink(missing_ok=True)
    for name, target in BT_FW_LINKS.items():
        link = FIRMWARE_DIR / name
        if link.is_symlink() and os.readlink(link) == target:
            link.unlink()
    subprocess.run(['systemctl', 'daemon-reload'], check=False)
    print('BLUETOOTH-ANPASSUNG ENTFERNT. Nach einem Neustart hängt der Chip wieder am allgemeinen Treiber.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check', help='Voraussetzungen prüfen, nichts ändern')
    b = sub.add_parser('build', help='Treiber bauen, nichts installieren')
    b.add_argument('--output', required=True, type=Path)
    i = sub.add_parser('install', help='Gebauten Treiber für den nächsten Start installieren')
    i.add_argument('--build-dir', required=True, type=Path)
    i.add_argument('--accept-experimental', action='store_true')
    i.add_argument('--no-bluetooth', action='store_true', help='nur WLAN, Bluetooth-Anpassung nicht einrichten')
    sub.add_parser('uninstall', help='Alles entfernen, zurück zum eingebauten Treiber')
    sub.add_parser('status', help='Zustand anzeigen')
    sub.add_parser('boot', help='(Start-Dienst) Bau und Kernel abgleichen')
    sub.add_parser('bt-install', help='Bluetooth des RTL8852BE einrichten (Herstellertreiber + Firmware)')
    sub.add_parser('bt-uninstall', help='Bluetooth-Anpassung entfernen')
    sub.add_parser('bt-attach', help='(Start-Dienst) Bluetooth-Chip auf den Herstellertreiber umstellen')
    sub.add_parser('rebuild', help='(Start-Dienst) nach Kernel-Update neu bauen')
    args = parser.parse_args(argv)
    try:
        if args.command != 'status' and os.geteuid() != 0:
            raise Refused('Als root ausführen.')
        if args.command == 'check':
            check()
            print('KOMPATIBEL. Keine Änderungen.')
        elif args.command == 'build':
            info = build(args.output)
            print('BUILD GEPRÜFT. Noch NICHT installiert oder geladen.')
            print(json.dumps(info, indent=1))
        elif args.command == 'install':
            require(args.accept_experimental, 'Experimentell: zur Bestätigung --accept-experimental angeben.')
            install(args.build_dir, bluetooth=not args.no_bluetooth)
        elif args.command == 'uninstall':
            uninstall()
        elif args.command == 'status':
            status()
        elif args.command == 'bt-install':
            bt_install()
        elif args.command == 'bt-uninstall':
            bt_uninstall()
        elif args.command == 'bt-attach':
            bt_attach()
        elif args.command == 'boot':
            boot()
        elif args.command == 'rebuild':
            rebuild()
    except (Refused, OSError, subprocess.CalledProcessError, ValueError, KeyError) as exc:
        print('ABBRUCH: %s' % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
