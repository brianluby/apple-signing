#!/usr/bin/env python3
"""Upload signing secrets from a private terminal; never print their values."""
import base64
import getpass
import json
import pathlib
import re
import subprocess
import sys


def validate_p12(cert_path, password):
    """Validate an export, enabling legacy ciphers only for compatible errors."""
    if "\n" in password or "\r" in password:
        raise SystemExit("The export password must not contain a newline")
    command = ["openssl", "pkcs12", "-in", str(cert_path), "-noout", "-passin", "stdin"]
    options = dict(input=password.encode() + b"\n", stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    result = subprocess.run(command, **options)
    error = result.stderr.decode(errors="replace").lower()
    legacy = any(marker in error for marker in ("unsupported", "unknown cipher", "rc2-40-cbc"))
    if result.returncode and legacy:
        print("Export uses an older cipher; retrying with OpenSSL legacy support.")
        result = subprocess.run(command + ["-legacy"], **options)
        error = result.stderr.decode(errors="replace").lower()
    if not result.returncode:
        return
    if "mac verify" in error or "invalid password" in error:
        raise SystemExit("The .p12 export password did not verify; no secrets uploaded")
    if legacy:
        raise SystemExit("OpenSSL could not read the older export format even with legacy support; "
                         "no secrets uploaded. Test locally with openssl pkcs12 -legacy -info -noout.")
    raise SystemExit("OpenSSL could not parse the .p12 export; no secrets uploaded. "
                     "Test locally with openssl pkcs12 -info -noout for the specific error.")


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", sys.argv[1]):
        raise SystemExit("Usage: python3 configure-secrets.py OWNER/REPO")
    if not sys.stdin.isatty():
        raise SystemExit("Run in your own interactive terminal; credentials must stay out of chat/logs")
    repo = sys.argv[1]
    # Check the target before requesting sensitive input. Secrets go only here.
    subprocess.run(["gh", "api", f"repos/{repo}/environments/release-signing"],
                   check=True, stdout=subprocess.DEVNULL)
    print(f"Target: {repo}, environment: release-signing")
    cert_path = pathlib.Path(input("Path to exported Developer ID .p12: ").strip()).expanduser()
    if cert_path.suffix.lower() != ".p12" or not cert_path.is_file():
        raise SystemExit("Expected an exported .p12 file")
    cert_password = getpass.getpass("Password for the .p12 export: ")
    if not cert_password:
        raise SystemExit("A password-protected export is required")
    validate_p12(cert_path, cert_password)
    apple_id = input("Developer Apple Account: ").strip()
    notary_password = getpass.getpass("Apple app-specific password for notarization: ")
    if not all((apple_id, notary_password)):
        raise SystemExit("All credentials are required")
    values = {
        "APPLE_CERTIFICATE_P12_BASE64": base64.b64encode(cert_path.read_bytes()),
        "APPLE_CERTIFICATE_PASSWORD": cert_password.encode(),
        "APPLE_ID": apple_id.encode(),
        "APPLE_APP_SPECIFIC_PASSWORD": notary_password.encode(),
    }
    # GitHub secret values have a 48 KB limit (base64 increases the export size).
    if any(len(value) > 48 * 1024 for value in values.values()):
        raise SystemExit("A value exceeds GitHub's 48 KB secret limit; no secrets uploaded")
    for name, value in values.items():
        subprocess.run(["gh", "secret", "set", name, "--repo", repo,
                        "--env", "release-signing"], input=value, check=True)
        print("Saved", name)
    raw = subprocess.check_output(["gh", "api", f"repos/{repo}/environments/release-signing/secrets"])
    names = {entry["name"] for entry in json.loads(raw)["secrets"]}
    if not set(values) <= names:
        raise SystemExit("Secret metadata verification failed")
    print("Verified all four secret names. Values were not printed or saved by this helper.")


if __name__ == "__main__":
    main()
