# syntax=docker/dockerfile:1
# Contract R3: candidate Docker build; container acceptance is recorded separately.
FROM ubuntu:24.04@sha256:534baea6a22c03a63003dbc8dbe78fe34bc0d7e595d9a9dc9834884ff530eb55 AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates libseccomp2 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin checker \
    && mkdir -p /opt/credproof-runtime /opt/credproof /out \
    && chown -R checker:checker /opt/credproof-runtime /opt/credproof /out

FROM base AS runtime
ARG SOURCE_COMMIT
COPY --chown=checker:checker agent_pilot /build/agent_pilot
COPY --chown=checker:checker credproof_safety /build/credproof_safety
COPY --chown=checker:checker credproof_access /build/credproof_access
COPY --chown=checker:checker credproof /build/credproof
COPY --chown=checker:checker pyproject.toml /build/pyproject.toml
COPY --chown=checker:checker scripts/runtime/setup-linux.py /build/scripts/runtime/setup-linux.py
USER checker
# BuildKit may block nested namespaces. Permit only completed material creation;
# actual namespace readiness must be re-tested by doctor in the running container.
RUN python3 /build/scripts/runtime/setup-linux.py --runtime-root /opt/credproof-runtime; \
    cd /build && python3 -c 'from credproof_safety.runtime_setup import verify_runtime; verify_runtime("/opt/credproof-runtime")'
RUN python3 -m venv /opt/credproof/venv \
    && /opt/credproof/venv/bin/pip install --no-cache-dir setuptools wheel \
    && /opt/credproof/venv/bin/pip wheel --no-deps --no-build-isolation --wheel-dir /build/wheels /build \
    && /opt/credproof/venv/bin/pip install --no-deps /build/wheels/*.whl \
    && /opt/credproof/venv/bin/python -c 'import hashlib,json,pathlib,subprocess; p=next(pathlib.Path("/build/wheels").glob("*.whl")); pathlib.Path("/opt/credproof/build-receipt.json").write_text(json.dumps({"wheel":p.name,"wheel_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"apt":subprocess.check_output(["dpkg-query","-W","python3","python3-venv","libseccomp2"],text=True)},indent=2))'
RUN test -n "$SOURCE_COMMIT" && printf '%s\n' "$SOURCE_COMMIT" > /opt/credproof/source-commit.txt

FROM base AS final
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT
COPY --from=runtime /opt/credproof-runtime /opt/credproof-runtime
COPY --from=runtime /opt/credproof /opt/credproof
ENV CREDPROOF_CONFIG=/opt/credproof-runtime/runtime.json
USER checker
WORKDIR /workspace
ENTRYPOINT ["/opt/credproof/venv/bin/credproof-safety"]
