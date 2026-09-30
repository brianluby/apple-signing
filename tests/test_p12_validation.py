import importlib.util
import pathlib
import subprocess
import tempfile
import unittest

HELPER = pathlib.Path(__file__).parents[1] / "scripts/configure-secrets.py"
spec = importlib.util.spec_from_file_location("configure_secrets", HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class P12Validation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = pathlib.Path(cls.directory.name)
        # Disposable generated fixture keys, never the user's signing key.
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-keyout", str(cls.path / "key.pem"), "-out", str(cls.path / "cert.pem"),
                        "-subj", "/CN=Disposable test fixture", "-days", "1"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for name, options in (("modern", []), ("legacy", ["-legacy"])):
            subprocess.run(["openssl", "pkcs12", "-export", "-inkey", str(cls.path / "key.pem"),
                            "-in", str(cls.path / "cert.pem"), "-out", str(cls.path / (name + ".p12")),
                            "-passout", "stdin"] + options, input=b"fixture-only-password\n",
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_modern_correct_password(self):
        helper.validate_p12(self.path / "modern.p12", "fixture-only-password")

    def test_legacy_correct_password(self):
        helper.validate_p12(self.path / "legacy.p12", "fixture-only-password")

    def test_wrong_password(self):
        for name in ("modern", "legacy"):
            with self.subTest(name=name), self.assertRaisesRegex(SystemExit, "password did not verify"):
                helper.validate_p12(self.path / (name + ".p12"), "wrong-fixture-password")
