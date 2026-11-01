#!/usr/bin/env python3
"""Tests for folding Proton multiline secrets into GKeyFile INI."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sanitize_keyring import (  # noqa: E402
    gkeyfile_escape,
    gkeyfile_unescape,
    is_key_line,
    persist_session,
    sanitize_keyring_file,
    sanitize_keyring_text,
)


CORRUPT = """[keyring]
display-name=Default keyring
lock-on-idle=false
lock-after=false

[4]
item-type=0
display-name=Password for 'proton-sso-account' on 'Proton'
secret={"ClientKey": "-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEASnHFoFbMzZGJ4ZHExZ8F1CkN1ccaE4WbNxMj6jzoU+U=
-----END PUBLIC KEY-----"}
mtime=1

[4:attribute0]
name=service
type=0
value=Proton
"""


class SanitizeKeyringTests(unittest.TestCase):
    def test_reencodes_json_instead_of_folding_it(self) -> None:
        out = sanitize_keyring_text(CORRUPT)
        line = next(l for l in out.split("\n") if l.startswith("secret="))
        stored = gkeyfile_unescape(line[len("secret="):])
        # The daemon holds the decoded value: it must be JSON, not a string with
        # raw newlines in it. proton.keyring_linux deletes an item whose stored
        # JSON will not parse, which surfaces as "logged out of Proton VPN"
        # with nothing in vpn-cli.log.
        payload = json.loads(stored)
        self.assertEqual(payload["ClientKey"].count("\n"), 2)
        self.assertNotIn("\\n", payload["ClientKey"])  # not literal backslash-n
        self.assertIn("\\\\nMCow", out)  # one escaping level in the file text
        self.assertIn("name=service", out)
        self.assertIn("value=Proton", out)
        self.assertIn("\n\n[4:attribute0]\n", out)

    def test_repairs_a_json_value_that_was_folded_not_escaped(self) -> None:
        # Pre-fix behaviour: PEM newlines folded to a single \n, so the file
        # parses but the decoded value holds real newlines and is invalid JSON.
        folded = CORRUPT.replace(
            "-----BEGIN PUBLIC KEY-----\nMCow\n-----END PUBLIC KEY-----",
            "-----BEGIN PUBLIC KEY-----\nMCow\n-----END PUBLIC KEY-----",
        )
        with self.assertRaises(ValueError):
            json.loads(folded.split("secret=")[1].split("\nmtime=")[0])

        out = sanitize_keyring_text(folded)
        line = next(l for l in out.split("\n") if l.startswith("secret="))
        payload = json.loads(gkeyfile_unescape(line[len("secret="):]))
        self.assertEqual(payload["ClientKey"].count("\n"), 2)

    def test_leaves_valid_json_and_plain_strings_untouched(self) -> None:
        value = gkeyfile_escape('{"a": "b"}')
        text = f"[9]\nitem-type=0\nsecret={value}\nmtime=1\n"
        self.assertEqual(sanitize_keyring_text(text), text)
        plain = "[9]\nitem-type=0\ndisplay-name=hello\nmtime=1\n"
        self.assertEqual(sanitize_keyring_text(plain), plain)

    def test_does_not_fold_blank_line_into_attribute_values(self) -> None:
        text = (
            "[1:attribute0]\n"
            "name=service\n"
            "type=0\n"
            "value=Proton\n"
            "\n"
            "[1:attribute1]\n"
            "name=username\n"
            "type=0\n"
            "value=proton-sso-accounts\n"
        )
        out = sanitize_keyring_text(text)
        self.assertEqual(out, text)

    def test_keeps_a_binary_secret_on_its_own_line(self) -> None:
        # gnome-keyring writes a secret that is not valid UTF-8 as
        # `binary-secret=<hex>` (ZapFast's 32-byte archive key, for one).
        # Folding that line into the value above it moves the secret into the
        # item's *label*, and the app then reads back an empty secret.
        secret = "AB12" * 16
        text = (
            "[7]\n"
            "item-type=0\n"
            "display-name=keyring:archive-0000@rocks.zapfast.ZapFast\n"
            f"binary-secret={secret}\n"
            "mtime=1\n"
        )
        out = sanitize_keyring_text(text)
        self.assertIn(f"binary-secret={secret}\n", out)
        self.assertNotIn("\\nbinary-secret=", out)

    def test_keeps_an_unknown_gkeyfile_field_on_its_own_line(self) -> None:
        text = (
            "[8]\n"
            "item-type=0\n"
            "display-name=other-app\n"
            "schema=org.example.Item\n"
            "mtime=1\n"
        )
        out = sanitize_keyring_text(text)
        self.assertEqual(out, text)
        self.assertNotIn("\\nschema=", out)

    def test_pem_continuation_is_not_a_key_line(self) -> None:
        self.assertTrue(is_key_line("secret={"))
        self.assertTrue(is_key_line("binary-secret=ab"))
        self.assertFalse(
            is_key_line(
                "MCowBQYDK2VwAyEASnHFoFbMzZGJ4ZHExZ8F1CkN1ccaE4WbNxMj6jzoU+U=",
            ),
        )
        self.assertFalse(is_key_line("-----END PUBLIC KEY-----\"}"))

    def test_idempotent_when_already_single_line(self) -> None:
        once = sanitize_keyring_text(CORRUPT)
        self.assertEqual(once, sanitize_keyring_text(once))

    def test_file_rewrite_changes_corrupt_ini(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Default_keyring.keyring"
            path.write_text(CORRUPT, encoding="utf-8")
            self.assertTrue(sanitize_keyring_file(path))
            self.assertFalse(sanitize_keyring_file(path))
            body = path.read_text(encoding="utf-8")
            self.assertIn("\\nMCow", body)
            self.assertNotIn("\nMCow", body)

    def test_persist_noop_without_ini(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            keyring_dir = Path(tmp) / "keyrings"
            keyring_dir.mkdir()
            os.environ["PROTONVPN_KEYRING_DIR"] = str(keyring_dir)
            try:
                self.assertFalse(persist_session())
            finally:
                del os.environ["PROTONVPN_KEYRING_DIR"]
            self.assertFalse((keyring_dir / "default").exists())
            self.assertFalse((keyring_dir / "Default_keyring.keyring").exists())

    def test_persist_folds_ini_and_pins_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            keyring_dir = Path(tmp) / "keyrings"
            keyring_dir.mkdir()
            ini = keyring_dir / "Default_keyring.keyring"
            ini.write_text(CORRUPT, encoding="utf-8")
            (keyring_dir / "default").write_text("Default\n", encoding="utf-8")
            os.environ["PROTONVPN_KEYRING_DIR"] = str(keyring_dir)
            try:
                self.assertTrue(persist_session())
                self.assertFalse(persist_session())
            finally:
                del os.environ["PROTONVPN_KEYRING_DIR"]
            body = ini.read_text(encoding="utf-8")
            self.assertIn("\\nMCow", body)
            self.assertNotIn("\nMCow", body)
            self.assertEqual((keyring_dir / "default").read_text(encoding="utf-8"), "Default_keyring\n")
            self.assertEqual(stat.S_IMODE(ini.stat().st_mode), 0o600)
            self.assertFalse((keyring_dir / "default.tmp").exists())

    def test_persist_skips_encrypted_keyring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            keyring_dir = Path(tmp) / "keyrings"
            keyring_dir.mkdir()
            ini = keyring_dir / "Default_keyring.keyring"
            ini.write_text("GKR\x00encrypted", encoding="latin-1")
            os.environ["PROTONVPN_KEYRING_DIR"] = str(keyring_dir)
            try:
                self.assertFalse(persist_session())
            finally:
                del os.environ["PROTONVPN_KEYRING_DIR"]
            self.assertEqual(ini.read_text(encoding="latin-1"), "GKR\x00encrypted")
            self.assertFalse((keyring_dir / "default").exists())

    def test_file_rewrite_skips_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.keyring"
            real.write_text(CORRUPT, encoding="utf-8")
            link = Path(tmp) / "Default_keyring.keyring"
            link.symlink_to(real)
            self.assertFalse(sanitize_keyring_file(link))
            self.assertEqual(real.read_text(encoding="utf-8"), CORRUPT)

    def test_persist_skips_symlink_ini(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            keyring_dir = Path(tmp) / "keyrings"
            keyring_dir.mkdir()
            real = Path(tmp) / "elsewhere.keyring"
            real.write_text(CORRUPT, encoding="utf-8")
            (keyring_dir / "Default_keyring.keyring").symlink_to(real)
            os.environ["PROTONVPN_KEYRING_DIR"] = str(keyring_dir)
            try:
                self.assertFalse(persist_session())
            finally:
                del os.environ["PROTONVPN_KEYRING_DIR"]
            self.assertEqual(real.read_text(encoding="utf-8"), CORRUPT)


if __name__ == "__main__":
    unittest.main()
