# Apple signing for macOS releases

Reusable GitHub Actions workflow for Developer ID signing and Apple notarization of standalone macOS command-line executables. The same certificate can sign multiple applications. This first workflow handles one executable inside a tar.gz package; application bundles, nested libraries, custom entitlements, DMGs and PKG installers need a dedicated extension before use.

## Setup for each application repository

Create a `release-signing` environment in the **calling repository**. Require a maintainer review, allow only `main` branch and release tags (`v*`), and keep pull request workflows away from this environment. Solo maintainers may approve their own release runs. The environment still permits trusted workflows to access all its secrets after approval: protect release workflow changes and tag creation accordingly.

Configure these environment secrets through the private terminal helper below:

| Secret | Value |
| --- | --- |
| APPLE_CERTIFICATE_P12_BASE64 | Base64 of Developer ID Application certificate **and its private key** exported from Keychain Access as a password-protected .p12 |
| APPLE_CERTIFICATE_PASSWORD | Password chosen for that .p12 export |
| APPLE_ID | Developer Apple Account identifier |
| APPLE_APP_SPECIFIC_PASSWORD | Apple app-specific password for notarization |

The local `apple-notary` Keychain profile does not transfer to GitHub runners. Never put any credential in Git, issue comments, workflow inputs or logs. `scripts/configure-secrets.py OWNER/REPO` prompts privately, sends values directly to `gh secret set` over stdin, and prints only names. It does not save secrets to files. Run it in your own interactive terminal after exporting the .p12; enter the app-specific password there.

Organization secrets can be reused within an organization with a selected repository access policy. Personal repositories require secrets per repository. Environment approvals and branch/tag policies are also per repository. GitHub Free organizations do not expose organization secrets to private repositories.

## Workflow contract

The caller builds and tests without signing credentials, then uploads an artifact containing a tar.gz package and checksum. Call `.github/workflows/sign-macos.yml` pinned to a reviewed commit SHA, with `artifact-name`, `archive-name`, and `binary-path` inputs. The signing job uses a separate macOS runner, downloads only the artifact from the current run, validates extraction, imports the identity into a temporary Keychain, signs with hardened runtime and a trusted timestamp, requires Apple's `Accepted` result, verifies notarization, regenerates the tar.gz and checksum, and replaces the artifact under its original name. It never executes the supplied executable. The publish job must depend on the signing job and download only the application's artifact pattern, excluding signing evidence.

The default identity/team are `Developer ID Application: Brian Luby (DVH6X33J83)` and `DVH6X33J83`. Override the inputs for another team. macOS retrieves tickets for standalone Mach-O tools online; `stapler` cannot attach a ticket to a plain executable or ZIP. Re-signing after acceptance changes the signature and requires re-notarization.

## Rollout

First run the caller's `release` workflow manually on `main`. Approve its signing environment. This produces signed, notarized run artifacts without publishing a release. After this succeeds, a protected version tag can use the same pipeline to publish. A failure to sign or notarize blocks publication. Signing evidence is uploaded separately as `apple-notarization-ARTIFACT_NAME`.

References: [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows), [GitHub secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets), [Apple notarization](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
