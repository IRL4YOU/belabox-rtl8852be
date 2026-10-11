import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rtw89ctl as ctl  # noqa: E402


class Env:
    """Temporäre Ersatzverzeichnisse für Systempfade; keine echten Systemaufrufe."""

    def __init__(self, test, kernel_build='#168 SMP Tue Sep 8'):
        self.tmp = Path(tempfile.mkdtemp())
        test.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        self.build = kernel_build
        self.calls = []
        patches = {
            'STATE_DIR': self.tmp / 'state', 'SHARE_DIR': self.tmp / 'share', 'BLACKLIST': self.tmp / 'bl.conf',
            'MODULE_ROOT': self.tmp / 'modules', 'UNIT_DIR': self.tmp / 'units', 'SBIN': self.tmp / 'rtw89ctl',
            'FIRMWARE_DIR': self.tmp / 'firmware', 'SYS_USB': self.tmp / 'usb',
        }
        for name, value in patches.items():
            p = mock.patch.object(ctl, name, value)
            p.start()
            test.addCleanup(p.stop)
        for p in (mock.patch.object(ctl, 'kernel_release', lambda: ctl.KERNEL),
                  mock.patch.object(ctl, 'kernel_build', lambda: self.build),
                  mock.patch.object(ctl, 'run', self.fake_run),
                  mock.patch.object(ctl.subprocess, 'run', self.fake_subprocess)):
            p.start()
            test.addCleanup(p.stop)
        (self.tmp / 'units').mkdir()
        (self.tmp / 'modules' / ctl.KERNEL).mkdir(parents=True)
        self.src = self.tmp / 'build' / 'src'
        self.src.mkdir(parents=True)
        (self.src / 'core.c').write_text('int x;\n')
        (self.src / 'Makefile').write_text('all:\n')
        for name in ctl.MODULES:
            (self.src / (name + '.ko')).write_bytes(name.encode())

    def fake_run(self, *cmd, **kw):
        self.calls.append(cmd)
        if cmd[0] == 'depmod':
            (ctl.MODULE_ROOT / ctl.KERNEL / 'modules.dep').write_text('rtw89_8852be_git.ko:\n')
        return ''

    def fake_subprocess(self, cmd, **kw):
        self.calls.append(tuple(cmd))
        if cmd[0] == 'depmod':
            (ctl.MODULE_ROOT / ctl.KERNEL / 'modules.dep').write_text('rtw89_8852be_git.ko:\n')
        return mock.Mock(returncode=0)

    def result_file(self, kernel_build=None):
        modules = {n: hashlib.sha256((self.src / (n + '.ko')).read_bytes()).hexdigest() for n in ctl.MODULES}
        (self.tmp / 'build' / 'build-result.json').write_text(json.dumps(
            {'kernel': ctl.KERNEL, 'kernel_build': kernel_build or self.build, 'modules': modules}))

    def install(self):
        self.result_file()
        with mock.patch.object(ctl, 'check'), mock.patch.object(ctl, 'install_units'):
            ctl.install(self.tmp / 'build', bluetooth=False)

    def started(self, word):
        return any(word in ' '.join(c) for c in self.calls)


class BootTests(unittest.TestCase):
    def test_matching_install_blocks_builtin_driver_and_does_not_rebuild(self):
        env = Env(self)
        env.install()
        env.calls.clear()
        self.assertTrue(ctl.boot())
        self.assertTrue(ctl.BLACKLIST.exists())
        self.assertFalse(env.started('belabox-rtw89-rebuild'))

    def test_kernel_update_releases_builtin_driver_removes_stale_modules_and_rebuilds(self):
        env = Env(self)
        env.install()
        env.build = '#169 SMP Tue Nov 3'
        env.calls.clear()
        self.assertFalse(ctl.boot())
        self.assertFalse(ctl.BLACKLIST.exists())
        self.assertFalse(ctl.module_dir().exists())
        self.assertTrue(env.started('depmod'))
        self.assertTrue(env.started('belabox-rtw89-rebuild.service'))

    def test_changed_source_counts_as_mismatch(self):
        env = Env(self)
        env.install()
        (ctl.SHARE_DIR / 'src' / 'core.c').write_text('int y;\n')
        self.assertFalse(ctl.boot())
        self.assertFalse(ctl.BLACKLIST.exists())

    def test_missing_module_file_counts_as_mismatch(self):
        env = Env(self)
        env.install()
        (ctl.module_dir() / 'rtw89_pci_git.ko').unlink()
        self.assertFalse(ctl.boot())
        self.assertFalse(ctl.BLACKLIST.exists())

    def test_lost_depmod_entry_after_kernel_package_update_is_restored(self):
        env = Env(self)
        env.install()
        (ctl.MODULE_ROOT / ctl.KERNEL / 'modules.dep').write_text('other.ko:\n')
        env.calls.clear()
        self.assertTrue(ctl.boot())
        self.assertTrue(env.started('depmod'))
        self.assertTrue(ctl.depmod_has_entry(ctl.KERNEL))

    def test_without_install_nothing_is_started(self):
        env = Env(self)
        self.assertFalse(ctl.boot())
        self.assertFalse(env.started('belabox-rtw89-rebuild'))
        self.assertFalse(ctl.BLACKLIST.exists())


