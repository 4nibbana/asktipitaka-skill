#!/bin/sh
# 老写法还留着：`bash install.sh` 仍然能用。
# ⚠️ 真正的安装程序是 install.py（Python 写的）——因为 **Windows 没有 sh**，
#    这个壳在那些机器上跑不起来。凡是新写的文档一律用：
#
#        python3 install.py
#
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for PY in python3 python; do
    if command -v "$PY" >/dev/null 2>&1; then
        exec "$PY" "$HERE/install.py" "$@"
    fi
done
printf '\n✗ 没有找到 Python 3。装好 Python 3 再跑一次。\n' >&2
exit 1
