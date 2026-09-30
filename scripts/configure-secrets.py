#!/usr/bin/env python3
"""Upload signing secrets from a private terminal; never print their values."""
import base64
import getpass
import json
import pathlib
import re
import subprocess
import sys


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
    apple_id = input("Developer Apple Account: ").strip()
    notary_password = getpass.getpass("Apple app-specific password for notarization: ")
    if not all((cert_password, apple_id, notary_password)):
        raise SystemExit("All credentials are required")
    # Validate the export password without outputting certificates or keys.
    result = subprocess.run(["openssl", "pkcs12", "-in", str(cert_path), "-noout",
                             "-passin", "stdin"], input=cert_password.encode() + b"\n",
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise SystemExit("Unable to open .p12 with that password; no secrets uploaded")
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
