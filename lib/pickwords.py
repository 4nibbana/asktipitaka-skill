#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文问题 → 候选巴利检索词。

WikiPali 的检索走的是巴利词，这一步负责把中文这一头接上去：
读者用中文问，这里给出该去检索哪几个巴利词。

用法：

    python3 lib/pickwords.py "七色七非色是什么"
    python3 lib/pickwords.py --json "有一个名字叫荤腥的外道吗"

输出是**候选**，不是结论——最终查哪几个词由调用它的 agent 自己定（见 SKILL.md）。

⚠️ 只用 Python 标准库，不需要 pip 装任何东西。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS_PATH = os.path.join(HERE, os.pardir, "data", "terms.json")


# ── 判据一：二字组合重叠 ────────────────────────────────────────────
#
# 把译名表里每条中译切成二字组合建索引，再把问题也切成二字组合，看重叠。

# 太常见、拿来检索毫无区分度的二字组合，不参与匹配
_STOP_CH = set("是的什么有在怎为吗呢和与及了着过这那哪谁又都很就说讲请问我你他")


def _cn_grams(s):
    """取中文二字组合，跳过含停用字的。"""
    out = []
    for i in range(len(s) - 1):
        a, b = s[i], s[i + 1]
        if '一' <= a <= '鿿' and '一' <= b <= '鿿' \
                and a not in _STOP_CH and b not in _STOP_CH:
            out.append(a + b)
    return out


# 候选的「巴利词」必须是拉丁转写，否则整条不入索引。
# ⚠️ 实测 317/17059 条是缅文或方括号残渣（'အတွက်'、'[paṭiccasamuppāda'）。
#    它们当不了检索词，捞出来只会挤掉真候选——放宽判据那次，
#    「迦絺那衣」那题就被缅文条目灌了满屏。
_LATIN_WORD = re.compile(
    r"^[A-Za-zĀāĪīŪūṀṁṂṃṄṅÑñṆṇṬṭḌḍḶḷḸḹṚṛŚśṢṣ]"
    r"[\sA-Za-zĀāĪīŪūṀṁṂṃṄṅÑñṆṇṬṭḌḍḶḷḸḹṚṛŚśṢṣ.'’\-]*$")

# ⚠️ 一个二字组合出现在**不超过这么多条**里，就算「稀有」——
#    稀有到这个地步，它基本就是个唯一标识符，一次命中就够。
#    实测（17059 条表、12293 个不同二字组合）：
#      央掘 1 条、荤腥 2 条        ← 这是信号
#      故事 26、比库 62、本生 204、长老 233  ← 这是噪声
#    3 这条线把两边分得很干净。
_RARE_DF = 3

# ⚠️ 带这些字的二字组合**不走稀有捷径**。
#    它们在表里稀有、在**问题里却极通用**——是提问的脚手架，不是术语。
#    实测捞回来的是「一个对象」「当……的时候」这类语法注解。
#    ⚠️ 它们只是不享受「命中一个就算」的优待，命中 ≥2 个照常算候选。
_QUANT_CH = set("一二三四五六七八九十几每某各半全个部些样种时候")


# ── 判据二：精确匹配中译 ────────────────────────────────────────────
#
# ⚠️ 为什么还要这一道：稀有度判据治不了**泛词**。
#    实测表里「中译恰好两个汉字」的术语 2205 个，稀有度能捞到 1520 个，
#    **剩 685 个捞不到**——性质、善法、不死、有为、解脱、空性……
#    它们在表里出现太多条，过不了「≤3 条算稀有」那道门槛。
#    **调阈值治不了，得换判据。**
#
# 换的判据是：问题里若出现一个字串**恰好等于表里某条的中译**，那就是命中。
# 实测 9138 个「2–8 个纯汉字」的中译里，8147 个（89%）只对应一个巴利词。
# 那 685 个原本捞不到的，全部捞到。

# 表里的元数据占位，不是术语。实测「无法确定」挂 27 个词、「动词」26 个。
_META_MEANING = re.compile(
    r"^(无法确定|无法翻译|无可靠文献记载|待查|不详|未知|同上"
    r"|动词|名词|形容词|副词|代词|数词|连词|介词|助词|叹词|前缀|后缀|词根)$")

_EXACT_MAX_WORDS = 6      # 一个中译挂太多词就不是精准标识了

