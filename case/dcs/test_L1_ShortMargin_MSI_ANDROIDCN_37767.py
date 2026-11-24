# -*- coding:utf-8 -*-
"""Test Case: ANDROIDCN-37767 - Verify Short Margin property for MSI."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from common.adb_common import (save_step_screenshot, dcs_test_cleanup_devices, dcs_test_press_home,
                               dcs_test_prepare_image_on_display_device, dcs_test_trigger_honeywell_scan,
                               dcs_test_wait_device_online, dcs_test_wake_and_unlock)
from common.common_method import (scan_clear_input_field, scan_get_input_field_text, scan_open_input_field,
                                  scan_verify_decode_result, dcs_test_connect_u2,
                                  dcs_test_goto_data_processing_settings, dcs_test_goto_symbology_setting,
                                  dcs_test_set_option_checked)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
SCRIPT_BASENAME = os.path.splitext(os.path.basename(__file__))[0]
SCRIPT_IMG_DIR = os.path.join(PROJECT_ROOT, "img", SCRIPT_BASENAME)
os.makedirs(SCRIPT_IMG_DIR, exist_ok=True)
MSI_SAMPLES = (
    ("codes_p01_01", "delhaize_codes_p01_01.png", "41186180"),
    ("codes_p01_02", "delhaize_codes_p01_02.png", "000008064016598"),
    ("codes_p01_03", "delhaize_codes_p01_03.png", "41485160"),
    ("codes_p01_04", "delhaize_codes_p01_04.png", "540011254870771"),
    ("brochure_p01_01", "delhaize_brochure_p01_01.png", "38600201"),
    ("brochure_p01_02", "delhaize_brochure_p01_02.png", "38427399"),
    ("brochure_p01_03", "delhaize_brochure_p01_03.png", "38650297"),
    ("brochure_p01_04", "delhaize_brochure_p01_04.png", "38640223"),
    ("brochure_p01_05", "delhaize_brochure_p01_05.png", "38500054"),
    ("brochure_p01_06", "delhaize_brochure_p01_06.png", "38354361"),
    ("brochure_p02_01", "delhaize_brochure_p02_01.png", "38447017"),
    ("brochure_p02_02", "delhaize_brochure_p02_02.png", "38067344"),
    ("brochure_p02_03", "delhaize_brochure_p02_03.png", "38046066"),
    ("brochure_p02_04", "delhaize_brochure_p02_04.png", "38218244"),
    ("brochure_p02_05", "delhaize_brochure_p02_05.png", "38093084"),
    ("brochure_p02_06", "delhaize_brochure_p02_06.png", "38055042"),
    ("brochure_p02_07", "delhaize_brochure_p02_07.png", "38091005"),
    ("brochure_p03_01", "delhaize_brochure_p03_01.png", "38057022"),
    ("brochure_p03_02", "delhaize_brochure_p03_02.png", "38056032"),
    ("brochure_p03_03", "delhaize_brochure_p03_03.png", "38053062"),
    ("brochure_p03_04", "delhaize_brochure_p03_04.png", "38054052"),
    ("brochure_p03_05", "delhaize_brochure_p03_05.png", "38053146"),
    ("brochure_p04_01", "delhaize_brochure_p04_01.png", "42787762"),
    ("brochure_p05_01", "delhaize_brochure_p05_01.png", "37255205"),
    ("brochure_p06_01", "delhaize_brochure_p06_01.png", "77300051"),
    ("brochure_p06_02", "delhaize_brochure_p06_02.png", "77300135"),
    ("brochure_p06_03", "delhaize_brochure_p06_03.png", "77300218"),
    ("brochure_p06_04", "delhaize_brochure_p06_04.png", "77300473"),
    ("brochure_p06_05", "delhaize_brochure_p06_05.png", "77300390"),
    ("brochure_p06_06", "delhaize_brochure_p06_06.png", "77081420"),
    ("brochure_p06_07", "delhaize_brochure_p06_07.png", "77361194"),
    ("brochure_p06_08", "delhaize_brochure_p06_08.png", "77360287"),
    ("brochure_p06_09", "delhaize_brochure_p06_09.png", "77300705"),
    ("brochure_p06_10", "delhaize_brochure_p06_10.png", "77300549"),
    ("brochure_p06_11", "delhaize_brochure_p06_11.png", "77300960"),
    ("brochure_p06_12", "delhaize_brochure_p06_12.png", "77300887"),
    ("brochure_p06_13", "delhaize_brochure_p06_13.png", "77369296"),
    ("brochure_p06_14", "delhaize_brochure_p06_14.png", "77369379"),
)

_SCANNING_LABELS = ["Scanning"]
_INTERNAL_SCANNER_LABELS = ["Internal Scanner", "Internal scanner"]
_DEFAULT_PROFILE_LABELS = ["Default profile", "Default Profile"]
_DATA_PROCESSING_LABELS = ["Data Processing Settings", "Data Processing"]
_SYMBOLOGY_LABELS = ["Symbology Settings", "Symbology"]
_MSI_LABELS = ["MSI"]


def _load_device_serials_from_environment():
    dev0 = (os.environ.get("AUTONEXUS_DEV0_SN") or "").strip()
    dev1 = (os.environ.get("AUTONEXUS_DEV1_SN") or "").strip()
    if not dev0 or not dev1:
        raise RuntimeError("AUTONEXUS_DEV0_SN and AUTONEXUS_DEV1_SN must be provided by the web task")
    return dev0, dev1


DEV0_SERIAL, DEV1_SERIAL = _load_device_serials_from_environment()


class Test_ShortMargin_MSI(unittest.TestCase):
    @classmethod
    def _ensure_device_sessions(cls):
        if hasattr(cls, "d0"):
            return
        if not dcs_test_wait_device_online(DEV0_SERIAL, 25) or not dcs_test_wait_device_online(DEV1_SERIAL, 25):
            raise RuntimeError("Configured MSI test devices are offline")
        cls.d0 = dcs_test_connect_u2(DEV0_SERIAL)
        cls.d1 = dcs_test_connect_u2(DEV1_SERIAL)

    def setUp(self):
        self.__class__._ensure_device_sessions()
        dcs_test_wake_and_unlock(DEV0_SERIAL, self.d0)
        dcs_test_wake_and_unlock(DEV1_SERIAL, self.d1)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def tearDown(self):
        dcs_test_cleanup_devices(DEV0_SERIAL, DEV1_SERIAL)
        dcs_test_press_home(DEV0_SERIAL)
        dcs_test_press_home(DEV1_SERIAL)

    def _configure_msi(self):
        dcs_test_goto_symbology_setting(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
                                        _DEFAULT_PROFILE_LABELS, _SYMBOLOGY_LABELS, _MSI_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "MSI", True), "Failed to enable MSI")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Short Margin", True), "Failed to enable Short Margin")
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Out of spec codes", True), "Failed to enable Out of spec codes")
        save_step_screenshot(self.d0, "step02_short_margin_and_out_of_spec_enabled", SCRIPT_IMG_DIR)

    def test_short_margin_msi(self):
        """Test steps:
        1. Enable Wedge for keyboard output.
        2. Enable MSI, Short Margin, and Out of spec codes.
        3. Scan every barcode extracted from both Delhaize PDF attachments three times.
        4. Verify each decoded value exactly matches its fixture expectation.
        """
        print("\n[Step 1] Open Data Processing Settings and enable Wedge")
        dcs_test_goto_data_processing_settings(DEV0_SERIAL, self.d0, _SCANNING_LABELS, _INTERNAL_SCANNER_LABELS,
                                               _DEFAULT_PROFILE_LABELS, _DATA_PROCESSING_LABELS)
        self.assertTrue(dcs_test_set_option_checked(self.d0, "Wedge", True), "Failed to enable Wedge")

        print("[Step 2] Enable MSI, Short Margin, and Out of spec codes")
        self._configure_msi()

        print("[Step 3] Verify every Delhaize MSI barcode decodes to its exact expected value")
        for sample_name, filename, expected_value in MSI_SAMPLES:
            image_path = os.path.join(PROJECT_ROOT, "files", "images", "dcs_imgs", "delhaize_msi_barcodes", filename)
            for round_number in range(1, 4):
                with self.subTest(sample=sample_name, round_number=round_number):
                    dcs_test_prepare_image_on_display_device(DEV1_SERIAL, self.d1, image_path, "/sdcard/Pictures/" + filename)
                    self.assertTrue(scan_open_input_field(self.d0, DEV0_SERIAL), "Failed to focus input field")
                    scan_clear_input_field(self.d0)
                    self.assertTrue(dcs_test_trigger_honeywell_scan(DEV0_SERIAL), "Scan trigger failed")
                    detected = scan_verify_decode_result(self.d0, max_wait_seconds=5)
                    value = scan_get_input_field_text(self.d0) if detected else ""
                    print(f"  {sample_name} round {round_number}: detected={detected}, value='{value}'")
                    save_step_screenshot(self.d0, f"step03_{sample_name}_round{round_number}", SCRIPT_IMG_DIR)
                    self.assertTrue(detected, f"{sample_name} round {round_number}: MSI barcode was not decoded")
                    self.assertEqual(value, expected_value, f"{sample_name} round {round_number}: unexpected decoded value")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_ShortMargin_MSI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)