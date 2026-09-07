#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键安装：把底座（WikiPali 检索 CLI）取下来，然后自检一遍。

    python3 install.py

装完就能用，不需要登录、不需要 `pip install`、不需要另外装插件。
重复跑是安全的：已经装过就只做更新。

⚠️ 2026-09-07 从 `install.sh` 改写成 Python，并且**不再要求装 git**。
   原因：**Windows 没有 sh**，原先那版在那些机器上装不了；
   而 git 也不是人人都有。Python 才是本 skill 真正的硬要求（选词层就是 Python）。
   有 git 就用 git（省流量），没有就下整包——整包压缩后约 0.2 MB。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
import portable  # noqa: E402


def say(m=""):
    print(m)


def die(m):
    sys.stderr.write("\n✗ %s\n" % m)
    sys.exit(1)


def fix_origin():
    """仓库搬过家的话，把 origin 指到新地址。

    ⚠️ 为什么要这一步：仓库地址变动之后旧地址只是**跳转**，而 git 不会改本地的
       origin——克隆会一直靠那个跳转活着，跳转哪天失效就连不上了。
       REPO_URL 记的是仓库现在的正式地址，拉到新的就顺手改过来。
       （git fetch 走跳转时不打印任何提示，所以只能靠这个文件对。）
    """
    if not (os.path.isdir(os.path.join(HERE, ".git")) and portable.have_git()):
        return
    want = portable.repo_slug(HERE)
    have_url = portable._git(HERE, "remote", "get-url", "origin") or ""
    have = portable._slug(have_url)
    if not have or not want or have == want:
        return
    # 只比 owner/repo，不比协议——照顾用 SSH 克隆的人
    new = ("git@github.com:%s.git" % want) if have_url.startswith(("git@", "ssh://")) \
          else ("https://github.com/%s" % want)
    if portable._git(HERE, "remote", "set-url", "origin", new) is not None:
        say("· 仓库换地址了，已把 origin 改成：%s" % new)


def main():
    say("问藏 skill · 安装")
    say("──────────────────────────────")

    # ── 1. 环境 ───────────────────────────────────────────
    # ⚠️ 只查 Python。git 不再是必需的——没有 git 就走整包下载那条路。
    if sys.version_info[0] < 3:
        die("需要 Python 3。")
    say("✓ python %s" % ".".join(str(x) for x in sys.version_info[:3]))
    if not portable.have_git():
        say("  （系统里没有 git，更新与安装改走整包下载，不影响使用）")

    # ── 2. 先更新本 skill 自己 ────────────────────────────
    say("· 更新本 skill…")
    state, old, new = portable.self_update(HERE)
    if state == "updated":
        say("✓ 已更新到最新（%s → %s）" % (old or "?", new or "?"))
    elif state == "same":
        say("✓ 已是最新（%s）" % (old or "?"))
    elif state == "offline":
        say("  ⚠ 连不上 github.com，这次没更新。")
        say("    ⚠️ **当前仍是旧版 %s**，下面的自检针对的是旧版。" % (old or "?"))
    elif state == "dirty":
        say("  ⚠ 本地改过文件，为免弄丢你的改动，这次没有自动更新。")
        say("    ⚠️ **当前仍是旧版 %s**，下面的自检针对的是旧版。" % (old or "?"))
        say("    改过的是这些：")
        for f in portable.dirty_files(HERE):
            say("        " + f)
        say("    确认这些改动不要了，就强制跟上最新版：")
        say('        git -C "%s" checkout -B main FETCH_HEAD' % HERE)

    fix_origin()

    # ── 3. 底座：WikiPali 检索 CLI ────────────────────────
    # 检索、取原文全靠它。它是 MIT 公开的独立项目，这里只是取下来用，不改它。
    if not portable.ensure_base(HERE):
        die("取底座失败。检查网络能不能访问 github.com，然后重跑。")
    say("✓ 底座就位")

    # ── 4. 自检：真跑一次，不只是看文件在不在 ─────────────
    say("· 自检…")
    r = subprocess.call([sys.executable, os.path.join(HERE, "lib", "pickwords.py"),
                         "别住是什么", "--json"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r != 0:
        die("选词层跑不起来。请提 issue 并附上上面的报错。")
    say("  ✓ 选词层（17059 条译名表）")

    r = subprocess.call([sys.executable, os.path.join(HERE, "bin", "wp"),
                         "forms", "parivāsa"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r == 0:
        say("  ✓ 检索（已连通 WikiPali）")
    else:
        say("  ⚠ 检索没跑通——多半是暂时连不上 WikiPali。")
        say("    别的都装好了，过一会儿再试；命令是：python3 bin/wp forms parivāsa")

    say("──────────────────────────────")
    say("✓ 装好了。")
    say()
    say("直接用中文问你的 AI 就行，例如：")
    say("    别住（parivāsa）是什么，什么情况下要别住")
    say("    舍利弗尊者原名叫什么")
    say()
    say("它会自己去巴利三藏里查，答案每条引用都带 [书号:段号] 坐标。")
    say("⚠️ 当前版本的坐标没有经过机器核验，引用前请自己点开核对一遍（详见 README）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
