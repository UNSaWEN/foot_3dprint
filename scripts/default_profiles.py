from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_PROFILE_NAME = "healthy_asian_male_mixed"


PROFILES: dict[str, dict[str, Any]] = {
    "healthy_asian_male_mixed": {
        "label": "Healthy adult Asian male, mixed daily use",
        "zone_settings": {
            "base": {
                "role": "base_model",
                "infill_pattern": "gyroid",
                "infill_density_percent": 20,
                "walls": 3,
                "top_shell_layers": 4,
                "bottom_shell_layers": 4,
                "notes": "基础鞋垫主体，适合日常步行与轻运动混合场景。",
            },
            "innerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 24,
                "walls": None,
                "notes": "内侧后跟中性稳定区，默认继承主体墙数以减少边界硬峰。",
            },
            "outerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 20,
                "walls": None,
                "notes": "外侧后跟落地缓冲区，保留正常步态初始接触的缓冲感。",
            },
            "innerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 34,
                "walls": None,
                "notes": "内侧足弓中等支撑区，面向健康成年男性的中性支撑模板。",
            },
            "outerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 26,
                "walls": None,
                "notes": "外侧中足过渡区，保持稳定但避免整体过硬。",
            },
            "innerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": None,
                "notes": "内侧前掌承力区，兼顾推进和轻度支撑。",
            },
            "centralForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": None,
                "notes": "前掌中央重点承力区，贴近正常步态中第2跖骨头附近的负荷路径，并避免局部墙造成额外硬峰。",
            },
            "outerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 17,
                "walls": None,
                "notes": "外侧前掌释放区，减少外缘持续顶压感。",
            },
            "toe": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 13,
                "walls": None,
                "notes": "脚趾灵活区，保持自然弯折与较软脚感。",
            },
            "edgeFrame": {
                "role": "modifier",
                "infill_pattern": "grid",
                "infill_density_percent": 70,
                "walls": None,
                "notes": "边框稳固区，默认主要通过高密度与边框宽度强化，而非额外局部墙。",
            },
        },
        "tpms_thresholds": {
            "innerHeel": 0.18,
            "outerHeel": 0.17,
            "innerArch": 0.24,
            "outerArch": 0.19,
            "innerForefoot": 0.17,
            "centralForefoot": 0.18,
            "outerForefoot": 0.14,
            "toe": 0.10,
            "edgeFrame": 0.35,
        },
    },
    "healthy_asian_male_daily_soft": {
        "label": "Healthy adult Asian male, softer daily use",
        "zone_settings": {
            "base": {
                "role": "base_model",
                "infill_pattern": "gyroid",
                "infill_density_percent": 18,
                "walls": 3,
                "top_shell_layers": 4,
                "bottom_shell_layers": 4,
                "notes": "基础鞋垫主体，偏柔和脚感的日常模板。",
            },
            "innerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": None,
                "notes": "内侧后跟较柔和稳定区。",
            },
            "outerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 18,
                "walls": None,
                "notes": "外侧后跟偏柔和缓冲区。",
            },
            "innerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 30,
                "walls": None,
                "notes": "内侧足弓轻中度支撑区。",
            },
            "outerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 24,
                "walls": None,
                "notes": "外侧中足柔和过渡区。",
            },
            "innerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 20,
                "walls": None,
                "notes": "内侧前掌中等缓冲区。",
            },
            "centralForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 19,
                "walls": None,
                "notes": "中央前掌柔和过渡区。",
            },
            "outerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 16,
                "walls": None,
                "notes": "外侧前掌较软释放区。",
            },
            "toe": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 12,
                "walls": None,
                "notes": "脚趾灵活区。",
            },
            "edgeFrame": {
                "role": "modifier",
                "infill_pattern": "grid",
                "infill_density_percent": 65,
                "walls": None,
                "notes": "边框稳固区。",
            },
        },
        "tpms_thresholds": {
            "innerHeel": 0.17,
            "outerHeel": 0.15,
            "innerArch": 0.21,
            "outerArch": 0.18,
            "innerForefoot": 0.16,
            "centralForefoot": 0.16,
            "outerForefoot": 0.13,
            "toe": 0.09,
            "edgeFrame": 0.33,
        },
    },
    "healthy_asian_male_sport_stable": {
        "label": "Healthy adult Asian male, sport stable",
        "zone_settings": {
            "base": {
                "role": "base_model",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": 3,
                "top_shell_layers": 4,
                "bottom_shell_layers": 4,
                "notes": "基础鞋垫主体，偏稳态的轻运动模板。",
            },
            "innerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 27,
                "walls": None,
                "notes": "内侧后跟稳定区，适合更积极的快速行走或轻运动。",
            },
            "outerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": None,
                "notes": "外侧后跟缓冲兼稳定区。",
            },
            "innerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 38,
                "walls": None,
                "notes": "内侧足弓较强支撑区。",
            },
            "outerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 30,
                "walls": None,
                "notes": "外侧中足稳定过渡区。",
            },
            "innerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 23,
                "walls": None,
                "notes": "内侧前掌承力区。",
            },
            "centralForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 24,
                "walls": None,
                "notes": "中央前掌重点承力区，适合推进更积极的场景。",
            },
            "outerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 18,
                "walls": None,
                "notes": "外侧前掌释放区。",
            },
            "toe": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 14,
                "walls": None,
                "notes": "脚趾灵活区。",
            },
            "edgeFrame": {
                "role": "modifier",
                "infill_pattern": "grid",
                "infill_density_percent": 70,
                "walls": None,
                "notes": "边框稳固区。",
            },
        },
        "tpms_thresholds": {
            "innerHeel": 0.20,
            "outerHeel": 0.18,
            "innerArch": 0.27,
            "outerArch": 0.22,
            "innerForefoot": 0.18,
            "centralForefoot": 0.20,
            "outerForefoot": 0.15,
            "toe": 0.11,
            "edgeFrame": 0.35,
        },
    },
    "supportive_generic": {
        "label": "Legacy supportive generic profile",
        "zone_settings": {
            "base": {
                "role": "base_model",
                "infill_pattern": "gyroid",
                "infill_density_percent": 20,
                "walls": 3,
                "top_shell_layers": 4,
                "bottom_shell_layers": 4,
                "notes": "基础鞋垫主体，其他区域通过 modifier 覆盖。",
            },
            "innerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 28,
                "walls": 4,
                "notes": "内侧后跟稳态区，优先控制落地稳定与轻度缓冲。",
            },
            "outerHeel": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 22,
                "walls": 3,
                "notes": "外侧后跟缓冲区，优先吸收初始落地冲击。",
            },
            "innerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 40,
                "walls": 4,
                "notes": "内侧足弓主支撑区，参考通用足弓支撑原则提高形状保持。",
            },
            "outerArch": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 30,
                "walls": 3,
                "notes": "外侧中足过渡区，保留稳定同时避免全掌过硬。",
            },
            "innerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 24,
                "walls": 3,
                "notes": "内侧前掌承力区，对应第一跖骨头附近的常见高压区域。",
            },
            "centralForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 20,
                "walls": 3,
                "notes": "中央前掌过渡区，兼顾回弹与减压。",
            },
            "outerForefoot": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 18,
                "walls": 2,
                "notes": "外侧前掌释放区，减小外缘持续顶压感。",
            },
            "toe": {
                "role": "modifier",
                "infill_pattern": "gyroid",
                "infill_density_percent": 14,
                "walls": 2,
                "notes": "脚趾灵活区，保留更软的脚感。",
            },
            "edgeFrame": {
                "role": "modifier",
                "infill_pattern": "grid",
                "infill_density_percent": 70,
                "walls": 4,
                "notes": "边框稳固区，优先保证边缘完整与耐用。",
            },
        },
        "tpms_thresholds": {
            "innerHeel": 0.20,
            "outerHeel": 0.16,
            "innerArch": 0.28,
            "outerArch": 0.22,
            "innerForefoot": 0.19,
            "centralForefoot": 0.16,
            "outerForefoot": 0.14,
            "toe": 0.11,
            "edgeFrame": 0.35,
        },
    },
}


