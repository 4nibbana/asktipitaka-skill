#!/bin/sh
# 一键安装：把底座（WikiPali 检索 CLI）取下来，然后自检一遍。
#
#     bash install.sh
#
# 装完就能用，不需要登录、不需要 pip install、不需要另外装插件。
# 重复跑是安全的：已经装过就只做更新。
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BASE="$HERE/.wikipali"
UPSTREAM="https://github.com/iapt-platform/wikipali-plugins"
CLI="$BASE/plugins/wikipali/bin/wikipali"

say() { printf '%s\n' "$*"; }
die() { printf '\n✗ %s\n' "$*" >&2; exit 1; }

say "问藏 skill · 安装"
say "──────────────────────────────"

# ── 1. 环境 ───────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || die "没有 python3。装好 Python 3 再跑一次。"
command -v git     >/dev/null 2>&1 || die "没有 git。装好 git 再跑一次。"
say "✓ python3 $(python3 -c 'import sys;print(".".join(map(str,sys.version_info[:3])))')"

# ── 2. 先更新本 skill 自己 ────────────────────────────────
# ⚠️ 这一步以前没有：重跑 install.sh 只更新底座、不更新 skill 本身，
#    于是「重跑一次就是更新」这句话是假的。现在真了。
#
# ⚠️ 2026-09-07 加「历史对不上也能自动跟上」。为什么：
#    公开库重建过一次历史，于是**已经装过的人再跑 install.sh 一律卡在
#    「更新失败」**，得自己手敲一条 reset --hard 才跟得上——这对普通使用者是个坑。
#    现在只要本地一个跟踪文件都没改过，就直接切到线上最新版，不用人动手。
#    ⚠️ 本地改过文件的才停下来问：那种情况下强切会毁掉他自己的东西。
if [ -d "$HERE/.git" ]; then
    say "· 更新本 skill…"
    OLD=$(cat "$HERE/VERSION" 2>/dev/null | tr -d '[:space:]')
    if ! git -C "$HERE" fetch --quiet --depth 1 origin main 2>/dev/null; then
        say "  ⚠ 连不上 github.com，这次没更新。"
        say "    ⚠️ **当前仍是旧版 ${OLD:-?}**，下面的自检针对的是旧版。"
    elif [ "$(git -C "$HERE" rev-parse HEAD 2>/dev/null)" \
         = "$(git -C "$HERE" rev-parse FETCH_HEAD 2>/dev/null)" ]; then
        say "✓ 已是最新（${OLD:-?}）"
    elif git -C "$HERE" diff-index --quiet HEAD -- 2>/dev/null; then
        # 上一行已确认**本地一个跟踪文件都没改过**，所以直接切到线上那一版是安全的：
        # 没有东西会丢，未跟踪的文件（.wikipali 底座）也原地不动。
        # ⚠️ 为什么不用 git pull / merge --ff-only：装机都是 --depth 1 浅克隆，
        #    浅克隆里根本判不了「能不能快进」，正常升级也会被判成失败——
        #    上一版就是卡在这，于是「重跑一次就是更新」又变成假话。
        # ⚠️ 用 checkout -B 而不是 reset --hard，是因为它顺带把 detached HEAD 接回 main。
        git -C "$HERE" checkout --quiet -B main FETCH_HEAD
        say "✓ 已更新到最新（${OLD:-?} → $(cat "$HERE/VERSION" 2>/dev/null | tr -d '[:space:]')）"
    else
        # 本地改过跟踪文件。**不强切**——那会毁掉使用者自己的东西。
        say "  ⚠ 本地改过文件，为免弄丢你的改动，这次没有自动更新。"
        say "    ⚠️ **当前仍是旧版 ${OLD:-?}**，下面的自检针对的是旧版。"
        say "    改过的是这些："
        git -C "$HERE" diff-index --name-only HEAD -- 2>/dev/null | sed 's/^/        /'
        say "    确认这些改动不要了，就强制跟上最新版："
        say "        git -C \"$HERE\" checkout -B main FETCH_HEAD"
    fi
fi

# ── 2b. 仓库搬过家的话，把 origin 指到新地址 ─────────────
# ⚠️ 为什么要这一步：仓库地址变动之后旧地址只是**跳转**，而 git 不会改本地的
#    origin——克隆会一直靠那个跳转活着，跳转哪天失效就连不上了。
#    REPO_URL 记的是仓库现在的正式地址，拉到新的就顺手改过来。
#    （git fetch 走跳转时不打印任何提示，所以只能靠这个文件对。）
if [ -d "$HERE/.git" ] && [ -f "$HERE/REPO_URL" ]; then
    WANT=$(tr -d '[:space:]' < "$HERE/REPO_URL")
    HAVE=$(git -C "$HERE" remote get-url origin 2>/dev/null || echo "")
    # 只比 owner/repo，不比协议——照顾用 SSH 克隆的人
    slug() { printf '%s' "$1" | sed -e 's#\.git$##' -e 's#/$##' \
             -e 's#^.*[:/]\([^/]*/[^/]*\)$#\1#' | tr 'A-Z' 'a-z'; }
    if [ -n "$HAVE" ] && [ "$(slug "$HAVE")" != "$(slug "$WANT")" ]; then
        case "$HAVE" in
            git@*|ssh://*) NEW="git@github.com:$(slug "$WANT").git" ;;
            *)             NEW="$WANT" ;;
        esac
        git -C "$HERE" remote set-url origin "$NEW"
        say "· 仓库换地址了，已把 origin 改成：$NEW"
    fi
fi

# ── 3. 底座：WikiPali 检索 CLI ────────────────────────────
# 检索、取原文全靠它。它是 MIT 公开的独立项目，这里只是取下来用，不改它。
if [ -d "$BASE/.git" ]; then
    say "· 底座已在，检查更新…"
    git -C "$BASE" pull --quiet --ff-only 2>/dev/null || say "  （拉取失败，继续用现有版本）"
else
    say "· 取底座（WikiPali 检索 CLI）…"
    rm -rf "$BASE"
    git clone --depth 1 --quiet "$UPSTREAM" "$BASE" \
        || die "取底座失败。检查网络能不能访问 github.com，然后重跑。"
fi
[ -f "$CLI" ] || die "底座目录结构不对，没找到 $CLI。请提 issue。"
say "✓ 底座就位"

# ── 4. 自检：真跑一次，不只是看文件在不在 ─────────────────
say "· 自检…"

python3 "$HERE/lib/pickwords.py" "别住是什么" --json >/dev/null 2>&1 \
    || die "选词层跑不起来。请提 issue 并附上上面的报错。"
say "  ✓ 选词层（17059 条译名表）"

if "$HERE/bin/wp" forms parivāsa >/dev/null 2>&1; then
    say "  ✓ 检索（已连通 WikiPali）"
else
    say "  ⚠ 检索没跑通——多半是暂时连不上 WikiPali。"
    say "    别的都装好了，过一会儿再试；命令是：bin/wp forms parivāsa"
fi

say "──────────────────────────────"
say "✓ 装好了。"
say ""
say "直接用中文问你的 AI 就行，例如："
say "    别住（parivāsa）是什么，什么情况下要别住"
say "    舍利弗尊者原名叫什么"
say ""
say "它会自己去巴利三藏里查，答案每条引用都带 [书号:段号] 坐标。"
say "⚠️ 当前版本的坐标没有经过机器核验，引用前请自己点开核对一遍（详见 README）。"
