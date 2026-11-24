"""Shared helpers for General Settings Excel-derived test cases."""

import re
import time
import xml.etree.ElementTree as ET

from common.common_method import shell


def package_installed(serial, package_name):
    output = shell(serial, "pm", "list", "packages", package_name)
    return "package:" + package_name in output


def wait_for_text(device, labels, attempts=8):
    """Return the first visible text selector from labels, scrolling when possible."""
    for _ in range(attempts):
        for label in labels:
            selector = device(text=label)
            if selector.exists(timeout=0.4):
                return selector, label
            selector = device(textContains=label)
            if selector.exists(timeout=0.4):
                return selector, label
        if device(scrollable=True).exists(timeout=0.3):
            device(scrollable=True).scroll.vert.forward(steps=35)
        else:
            device.swipe(0.5, 0.82, 0.5, 0.25, duration=0.3)
        time.sleep(0.4)
    return None, None


def require_visible(test_case, device, labels, description):
    selector, label = wait_for_text(device, labels)
    if selector is None:
        test_case.fail("{} was not found: {}".format(description, " / ".join(labels)))
    return selector, label


def click_visible(test_case, device, labels, description):
    selector, label = require_visible(test_case, device, labels, description)
    selector.click()
    time.sleep(0.8)
    return label


def _node_center(bounds):
    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not match:
        return None
    left, top, right, bottom = (int(value) for value in match.groups())
    return (left + right) // 2, (top + bottom) // 2


def switch_state(device, labels):
    """Return a Settings switch state located beside one of the supplied labels."""
    root = ET.fromstring(device.dump_hierarchy(compressed=False))
    nodes = list(root.iter("node"))
    for index, node in enumerate(nodes):
        text = (node.attrib.get("text") or "").strip()
        if text not in labels and not any(label in text for label in labels):
            continue
        for sibling in nodes[index + 1:index + 10]:
            if sibling.attrib.get("class") in ("android.widget.Switch", "android.widget.CheckBox"):
                return sibling.attrib.get("checked", "false").lower() == "true"
    return None


def set_switch(test_case, device, labels, enabled):
    current = switch_state(device, labels)
    if current is None:
        selector, _ = require_visible(test_case, device, labels, "Setting option")
        selector.click()
        time.sleep(0.8)
        current = switch_state(device, labels)
    if current == enabled:
        return
    selector, _ = require_visible(test_case, device, labels, "Setting option")
    selector.click()
    time.sleep(0.8)
    test_case.assertEqual(switch_state(device, labels), enabled, "Failed to set {}".format(" / ".join(labels)))


def screen_is_on(serial):
    return "mWakefulness=Awake" in shell(serial, "dumpsys", "power")


def prepare_settings_entry(serial):
    """Make Settings intents visible instead of leaving them behind keyguard or system overlays."""
    if not screen_is_on(serial):
        shell(serial, "input", "keyevent", "224")
        time.sleep(0.8)
    shell(serial, "input", "keyevent", "82")
    shell(serial, "input", "swipe", "540", "1900", "540", "300", "600")
    shell(serial, "wm", "dismiss-keyguard")
    shell(serial, "cmd", "statusbar", "collapse")
    time.sleep(0.5)
