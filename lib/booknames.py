# -*- coding: utf-8 -*-
"""巴利书名 → 中文标注。

给不懂巴利的读者看的。**不用 AI 翻译**——书名翻译一旦被编造就是假出处，
踩作者的红线。巴利书名构词高度规律（部派＋品名＋层次后缀），
所以这里做的是确定的词素替换：查得到就标，查不到就只标层次，绝不猜。

输出形如：Apadāna-aṭṭhakathā  →  ［譬喻经·义注］
"""

# 层次后缀：先长后短，且 ṭīkā 必须先于 aṭṭhakathā —— 复注书名里常含 aṭṭhakathā
#
# ⚠️ 这张表只是**兜底**：层次与复注子类优先从实时输出的 tags 读
# （`app.py` 的 `book_layer_index()`），实测 281 部书 100% 有 tag。
# 这里留着是为了实时输出没给时还能标出个大概，别让它成为主路径。
LAYER = [
    ("mūlaṭīkā", "根本复注"),
    ("mahāṭīkā", "大复注"),
    ("anuṭīkā", "随复注"),
    ("abhinavaṭīkā", "新复注"),
    ("purāṇaṭīkā", "古复注"),
    # 连字符的位置有两种写法：Abhidhammāvatāra-purāṇaṭīkā 与
    # Kaṅkhāvitaraṇīpurāṇa-ṭīkā 是同一类，后者曾因此退成泛的「复注」。
    ("purāṇa-ṭīkā", "古复注"),
    ("ṭīkā", "复注"),
    ("ṭikā", "复注"),
    ("aṭṭhakathā", "义注"),
    ("ṭṭhakathā", "义注"),
    ("atthakatha", "义注"),
    ("yojanā", "释疏"),
    ("pāḷi", "根本"),
    ("pali", "根本"),
]

# 部派 / 藏
NIKAYA = [
    ("dīghanikāya", "长部"), ("(dn)", "长部"), ("dīgha", "长部"),
    ("majjhimanikāya", "中部"), ("(mn)", "中部"), ("majjhima", "中部"),
    ("saṃyuttanikāya", "相应部"), ("(sn)", "相应部"), ("saṃyutta", "相应部"),
    ("aṅguttaranikāya", "增支部"), ("(an)", "增支部"), ("aṅguttara", "增支部"),
    ("khuddakanikāya", "小部"), ("(kn)", "小部"), ("khuddaka", "小部"),
    ("(vn)", "律藏"), ("(sp)", "律藏"), ("vinaya", "律藏"),
    ("abhidhamma", "论藏"),
]

# 品名 / 经名 / 论名——只收有共识译名的，宁缺毋滥
WORKS = [
    ("sīlakkhandhavagg", "戒蕴品"), ("nidānavagg", "因缘品"),
    ("mahāvagg", "大品"), ("cūḷavagg", "小品"), ("culavagg", "小品"),
    ("majjhimapaṇṇāsa", "中五十"), ("mūlapaṇṇāsa", "根本五十"),
    ("uparipaṇṇāsa", "后五十"), ("pāthikavagg", "波梨品"),
    ("salāyatanavagg", "六处品"), ("khandhavagg", "蕴品"),
    ("sagāthāvagg", "有偈品"), ("mahāvaggasaṃyutta", "大品相应"),
    ("suttavibhaṅga", "经分别"), ("pārājika", "波罗夷"),
    ("pācittiya", "波逸提"), ("saṅghādisesa", "僧残"),
    ("khandhaka", "犍度"), ("parivāra", "附随"),
    ("pātimokkha", "波罗提木叉"), ("bhikkhunīvibhaṅga", "比丘尼分别"),
    ("dhammapada", "法句经"), ("apadāna", "譬喻经"),
    ("theragāthā", "长老偈"), ("therīgāthā", "长老尼偈"),
    ("jātaka", "本生经"), ("suttanipāta", "经集"),
    ("udāna", "自说经"), ("itivuttaka", "如是语"),
    ("vimānavatthu", "天宫事"), ("petavatthu", "饿鬼事"),
    ("buddhavaṃsa", "佛种姓经"), ("cariyāpiṭaka", "所行藏"),
    ("paṭisambhidāmagga", "无碍解道"), ("niddesa", "义释"),
    ("visuddhimagga", "清净道论"), ("milindapañha", "弥兰王问经"),
    ("mahāvaṃsa", "大史"), ("dīpavaṃsa", "岛史"),
    ("abhidhānappadīpikā", "名义灯论"), ("saddanīti", "语法论"),
    ("kaṅkhāvitaraṇī", "疑惑度脱"), ("samantapāsādikā", "普端严"),
    ("sumaṅgalavilāsinī", "吉祥悦意"), ("papañcasūdanī", "破斥犹豫"),
    ("sāratthappakāsinī", "显扬心义"), ("manorathapūraṇī", "满足希求"),
    ("paramatthajotikā", "胜义光明"), ("sāratthadīpanī", "心义灯"),
    ("vinayālaṅkāra", "律庄严"), ("vinayavinicchaya", "律抉择"),
    ("vinayasaṅgaha", "律摄"), ("khuddasikkhā", "小学处"),
    ("dhammasaṅgaṇī", "法集论"), ("vibhaṅga", "分别论"),
    ("kathāvatthu", "论事"), ("puggalapaññatti", "人施设论"),
    ("yamaka", "双论"), ("paṭṭhāna", "发趣论"), ("dhātukathā", "界论"),
]


