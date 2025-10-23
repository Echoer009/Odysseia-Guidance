# -*- coding: utf-8 -*-

"""
表情符号配置文件
用于定义AI输出文本到Discord自定义表情符号的映射关系
使用正则表达式进行匹配和替换
"""

import re

# 定义表情符号映射
# 格式: [(正则表达式, Discord表情符号), ...]
EMOJI_MAPPINGS = [
    (re.compile(r"\<微笑\>"), ["<:xianhua:1410752700702003210>"]),
    (re.compile(r"\<伤心\>"), ["<:shang_xin:1413095411601637479>"]),
    (re.compile(r"\<生气\>"), ["<:shen_qi:1413095198258630748>"]),
    (re.compile(r"\<乖巧\>"), ["<:guai_qiao:1413095057099067442>"]),
    (re.compile(r"\<傲娇\>"), ["<:ao_jiao:1413094971799502869>"]),
    (re.compile(r"\<尴尬赞\>"), ["<:ganga_zan:1425171040354701454>"]),
    (re.compile(r"\<赞\>"), ["<:good:1425170994917675139>"]),
    (re.compile(r"\<吃瓜\>"), ["<:chi_gua:1425170954052440074>"]),
    (re.compile(r"\<偷笑\>"), ["<:tou_xiao:1425170902370484304>"]),
    (re.compile(r"\<无语\>"), ["<:wu_yu:1425170859227742402>"]),
    (re.compile(r"\<鬼脸\>"), ["<:ghost_face:1425170793385562132>"]),
    (re.compile(r"\<鄙视\>"), ["<:bi_shi:1425170749072736329>"]),
    (re.compile(r"\<思考\>"), ["<:ping_jing:1425170646639312916>"]),
    (re.compile(r"\<害羞\>"), ["<:shy:1425170441739436032>"]),
]

# --- 活动专属表情 ---

# 万圣节 2025 - 幽灵派系
_HALLOWEEN_GHOST_EMOJI_MAPPINGS = [
    (re.compile(r"\<害羞\>"), ["<:hai_xiu:1430196858394902683>"]),
    (re.compile(r"\<害怕\>"), ["<:hai_pa:1430196738240806973>"]),
    (re.compile(r"\<开心\>"), ["<:kai_xin:1430196805194223707>"]),
    (re.compile(r"\<紧张\>"), ["<:jing_zhang:1430197186636812378>"]),
    (re.compile(r"\<鲜花\>"), ["<:xian_hua:1430197117703684219>"]),
    (re.compile(r"\<生气\>"), ["<:sheng_qi:1430197007183642724>"]),
    (re.compile(r"\<呆\>"), ["<:dai:1430196922039402548>"]),
]

# 万圣节 2025 - 吸血鬼派系
_HALLOWEEN_VAMPIRE_EMOJI_MAPPINGS = [
    (re.compile(r"\<得意\>"), ["<:de_yi_x:1430506851946201120>"]),
    (re.compile(r"\<害羞\>"), ["<:hai_xiu_x:1430506905792413828>"]),
    (re.compile(r"\<生气\>"), ["<:sheng_qi_x:1430506963581534321>"]),
    (re.compile(r"\<惊慌\>"), ["<:jing_huang:1430506696219820134>"]),
    (re.compile(r"\<思考\>"), ["<:si_kao_x:1430506590800318515>"]),
    (re.compile(r"\<无奈\>"), ["<:wu_nai:1430507004014755850>"]),
    (re.compile(r"\<挑衅\>"), ["<:tiao_xing:1430506499184263228>"]),
    (re.compile(r"\<坏笑\>"), ["<:huai_xiao:1430506761529593906>"]),
]

# 万圣节 2025 - 教会派系
_HALLOWEEN_CHURCH_EMOJI_MAPPINGS = [
    (re.compile(r"\<开心\>"), ["<:kai_xin_church:1430887660875943946>"]),
    (re.compile(r"\<得意\>"), ["<:de_yi_church:1430887600897658920>"]),
    (re.compile(r"\<嘴馋\>"), ["<:zui_chan:1430887403681480724>"]),
    (re.compile(r"\<期待\>"), ["<:qi_dai:1430887364238119043>"]),
    (re.compile(r"\<满足\>"), ["<:man_zu:1430887322626428928>"]),
    (re.compile(r"\<生气\>"), ["<:sheng_qi_church:1430887232126058518>"]),
    (re.compile(r"\<感谢\>"), ["<:gan_xie:1430887181831897209>"]),
    (re.compile(r"\<祈祷\>"), ["<:qi_dao:1430887118850359327>"]),
    (re.compile(r"\<饿了\>"), ["<:e_le:1430886719569526795>"]),
]

# --- 派系表情总配置 ---
# 结构: { "event_id": { "faction_id": MAPPING_LIST } }
FACTION_EMOJI_MAPPINGS = {
    "halloween_2025": {
        "ghost": _HALLOWEEN_GHOST_EMOJI_MAPPINGS,
        "vampire": _HALLOWEEN_VAMPIRE_EMOJI_MAPPINGS,
        "church": _HALLOWEEN_CHURCH_EMOJI_MAPPINGS,
    }
}
