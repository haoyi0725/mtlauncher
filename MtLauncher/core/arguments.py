# -*- coding: utf-8 -*-
"""
正確解析 Minecraft version JSON 的 arguments.jvm / arguments.game
並過濾 Quick Play 衝突參數
"""
from typing import List, Dict, Any, Optional
from .libraries import check_rule, get_os_name

# 這些參數一次只能出現一種，一般啟動不需要
QUICK_PLAY_ARGS = {
    "--quickPlayPath",
    "--quickPlaySingleplayer",
    "--quickPlayMultiplayer",
    "--quickPlayRealms",
}

def resolve_arguments(
    version_json: Dict,
    placeholders: Dict[str, str],
    features: Optional[Dict] = None
) -> tuple[List[str], List[str]]:
    """
    回傳 (jvm_args, game_args)
    """
    if features is None:
        # 一般離線啟動不啟用 quick play / demo 等特殊功能
        features = {
            "is_demo_user": False,
            "has_custom_resolution": False,
            "has_quick_play_support": False,   # 關鍵：關掉 quick play
            "is_quick_play_singleplayer": False,
            "is_quick_play_multiplayer": False,
            "is_quick_play_realms": False,
        }

    args = version_json.get("arguments", {})
    jvm = _parse_arg_list(args.get("jvm", []), placeholders, features)
    game = _parse_arg_list(args.get("game", []), placeholders, features)

    # 舊版 minecraftArguments 相容
    if not game and "minecraftArguments" in version_json:
        raw = version_json["minecraftArguments"]
        game = [replace_placeholders(p, placeholders) for p in raw.split()]

    # 額外保險：把可能殘留的 quick play 參數全部移除
    game = _filter_quick_play(game)

    return jvm, game

def _parse_arg_list(arg_list: List, placeholders: Dict[str, str], features: Optional[Dict]) -> List[str]:
    result = []
    for item in arg_list:
        if isinstance(item, str):
            result.append(replace_placeholders(item, placeholders))
        elif isinstance(item, dict):
            rules = item.get("rules", [])
            value = item.get("value")

            # 沒有 rules → 直接加入
            # 有 rules → 必須全部符合才加入
            allowed = True
            if rules:
                allowed = False
                for rule in rules:
                    if check_rule(rule, features):
                        if rule.get("action") == "allow":
                            allowed = True
                        elif rule.get("action") == "disallow":
                            allowed = False

            if allowed:
                if isinstance(value, list):
                    for v in value:
                        result.append(replace_placeholders(str(v), placeholders))
                elif value is not None:
                    result.append(replace_placeholders(str(value), placeholders))
    return result

def _filter_quick_play(args: List[str]) -> List[str]:
    """移除所有 quick play 相關參數，避免衝突"""
    filtered = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in QUICK_PLAY_ARGS:
            # 跳過這個參數以及它後面的值
            skip_next = True
            continue
        # 也過濾掉 ${quickPlay...} 這種未替換的佔位符
        if "quickPlay" in arg.lower():
            continue
        filtered.append(arg)
    return filtered

def replace_placeholders(s: str, ph: Dict[str, str]) -> str:
    for k, v in ph.items():
        s = s.replace(f"${{{k}}}", str(v))
    return s