class InstallTests(unittest.TestCase):
    def test_install_refuses_a_build_from_another_kernel_build(self):
        env = Env(self)
        env.result_file(kernel_build='#167 SMP Fri Jan 16')
        with mock.patch.object(ctl, 'check'), self.assertRaises(ctl.Refused):
            ctl.install(env.tmp / 'build')
        self.assertFalse(ctl.BLACKLIST.exists())

    def test_install_refuses_changed_module_file(self):
        env = Env(self)
        env.result_file()
        (env.src / 'rtw89_core_git.ko').write_bytes(b'manipuliert')
        with mock.patch.object(ctl, 'check'), mock.patch.object(ctl, 'install_units'), self.assertRaises(ctl.Refused):
            ctl.install(env.tmp / 'build')
        self.assertFalse(ctl.BLACKLIST.exists())
        self.assertIsNone(ctl.read_state())

    def test_install_writes_modules_state_blacklist_and_keeps_sources(self):
        env = Env(self)
        env.install()
        self.assertTrue(all((ctl.module_dir() / (n + '.ko')).is_file() for n in ctl.MODULES))
        self.assertIn('blacklist ' + ctl.OLD_DRIVER, ctl.BLACKLIST.read_text())
        self.assertEqual(ctl.read_state()['kernel'], ctl.KERNEL)
        self.assertTrue((ctl.SHARE_DIR / 'src' / 'core.c').is_file())
        self.assertFalse(list((ctl.SHARE_DIR / 'src').glob('*.ko')))

    def test_uninstall_removes_everything_and_releases_builtin_driver(self):
        env = Env(self)
        env.install()
        with mock.patch.object(ctl.shutil, 'which', return_value='x'):
            ctl.uninstall()
        self.assertFalse(ctl.BLACKLIST.exists())
        self.assertFalse(ctl.module_dir().exists())
        self.assertIsNone(ctl.read_state())
        self.assertFalse(ctl.SHARE_DIR.exists())

    def test_build_id_depends_on_kernel_build_and_source(self):
        env = Env(self)
        a = ctl.build_id(env.src)
        env.build = '#169 SMP'
        b = ctl.build_id(env.src)
        (env.src / 'core.c').write_text('int z;\n')
        c = ctl.build_id(env.src)
        self.assertEqual(len({a, b, c}), 3)


class CombinedInstallTests(unittest.TestCase):
    def run_install(self, env, devices):
        env.result_file()
        with mock.patch.object(ctl, 'check'), mock.patch.object(ctl, 'install_units'), \
             mock.patch.object(ctl, 'bt_devices', return_value=devices), \
             mock.patch.object(ctl, 'bt_install') as bt:
            ctl.install(env.tmp / 'build')
            return bt

    def test_install_also_sets_up_bluetooth_when_the_chip_is_present(self):
        env = Env(self)
        with mock.patch.object(ctl, 'HERE', Path(__file__).resolve().parents[1]):
            bt = self.run_install(env, [('1-1.3', Path('x'))])
        bt.assert_called_once()

    def test_install_skips_bluetooth_without_the_chip_but_still_installs_wifi(self):
        env = Env(self)
        with mock.patch.object(ctl, 'HERE', Path(__file__).resolve().parents[1]):
            bt = self.run_install(env, [])
        bt.assert_not_called()
        self.assertTrue(ctl.BLACKLIST.exists())

    def test_rebuild_path_does_not_touch_bluetooth(self):
        env = Env(self)
        env.result_file()
        with mock.patch.object(ctl, 'check'), mock.patch.object(ctl, 'install_units'), \
             mock.patch.object(ctl, 'bt_install') as bt:
            ctl.install(env.tmp / 'build', bluetooth=False)
        bt.assert_not_called()

    def test_uninstall_also_removes_the_bluetooth_part(self):
        env = Env(self)
        env.install()
        with mock.patch.object(ctl, 'bt_uninstall') as bt:
            ctl.uninstall()
        bt.assert_called_once()