def available_profiles() -> tuple[str, ...]:
    return tuple(PROFILES.keys())


def has_profile(profile_name: str) -> bool:
    return profile_name in PROFILES


def resolve_profile_name(config: dict[str, Any] | None = None) -> str:
    if config is None:
        return DEFAULT_PROFILE_NAME
    profile_name = str(config.get("default_profile", DEFAULT_PROFILE_NAME))
    if not has_profile(profile_name):
        raise ValueError(
            f"Unknown default_profile: {profile_name}. Available profiles: {', '.join(available_profiles())}"
        )
    return profile_name


def get_profile(profile_name: str) -> dict[str, Any]:
    if not has_profile(profile_name):
        raise ValueError(
            f"Unknown profile: {profile_name}. Available profiles: {', '.join(available_profiles())}"
        )
    return deepcopy(PROFILES[profile_name])


def _merge_nested_settings(base: dict[str, dict[str, Any]], overrides: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged = deepcopy(base)
    for zone_name, values in overrides.items():
        if zone_name not in merged:
            raise ValueError(f"Unknown zone_settings_overrides zone: {zone_name}")
        merged[zone_name].update(values)
    return merged


def resolve_zone_settings(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    profile = get_profile(resolve_profile_name(config))
    settings = deepcopy(profile["zone_settings"])
    if config is None:
        return settings
    overrides = config.get("zone_settings_overrides", {})
    if overrides:
        settings = _merge_nested_settings(settings, overrides)
    return settings


def resolve_tpms_thresholds(config: dict[str, Any] | None = None) -> dict[str, float]:
    profile = get_profile(resolve_profile_name(config))
    thresholds = deepcopy(profile["tpms_thresholds"])
    if config is None:
        return thresholds
    tpms = config.get("tpms", {})
    legacy = tpms.get("thresholds", {})
    overrides = tpms.get("threshold_overrides", {})
    for source in (legacy, overrides):
        for zone_name, value in source.items():
            if zone_name not in thresholds:
                raise ValueError(f"Unknown TPMS threshold override zone: {zone_name}")
            thresholds[zone_name] = float(value)
    return thresholds
