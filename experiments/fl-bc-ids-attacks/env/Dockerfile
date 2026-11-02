# FL-BC-IDS experiment environment: a Linux x86_64 image (the repository's DP-XGBoost package has no Apple-silicon
# wheel) with the repository's pinned Python 3.12 dependencies built from source where needed, Node 24 with the
# repository's locked snarkjs/circomlib, and the circom 2.1.8 compiler. The clone is never copied into the image;
# run.sh mounts it read-only and copies it into the container's scratch space for each run.
FROM --platform=linux/amd64 python:3.12.10-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake git curl ca-certificates libgomp1 libomp-dev pkg-config xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Node 24 (the repository's environment/node_version.txt: v24.19.0) from the official tarball
ARG NODE_VERSION=24.19.0
RUN curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && mkdir -p /opt/node && tar -xJf /tmp/node.tar.xz -C /opt/node --strip-components=1 && rm /tmp/node.tar.xz
ENV PATH="/opt/node/bin:${PATH}"

# circom 2.1.8 (environment/circom_version.txt), the release binary for linux amd64
RUN curl -fsSL "https://github.com/iden3/circom/releases/download/v2.1.8/circom-linux-amd64" -o /usr/local/bin/circom \
    && chmod +x /usr/local/bin/circom && circom --version

# the repository's locked Node dependencies (snarkjs 0.7.5, circomlib, circomlibjs), installed outside the clone
COPY node-env/package.json node-env/package-lock.json /opt/node-env/
RUN cd /opt/node-env && npm ci --no-audit --no-fund && ls node_modules/.bin/snarkjs

# the repository's pinned Python dependencies; dp-xgboost 0.2.10 has no wheel for Python 3.12, so it builds from source
COPY requirements-repro.txt /opt/requirements-repro.txt
# setuptools is held below 81 because dp_xgboost/compat.py still imports pkg_resources, which newer setuptools removed
RUN python -m pip install --upgrade pip "setuptools<81" wheel \
    && pip install -r /opt/requirements-repro.txt
RUN python -c "import dp_xgboost, xgboost, flwr, ray, web3, dask; print('ok', xgboost.__version__, flwr.__version__)"

ENV FLBCIDS_NODE_MODULES=/opt/node-env/node_modules ANCHOR_ZKP_NODE_MODULES=/opt/node-env/node_modules \
    ANCHOR_ZKP_CIRCOM_LINK_LIBS=/opt/node-env/node_modules CIRCOM_LINK_LIBS=/opt/node-env/node_modules \
    ANCHOR_ZKP_CIRCOM_CMD=circom ANCHOR_ZKP_NODE_CMD=node
WORKDIR /work
CMD ["bash"]