class CheckTests(unittest.TestCase):
    def test_other_kernel_is_refused(self):
        with mock.patch.object(ctl, 'kernel_release', lambda: '6.1.0'), \
             mock.patch.object(ctl.platform, 'system', lambda: 'Linux'), \
             mock.patch.object(ctl.platform, 'machine', lambda: 'aarch64'):
            with self.assertRaises(ctl.Refused):
                ctl.check()

    def test_missing_device_is_refused(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(tmp, ignore_errors=True))
        with mock.patch.object(ctl, 'kernel_release', lambda: ctl.KERNEL), \
             mock.patch.object(ctl.platform, 'system', lambda: 'Linux'), \
             mock.patch.object(ctl.platform, 'machine', lambda: 'aarch64'), \
             mock.patch.object(ctl, 'SYS_PCI', tmp):
            with self.assertRaises(ctl.Refused):
                ctl.check()


class BluetoothTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(self.tmp, ignore_errors=True))
        self.usb = self.tmp / 'usb'
        self.fw = self.tmp / 'firmware'
        (self.fw / 'rtl_bt').mkdir(parents=True)
        for name in ('rtl8852bu_fw.bin', 'rtl8852bu_config.bin'):
            (self.fw / 'rtl_bt' / name).write_bytes(b'x')
        dev = self.usb / 'devices' / '1-1.3'
        dev.mkdir(parents=True)
        (dev / 'idVendor').write_text('13d3\n')
        (dev / 'idProduct').write_text('3572\n')
        for iface in ('1-1.3:1.0', '1-1.3:1.1'):
            (dev / iface).mkdir()
        (self.usb / 'drivers' / 'btusb').mkdir(parents=True)
        (self.usb / 'drivers' / 'rtk_btusb').mkdir(parents=True)
        self.writes = []
        for p in (mock.patch.object(ctl, 'SYS_USB', self.usb), mock.patch.object(ctl, 'FIRMWARE_DIR', self.fw),
                  mock.patch.object(ctl, 'write_sysfs', lambda path, text: self.writes.append((Path(path).relative_to(self.usb).as_posix(), text))),
                  mock.patch.object(ctl.subprocess, 'run', lambda *a, **k: mock.Mock(returncode=0))):
            p.start()
            self.addCleanup(p.stop)

    def bind_generic(self):
        for iface in ('1-1.3:1.0', '1-1.3:1.1'):
            (self.usb / 'drivers' / 'btusb' / iface).mkdir()

    def test_chip_on_generic_driver_is_moved_to_the_vendor_driver(self):
        self.bind_generic()
        self.assertTrue(ctl.bt_attach())
        self.assertEqual(self.writes, [
            ('drivers/btusb/unbind', '1-1.3:1.0'), ('drivers/btusb/unbind', '1-1.3:1.1'),
            ('drivers/rtk_btusb/new_id', '13d3 3572'),
            ('drivers/rtk_btusb/bind', '1-1.3:1.0'), ('drivers/rtk_btusb/bind', '1-1.3:1.1')])

    def test_firmware_links_point_to_the_rtl_bt_files(self):
        ctl.bt_attach()
        self.assertEqual(os_readlink(self.fw / 'rtl8852bu_fw'), 'rtl_bt/rtl8852bu_fw.bin')
        self.assertTrue((self.fw / 'rtl8852bu_config').exists())

    def test_attach_is_repeatable_when_already_on_the_vendor_driver(self):
        for iface in ('1-1.3:1.0', '1-1.3:1.1'):
            (self.usb / 'drivers' / 'rtk_btusb' / iface).mkdir()
        ctl.bt_attach()
        self.assertEqual([w for w in self.writes if w[0].endswith(('unbind', 'bind'))], [])

    def test_no_chip_means_nothing_happens(self):
        (self.usb / 'devices' / '1-1.3' / 'idProduct').write_text('9999\n')
        self.assertFalse(ctl.bt_attach())
        self.assertEqual(self.writes, [])
        self.assertFalse((self.fw / 'rtl8852bu_fw').exists())

    def test_existing_real_firmware_file_is_not_overwritten(self):
        (self.fw / 'rtl8852bu_fw').write_bytes(b'eigene Datei')
        ctl.bt_links()
        self.assertEqual((self.fw / 'rtl8852bu_fw').read_bytes(), b'eigene Datei')

    def test_missing_firmware_is_refused(self):
        (self.fw / 'rtl_bt' / 'rtl8852bu_fw.bin').unlink()
        with self.assertRaises(ctl.Refused):
            ctl.bt_links()


def os_readlink(path):
    return __import__('os').readlink(path)


if __name__ == '__main__':
    unittest.main()
