#!/bin/bash
# SPDX-License-Identifier: GPL-2.0

set -e

TARGET_DEVICE="mgk_64_k61"
GKI_BUILD_ID="16528172" # android14-6.1-2026-09_r3

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${ROOT_DIR}"

KERNEL_MODULES_DIR="$(find "${ROOT_DIR}" -maxdepth 1 -type d -name 'kernel_device_modules-*' | sort -V | tail -n1)"
if [ -z "${KERNEL_MODULES_DIR}" ] || [ ! -f "${KERNEL_MODULES_DIR}/build.sh" ]; then
    echo "error: no kernel_device_modules-*/build.sh found for MGKI build" >&2
    exit 1
fi
KERNEL_MODULES_NAME="$(basename "${KERNEL_MODULES_DIR}")"

# _setup_env.sh prepends ROOT_DIR twice if out/ doesn't exist yet
export OUT_DIR="${ROOT_DIR}/out"
mkdir -p "${OUT_DIR}"

INTERMEDIATE_DIST="${OUT_DIR}/dist"
FINAL_DIST="${OUT_DIR}/${TARGET_DEVICE}/dist"

rm -rf "${INTERMEDIATE_DIST}" "${FINAL_DIST}"

"${KERNEL_MODULES_DIR}/build.sh"

SRC="${INTERMEDIATE_DIST}/${KERNEL_MODULES_NAME}"
if [ ! -d "${SRC}" ]; then
    echo "error: MGKI dist output not found under ${SRC}" >&2
    exit 1
fi

mkdir -p "${FINAL_DIST}"

cp -a "${SRC}/${TARGET_DEVICE}_customer_modules_install.user/"*.ko "${FINAL_DIST}/"

find "${SRC}/${TARGET_DEVICE}_kernel_aarch64.user/" -name '*.ko' -exec cp -t "${FINAL_DIST}/" {} +
cp -a "${SRC}/${TARGET_DEVICE}_kernel_aarch64.user/"Image.* "${FINAL_DIST}/"

dtbo_img="${SRC}/${TARGET_DEVICE}_kernel_images.user_dtbo/dtbo.img"
if [ -f "${dtbo_img}" ]; then
    cp -a "${dtbo_img}" "${FINAL_DIST}/"
fi

cp -a "${SRC}/${TARGET_DEVICE}_merged_uapi_headers.user/"* "${FINAL_DIST}/"

cp -a "${SRC}/${TARGET_DEVICE}.user/"*.dtb "${FINAL_DIST}/"
find "${SRC}/${TARGET_DEVICE}.user/" -name '*.ko' -exec cp -n -t "${FINAL_DIST}/" {} +

echo "MGKI kernel artifacts staged in ${FINAL_DIST}"

GKI_PREBUILTS_DIR="${ROOT_DIR}/prebuilts/gki" # Created by download_prebuilts.py
GKI_PREBUILTS_INTERMEDIATE_DIST="${GKI_PREBUILTS_DIR}"/kernel_aarch64/tmp_dist
GKI_PREBUILTS_DIST="${GKI_PREBUILTS_DIR}/dist"

python3 "${ROOT_DIR}"/download_prebuilts.py --force --build_target kernel_aarch64 --build_id "${GKI_BUILD_ID}"

mkdir -p "${GKI_PREBUILTS_INTERMEDIATE_DIST}"
mkdir -p "${GKI_PREBUILTS_DIST}"

tar -xzf "${GKI_PREBUILTS_DIR}"/kernel_aarch64/system_dlkm_staging_archive.tar.gz -C "${GKI_PREBUILTS_INTERMEDIATE_DIST}/"

find "${GKI_PREBUILTS_INTERMEDIATE_DIST}/flatten/lib/modules/" -name '*.ko' -exec cp -t "${GKI_PREBUILTS_DIST}/" {} +
cp -a "${GKI_PREBUILTS_DIR}"/kernel_aarch64/Image.lz4 "${GKI_PREBUILTS_DIST}/"
cp -a "${GKI_PREBUILTS_DIST}"/* "${FINAL_DIST}/"

rm -rf "${GKI_PREBUILTS_DIR}"

echo "Google GKI kernel artifacts staged in ${FINAL_DIST}"
