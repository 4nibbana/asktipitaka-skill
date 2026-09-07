# -*- coding: utf-8 -*-
"""自更新与底座安装。**不依赖 git，也不依赖 sh。** 只用 Python 标准库。

⚠️ 这个文件为什么存在：

整个 skill 原先建在 `sh` 上——`install.sh`、`bin/wp`、`bin/check-update` 都是 sh 脚本。
**而 Windows 没有 sh。** 于是在那些机器上：装不了、更新不了，
连检索入口 `bin/wp` 都跑不起来——那份 skill 事实上是死的。

**Python 才是这个 skill 真正的硬要求**（选词层 `lib/pickwords.py` 就是 Python，
没有 Python 一步都走不了），`sh` 不是。所以一切改走 Python。

两条路，自己判断走哪条，不问使用者：

- **有 .git 且系统里有 git** → 走 git。省流量，而且**能判断本地改没改过文件**，
  改过就不动它。
- **否则** → 下载整包覆盖。整包压缩后约 0.2 MB，比一张照片还小。
  ⚠️ 这条路**没法知道使用者改没改过文件**，所以是直接覆盖——
  README 里已写明：手工拷贝的那份别在里面改东西。
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

BASE_UPSTREAM = "iapt-platform/wikipali-plugins"   # 底座：MIT 公开的独立项目，取来用，不改它
_TIMEOUT = 20


# ── 基本信息 ──────────────────────────────────────────────

def root_of(script_path):
    """从 bin/xxx 或 install.py 反推包根目录。"""
    d = os.path.dirname(os.path.abspath(script_path))
    return d if os.path.isfile(os.path.join(d, "VERSION")) else os.path.dirname(d)


def version(root):
    try:
        with io.open(os.path.join(root, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _slug(url):
    """从任意形式的仓库地址里取出 owner/repo，小写。SSH、HTTPS、带不带 .git 都吃。"""
    u = (url or "").strip().rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    parts = u.replace(":", "/").split("/")
    return "/".join(parts[-2:]).lower() if len(parts) >= 2 else ""


def repo_slug(root):
    """本包是从哪个仓库来的。以 REPO_URL 文件为准——
    ⚠️ 不写死地址：仓库将来换名字或换地方，这里不用改。"""
    p = os.path.join(root, "REPO_URL")
    if os.path.isfile(p):
        try:
            with io.open(p, encoding="utf-8") as f:
                s = _slug(f.read())
            if s:
                return s
        except Exception:
            pass
    return _slug(_git(root, "remote", "get-url", "origin") or "")


# ── 小工具 ────────────────────────────────────────────────

def have_git():
    return shutil.which("git") is not None


def _git(root, *args):
    """跑一条 git，成功返回输出，失败返回 None。任何情况下不抛。"""
    if not have_git():
        return None
    try:
        p = subprocess.run(["git", "-C", root] + list(args),
                           capture_output=True, timeout=120)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    return (p.stdout or b"").decode("utf-8", "replace").strip()


def http_get(url):
    """取一个网址，失败返回 None。⛔ 绝不因为网络问题打断使用者提问。"""
    try:
        from urllib.request import Request, urlopen
        req = Request(url, headers={"User-Agent": "asktipitaka-skill"})
        with urlopen(req, timeout=_TIMEOUT) as r:
            return r.read()
    except Exception:
        return None


def remote_version(slug):
    b = http_get("https://raw.githubusercontent.com/%s/main/VERSION" % slug)
    return b.decode("utf-8", "replace").strip() if b else None


def _unzip_over(data, dest, strip_top=True):
    """把 zip 内容覆盖到 dest。**只覆盖、不删除**——
    ⚠️ 线上删掉的文件在本地会留着。宁可留下孤儿，也不敢替使用者删东西。"""
    tmp = tempfile.mkdtemp(prefix="asktipitaka-")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
        src = tmp
        if strip_top:
            entries = [e for e in os.listdir(tmp) if not e.startswith(".")]
            if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
                src = os.path.join(tmp, entries[0])
        for dirpath, _dirnames, filenames in os.walk(src):
            rel = os.path.relpath(dirpath, src)
            out = dest if rel == "." else os.path.join(dest, rel)
            os.makedirs(out, exist_ok=True)
            for fn in filenames:
                shutil.copy2(os.path.join(dirpath, fn), os.path.join(out, fn))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _make_executable(root):
    """zip 里不带可执行位。类 Unix 上补回来，Windows 上这一步无意义也无害。"""
    for name in ("bin/wp", "bin/gather", "bin/check-update", "install.sh"):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            try:
                os.chmod(p, os.stat(p).st_mode | 0o111)
            except Exception:
                pass


# ── 自更新 ────────────────────────────────────────────────
# 返回 (状态, 旧版本, 新版本)。状态取值：
#   same    已是最新（或判断不了，当作最新）
#   updated 已更新
#   dirty   有新版但本地改过文件，没动它
#   offline 连不上，什么都没做

def self_update(root):
    old = version(root)
    slug = repo_slug(root)
    if not slug:
        return ("same", old, old)

    if os.path.isdir(os.path.join(root, ".git")) and have_git():
        return _update_via_git(root, old)
    return _update_via_zip(root, slug, old)


def _update_via_git(root, old):
    if _git(root, "fetch", "--quiet", "--depth", "1", "origin", "main") is None:
        return ("offline", old, old)
    local = _git(root, "rev-parse", "HEAD")
    remote = _git(root, "rev-parse", "FETCH_HEAD")
    if not remote or local == remote:
        return ("same", old, old)

    # ⚠️ 只有本地一个跟踪文件都没改过，才敢切。改过就不动——强切会毁掉他自己的东西。
    if _git(root, "diff-index", "--quiet", "HEAD", "--") is None:
        return ("dirty", old, old)

    # ⚠️ 用 checkout -B 而不是 pull / merge --ff-only：装机都是 --depth 1 浅克隆，
    #    浅克隆里根本判不了「能不能快进」，用 pull 连正常升级都会失败。
    #    -B 还顺带把 detached HEAD（按 tag 克隆的）接回 main。
    if _git(root, "checkout", "--quiet", "-B", "main", "FETCH_HEAD") is None:
        return ("offline", old, old)
    return ("updated", old, version(root))


def _ver(v):
    """把 "1.5.0" 变成 (1,5,0) 好比大小。比不了就返回 None。"""
    try:
        return tuple(int(x) for x in (v or "").strip().split("."))
    except Exception:
        return None


def _update_via_zip(root, slug, old):
    new = remote_version(slug)
    if new is None:
        return ("offline", old, old)
    if new == old:
        return ("same", old, old)
    # ⚠️ **只往前，不往后。** 版本号不同不等于该覆盖——
    #    本地比线上新的情形是真会发生的（改这个包的人，他的目录里没有 .git，
    #    会走到这条路上来）。不加这一道，跑一次安装就把自己的新代码
    #    整包覆盖成线上的旧版，而且一声不响。
    a, b = _ver(old), _ver(new)
    if a is not None and b is not None and b <= a:
        return ("same", old, old)
    data = http_get("https://codeload.github.com/%s/zip/refs/heads/main" % slug)
    if not data:
        return ("offline", old, old)
    try:
        _unzip_over(data, root)
    except Exception:
        return ("offline", old, old)
    _make_executable(root)
    return ("updated", old, version(root))


def dirty_files(root):
    out = _git(root, "diff-index", "--name-only", "HEAD", "--")
    return [l for l in (out or "").splitlines() if l.strip()]


# ── 底座（WikiPali 检索 CLI）──────────────────────────────

def cli_path(root):
    return os.path.join(root, ".wikipali", "plugins", "wikipali", "bin", "wikipali")


def ensure_base(root, quiet=False):
    """底座就位。有 git 走 git，没有就下 zip。返回 True/False。"""
    base = os.path.join(root, ".wikipali")
    def say(m):
        if not quiet:
            print(m)

    if os.path.isdir(os.path.join(base, ".git")) and have_git():
        say("· 底座已在，检查更新…")
        # ⚠️ 同样不用 pull：底座也是浅克隆。底座不由使用者改动，直接对齐远端即可。
        if _git(base, "fetch", "--quiet", "--depth", "1", "origin", "HEAD") is not None:
            _git(base, "reset", "--quiet", "--hard", "FETCH_HEAD")
        else:
            say("  （拉取失败，继续用现有版本）")
        return os.path.isfile(cli_path(root))

    if os.path.isfile(cli_path(root)):
        return True

    say("· 取底座（WikiPali 检索 CLI）…")
    if have_git():
        shutil.rmtree(base, ignore_errors=True)
        try:
            p = subprocess.run(["git", "clone", "--depth", "1", "--quiet",
                                "https://github.com/%s" % BASE_UPSTREAM, base],
                               capture_output=True, timeout=600)
            if p.returncode == 0 and os.path.isfile(cli_path(root)):
                return True
        except Exception:
            pass
    # 没有 git，或 git clone 失败：下整包
    data = http_get("https://codeload.github.com/%s/zip/refs/heads/main" % BASE_UPSTREAM)
    if not data:
        return False
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(base, exist_ok=True)
    try:
        _unzip_over(data, base)
    except Exception:
        return False
    return os.path.isfile(cli_path(root))
