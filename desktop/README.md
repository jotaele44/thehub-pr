# TheHub desktop

## Install on macOS — no Terminal

1. Open this repository's **Releases** page and download the latest
   `PRII-THEHUB-macOS.dmg`.
2. Open the disk image and drag **TheHub** to **Applications**.
3. Open TheHub from Applications.

The release contains its own Python runtime, local federation backend, compiled
interface, registry, schemas, and readiness snapshot. Python, Node.js, Git,
Homebrew, and Terminal are not required.

On first launch, the native **Setup & Repair** screen asks for a writable data
location, verifies packaged resources and private loopback networking, and
starts the app. TheHub creates its mutable SQLite store in that location.
**Setup & Diagnostics** remains available in the lower-right corner; repair
does not delete the store.

## If macOS blocks the first open

Open **System Settings → Privacy & Security**, find the message naming TheHub,
and choose **Open Anyway**. No quarantine command is required. Release CI
applies an ad-hoc integrity signature, but public downloads are not
Apple-notarized unless a release is signed with project Developer ID
credentials.

The `PRII-THEHUB.app` committed in a source checkout is a Finder-only download
helper. The self-contained product is the app inside the release disk image.
`PRII Federation.app` is a legacy Finder-only alias to the same release helper;
it is not required to use TheHub.

## Shared runtime and release contract

`packages/prii_desktop` owns native setup, repair, diagnostics, storage
selection, single-instance handling, local-service lifecycle, and accessible
in-app setup controls. Producer repositories contain only configuration and
specialized server adapters.

The `desktop-build` workflow runs shared runtime tests, builds on clean Linux,
macOS, and Windows runners, and tests both the fresh-machine setup contract and
backend health on the frozen executable. macOS CI verifies the bundle signature
before producing the `.dmg`.

Source-checkout setup scripts remain developer conveniences and are not part of
end-user installation.
