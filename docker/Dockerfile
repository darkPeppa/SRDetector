# syntax=docker/dockerfile:1.6
# SRDetector: Geant4 is built from source inside the image.
#
# Targets:
#   geant4  - Ubuntu 24.04 + compilers + Geant4 (MT, GDML, offscreen vis) + selected datasets
#   srdet   - geant4 + Python analysis env + the srdet application (default)
#   root    - srdet on top of the official ROOT image (TBrowser / JSROOT web GUI)
#
#   docker build -f docker/Dockerfile -t srdet .
#   docker build -f docker/Dockerfile --target root -t srdet-root .
#   slow network: put datasets into docker/g4data/ and add --build-context g4data=docker/g4data

ARG UBUNTU=24.04
ARG ROOT_IMAGE=rootproject/root:6.34.00-ubuntu24.04

############################ Geant4 ############################
# Optional pre-downloaded datasets: docker build --build-context g4data=docker/g4data ...
# (extracted <NAME><VERSION>/ folders or original archives); empty by default.
FROM scratch AS g4data

FROM ubuntu:${UBUNTU} AS geant4-build

ARG GEANT4_VERSION=11.3.2
ARG BUILD_JOBS=0

ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build curl ca-certificates git \
        libexpat1-dev zlib1g-dev libxerces-c-dev libfreetype-dev \
        python3 python3-venv python3-pip zstd xz-utils \
    && rm -rf /var/lib/apt/lists/*

# 1) compile + install Geant4 (own layer: cached independently of the datasets)
RUN set -eux; \
    mkdir -p /opt/src && cd /opt/src; \
    curl -fsSL --retry 5 -o g4.tar.gz \
        "https://github.com/Geant4/geant4/archive/refs/tags/v${GEANT4_VERSION}.tar.gz"; \
    tar xzf g4.tar.gz && rm g4.tar.gz; \
    jobs="${BUILD_JOBS}"; [ "$jobs" = 0 ] && jobs="$(nproc)"; \
    cmake -S geant4-${GEANT4_VERSION} -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/opt/geant4 \
        -DGEANT4_BUILD_MULTITHREADED=ON \
        -DGEANT4_USE_GDML=ON \
        -DGEANT4_USE_SYSTEM_EXPAT=ON \
        -DGEANT4_USE_SYSTEM_ZLIB=ON \
        -DGEANT4_USE_FREETYPE=ON \
        -DGEANT4_USE_QT=OFF -DGEANT4_USE_OPENGL_X11=OFF \
        -DGEANT4_INSTALL_DATA=OFF \
        -DGEANT4_INSTALL_EXAMPLES=OFF -DBUILD_TESTING=OFF; \
    cmake --build build -j "$jobs"; \
    cmake --install build; \
    cp geant4-${GEANT4_VERSION}/cmake/Modules/G4DatasetDefinitions.cmake /opt/geant4/share/Geant4/; \
    cd / && rm -rf /opt/src

FROM geant4-build AS geant4

# 2) datasets needed by the EM + optical physics (versions taken from the Geant4 sources).
#    Archives are kept in a BuildKit cache mount, so a failed / changed build never downloads twice.
ARG G4_DATASETS="G4EMLOW G4ENSDFSTATE RealSurface PhotonEvaporation RadioactiveDecay G4PARTICLEXS G4SAIDDATA"
COPY docker/fetch_datasets.py /opt/geant4/bin/fetch_datasets.py
RUN --mount=type=bind,from=g4data,target=/seed \
    --mount=type=cache,target=/var/cache/g4data \
    python3 /opt/geant4/bin/fetch_datasets.py --defs /opt/geant4/share/Geant4/G4DatasetDefinitions.cmake \
        --dest /opt/geant4/share/Geant4/data --cache /var/cache/g4data --seed /seed ${G4_DATASETS}

ENV GEANT4_DIR=/opt/geant4 \
    PATH=/opt/geant4/bin:${PATH} \
    LD_LIBRARY_PATH=/opt/geant4/lib

############################ Python + app ############################
FROM geant4 AS srdet

COPY python/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

ENV PATH=/opt/venv/bin:${PATH} \
    MPLBACKEND=Agg \
    PYTHONDONTWRITEBYTECODE=1 \
    SRDET_HOME=/opt/srdet \
    SRDET_BIN=/opt/srdet/bin/srdet-sim

COPY CMakeLists.txt /opt/srdet/src/CMakeLists.txt
COPY app /opt/srdet/src/app
RUN set -eux; \
    cmake -S /opt/srdet/src -B /opt/srdet/build -G Ninja -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_INSTALL_PREFIX=/opt/srdet; \
    cmake --build /opt/srdet/build -j "$(nproc)"; \
    cmake --install /opt/srdet/build

COPY python /opt/srdet/python
RUN /opt/venv/bin/pip install --no-cache-dir -e /opt/srdet/python

COPY docker/entrypoint.sh /usr/local/bin/srdet-entrypoint
RUN chmod +x /usr/local/bin/srdet-entrypoint

WORKDIR /work
ENTRYPOINT ["srdet-entrypoint"]
CMD ["--help"]

############################ ROOT flavour ############################
FROM ${ROOT_IMAGE} AS root

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        libexpat1 libxerces-c3.2t64 python3-venv zstd \
    && rm -rf /var/lib/apt/lists/*
COPY --from=srdet /opt/geant4 /opt/geant4
COPY --from=srdet /opt/srdet /opt/srdet
COPY python/requirements.txt /tmp/requirements.txt
RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && /opt/venv/bin/pip install --no-cache-dir -e /opt/srdet/python
COPY docker/entrypoint.sh /usr/local/bin/srdet-entrypoint
RUN chmod +x /usr/local/bin/srdet-entrypoint
ENV GEANT4_DIR=/opt/geant4 \
    PATH=/opt/venv/bin:/opt/geant4/bin:${PATH} \
    LD_LIBRARY_PATH=/opt/geant4/lib:${LD_LIBRARY_PATH} \
    MPLBACKEND=Agg \
    SRDET_HOME=/opt/srdet \
    SRDET_BIN=/opt/srdet/bin/srdet-sim
WORKDIR /work
EXPOSE 8888 8090
ENTRYPOINT ["srdet-entrypoint"]
CMD ["--help"]
