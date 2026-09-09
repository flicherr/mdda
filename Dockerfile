# syntax=docker/dockerfile:1

FROM archlinux:base-devel-20260823.0.578598

ARG ARCH_SNAPSHOT=2026/08/23
ARG REQUIRED_CLANG_VERSION=22.1.8

RUN printf 'Server = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' \
      "${ARCH_SNAPSHOT}" > /etc/pacman.d/mirrorlist \
    && pacman -Syu --needed --noconfirm \
       clang llvm cmake ninja python make \
    && pacman -Scc --noconfirm \
    && clang++ --version | grep -F "clang version ${REQUIRED_CLANG_VERSION}"

ENV PYTHONPATH=/workspace/python \
    LC_ALL=C \
    LANG=C \
    TZ=UTC

WORKDIR /workspace
COPY . /workspace

RUN sed -i 's/\r$//' environment/run-container-experiment.sh \
    && chmod +x environment/run-container-experiment.sh \
    && cp environment/toolchain.example.json environment/toolchain.json \
    && make build \
    && make test \
    && make validate \
    && make doctor

ENTRYPOINT ["/workspace/environment/run-container-experiment.sh"]