# ⚠️ **提问的脚手架，不是术语。** 这几条不是拍脑袋列的，
#    是拿 817 个真实问题实测出来的高频误命中：
#      如何 → kathañca（疑问副词）      44 次
#      意思 → manosañcetanā（意思食）   31 次 ← 「X 是什么意思」是最常见的问法
#      第一 → paṭhama                  20 次
#      尊者 → bhante（称谓）            17 次
#      区别 → upalakkhaṇa              13 次
#    ⚠️ 光看频次分不开：「佛陀」命中 72 次却是好的。
#       分界是**它是问句成分还是内容词**。
_ASK_FRAME = {"如何", "意思", "分别", "区别", "第一", "尊者", "在哪里", "什么",
              "这样", "那样", "怎样", "哪些", "多少", "为什么", "是否", "可以"}


def load_terms(path=None):
    """读译名表：[[巴利词, 中译], …]"""
    with open(path or TERMS_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 判据三：单字术语（2026-09-07 加）────────────────────────────────
#
# 中译只有一个汉字的术语，**上面两道判据都够不着**：
# 二字组合要两个汉字才成组合，精确匹配限定 2–8 字。
# 于是 546 条单字中译全部隐形——`lasuṇa → 蒜` 就在表里，问「大蒜」却一个候选都没有。
#
# ⚠️ **不能整批放开**：表里的单字中译包括「的」「吗」「不」「中」这些纯功能词，
#    「的」出现在 42% 的真实提问里。实测放开＝87% 的提问被污染。
#
# ⚠️ **也不能用「表里稀有」当判据**（上面 _RARE_DF 那条在这里不成立）：
#    「不」「大」「来」「意」在表里同样只挂一个词，在提问里却极通用。最严的一档仍污染 70%。
#
# 成立的判据是**「在真实提问里出现得够少」**——拿 2865 个去重真题量出来，
# 取出现率 <1% 的 109 个字、137 个巴利词。实测这 137 个**全部只有这一条路能进**
# （与二字路零重叠），其中包括 cīvara(衣)、phassa(触)、saddhā(信)、
# nirodha(灭)、kasiṇa(遍) 这些并不冷僻的词。
#
# ⚠️ 结果**固化在 data/单字术语表.json**，不在运行时重算——
#    动态算的话同一道题不同时候给出不同候选，回归就没有基线了。
#
# ⚠️ **这一类单独返回，不并进主候选**：调用方应当把它作为**另一块**交给模型，
#    并说明「可能不相干」。混进主列表会挤掉真候选（名额只有 4 个）。
SINGLE_PATH = os.path.join(HERE, os.pardir, "data", "单字术语表.json")


def load_single(path=None):
    """读单字术语表 → {字: [巴利词, …]}。文件缺失就返回空，绝不因此影响主流程。"""
    try:
        with open(path or SINGLE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {c: v["词"] for c, v in (d.get("字") or {}).items()}
    except Exception:
        return {}


def single_hits(question, table):
    """问题里出现了哪些单字术语。返回 [(字, [巴利词, …])]，按字在问题里的先后。"""
    if not table:
        return []
    seen, out = set(), []
    for ch in question or "":
        if ch in table and ch not in seen:
            seen.add(ch)
            out.append((ch, list(table[ch])))
    return out


def build_indexes(rows):
    """一次建好两张索引。表一万七千条，建一次约零点几秒，别在循环里反复调。"""
    gram, exact = {}, {}
    for word, meaning in rows:
        if not _LATIN_WORD.match(word or ""):
            continue
        # ⚠️ 用 set 去重：表里有重复条目（同一个「词+中译」出现多次）。
        #    不去重的话同一条会被计分两次，噪声词凑够门槛混进候选。
        for g in set(_cn_grams(meaning)):
            gram.setdefault(g, set()).add((word, meaning))

        t = re.sub(r"[《》〔〕()【】\[\]\s]", "", meaning or "")
        if not (2 <= len(t) <= 8):
            continue
        if not all("一" <= c <= "鿿" for c in t):
            continue
        if _META_MEANING.match(t) or t in _ASK_FRAME:
            continue
        exact.setdefault(t, set()).add(word)
    exact = {t: ws for t, ws in exact.items() if len(ws) <= _EXACT_MAX_WORDS}
    return gram, exact


def exact_hits(question, exact):
    """在问题里找「恰好等于某条中译」的字串。**长的优先**，已占用的字不再匹配。

    ⚠️ 长优先是必须的：「有为法」要整体命中 saṅkhatadhamma，
       而不能先被「有为」切走。
    """
    q = question or ""
    used = [False] * len(q)
    out = []
    for L in range(8, 1, -1):
        for i in range(len(q) - L + 1):
            if any(used[i:i + L]):
                continue
            t = q[i:i + L]
            if t in exact:
                out.append((t, sorted(exact[t])))
                for k in range(i, i + L):
                    used[k] = True
    return out


def pick(question, gram, exact, top=14):
    """返回 [(巴利词, 中译)]，越靠前越可能是这道题真正要查的。"""
    score, rarest = {}, {}
    for g in set(_cn_grams(question)):
        df = len(gram.get(g, ()))              # 这个二字组合出现在表里几条
        rare_ok = df <= _RARE_DF and not (set(g) & _QUANT_CH)
        for word, meaning in gram.get(g, []):
            k = (word, meaning)
            score[k] = score.get(k, 0) + 1
            if rare_ok:
                rarest[k] = min(rarest.get(k, 10 ** 9), df)

    # ⚠️ 放行判据：命中 **2 个**二字组合，**或**命中一个**稀有**的。
    #
    # 只用「≥2 个」有个结构性盲区：**刚好两个字的中文专名只产生一个二字组合，
    # 得分永远是 1，够不着门槛。** 实例：「有一个名字叫荤腥的外道吗？」——
    # 表里明明有 āmagandhasutta →《荤腥经》，却因为「荤腥」只算 1 分被滤掉，
    # 于是只好按字面把「荤腥」拆成 āmaka（生）＋ maṃsa（肉），整题答砸。
    #
    # 稀有度才是正确的判据：**出现在 ≤3 条里的二字组合近乎唯一标识符**，
    # 一次命中就够；泛词出现在几十上百条里，命中多少次都不足信。
    keep = ((k, n) for k, n in score.items() if n >= 2 or k in rarest)
    ranked = sorted(keep, key=lambda kv: (0 if kv[0] in rarest else 1,
                                          rarest.get(kv[0], 10 ** 9),
                                          -kv[1], -len(kv[0][1])))

    out, seen = [], set()
    # ── 精确命中先放，但**只占一半名额**，且按特异性排 ────────────────
    #
    # ⚠️ **不能让精确命中一律排最前、占满名额。** 实测「有一个名字叫荤腥的外道吗？」：
    #    「外道」精确命中 titthiya／bāhiraka 会把 āmagandhasutta（那题真正的正解）
    #    挤到第 3 位——而最终只选 4 个词。差点把刚修好的那题又挤坏。
    #
    # 特异性判据：**中译越长越具体**（有为法 > 有为），**挂的词越少越精准**。
    for t, words in sorted(exact_hits(question, exact),
                           key=lambda tw: (-len(tw[0]), len(tw[1]))):
        if len(out) >= max(1, top // 2):
            break
        for w in words:
            if w in seen:
                continue
            seen.add(w)
            out.append((w, t))

    for (word, meaning), _n in ranked:
        if word in seen:
            continue
        seen.add(word)
        out.append((word, meaning))
        if len(out) >= top:
            break
    return out


def main():
    ap = argparse.ArgumentParser(
        description="中文问题 → 候选巴利检索词（输出是候选，不是结论）")
    ap.add_argument("question", help="中文问题原文")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--top", type=int, default=14, help="最多给几个候选（默认 14）")
    ap.add_argument("--terms", default=None, help="译名表路径（默认 ../data/terms.json）")
    a = ap.parse_args()

    rows = load_terms(a.terms)
    gram, exact = build_indexes(rows)
    hits = pick(a.question, gram, exact, a.top)
    singles = single_hits(a.question, load_single())

    if a.json:
        json.dump({"question": a.question,
                   "candidates": [{"pali": w, "cn": m} for w, m in hits],
                   "single_char": [{"cn": c, "pali": ws} for c, ws in singles]},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if hits:
        print("候选（越靠前越可能是这题要查的；最终选哪几个由你定，最多 4 个）：")
        for w, m in hits:
            print("  %-32s %s" % (w, m))
    else:
        print("译名表里没有捞到候选词。")
        print("⚠️ 这不代表三藏里没有——按 SKILL.md 的规矩，")
        print("   自己判断该查哪个巴利词，并且记住「查到 0 条先怀疑拼法」。")

    if singles:
        print()
        print("单字术语（另一类，**可能跟这道题不相干，自己判断**）：")
        for c, ws in singles:
            print("  %-32s %s" % ("、".join(ws), c))


if __name__ == "__main__":
    main()
