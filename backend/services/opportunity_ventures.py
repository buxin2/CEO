"""Venture definitions for the Daily Opportunity Intelligence Center."""

OPPORTUNITY_TYPES = {
    "investment": {"label": "Investment", "emoji": "💰"},
    "grant": {"label": "Grant", "emoji": "💵"},
    "competition": {"label": "Competition", "emoji": "🏆"},
    "accelerator": {"label": "Accelerator", "emoji": "🚀"},
    "pitch": {"label": "Pitching", "emoji": "🎤"},
    "partnership": {"label": "Partnership", "emoji": "🤝"},
    "government": {"label": "Government Program", "emoji": "🏢"},
    "tender": {"label": "Tender", "emoji": "📋"},
    "market": {"label": "Market Opportunity", "emoji": "🌍"},
    "manufacturing": {"label": "Manufacturing", "emoji": "🏭"},
    "education": {"label": "Education Program", "emoji": "🎓"},
    "research": {"label": "Research Program", "emoji": "🔬"},
    "other": {"label": "Other", "emoji": "📌"},
}

VENTURES = [
    {
        "key": "buxin_ev",
        "label": "BuXin EV",
        "emoji": "🚗",
        "company_patterns": ["buxin ev", "ev", "electric vehicle"],
        "search_queries": [
            "electric vehicle grant application Africa 2026",
            "EV startup funding program application",
            "electric mobility tender procurement Africa",
            "electric bus minibus fleet electrification grant",
            "battery technology startup accelerator application",
            "EV charging infrastructure funding program",
            "electric tractor agriculture grant application",
            "African electric vehicle investment opportunity",
        ],
    },
    {
        "key": "bfa",
        "label": "BuXin Future Academy",
        "emoji": "🎓",
        "company_patterns": ["future academy", "bfa", "buxin future"],
        "search_queries": [
            "robotics education competition application schools 2026",
            "STEM education grant program application",
            "AI education funding schools technology",
            "international robotics competition registration",
            "youth technology program grant Africa",
            "education technology startup accelerator",
            "scholarship STEM robotics program application",
            "school partnership technology education grant",
        ],
    },
    {
        "key": "aidobot",
        "label": "AiDoBot",
        "emoji": "🤖",
        "company_patterns": ["aidobot", "ai do bot", "healthcare robot"],
        "search_queries": [
            "healthcare robotics accelerator application 2026",
            "medical AI startup funding grant",
            "hospital pilot program robotics technology",
            "healthcare innovation grant application",
            "medical robotics competition startup",
            "AI healthcare tender procurement",
            "healthcare technology incubator application",
            "assistive medical robot funding program",
        ],
    },
    {
        "key": "vibe_eye",
        "label": "Vibe Eye AI Smart Glasses",
        "emoji": "👓",
        "company_patterns": ["vibe eye", "smart glasses", "vibe"],
        "search_queries": [
            "AI smart glasses startup pitch competition 2026",
            "wearable AI hardware accelerator application",
            "assistive technology grant smart glasses",
            "computer vision startup funding program",
            "accessibility technology innovation grant",
            "wearable technology demo day pitch",
            "AI hardware exhibition startup showcase",
            "smart glasses investment opportunity application",
        ],
    },
]


def venture_meta(key):
    for v in VENTURES:
        if v["key"] == key:
            type_labels = {
                t: f"{OPPORTUNITY_TYPES[t]['emoji']} {OPPORTUNITY_TYPES[t]['label']}"
                for t in OPPORTUNITY_TYPES
            }
            return {**v, "type_labels": type_labels}
    return {"key": key, "label": key, "emoji": "📰", "type_labels": {}}


def all_venture_keys():
    return [v["key"] for v in VENTURES]


def venture_by_key(key):
    for v in VENTURES:
        if v["key"] == key:
            return v
    return None