def _find(text, table):
    """返回 (中文, 命中的巴利词)；按巴利词长度优先，避免短词先命中。"""
    hit = None
    for pali, cn in table:
        if pali in text:
            if hit is None or len(pali) > len(hit[1]):
                hit = (cn, pali)
    return hit


def chinese_label(title, with_layer=True, with_nikaya=True):
    """把巴利书名标成中文。查不到就只给层次，绝不硬猜。

    Apadāna-aṭṭhakathā            → 譬喻经·义注
    (DN) Sīlakkhandhavaggaṭṭhakathā → 长部·戒蕴品·义注
    Abhidhānappadīpikāṭīkā        → 名义灯论·复注
    某本没收录的书-ṭīkā             → 复注

    ⚠️ `with_layer=False` 时只给「部派·作品」，不带层次——**这是给答题材料用的**。
    2026-08-12 查出：材料里原本写的是 `chinese_label(title) or layer`，
    于是书名后缀拼得出中文标注时，**权威层次就被挤掉了**：
    `Abhidhānappadīpikāṭīkā` 显示成「名义灯论·复注」而不是「藏外·复注」，
    `Cūḷaganthavaṃsapāḷi`（小书志）显示成「根本」而不是「藏外」——
    正是 b13 号称修掉、其实只修了索引没修显示的那两类错。
    """
    if not title:
        return ""
    t = title.lower()
    parts = []

    # ⚠️ `with_nikaya=False` 用在「藏外」那一档（作者 2026-08-12 定）。
    # 「结集问答」系列（书 39–45）书名里含 Saṃyuttanikāye，拼出来是
    # ［相应部·藏外］——「相应部」暗示正典，与「藏外」自相矛盾。
    # 部派名不拼，作品名照拼，所以「名义灯论·藏外·复注」不受影响。
    nk = _find(t, NIKAYA) if with_nikaya else None
    if nk:
        parts.append(nk[0])

    wk = _find(t, WORKS)
    if wk and (not nk or wk[0] != nk[0]):
        parts.append(wk[0])

    if with_layer:
        ly = _find(t, LAYER)
        if ly:
            parts.append(ly[0])

    # 只认出层次（如「本文」）而没认出是哪部书时，标它意义不大，但仍比没有强
    return "·".join(dict.fromkeys(parts))


def layer_only(title):
    """只取文献层次。术语用作者的说法：根本／义注／复注（不写「本文」）。

    ⚠️ 认不出来时返回「层次未标注」，**绝不默认「根本」**。
    2026-08-08 修：原来的默认值是「根本」，于是《清净道论》这类书名里没有
    pāḷi／aṭṭhakathā／ṭīkā 标记的论师著作，全被标成了佛陀教说——
    「把论师的话当成佛说」正是本站承诺不犯的错。
    认不出层次是小事，认错层次是大事；不确定就说不确定。
    """
    ly = _find((title or "").lower(), LAYER)
    return ly[0] if ly else "层次未标注"
