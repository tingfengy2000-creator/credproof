# Linux / Docker runtime — contract R3, part B

This branch implements preparation and harmless diagnosis. It does not run
models or change the 14 safety/business conditions. A and B start from the
contract merge `2a94ef8d6777676aba22e3ed68c23817c5f6aed2`.

## Supported preparation environment

Ubuntu 24.04, x86_64, non-root, system Python 3.12. WSL Ubuntu-24.04 uses the
same script inside Linux. Ubuntu 22.04 and Debian 12 are not supported here.
An operator installs system prerequisites first:

```sh
sudo apt-get install python3 python3-venv bubblewrap ca-certificates libseccomp2
python3 scripts/runtime/setup-linux.py --runtime-root /tmp/credproof-runtime-v1
export CREDPROOF_CONFIG=/tmp/credproof-runtime-v1/runtime.json
python3 -m credproof_safety doctor
python3 -m credproof_safety check --config examples/bench/b07-webhook-relay/project/credproof.toml
```

Preparation alone downloads the pinned official bwrap package and hashed
PyPI wheels. Check/doctor do not need model weights or a model service.
The lock is included in wheels. Use a persistent, operator-selected directory
instead of `/tmp` for routine deployment.

Existing runtimes are never deleted. Matching manifests, dependency bytes and
lock, bwrap, and preparer identity are verified before reuse. A missing or
different receipt is rejected: use a new versioned directory, retain the old
one. Reuse does not rewrite preparation or old probe receipts. A failed fresh
preparation remains for diagnosis; it is not silently resumed.

The rootfs contains a finite distribution Python/stdlib/shared-library
snapshot, not `/`, a link to `/`, or a copy of the container root. Its manifest
records files, modes, digests and package provenance. Doctor checks all bytes
and uses a fixed payload with the same bwrap namespace, read-only root and
pytest mount pattern as the checker. It verifies distinct namespaces, dropped
capabilities, private writable scratch, proc, and absence of host `/home`,
`/workspace`, `/opt/credproof`. No project code is imported by doctor.

Doctor returns 0 only when ready, otherwise 4 with structured hints. A check
whose boundary cannot run continues to produce UNKNOWN (3); a real policy
violation is FAIL (2). Do not interpret either as a successful safety check.

## Docker candidate: requires container acceptance

The Docker recipe and security profiles are **candidate configurations**.
Local WSL execution is not evidence that custom seccomp or AppArmor works in
Docker. This machine has no available Docker command; native/container hosted
VM acceptance belongs to C after A+B merge. Do not mark §6 complete yet.

```sh
docker build --platform linux/amd64 -f deploy/docker/Dockerfile \
  --build-arg SOURCE_COMMIT="$(git rev-parse HEAD)" -t credproof:dev38 .
mkdir -p credproof-out
docker run --rm --network none --read-only --tmpfs /tmp:exec \
  --cap-drop ALL --security-opt no-new-privileges \
  --security-opt seccomp=deploy/docker/seccomp-credproof.json \
  --security-opt systempaths=unconfined \
  -v "$PWD:/workspace:ro" -v "$PWD/credproof-out:/out" \
  credproof:dev38 doctor
```

Only after doctor is ready, run `check --config /workspace/<project>/credproof.toml`.
On A+B integration, derived outputs use A's `--source-root /workspace` and
`--sarif/--junit/--summary`. B alone adds only doctor to CLI.

The builder may prevent namespace creation. Build creation may proceed only
if `verify_runtime` proves completed materials; this is **not** a ready result.
Final-container doctor and anchor checks remain mandatory. The image records
source commit, wheel hash, base digest, apt versions and rootfs manifest hash.
No image is pushed. Root provisioning is only for installing distribution
packages; preparation and final execution run as uid 10001, never root.

Seccomp provenance/increments are in `deploy/docker/seccomp-source.json`;
the fixed original is saved alongside it. clone3 keeps ENOSYS. The added clone
rules admit explicit namespace combinations, not arbitrary clone3 structures.
Their sufficiency is unverified until container execution. Do not fall back to
privileged, cap-add, host networking or unconfined seccomp to pass acceptance.

On an AppArmor host, an operator may review/load the candidate:

```sh
sudo apparmor_parser -r deploy/apparmor/credproof-bwrap
```

Then explicitly add `--security-opt apparmor=credproof-bwrap`. This profile
allows namespace/mount work, while cap-drop and inner rootfs provide the
documented boundary. It has not been validated on an AppArmor Docker host.
If blocked, record attached profile and kernel denial events. Do not change
sysctl or silently choose apparmor=unconfined. Any explicit unconfined option
must have its own deployment evidence and scope stated before use.

## Image/member privacy scan

```sh
docker create --name credproof-scan credproof:dev38
docker export --output image.tar credproof-scan
docker rm credproof-scan
python3 scripts/runtime/scan-image.py image.tar --output image-scan.json
```

The scan does not extract tar members or follow links. Absolute/traversal
names, duplicates, empty scans and abnormal sizes fail; special files are
inventoried without reading them. rootfs/venv are allowed runtime materials,
unlike a viewer delivery package. All regular file bytes are hashed/counted;
binary internals are not claimed to be decoded source. Sensitive text uses the
existing delivery patterns. Exact vendor exceptions require file path, file
SHA256, match kind/hash and reason; no directory-wide exclusion is allowed.
Use `--private-values-file` for operator-known identities; never publish it.
Return codes: 0 no unexcepted hits, 1 hits, 4 incomplete scan. Do not claim a
zero-hit image based on fixture tests or a scan that never ran on image bytes.

## Evidence / scope

See [B evidence](evidence/runtime-b/README.md). Windows software tests, Linux
fixed-payload doctor, real WSL project checks, and future Docker/hosted VM
checks are separate evidence classes. No model calls are added by B.
