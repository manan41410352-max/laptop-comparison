import os
import json
import re
import sqlite3
import time
from math import ceil
from html import unescape
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HP_DB_PATH = os.path.join(DATA_DIR, "hp_laptops_india.db")
HP_SCHEMA_PATH = os.path.join(DATA_DIR, "hp_laptops_schema.sql")
HP_SNAPSHOT_PATH = os.path.join(DATA_DIR, "hp_gaming_catalog_snapshot.json")
HP_LEGACY_SNAPSHOT_PATHS = [os.path.join(DATA_DIR, "hp_omen_catalog_snapshot.json")]
LENOVO_CUSTOMIZATION_CACHE_PATH = os.path.join(DATA_DIR, "lenovo_customization_cache.json")
LENOVO_CUSTOMIZATION_CACHE_TTL_SECONDS = 60 * 60 * 24
LENOVO_CUSTOMIZATION_CACHE_VERSION = 2
HP_REGION = "India"
DEFAULT_REVIEW_STATUS = os.getenv("DEFAULT_REVIEW_STATUS", "approved").strip().lower() or "approved"
if DEFAULT_REVIEW_STATUS not in {"approved", "pending"}:
    DEFAULT_REVIEW_STATUS = "approved"
HP_OMEN_LISTING_URL = "https://www.hp.com/in-en/shop/laptops/personal-laptops/omen-laptops.html"
HP_VICTUS_LISTING_URL = "https://www.hp.com/in-en/shop/laptops/personal-laptops/victus-laptops.html"
HP_GAMING_LISTING_SOURCES = [
    {
        "family": "OMEN",
        "label": "HP India OMEN Series",
        "url": HP_OMEN_LISTING_URL,
    },
    {
        "family": "Victus",
        "label": "HP India Victus Series",
        "url": HP_VICTUS_LISTING_URL,
    },
]

HOME_GUIDE = {
    "snapshot_date": "February 14, 2026",
    "intro": (
        "Simple laptop buying guide. Follow quick steps first, then read each component section."
    ),
    "start_here_60s": [
        "Gaming: choose GPU first, then H/HX-class CPU and at least 16GB RAM.",
        "Coding: target modern 6-8 core CPU with 16GB RAM minimum.",
        "Creator work: dedicated GPU with 32GB RAM is preferred.",
        "Daily travel: efficient U/P-class CPU with 60Wh+ battery target.",
        "Longevity baseline: 6+ cores, 16GB RAM, NVMe SSD.",
    ],
    "safe_baseline_2026": {
        "specs": [
            "Modern 6-core class CPU",
            "16GB RAM",
            "512GB NVMe SSD",
            "300+ nit display",
            "Wi-Fi 6 or newer",
        ],
        "note": "Below this baseline is usually a budget-compromise tier.",
    },
    "real_scenarios": [
        {
            "persona": "B.Tech CSE student (coding + light gaming)",
            "recommendation": "Ryzen 5 H-class + 16GB RAM + 1TB SSD + RTX 4050 class",
        },
        {
            "persona": "MBA student (battery priority)",
            "recommendation": "U/P-class CPU + 16GB RAM + 60Wh+ battery",
        },
        {
            "persona": "Beginner YouTube editor",
            "recommendation": "Ryzen 7 class + RTX 4060 class + 32GB RAM",
        },
    ],
    "red_flags": [
        "8GB RAM in 2026 for long-term usage",
        "Single-channel RAM in a gaming-oriented laptop",
        "250-nit display in higher-priced productivity/gaming tiers",
        "RTX-class GPU listings without disclosed power behavior context",
        "256GB SSD in creator or gaming workflows",
    ],
    "quick_steps": [
        {"title": "Set budget", "text": "Budget decides realistic CPU, GPU, and display options."},
        {"title": "Choose use case", "text": "Pick main goal: gaming, coding, creator work, or battery-first study."},
        {"title": "Lock core specs", "text": "Set CPU, GPU, RAM, SSD, battery, and display baseline before brand extras."},
        {"title": "Compare exact model", "text": "Same chip name can perform differently due to cooling and power limits."},
        {"title": "Final checks", "text": "Verify warranty, ports, upgrade path, and return policy before payment."},
    ],
    "global_ranking": {
        "warning": "Global ranking is guidance only. Real results depend on thermals and power settings.",
        "ladders": [
            {"name": "CPU class", "order": ["HX/H", "HS/P", "U", "Entry"]},
            {"name": "GPU class", "order": ["High dedicated", "Mid dedicated", "Entry dedicated", "Integrated"]},
            {"name": "Memory + storage", "order": ["32GB + NVMe Gen4/5", "16GB + NVMe Gen4", "16GB + NVMe Gen3", "8GB + SATA"]},
        ],
    },
    "use_case_ranking": [
        {
            "use_case": "Gaming",
            "best_fit": "Dedicated GPU first, then H/HX class CPU",
            "second_fit": "Balanced H/HS + RTX 4050/4060 class",
            "why": "Most modern titles are GPU-limited before CPU-limited.",
        },
        {
            "use_case": "Coding",
            "best_fit": "Core i7/Core Ultra 7, Ryzen 7, or Apple M Pro class",
            "second_fit": "Core i5/Ryzen 5 + 16GB RAM",
            "why": "Compiles and multitasking need CPU + memory headroom.",
        },
        {
            "use_case": "Creator",
            "best_fit": "Strong CPU + dedicated GPU + 32GB RAM",
            "second_fit": "Balanced CPU + RTX 4060 class + 16GB/32GB",
            "why": "Editing and rendering need compute, VRAM, and memory.",
        },
        {
            "use_case": "Battery-first",
            "best_fit": "Efficiency-focused CPU class + efficient panel",
            "second_fit": "Mainstream CPU + larger battery + tuned settings",
            "why": "Platform efficiency and display power dominate unplugged life.",
        },
        {
            "use_case": "Students",
            "best_fit": "Mid-tier CPU + 16GB + NVMe SSD + good battery",
            "second_fit": "Entry-mid CPU with upgrade path",
            "why": "Balanced specs stay smooth longer than low-end configs.",
        },
    ],
    "components": [
        {
            "id": "cpu",
            "title": "CPU (Processor)",
            "why_important": "CPU controls speed, multitasking, compile time, and minimum frame stability.",
            "popular_companies": [
                {"name": "Intel", "why": "Very common in Windows laptops with U/P/H/HX classes."},
                {"name": "AMD", "why": "Strong Ryzen value and efficiency across price tiers."},
                {"name": "Qualcomm", "why": "Snapdragon X focuses on battery and AI features."},
                {"name": "Apple", "why": "M-series chips are efficient with strong macOS optimization."},
            ],
            "available_choices": [
                "Entry: i3 / Ryzen 3",
                "Mainstream: i5/Core Ultra 5 / Ryzen 5",
                "High: i7/Core Ultra 7 / Ryzen 7",
                "Flagship: i9/Core Ultra 9 / Ryzen 9",
            ],
            "series_explainer": [
                {"series": "Intel U/P/H/HX", "meaning": "U is efficient, P is thin-and-light performance, H/HX are higher power."},
                {"series": "AMD U/HS/H/HX", "meaning": "U favors battery, HS/H balance performance, HX is top mobile tier."},
                {"series": "Snapdragon X Plus/Elite", "meaning": "ARM laptop chips built for efficient, AI-ready systems."},
                {"series": "Apple M-series", "meaning": "Unified-memory SoCs with high performance-per-watt."},
            ],
            "global_better_order": ["Newest HX/H class", "H/HS/P class", "U class", "Entry class"],
            "use_case_better_order": [
                {"use_case": "Gaming", "recommendation": "H/HX after selecting GPU", "why": "Sustained clocks improve frame stability."},
                {"use_case": "Coding", "recommendation": "Core Ultra 7 / Ryzen 7 / Apple M Pro class", "why": "Better compile and multitask behavior."},
                {"use_case": "Battery", "recommendation": "Snapdragon X or efficient U/P class", "why": "Lower platform power draw."},
            ],
            "levels": {
                "beginner": [
                    "CPU is the laptop brain.",
                    "Newer generation + better tier usually feels faster.",
                    "Do not buy by brand name only.",
                ],
                "advanced": [
                    "Compare generation, then suffix/series, then exact model.",
                    "Cooling and power limits change real speed.",
                    "Use sustained benchmarks for heavy workloads.",
                    "Check architecture compatibility for ARM vs x86 before buying for specialized apps.",
                ],
                "enthusiast": [
                    "IPC, cache, and sustained clocks decide real ranking.",
                    "Same chip can differ strongly by laptop chassis.",
                    "Performance-per-watt matters for portability.",
                    "Intel hybrid architecture uses P-cores for heavy work and E-cores for background efficiency.",
                    "AMD Zen generation changes can improve IPC and efficiency per generation.",
                    "Apple unified memory architecture can reduce data-copy overhead in many workflows.",
                    "ARM vs x86 software compatibility should be checked before buying for specialized tools.",
                ],
            },
            "sources": [
                {
                    "label": "Intel naming",
                    "url": "https://www.intel.com/content/www/us/en/processors/processor-numbers.html",
                    "note": "Intel naming and suffix conventions.",
                },
                {
                    "label": "AMD Ryzen AI",
                    "url": "https://www.amd.com/en/products/processors/laptop/ryzen-ai.html",
                    "note": "AMD mobile AI processor context.",
                },
                {
                    "label": "Snapdragon X",
                    "url": "https://www.qualcomm.com/products/mobile/snapdragon/pcs-and-tablets",
                    "note": "Qualcomm PC platform overview.",
                },
                {
                    "label": "Apple specs",
                    "url": "https://www.apple.com/macbook-pro/specs/",
                    "note": "Apple laptop specs reference.",
                },
            ],
        },
        {
            "id": "gpu",
            "title": "GPU (Graphics)",
            "why_important": "GPU affects gaming FPS, visual quality, and creator acceleration.",
            "popular_companies": [
                {"name": "NVIDIA", "why": "Most common dedicated laptop GPUs with broad game support."},
                {"name": "AMD Radeon", "why": "Strong integrated and dedicated options with FSR."},
                {"name": "Intel Arc", "why": "Growing dedicated option in select laptops."},
            ],
            "available_choices": [
                "Integrated GPU",
                "Entry dedicated GPU",
                "Mid dedicated GPU",
                "High dedicated GPU with larger VRAM",
            ],
            "series_explainer": [
                {"series": "Integrated GPU", "meaning": "Good for office, coding, and light media/gaming."},
                {"series": "RTX/RX dedicated tiers", "meaning": "Higher tiers usually mean higher FPS and creator throughput."},
                {"series": "VRAM class", "meaning": "More VRAM helps higher textures and heavier creative work."},
            ],
            "global_better_order": ["High dedicated", "Mid dedicated", "Entry dedicated", "Integrated"],
            "use_case_better_order": [
                {"use_case": "Gaming", "recommendation": "Dedicated GPU first", "why": "Most game performance scales with GPU class."},
                {"use_case": "Creator", "recommendation": "Dedicated GPU + enough VRAM", "why": "Rendering and effects pipelines benefit."},
                {"use_case": "Student/coding", "recommendation": "Integrated can be enough", "why": "Better battery and cost for non-gaming workloads."},
            ],
            "levels": {
                "beginner": [
                    "For gaming, GPU matters most.",
                    "Integrated is fine for basic tasks.",
                    "Check exact GPU model before buying.",
                ],
                "advanced": [
                    "Check VRAM and laptop power limit.",
                    "DLSS/FSR can boost FPS in supported titles.",
                    "Cooling quality affects long-session results.",
                    "RTX 4060 at lower wattage can perform much lower than higher-wattage implementations.",
                ],
                "enthusiast": [
                    "Same GPU name can perform very differently by TGP.",
                    "Thermal throttling can decide real ranking.",
                    "Driver and encoder quality matter for creator workflows.",
                ],
            },
            "sources": [
                {
                    "label": "NVIDIA DLSS",
                    "url": "https://www.nvidia.com/en-us/geforce/technologies/dlss/",
                    "note": "Official DLSS overview.",
                },
                {
                    "label": "AMD FSR",
                    "url": "https://www.amd.com/en/products/graphics/technologies/fidelityfx/super-resolution.html",
                    "note": "Official FSR overview.",
                },
            ],
        },
        {
            "id": "ram",
            "title": "RAM (Memory)",
            "why_important": "RAM affects multitasking smoothness, app switching, and workflow stability.",
            "popular_companies": [
                {"name": "Micron/Crucial", "why": "Major memory ecosystem with practical guides."},
                {"name": "Samsung", "why": "Major DRAM supplier for many laptop vendors."},
                {"name": "SK hynix", "why": "Major supplier across mainstream and premium systems."},
            ],
            "available_choices": ["8GB", "16GB", "32GB+", "DDR4 / DDR5 / LPDDR5X"],
            "series_explainer": [
                {"series": "DDR4", "meaning": "Older standard still seen in budget models."},
                {"series": "DDR5", "meaning": "Newer standard with higher bandwidth."},
                {"series": "LPDDR5X", "meaning": "Efficient but usually soldered."},
                {"series": "Dual-channel", "meaning": "Usually better performance than single-channel."},
            ],
            "global_better_order": ["32GB+ dual-channel", "16GB dual-channel", "16GB single-channel", "8GB"],
            "use_case_better_order": [
                {"use_case": "Students/coding", "recommendation": "16GB dual-channel", "why": "Good baseline for modern multitasking."},
                {"use_case": "Gaming", "recommendation": "16GB min, 32GB preferred", "why": "New games plus background apps consume RAM quickly."},
                {"use_case": "Creator/AI", "recommendation": "32GB or higher", "why": "Large projects and tools need headroom."},
            ],
            "levels": {
                "beginner": [
                    "16GB is the practical baseline now.",
                    "8GB can feel limited quickly.",
                    "Check if RAM can be upgraded later.",
                ],
                "advanced": [
                    "Capacity matters first, then speed.",
                    "Dual-channel helps CPU and iGPU performance.",
                    "Soldered RAM means no future upgrade.",
                ],
                "enthusiast": [
                    "Memory bandwidth impacts integrated graphics heavily.",
                    "Confirm exact RAM config for your SKU.",
                    "Low-power memory can improve battery behavior.",
                ],
            },
            "sources": [
                {
                    "label": "Crucial DDR5",
                    "url": "https://www.crucial.com/articles/about-memory/ddr5-memory",
                    "note": "DDR5 basics.",
                },
                {
                    "label": "RAM sizing",
                    "url": "https://www.crucial.com/articles/about-memory/how-much-ram-do-i-need",
                    "note": "Capacity guidance.",
                },
            ],
        },
        {
            "id": "storage",
            "title": "Storage (SSD)",
            "why_important": "Storage affects boot time, app launch, game loading, and project file speed.",
            "popular_companies": [
                {"name": "Samsung", "why": "Common high-performance SSD vendor."},
                {"name": "Western Digital", "why": "Strong SSD presence across market tiers."},
                {"name": "Crucial/Micron", "why": "Mainstream SSD options and education resources."},
            ],
            "available_choices": ["SATA SSD", "NVMe Gen3", "NVMe Gen4", "NVMe Gen5"],
            "series_explainer": [
                {"series": "SATA SSD", "meaning": "Good upgrade from HDD but slower than NVMe."},
                {"series": "NVMe Gen3", "meaning": "Fast enough for many users."},
                {"series": "NVMe Gen4", "meaning": "Strong current balance for most buyers."},
                {"series": "NVMe Gen5", "meaning": "Top speed in premium systems, usually higher cost/heat."},
            ],
            "global_better_order": ["NVMe Gen5", "NVMe Gen4", "NVMe Gen3", "SATA SSD"],
            "use_case_better_order": [
                {"use_case": "Gaming", "recommendation": "NVMe Gen4", "why": "Better load-time consistency on large titles."},
                {"use_case": "Coding/student", "recommendation": "NVMe Gen3/Gen4", "why": "Both are smooth for most projects."},
                {"use_case": "Creator", "recommendation": "NVMe Gen4/Gen5 + larger capacity", "why": "Large files benefit from throughput headroom."},
            ],
            "levels": {
                "beginner": [
                    "Always choose SSD.",
                    "Try to get at least 512GB, preferably 1TB.",
                    "NVMe is usually faster than SATA.",
                ],
                "advanced": [
                    "Gen4 is a strong practical target.",
                    "Check if there is an extra SSD slot.",
                    "Thermal design can affect sustained SSD speed.",
                ],
                "enthusiast": [
                    "Controller and NAND quality matter, not only advertised peak speed.",
                    "Sustained write behavior is important for heavy workloads.",
                    "Separate drives can improve workflow comfort.",
                ],
            },
            "sources": [
                {
                    "label": "M.2 vs SATA",
                    "url": "https://www.crucial.com/articles/about-ssd/m2-ssd-vs-sata",
                    "note": "M.2/NVMe vs SATA context.",
                },
                {
                    "label": "What is NVMe",
                    "url": "https://www.crucial.com/articles/about-ssd/what-is-nvme",
                    "note": "NVMe fundamentals.",
                },
            ],
        },
        {
            "id": "battery",
            "title": "Battery",
            "why_important": "Battery quality decides how long a laptop remains useful away from the charger.",
            "popular_companies": [
                {"name": "LG Energy Solution", "why": "Major battery-cell supplier."},
                {"name": "Samsung SDI", "why": "Major battery-cell supplier."},
                {"name": "Amperex/ATL ecosystem", "why": "Widely used in consumer electronics battery supply chains."},
            ],
            "available_choices": ["40-55Wh", "60-75Wh", "80-99Wh", "Efficiency-focused platforms"],
            "series_explainer": [
                {"series": "Wh", "meaning": "Higher Wh usually means higher potential runtime."},
                {"series": "Platform efficiency", "meaning": "CPU/GPU/display efficiency can beat bigger battery sizes."},
                {"series": "Power mode", "meaning": "Balanced and saver modes can increase practical runtime."},
            ],
            "global_better_order": [
                "Efficient platform + larger battery",
                "Efficient platform + medium battery",
                "Power-hungry platform + larger battery",
                "Power-hungry platform + small battery",
            ],
            "use_case_better_order": [
                {"use_case": "Student/travel", "recommendation": "Efficiency-first CPU + practical battery size", "why": "Long unplugged productivity."},
                {"use_case": "Gaming", "recommendation": "Use charger for full performance", "why": "Gaming on battery usually reduces speed and runtime."},
                {"use_case": "Office/coding", "recommendation": "Balanced system + panel tuning", "why": "Brightness/refresh settings can add runtime."},
            ],
            "levels": {
                "beginner": [
                    "Battery life is size plus efficiency, not size only.",
                    "Check real mixed-use tests, not only one marketing number.",
                    "Students should target full class-day usage.",
                ],
                "advanced": [
                    "Display brightness and refresh can change battery life a lot.",
                    "Dedicated GPU activity often lowers unplugged runtime.",
                    "Power plans and background apps matter.",
                ],
                "enthusiast": [
                    "Idle platform power is a major hidden factor.",
                    "Workload-specific battery testing is best for decisions.",
                    "Battery health features can improve long-term lifespan.",
                ],
            },
            "sources": [
                {
                    "label": "FAA battery guide",
                    "url": "https://www.faa.gov/hazmat/packsafe/lithium-batteries",
                    "note": "Travel battery and lithium safety guidance.",
                },
                {
                    "label": "Snapdragon PCs",
                    "url": "https://www.qualcomm.com/products/mobile/snapdragon/pcs-and-tablets",
                    "note": "Efficiency-focused PC platform reference.",
                },
            ],
        },
        {
            "id": "display",
            "title": "Display",
            "why_important": "Display affects readability, eye comfort, color accuracy, smoothness, and battery draw.",
            "popular_companies": [
                {"name": "LG Display", "why": "Major laptop panel supplier."},
                {"name": "Samsung Display", "why": "Major OLED and advanced panel supplier."},
                {"name": "BOE/AUO", "why": "Large suppliers across many laptop classes."},
            ],
            "available_choices": ["IPS", "OLED", "Mini-LED", "60Hz to 165Hz+", "FHD/QHD/4K"],
            "series_explainer": [
                {"series": "IPS", "meaning": "Reliable all-round choice with good viewing angles."},
                {"series": "OLED", "meaning": "Excellent contrast with deep blacks and vivid look."},
                {"series": "Mini-LED", "meaning": "Better local contrast in premium panels."},
                {"series": "DisplayHDR tiers", "meaning": "VESA tiers provide HDR expectation baseline."},
            ],
            "global_better_order": [
                "Panel matched to your use case with enough brightness",
                "High refresh + balanced resolution",
                "Low-brightness basic panel",
            ],
            "use_case_better_order": [
                {"use_case": "Gaming", "recommendation": "120Hz+ with fast response", "why": "Improves smoothness and control feel."},
                {"use_case": "Creator", "recommendation": "High color accuracy and brightness", "why": "More reliable visual work."},
                {"use_case": "Student/office", "recommendation": "Comfortable IPS with decent brightness", "why": "Good readability and battery balance."},
            ],
            "levels": {
                "beginner": [
                    "Display is your daily experience, so do not ignore it.",
                    "IPS is a safe baseline for many buyers.",
                    "Gamers should prefer higher refresh displays.",
                ],
                "advanced": [
                    "Check nits, color coverage, refresh, and response behavior.",
                    "Higher resolution can reduce battery and increase GPU demand.",
                    "Pick display specs based on your main use case.",
                    "Check PWM flicker behavior and matte vs glossy surface preference for comfort.",
                ],
                "enthusiast": [
                    "Calibration quality matters for creator accuracy.",
                    "HDR quality varies by panel implementation and tier.",
                    "Display power behavior influences battery profile strongly.",
                ],
            },
            "sources": [
                {
                    "label": "VESA DisplayHDR",
                    "url": "https://displayhdr.org/",
                    "note": "Official HDR certification tiers.",
                },
                {
                    "label": "Apple display specs",
                    "url": "https://www.apple.com/macbook-pro/specs/",
                    "note": "Reference premium display specification sheet.",
                },
            ],
        },
    ],
    "performance_reality_check": {
        "points": [
            "Same CPU name does not guarantee same performance across laptops.",
            "Same GPU model does not guarantee same FPS across laptops.",
            "Cooling design changes sustained performance in gaming and creator workloads.",
            "GPU wattage (TGP/TBP class) matters for real gaming output.",
            "Single-channel RAM can reduce CPU and iGPU performance.",
            "Thin chassis can throttle under long heavy load.",
        ],
        "tip": "Check sustained benchmarks and long-run testing, not only peak numbers.",
        "sources": [
            {
                "label": "Intel naming",
                "url": "https://www.intel.com/content/www/us/en/processors/processor-numbers.html",
                "note": "Model names and suffixes are not full performance guarantees.",
            },
            {
                "label": "NVIDIA laptops",
                "url": "https://www.nvidia.com/en-us/geforce/laptops/",
                "note": "Laptop GPU performance context by platform design.",
            },
        ],
    },
    "thermal_power_behavior": {
        "why_it_matters": [
            "Sustained FPS stability in long gaming sessions.",
            "Compile duration consistency in long coding sessions.",
            "Rendering completion time and thermal stability.",
            "Fan noise behavior and keyboard surface temperature.",
        ],
        "key_terms": [
            {
                "term": "PL1 / PL2 (Intel tuning context)",
                "meaning": "Long and short duration CPU power behavior can change sustained vs burst performance.",
            },
            {
                "term": "TGP class for laptop GPUs",
                "meaning": "Higher allowed GPU power usually improves gaming/creator throughput when cooling can sustain it.",
            },
            {
                "term": "Vapor chamber vs heatpipe",
                "meaning": "Cooling architecture affects how long performance can stay stable before throttling.",
            },
        ],
        "thin_chassis_warning": (
            "Ultra-thin laptops can be excellent for portability but may trade sustained performance for acoustics and temperature limits."
        ),
        "sources": [
            {
                "label": "Intel power terms",
                "url": "https://www.intel.com/content/www/us/en/processors/processor-numbers.html",
                "note": "Intel processor classes and power context.",
            },
            {
                "label": "NVIDIA laptops",
                "url": "https://www.nvidia.com/en-us/geforce/laptops/",
                "note": "Laptop GPU platform design and performance framing.",
            },
        ],
    },
    "bottleneck_awareness": {
        "examples": [
            "RTX 4060 + 8GB RAM can bottleneck in modern multitasking/gaming scenarios.",
            "Ryzen 9 + SATA SSD can feel delayed in heavy creator workflows.",
            "165Hz display + weak GPU can underutilize panel refresh capability.",
        ],
        "principle": "Balanced systems usually outperform unbalanced systems with one very high-end part.",
        "mismatch_matrix": [
            {
                "configuration": "High GPU + 8GB RAM",
                "impact": "Frame-time spikes, app reloads, inconsistent multitasking.",
                "fix": "Upgrade to 16GB/32GB dual-channel.",
            },
            {
                "configuration": "Flagship CPU + weak cooling",
                "impact": "Fast bursts but lower sustained speed after heat buildup.",
                "fix": "Prioritize thicker chassis or better thermal design.",
            },
            {
                "configuration": "High refresh display + low GPU tier",
                "impact": "Panel capability is underused in many modern games.",
                "fix": "Match GPU class to display target and game settings.",
            },
            {
                "configuration": "Fast CPU/GPU + slow small SSD",
                "impact": "Loading delays and storage pressure in creator/game workflows.",
                "fix": "Prefer 1TB NVMe Gen4 class if budget allows.",
            },
        ],
        "diagnostic_signals": [
            {"signal": "Game FPS average looks fine, but stutter feels high", "likely_cause": "1% lows hit by RAM or thermal limits."},
            {"signal": "System slows after 15-20 minutes of heavy use", "likely_cause": "Cooling and power limits are restricting sustained clocks."},
            {"signal": "High-end CPU feels laggy in project loads", "likely_cause": "Storage or memory bottleneck rather than CPU tier."},
        ],
        "interest_balance_traps": [
            {
                "interest": "Gaming",
                "trap": "Spending on CPU tier but cutting GPU power class",
                "better_balance": "Match GPU class/cooling first, then CPU",
            },
            {
                "interest": "Coding",
                "trap": "High refresh display priority with low RAM",
                "better_balance": "16GB/32GB memory before display extras",
            },
            {
                "interest": "Creator",
                "trap": "Strong CPU with low VRAM and 256GB storage",
                "better_balance": "GPU/VRAM + RAM + SSD capacity as a set",
            },
            {
                "interest": "Students / Battery-first",
                "trap": "Choosing high-power hardware for mostly notes/web use",
                "better_balance": "Efficient platform + battery + practical specs",
            },
        ],
    },
    "price_intelligence": {
        "strategies": [
            "Watch festival, holiday, and back-to-school periods for better bundles and discounts.",
            "Track launch cycles and avoid buying very close to a known refresh if price is not attractive.",
            "Compare total value: specs + warranty + service quality, not sticker price only.",
            "Use 2-4 week price tracking before buying to avoid emotional purchase timing.",
        ],
        "note": "Regional pricing and sale quality vary by country and retailer.",
        "buying_windows": [
            {
                "window": "Major festival / seasonal sale",
                "best_for": "Mainstream and upper-mainstream value deals",
                "watch_out": "Flash discounts on weak-config SKUs with good branding",
            },
            {
                "window": "Back-to-school period",
                "best_for": "Student bundles and warranty add-ons",
                "watch_out": "Base RAM/storage cuts hidden behind education pricing",
            },
            {
                "window": "Post-refresh clearance",
                "best_for": "Previous generation with good price drop",
                "watch_out": "Buying before checking exact refresh improvements",
            },
        ],
        "deal_score_framework": [
            "Price vs 30-day average (30 points)",
            "Spec balance for your use case (25 points)",
            "Thermals + sustained review quality (20 points)",
            "Warranty and service quality (15 points)",
            "Upgrade path and ports (10 points)",
        ],
        "checkout_rules": [
            "Never buy only on discount percent; verify exact SKU specs first.",
            "Compare at least 2 equivalent alternatives before payment.",
            "Capture screenshot of final config and seller warranty terms before checkout.",
        ],
    },
    "interest_value_map": [
        {
            "interest": "Gaming",
            "where_to_spend": "GPU class + cooling quality + 16GB/32GB RAM",
            "where_to_save": "Premium ultra-thin chassis and creator-grade color specs if not needed",
            "value_signal": "Consistent 1% low FPS and stable thermals > peak burst numbers",
        },
        {
            "interest": "Coding",
            "where_to_spend": "Modern CPU class + 16GB/32GB RAM + keyboard quality",
            "where_to_save": "Very high refresh panel and top-tier GPU if no gaming/render need",
            "value_signal": "Smooth compile/multitask behavior over long sessions",
        },
        {
            "interest": "Creator",
            "where_to_spend": "CPU/GPU balance + RAM headroom + color-accurate display",
            "where_to_save": "Overpaying for flagship CPU when GPU/VRAM is limited",
            "value_signal": "Timeline/export stability with no memory bottleneck",
        },
        {
            "interest": "Students / Battery-first",
            "where_to_spend": "Efficient platform + battery + practical durability",
            "where_to_save": "High-watt gaming hardware if mostly class/office workflows",
            "value_signal": "Reliable full-day usage and low carry burden",
        },
    ],
    "performance_per_inr": {
        "points": [
            "Higher tier hardware does not always mean better value.",
            "Mid-tier systems often deliver the strongest price-to-performance ratio.",
            "Pay flagship premium only when your workload clearly needs it.",
        ],
        "bands": [
            {
                "band": "Entry budget",
                "best_value_focus": "Modern CPU generation + 16GB upgradability + SSD quality",
                "avoid": "8GB locked RAM and very low-brightness panels",
            },
            {
                "band": "Mainstream",
                "best_value_focus": "Balanced CPU/GPU with 16GB baseline and thermal stability",
                "avoid": "Overpaying for branding with weak GPU power behavior",
            },
            {
                "band": "Performance tier",
                "best_value_focus": "Sustained GPU/CPU class + display quality + warranty",
                "avoid": "Paying premium for peak benchmark marketing only",
            },
        ],
    },
    "longevity_score": {
        "tiers": [
            {
                "profile": "Entry CPU + 8GB RAM + basic SSD",
                "three_year_estimate": "Low",
                "reason": "Can become limiting quickly for modern multitasking.",
            },
            {
                "profile": "Modern 6-core class + 16GB RAM + NVMe SSD",
                "three_year_estimate": "Stable",
                "reason": "Strong baseline for study, coding, and mixed use.",
            },
            {
                "profile": "8-core+ class + 32GB RAM + stronger GPU",
                "three_year_estimate": "High",
                "reason": "Best long-term headroom for demanding workflows.",
            },
        ],
        "note": "Longevity depends on workload growth, software updates, and thermal behavior.",
        "workload_survival_matrix": [
            {
                "workload": "Study + office + browsing",
                "entry_tier": "Can work initially but ages quickly",
                "balanced_tier": "Reliable for full 3-year cycle",
                "performance_tier": "Comfortable headroom",
            },
            {
                "workload": "Coding + IDE + multitasking",
                "entry_tier": "Frequent slowdowns over time",
                "balanced_tier": "Stable with 16GB baseline",
                "performance_tier": "Best for heavy builds and VMs",
            },
            {
                "workload": "Gaming / creator mix",
                "entry_tier": "Compromise-heavy by year 2-3",
                "balanced_tier": "Playable/productive with settings tuning",
                "performance_tier": "Strong long-term comfort",
            },
        ],
        "risk_hotspots": [
            {
                "risk": "Thermal saturation over long sessions",
                "impact": "Performance falls earlier than expected",
                "prevention": "Prefer known cooling quality and sustained reviews",
            },
            {
                "risk": "No memory/storage headroom",
                "impact": "Forced replacement instead of cheap upgrade",
                "prevention": "Choose upgradeable RAM/SSD path where possible",
            },
            {
                "risk": "Weak battery aging behavior",
                "impact": "Portable use degrades quickly",
                "prevention": "Check battery health features and service path",
            },
        ],
    },
    "interest_longevity_playbook": [
        {
            "interest": "Gaming",
            "upgrade_first": "RAM to 32GB and SSD capacity",
            "watch_trigger": "1% lows and stutter increase in newer titles",
            "three_year_target": "Dedicated GPU + strong cooling + upgrade path",
        },
        {
            "interest": "Coding",
            "upgrade_first": "RAM first, then SSD for project growth",
            "watch_trigger": "Compile times rise and multitask lag appears",
            "three_year_target": "Modern 6-8 core class + 16GB/32GB RAM",
        },
        {
            "interest": "Creator",
            "upgrade_first": "RAM and high-capacity NVMe workspace",
            "watch_trigger": "Timeline stutter and export slowdowns under effects",
            "three_year_target": "Balanced CPU/GPU + 32GB memory headroom",
        },
        {
            "interest": "Students / Office",
            "upgrade_first": "SSD capacity and battery service path",
            "watch_trigger": "Battery runtime drops below class-day requirements",
            "three_year_target": "Efficient CPU class + good battery stability",
        },
    ],
    "upgrade_path": {
        "checks": [
            "RAM: soldered or upgradeable slot configuration?",
            "SSD: number of M.2 slots and max supported capacity?",
            "Wi-Fi card: replaceable or soldered?",
            "Battery: service-friendly replacement path available?",
        ],
        "priority_order": [
            "RAM capacity first (if workload is memory-limited)",
            "SSD capacity second (for workspace and performance consistency)",
            "Battery service third (for mobility-heavy users)",
        ],
    },
    "build_portability": {
        "weight_bands": [
            {"band": "Below 1.3 kg", "tag": "Ultra-portable", "fit": "Travel-heavy users and students who carry daily."},
            {"band": "1.5 to 2.0 kg", "tag": "Balanced", "fit": "Good mix of mobility and performance."},
            {"band": "2.2 kg and above", "tag": "Performance-heavy", "fit": "Gaming/workstation style systems with stronger cooling."},
        ],
        "material_notes": [
            "Aluminum builds usually feel more rigid and premium.",
            "Plastic builds can still be good but vary more by chassis quality.",
            "MIL-STD claims are useful context, but verify real hinge and build reviews.",
        ],
    },
    "ports_connectivity": {
        "checks": [
            "USB-C charging support and charge wattage behavior",
            "Thunderbolt or full-feature USB4 support",
            "HDMI version for external display targets",
            "Ethernet availability for stable low-latency networking",
            "SD card reader need for creator workflows",
            "Wi-Fi 6E / Wi-Fi 7 support based on your network setup",
        ],
    },
    "warranty_support": {
        "checks": [
            "On-site vs carry-in warranty model",
            "Accidental damage protection option",
            "Spare parts availability in your region",
            "Service center reach and response quality",
        ],
    },
    "ai_future_tech": {
        "points": [
            "NPU capability matters for on-device AI tasks and future software acceleration.",
            "OS-level AI features may have hardware requirements that older laptops miss.",
            "Modern AI-ready laptops can offer better long-term compatibility for emerging tools.",
        ],
        "sources": [
            {
                "label": "Snapdragon PCs",
                "url": "https://www.qualcomm.com/products/mobile/snapdragon/pcs-and-tablets",
                "note": "NPU-focused modern laptop platform context.",
            },
            {
                "label": "Microsoft Copilot",
                "url": "https://www.microsoft.com/en-us/windows/copilot-ai-features",
                "note": "Windows AI feature direction and ecosystem context.",
            },
        ],
    },
    "who_should_not_buy": [
        {
            "product": "Performance gaming laptop",
            "not_for": [
                "Daily lightweight travel users",
                "Silent-library usage expectations",
                "Battery-first all-day unplugged workflows",
            ],
        },
        {
            "product": "Ultra-thin laptop",
            "not_for": [
                "Heavy sustained gaming workloads",
                "Long 3D/render sessions without thermal compromise",
                "Users who need broad upgradeability",
            ],
        },
    ],
    "decision_engine": {
        "currency": "INR",
        "bands": [
            {
                "budget": "Below INR 50,000",
                "focus": "CPU generation + SSD + upgrade path",
            },
            {
                "budget": "INR 50,000 to 80,000",
                "focus": "Balanced CPU + GPU + 16GB RAM baseline",
            },
            {
                "budget": "INR 80,000 to 120,000",
                "focus": "Gaming and creator sweet spot with stronger dedicated GPU",
            },
            {
                "budget": "INR 120,000+",
                "focus": "Long-term investment tier with stronger thermals and headroom",
            },
        ],
        "note": "Adjust by local promotions and exact model thermal design.",
    },
    "benchmark_methodology": {
        "principles": [
            "Gaming tests should clearly state resolution and preset (for example, 1080p High unless specified).",
            "Sustained performance should be measured after thermal stabilization, not only first-minute burst.",
            "Battery testing should use a mixed productivity loop, not idle-only readings.",
            "RAM configuration should be disclosed (single-channel vs dual-channel).",
            "Power mode used in test should be explicitly stated.",
        ],
        "why": "Methodology transparency builds trust and makes comparisons meaningful.",
    },
    "stability_philosophy": "We prioritize sustained performance stability over short burst benchmark numbers.",
    "data_confidence_labels": [
        {"label": "Lab Tested", "meaning": "Measured using a repeatable controlled setup."},
        {"label": "Community Verified", "meaning": "Cross-checked from multiple independent user reports."},
        {"label": "Manufacturer Data", "meaning": "Official vendor data not yet fully independent-validated."},
        {"label": "Estimated Range", "meaning": "Estimated performance band when exact SKU data is limited."},
    ],
    "sku_awareness": {
        "points": [
            "Same laptop name can have many SKUs with different real performance.",
            "GPU wattage, display panel, and RAM layout can differ within one model name.",
            "SSD type and speed class can change between variants.",
            "Always verify exact model code before buying.",
        ],
    },
    "gpu_power_class_awareness": {
        "headline": "RTX 4060 (80W class) is not equal to RTX 4060 (140W class).",
        "effects": [
            "Higher wattage implementations generally deliver higher FPS.",
            "Higher wattage usually needs stronger cooling and can increase noise/weight.",
            "Lower wattage variants may be cooler and lighter but can perform lower in sustained load.",
        ],
    },
    "noise_profile_awareness": {
        "points": [
            "Thin laptops may prioritize acoustics over sustained performance.",
            "Performance laptops can become loud under full load in long sessions.",
            "Fan curve tuning and power mode selection affect comfort during coding/gaming.",
        ],
    },
    "display_metrics": {
        "points": [
            "Brightness in nits (300+ is a practical baseline for many users).",
            "Color coverage (sRGB and DCI-P3 relevance by workload).",
            "Response time matters for competitive gaming smoothness.",
            "PWM flicker behavior can affect eye comfort for sensitive users.",
            "Matte vs glossy finish preference should match your environment.",
        ],
    },
    "repairability_sustainability": {
        "points": [
            "Battery design: screwed modules are usually easier to service than heavily glued builds.",
            "Standard M.2 SSD support is more upgrade-friendly than proprietary storage paths.",
            "OEM BIOS and firmware support history matters for long-term stability.",
            "Driver availability over time affects long-term usability.",
        ],
    },
    "software_environment": {
        "points": [
            "OEM background utilities can affect performance and battery behavior.",
            "A clean OS setup can improve stability in some systems.",
            "BIOS updates can change power behavior and sustained performance.",
        ],
    },
    "architecture_compatibility": {
        "points": [
            "ARM vs x86 differences can affect app compatibility and workflow tools.",
            "Virtualization support and workflow requirements should be checked before purchase.",
            "Linux support quality can vary by platform and vendor implementation.",
            "Check software ecosystem maturity for Snapdragon X and Apple silicon workflows.",
        ],
    },
    "networking_performance": {
        "points": [
            "Antenna quality and placement affect real signal stability.",
            "2x2 Wi-Fi can perform better than 1x1 in many real network conditions.",
            "Ethernet remains preferred for stable low-latency competitive gaming.",
        ],
    },
    "common_buying_mistakes": {
        "mistakes": [
            "Buying high-refresh display with a GPU too weak to drive it well.",
            "Buying 8GB RAM in 2026 for long-term use.",
            "Ignoring thermal design and sustained performance behavior.",
            "Buying 256GB SSD for gaming/creator workloads.",
            "Buying near a refresh window without price advantage.",
        ],
    },
    "performance_portability_matrix": [
        {
            "category": "Weight",
            "thin_light": "Best (easy carry)",
            "balanced": "Moderate",
            "gaming": "Heavy",
        },
        {
            "category": "Sustained Performance",
            "thin_light": "Limited in long loads",
            "balanced": "Consistent",
            "gaming": "Highest",
        },
        {
            "category": "Battery Runtime",
            "thin_light": "Highest",
            "balanced": "Good",
            "gaming": "Lowest under heavy use",
        },
        {
            "category": "Thermal Headroom",
            "thin_light": "Lower",
            "balanced": "Good",
            "gaming": "Best",
        },
        {
            "category": "Fan Noise Under Load",
            "thin_light": "Low to Medium",
            "balanced": "Medium",
            "gaming": "High",
        },
        {
            "category": "Charger + Carry Burden",
            "thin_light": "Lowest",
            "balanced": "Medium",
            "gaming": "Highest",
        },
        {
            "category": "Desk Dependency",
            "thin_light": "Low",
            "balanced": "Medium",
            "gaming": "High",
        },
        {
            "category": "Upgrade Flexibility",
            "thin_light": "Often limited",
            "balanced": "Usually fair",
            "gaming": "Usually best",
        },
    ],
    "use_case_fit_matrix": [
        {
            "use_case": "Lecture notes + browsing + docs",
            "thin_light": "Excellent",
            "balanced": "Excellent",
            "gaming": "Good but overkill",
        },
        {
            "use_case": "Coding + VMs + multitasking",
            "thin_light": "Good (if 16GB+)",
            "balanced": "Excellent",
            "gaming": "Excellent",
        },
        {
            "use_case": "AAA gaming",
            "thin_light": "Not ideal",
            "balanced": "Good",
            "gaming": "Excellent",
        },
        {
            "use_case": "Video editing / creator workflow",
            "thin_light": "Good for light edits",
            "balanced": "Excellent",
            "gaming": "Excellent",
        },
        {
            "use_case": "Travel-first work",
            "thin_light": "Excellent",
            "balanced": "Good",
            "gaming": "Difficult",
        },
    ],
    "mobility_reality_matrix": [
        {
            "factor": "Carry comfort during commute",
            "thin_light": "Easy",
            "balanced": "Manageable",
            "gaming": "Tiring over time",
        },
        {
            "factor": "Class/meeting battery confidence",
            "thin_light": "High",
            "balanced": "Medium to High",
            "gaming": "Low to Medium",
        },
        {
            "factor": "Noise in quiet room",
            "thin_light": "Low",
            "balanced": "Low to Medium",
            "gaming": "Medium to High",
        },
        {
            "factor": "Works well on lap",
            "thin_light": "Best",
            "balanced": "Okay",
            "gaming": "Not ideal under load",
        },
        {
            "factor": "Needs nearby power outlet",
            "thin_light": "Rarely",
            "balanced": "Sometimes",
            "gaming": "Frequently",
        },
    ],
    "matrix_takeaway": (
        "Choose the class that matches where you work most often. If your day is mostly desk power and heavy workloads, "
        "gaming-class is valid. If you move often, balanced or thin-and-light usually delivers better real-life satisfaction."
    ),
    "regional_buying_awareness": {
        "region": "India",
        "points": [
            "GST input-credit scenarios can change effective cost for business buyers.",
            "Student and education discounts can improve premium-tier value.",
            "Festival pricing can be volatile, so track prices before purchase.",
            "Imported grey-market SKUs can differ in warranty and support quality.",
        ],
    },
    "confidence_check": {
        "checks": [
            "CPU tier matches my main use case.",
            "GPU wattage class is confirmed for the exact SKU.",
            "16GB or higher RAM is confirmed.",
            "512GB or higher SSD is confirmed for my workload.",
            "Thermal and sustained performance reviews are verified.",
        ],
        "result_hint": "If most checks are true, you are in the safe purchase zone.",
    },
    "upgrade_instead_of_replace": {
        "points": [
            "Upgrade RAM first if the system is RAM-limited and upgradeable.",
            "Move to faster/larger NVMe SSD before replacing a still-capable laptop.",
            "Try clean OS install and firmware updates before buying new hardware.",
        ],
        "timeline": [
            {"phase": "0-12 months", "focus": "Setup optimization, warranty checks, and thermal mode tuning."},
            {"phase": "12-24 months", "focus": "RAM/SSD upgrade decision based on real workload pressure."},
            {"phase": "24-36 months", "focus": "Battery health review, deeper maintenance, and replace-vs-upgrade call."},
        ],
    },
    "trust_layer": {
        "points": [
            "Transparent benchmark methodology and assumptions.",
            "SKU-level awareness instead of model-name-only decisions.",
            "Sustained performance focus over burst-score marketing.",
            "No paid ranking bias in this guide framework.",
        ],
    },
    "final_checklist": [
        "I selected my main use case before comparing models.",
        "My CPU and GPU match my actual workload.",
        "I chose at least 16GB RAM and checked upgradeability.",
        "I chose SSD capacity that can last my course/work.",
        "I verified display quality for my daily usage.",
        "I checked practical battery expectations.",
        "I verified warranty, exact SKU, and return policy.",
    ],
}

LAPTOPS = [
    {
        "id": 1,
        "name": "ASUS TUF A15",
        "brand": "ASUS",
        "cpu": "Ryzen 7 7840HS",
        "gpu": "RTX 4060 8GB",
        "ram_gb": 16,
        "storage": "1TB NVMe Gen4",
        "display": "15.6\" FHD 144Hz",
        "weight_kg": 2.2,
        "price_usd": 1099,
        "use_case": ["gaming", "coding", "student"],
    },
    {
        "id": 2,
        "name": "Lenovo Legion 5",
        "brand": "Lenovo",
        "cpu": "Intel i7-13700H",
        "gpu": "RTX 4060 8GB",
        "ram_gb": 16,
        "storage": "1TB NVMe Gen4",
        "display": "16\" WQXGA 165Hz",
        "weight_kg": 2.4,
        "price_usd": 1249,
        "use_case": ["gaming", "editing", "coding"],
    },
    {
        "id": 3,
        "name": "Acer Nitro V",
        "brand": "Acer",
        "cpu": "Intel i5-13420H",
        "gpu": "RTX 4050 6GB",
        "ram_gb": 16,
        "storage": "512GB NVMe Gen4",
        "display": "15.6\" FHD 144Hz",
        "weight_kg": 2.1,
        "price_usd": 899,
        "use_case": ["gaming", "student"],
    },
    {
        "id": 4,
        "name": "HP Victus 16",
        "brand": "HP",
        "cpu": "Ryzen 5 7640HS",
        "gpu": "RTX 4050 6GB",
        "ram_gb": 16,
        "storage": "512GB NVMe Gen4",
        "display": "16.1\" FHD 144Hz",
        "weight_kg": 2.3,
        "price_usd": 949,
        "use_case": ["gaming", "coding", "student"],
    },
    {
        "id": 5,
        "name": "Dell XPS 15",
        "brand": "Dell",
        "cpu": "Intel i7-13700H",
        "gpu": "RTX 4050 6GB",
        "ram_gb": 32,
        "storage": "1TB NVMe Gen4",
        "display": "15.6\" 3.5K OLED 60Hz",
        "weight_kg": 1.9,
        "price_usd": 1899,
        "use_case": ["editing", "coding", "professional"],
    },
    {
        "id": 6,
        "name": "MSI Katana 15",
        "brand": "MSI",
        "cpu": "Intel i7-13620H",
        "gpu": "RTX 4070 8GB",
        "ram_gb": 16,
        "storage": "1TB NVMe Gen4",
        "display": "15.6\" FHD 144Hz",
        "weight_kg": 2.3,
        "price_usd": 1399,
        "use_case": ["gaming", "editing"],
    },
]

VALID_USE_CASES = sorted({case for laptop in LAPTOPS for case in laptop["use_case"]})

HP_PRODUCTS_SEED = [
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN MAX 16 (16-ah0076TX)",
        "sku": "B90KQPA",
        "price_inr": 309999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/hp-omen-max-gaming-laptop-16-ah0076tx-b90kqpa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "Ultra 9",
        "cpu_model": "Intel Core Ultra 9 275HX",
        "ram_gb": 32,
        "storage_type": "SSD",
        "storage_gb": 1024,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 5080",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.68,
        "battery_hours": 5.8,
        "rating": 4.9,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16-inch QHD 240Hz",
            "memory_type": "DDR5",
            "keyboard": "Per-key RGB backlit keyboard",
            "wireless": "Wi-Fi 7 + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "Configuration and sustained performance vary by thermal mode and ambient conditions.",
        },
        "benchmarks": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 122, "fps_1440p": 84},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 168, "fps_1440p": 121},
                {"title": "Valorant", "preset": "High", "fps_1080p": 350, "fps_1440p": 298},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,780"},
                {"name": "3DMark Time Spy Graphics", "score": "20,900"},
            ],
        },
    },
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN MAX 16 (16-ah0152TX)",
        "sku": "BQ6N9PA",
        "price_inr": 329999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/omen-max-gaming-laptop-16-ah0152tx-bq6n9pa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "Ultra 9",
        "cpu_model": "Intel Core Ultra 9 275HX",
        "ram_gb": 64,
        "storage_type": "SSD",
        "storage_gb": 1024,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 5080",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.70,
        "battery_hours": 5.6,
        "rating": 4.9,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16-inch QHD 240Hz",
            "memory_type": "DDR5",
            "keyboard": "Per-key RGB backlit keyboard",
            "wireless": "Wi-Fi 7 + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "Top-end OMEN MAX 16 variant with higher memory allocation.",
        },
        "benchmarks": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 128, "fps_1440p": 88},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 174, "fps_1440p": 126},
                {"title": "Call of Duty Warzone", "preset": "Ultra", "fps_1080p": 182, "fps_1440p": 130},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,820"},
                {"name": "3DMark Time Spy Graphics", "score": "21,300"},
            ],
        },
    },
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN 16 (16-wf0053TX)",
        "sku": "834J0PA",
        "price_inr": 279999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/laptops-tablets/personal-laptops/omen-laptops/omen-gaming-laptop-16-wf0053tx-834j0pa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "i9",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 32,
        "storage_type": "SSD",
        "storage_gb": 1024,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 5080",
        "screen_size": 16.1,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.45,
        "battery_hours": 5.4,
        "rating": 4.7,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16.1-inch QHD 240Hz",
            "memory_type": "DDR5",
            "keyboard": "4-zone RGB backlit keyboard",
            "wireless": "Wi-Fi 6E + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "High-performance OMEN 16 chassis; tuning mode affects sustained clocks.",
        },
        "benchmarks": {
            "games": [
                {"title": "Apex Legends", "preset": "High", "fps_1080p": 245, "fps_1440p": 192},
                {"title": "Red Dead Redemption 2", "preset": "Ultra", "fps_1080p": 136, "fps_1440p": 101},
                {"title": "Rainbow Six Siege", "preset": "Ultra", "fps_1080p": 318, "fps_1440p": 236},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,700"},
                {"name": "3DMark Time Spy Graphics", "score": "20,300"},
            ],
        },
    },
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN 16 (16-ae0003TX)",
        "sku": "B63FQPA",
        "price_inr": 189999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/hp-omen-gaming-laptop-16-ae0003tx-b63fqpa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "i7",
        "cpu_model": "Intel Core i7-14650HX",
        "ram_gb": 16,
        "storage_type": "SSD",
        "storage_gb": 1024,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 4070",
        "screen_size": 16.1,
        "resolution": "QHD",
        "refresh_hz": 165,
        "panel": "IPS",
        "weight_kg": 2.38,
        "battery_hours": 6.1,
        "rating": 4.5,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16.1-inch QHD 165Hz",
            "memory_type": "DDR5",
            "keyboard": "RGB backlit keyboard",
            "wireless": "Wi-Fi 6E + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "Balanced OMEN option for high-refresh 1440p gaming.",
        },
        "benchmarks": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "High", "fps_1080p": 102, "fps_1440p": 72},
                {"title": "Forza Horizon 5", "preset": "Ultra", "fps_1080p": 142, "fps_1440p": 105},
                {"title": "CS2", "preset": "High", "fps_1080p": 298, "fps_1440p": 238},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,430"},
                {"name": "3DMark Time Spy Graphics", "score": "15,800"},
            ],
        },
    },
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN 16 (16-am0248TX)",
        "sku": "C27E3PA",
        "price_inr": 154999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/omen-gaming-laptop-16-am0248tx-c27e3pa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "i7",
        "cpu_model": "Intel Core i7-14650HX",
        "ram_gb": 16,
        "storage_type": "SSD",
        "storage_gb": 1024,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 5050",
        "screen_size": 16.1,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.35,
        "battery_hours": 6.3,
        "rating": 4.4,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16.1-inch FHD 144Hz",
            "memory_type": "DDR5",
            "keyboard": "RGB backlit keyboard",
            "wireless": "Wi-Fi 6E + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "Mainstream OMEN configuration focused on value-oriented gaming.",
        },
        "benchmarks": {
            "games": [
                {"title": "Valorant", "preset": "High", "fps_1080p": 280, "fps_1440p": 210},
                {"title": "GTA V", "preset": "Very High", "fps_1080p": 148, "fps_1440p": 112},
                {"title": "Fortnite", "preset": "High", "fps_1080p": 162, "fps_1440p": 114},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,410"},
                {"name": "3DMark Time Spy Graphics", "score": "11,900"},
            ],
        },
    },
    {
        "brand": "HP",
        "series": "OMEN",
        "model": "OMEN 16 (16-am0173TX)",
        "sku": "C1NW9PA",
        "price_inr": 149999,
        "currency": "INR",
        "region": HP_REGION,
        "product_url": "https://www.hp.com/in-en/shop/hp-omen-gaming-laptop-16-am0173tx-c1nw9pa.html",
        "cpu_brand": "Intel",
        "cpu_tier": "i7",
        "cpu_model": "Intel Core i7-14650HX",
        "ram_gb": 16,
        "storage_type": "SSD",
        "storage_gb": 512,
        "gpu_type": "dedicated",
        "gpu_model": "RTX 5050",
        "screen_size": 16.1,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.33,
        "battery_hours": 6.0,
        "rating": 4.3,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
        "specs": {
            "display": "16.1-inch FHD 144Hz",
            "memory_type": "DDR5",
            "keyboard": "RGB backlit keyboard",
            "wireless": "Wi-Fi 6E + Bluetooth",
            "warranty": "1-year limited warranty",
            "notes": "Entry OMEN 16 variant with upgrade headroom.",
        },
        "benchmarks": {
            "games": [
                {"title": "Valorant", "preset": "High", "fps_1080p": 260, "fps_1440p": 194},
                {"title": "Apex Legends", "preset": "High", "fps_1080p": 152, "fps_1440p": 106},
                {"title": "Forza Horizon 5", "preset": "High", "fps_1080p": 118, "fps_1440p": 83},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,365"},
                {"name": "3DMark Time Spy Graphics", "score": "11,500"},
            ],
        },
    },
]

FINDER_SERIES_BY_BRAND = {
    "HP": ["OMEN", "OMEN MAX", "OMEN Transcend", "Victus", "HyperX OMEN"],
    "Lenovo": ["Legion", "LOQ"],
    "MSI": ["Stealth", "Raider", "Titan", "Crosshair"],
    "Dell": ["Alienware", "G Series"],
    "ASUS": ["ROG Strix", "ROG Zephyrus", "ROG Flow", "TUF Gaming"],
    "Acer": ["Predator", "Nitro"],
}
FINDER_BRANDS = list(FINDER_SERIES_BY_BRAND.keys())
FINDER_USE_CASES = ["gaming", "creator", "student"]
FINDER_SERIES_OPTIONS = list(
    dict.fromkeys(series for series_list in FINDER_SERIES_BY_BRAND.values() for series in series_list)
)
FINDER_CPU_BRANDS = ["Intel", "AMD"]
FINDER_CPU_TIERS = {
    "Intel": ["i5", "i7", "i9", "Ultra 7", "Ultra 9"],
    "AMD": ["Ryzen 5", "Ryzen 7", "Ryzen 9"],
}
FINDER_RAM_OPTIONS = [8, 16, 32, 64]
FINDER_STORAGE_TYPES = ["SSD", "HDD"]
FINDER_STORAGE_MIN_OPTIONS = [256, 512, 1024, 2048]
FINDER_GPU_TYPES = ["integrated", "dedicated"]
FINDER_GPU_MODELS = [
    "RTX 2050",
    "RTX 2060",
    "RTX 2070",
    "RTX 3050",
    "RTX 3060",
    "RTX 3070",
    "RTX 4050",
    "RTX 4060",
    "RTX 4070",
    "RTX 4080",
    "RTX 4090",
    "RTX 5050",
    "RTX 5060",
    "RTX 5070",
    "RTX 5070 Ti",
    "RTX 5080",
    "RTX 5090",
]
FINDER_SCREEN_BUCKETS = ["13-14", "15-16", "17+"]
FINDER_RESOLUTIONS = ["FHD", "2K", "QHD", "3K", "4K"]
FINDER_REFRESH_OPTIONS = ["120", "144", "165", "180", "240+"]
FINDER_PANELS = ["IPS", "OLED", "LED"]
FINDER_WEIGHT_BUCKETS = ["<1.5kg", "1.5-2.0kg", ">2.0kg"]
FINDER_BATTERY_BUCKETS = ["<6h", "6-10h", "10h+"]
FINDER_PORT_OPTIONS = ["USB-C", "Thunderbolt", "HDMI", "SD Card", "Ethernet", "Headphone jack"]
FINDER_EXTRA_OPTIONS = [
    ("srgb_100", "100% sRGB"),
    ("dci_p3", "DCI-P3"),
    ("good_cooling", "Good cooling"),
    ("ram_upgradable", "RAM upgradable"),
    ("extra_ssd_slot", "Extra SSD slot"),
    ("backlit_keyboard", "Backlit keyboard"),
]
FINDER_SORT_OPTIONS = [
    ("recommended", "Recommended"),
    ("price_asc", "Price: Low to High"),
    ("price_desc", "Price: High to Low"),
    ("rating_desc", "Rating"),
    ("battery_desc", "Battery life"),
    ("weight_asc", "Weight: Lightest"),
]
FINDER_PER_PAGE_OPTIONS = [12, 24, 48, 60, 120]
FINDER_DEFAULT_PER_PAGE = 120
FINDER_CPU_TIER_SET = {tier for tiers in FINDER_CPU_TIERS.values() for tier in tiers}
FINDER_SORT_LABELS = {key: label for key, label in FINDER_SORT_OPTIONS}
FINDER_TEMPLATE_OPTIONS = {
    "use_cases": [(value, value.title()) for value in FINDER_USE_CASES],
    "brands": FINDER_BRANDS,
    "series_by_brand": FINDER_SERIES_BY_BRAND,
    "series_options": FINDER_SERIES_OPTIONS,
    "cpu_brands": FINDER_CPU_BRANDS,
    "cpu_tiers": FINDER_CPU_TIERS,
    "ram_options": FINDER_RAM_OPTIONS,
    "storage_types": FINDER_STORAGE_TYPES,
    "storage_min_options": FINDER_STORAGE_MIN_OPTIONS,
    "gpu_types": FINDER_GPU_TYPES,
    "gpu_models": FINDER_GPU_MODELS,
    "screen_buckets": FINDER_SCREEN_BUCKETS,
    "resolutions": FINDER_RESOLUTIONS,
    "refresh_options": FINDER_REFRESH_OPTIONS,
    "panels": FINDER_PANELS,
    "weight_buckets": FINDER_WEIGHT_BUCKETS,
    "battery_buckets": FINDER_BATTERY_BUCKETS,
    "ports": FINDER_PORT_OPTIONS,
    "extras": FINDER_EXTRA_OPTIONS,
    "sort_options": FINDER_SORT_OPTIONS,
    "per_page_options": FINDER_PER_PAGE_OPTIONS,
}

FINDER_LAPTOPS = []

CURATED_BRAND_HUB_LINKS = {
    "Lenovo": "https://www.lenovo.com/in/en/gaming-laptops/",
    "MSI": "https://in.msi.com/Laptops/Products#?tag=Gaming-Series",
    "Dell": "https://www.dell.com/en-in/gaming/alienware",
    "ASUS": "https://www.asus.com/in/laptops/for-gaming/",
    "Acer": "https://store.acer.com/en-in/laptops/gaming-laptops",
}

CURATED_MULTI_BRAND_BASE_PRODUCTS = [
    {
        "brand": "Lenovo",
        "series": "Legion",
        "model": "Legion Pro 5i Gen 9 (16IRX9)",
        "sku": "LEN-LEGION-16IRX9-IN01",
        "price_inr": 179990,
        "product_url": "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-pro-series/legion-pro-5i-gen-9-16-inch-intel/len101g0033/",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 32,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.5,
        "battery_hours": 6.0,
        "battery_capacity_wh": 80,
        "battery_type": "4-cell, 80 Wh Li-ion",
        "rating": 4.6,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "Lenovo",
        "series": "LOQ",
        "model": "LOQ 15IRX9",
        "sku": "LEN-LOQ-15IRX9-IN01",
        "price_inr": 104990,
        "product_url": "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/len101q0009/",
        "cpu_model": "Intel Core i7-13650HX",
        "ram_gb": 16,
        "storage_gb": 512,
        "gpu_model": "RTX 4060",
        "screen_size": 15.6,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.4,
        "battery_hours": 5.5,
        "battery_capacity_wh": 60,
        "battery_type": "4-cell, 60 Wh Li-ion",
        "rating": 4.4,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "MSI",
        "series": "Stealth",
        "model": "Stealth 16 AI Studio A1V",
        "sku": "MSI-STEALTH16-A1V-IN01",
        "price_inr": 219990,
        "product_url": "https://in.msi.com/Laptop/Stealth-16-AI-Studio-A1VX",
        "cpu_model": "Intel Core Ultra 9 185H",
        "ram_gb": 32,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "OLED",
        "weight_kg": 1.99,
        "battery_hours": 7.2,
        "battery_capacity_wh": 99,
        "battery_type": "4-cell, 99 Wh Li-polymer",
        "rating": 4.5,
        "use_cases": ["gaming", "creator", "student"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "MSI",
        "series": "Katana",
        "model": "Katana 15 B13V",
        "sku": "MSI-KATANA15-B13V-IN01",
        "price_inr": 119990,
        "product_url": "https://in.msi.com/Laptop/Katana-15-B13VX",
        "cpu_model": "Intel Core i7-13620H",
        "ram_gb": 16,
        "storage_gb": 1024,
        "gpu_model": "RTX 4060",
        "screen_size": 15.6,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.25,
        "battery_hours": 4.8,
        "battery_capacity_wh": 54,
        "battery_type": "3-cell, 54 Wh Li-polymer",
        "rating": 4.3,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "MSI",
        "series": "Raider",
        "model": "Raider 18 HX A14V",
        "sku": "MSI-RAIDER18-A14V-IN01",
        "price_inr": 329990,
        "product_url": "https://in.msi.com/Laptop/Raider-18-HX-A14VX",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 32,
        "storage_gb": 2048,
        "gpu_model": "RTX 4080",
        "screen_size": 18.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 3.1,
        "battery_hours": 4.7,
        "battery_capacity_wh": 99,
        "battery_type": "4-cell, 99 Wh Li-polymer",
        "rating": 4.7,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "MSI",
        "series": "Vector",
        "model": "Vector 16 HX A14V",
        "sku": "MSI-VECTOR16-A14V-IN01",
        "price_inr": 239990,
        "product_url": "https://in.msi.com/Laptop/Vector-16-HX-A14VX",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 32,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.7,
        "battery_hours": 5.3,
        "battery_capacity_wh": 90,
        "battery_type": "4-cell, 90 Wh Li-polymer",
        "rating": 4.6,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "MSI",
        "series": "Titan",
        "model": "Titan 18 HX AI A2X",
        "sku": "MSI-TITAN18-A2X-IN01",
        "price_inr": 529990,
        "product_url": "https://in.msi.com/Laptop/Titan-18-HX-AI-A2XWX",
        "cpu_model": "Intel Core Ultra 9 285HX",
        "ram_gb": 64,
        "storage_gb": 2048,
        "gpu_model": "RTX 4080",
        "screen_size": 18.0,
        "resolution": "4K",
        "refresh_hz": 120,
        "panel": "IPS",
        "weight_kg": 3.6,
        "battery_hours": 4.6,
        "battery_capacity_wh": 99,
        "battery_type": "4-cell, 99 Wh Li-polymer",
        "rating": 4.8,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "SD Card", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "Dell",
        "series": "Alienware",
        "model": "Alienware m16 R2",
        "sku": "DEL-ALIENWARE-M16R2-IN01",
        "price_inr": 219990,
        "product_url": "https://www.dell.com/en-in/shop/gaming-and-games/alienware-m16-r2-gaming-laptop/spd/alienware-m16-r2-laptop",
        "cpu_model": "Intel Core Ultra 9 185H",
        "ram_gb": 32,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.61,
        "battery_hours": 6.1,
        "battery_capacity_wh": 90,
        "battery_type": "6-cell, 90 Wh Li-ion",
        "rating": 4.6,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "Dell",
        "series": "G Series",
        "model": "G15 5530",
        "sku": "DEL-G15-5530-IN01",
        "price_inr": 127990,
        "product_url": "https://www.dell.com/en-in/shop/gaming-and-games/g15-gaming-laptop/spd/g-series-15-5530-laptop",
        "cpu_model": "Intel Core i7-13650HX",
        "ram_gb": 16,
        "storage_gb": 1024,
        "gpu_model": "RTX 4060",
        "screen_size": 15.6,
        "resolution": "FHD",
        "refresh_hz": 165,
        "panel": "IPS",
        "weight_kg": 2.65,
        "battery_hours": 5.0,
        "battery_capacity_wh": 86,
        "battery_type": "6-cell, 86 Wh Li-ion",
        "rating": 4.4,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "ASUS",
        "series": "ROG Strix",
        "model": "ROG Strix G16 (2024)",
        "sku": "ASU-ROG-G16-2024-IN01",
        "price_inr": 189990,
        "product_url": "https://www.asus.com/in/laptops/for-gaming/rog/rog-strix-g16-2024/",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 32,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 240,
        "panel": "IPS",
        "weight_kg": 2.5,
        "battery_hours": 6.0,
        "battery_capacity_wh": 90,
        "battery_type": "4-cell, 90 Wh Li-ion",
        "rating": 4.6,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "ASUS",
        "series": "TUF Gaming",
        "model": "TUF Gaming A15 (FA507)",
        "sku": "ASU-TUF-A15-FA507-IN01",
        "price_inr": 109990,
        "product_url": "https://www.asus.com/in/laptops/for-gaming/tuf-gaming/asus-tuf-gaming-a15-2024/",
        "cpu_model": "AMD Ryzen 7 8845HS",
        "ram_gb": 16,
        "storage_gb": 1024,
        "gpu_model": "RTX 4060",
        "screen_size": 15.6,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.2,
        "battery_hours": 7.0,
        "battery_capacity_wh": 90,
        "battery_type": "4-cell, 90 Wh Li-ion",
        "rating": 4.4,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "Acer",
        "series": "Predator",
        "model": "Predator Helios Neo 16",
        "sku": "ACE-PREDATOR-NEO16-IN01",
        "price_inr": 154990,
        "product_url": "https://store.acer.com/en-in/predator-helios-neo-16-gaming-laptop",
        "cpu_model": "Intel Core i9-14900HX",
        "ram_gb": 16,
        "storage_gb": 1024,
        "gpu_model": "RTX 4070",
        "screen_size": 16.0,
        "resolution": "QHD",
        "refresh_hz": 165,
        "panel": "IPS",
        "weight_kg": 2.6,
        "battery_hours": 5.6,
        "battery_capacity_wh": 90,
        "battery_type": "4-cell, 90 Wh Li-ion",
        "rating": 4.5,
        "use_cases": ["gaming", "creator"],
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": True,
        "dci_p3": True,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
    {
        "brand": "Acer",
        "series": "Nitro",
        "model": "Nitro V 15",
        "sku": "ACE-NITROV15-IN01",
        "price_inr": 95990,
        "product_url": "https://store.acer.com/en-in/nitro-v-15-gaming-laptop",
        "cpu_model": "Intel Core i5-13420H",
        "ram_gb": 16,
        "storage_gb": 512,
        "gpu_model": "RTX 4050",
        "screen_size": 15.6,
        "resolution": "FHD",
        "refresh_hz": 144,
        "panel": "IPS",
        "weight_kg": 2.1,
        "battery_hours": 5.2,
        "battery_capacity_wh": 57,
        "battery_type": "3-cell, 57 Wh Li-ion",
        "rating": 4.3,
        "use_cases": ["gaming", "student"],
        "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
        "srgb_100": False,
        "dci_p3": False,
        "good_cooling": True,
        "ram_upgradable": True,
        "extra_ssd_slot": True,
        "backlit_keyboard": True,
    },
]


def _to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _unique(items):
    seen = set()
    ordered = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _normalize_choice(value, allowed):
    if value in (None, ""):
        return ""
    lookup = {item.lower(): item for item in allowed}
    return lookup.get(str(value).strip().lower(), "")


def _normalize_choices(values, allowed):
    lookup = {item.lower(): item for item in allowed}
    normalized = []
    for value in values:
        match = lookup.get(str(value).strip().lower())
        if match:
            normalized.append(match)
    return _unique(normalized)


def _normalize_int_choices(values, allowed):
    allowed_set = set(allowed)
    parsed = []
    for value in values:
        parsed_value = _to_int(value)
        if parsed_value is not None and parsed_value in allowed_set:
            parsed.append(parsed_value)
    return _unique(parsed)


def _arg_truthy(args, key):
    raw = args.get(key)
    if raw is None:
        return False
    return str(raw).strip().lower() not in {"", "0", "false", "no", "off"}


def _screen_bucket(size):
    if size < 15:
        return "13-14"
    if size < 17:
        return "15-16"
    return "17+"


def _weight_bucket(weight):
    if weight < 1.5:
        return "<1.5kg"
    if weight <= 2.0:
        return "1.5-2.0kg"
    return ">2.0kg"


def _battery_bucket(hours):
    if hours < 6:
        return "<6h"
    if hours <= 10:
        return "6-10h"
    return "10h+"


def _refresh_bucket(refresh_hz):
    if refresh_hz >= 240:
        return "240+"
    return str(int(refresh_hz))


def _normalize_resolution(value):
    normalized = re.sub(r"\s+", "", str(value or "").upper())
    if normalized in {"FHD", "1080P", "1920X1080"}:
        return "FHD"
    if normalized in {"2K", "QHD", "WQHD", "WQXGA", "2560X1440", "2560X1600", "1600P"}:
        return "2K"
    if normalized in {"3K", "3.5K", "3456X2160"}:
        return "3K"
    if normalized in {"4K", "UHD", "UHD+", "3840X2160"}:
        return "4K"
    return str(value or "").strip().upper()


def _resolution_matches_filter(resolution, selected_values):
    if not selected_values:
        return True
    normalized_target = _normalize_resolution(resolution)
    normalized_selected = {_normalize_resolution(value) for value in selected_values}
    return normalized_target in normalized_selected


def _panel_matches_filter(panel_name, selected_values):
    if not selected_values:
        return True

    panel_upper = str(panel_name or "").strip().upper()
    if not panel_upper:
        return False

    for selected in selected_values:
        selected_upper = str(selected or "").strip().upper()
        if selected_upper == "LED":
            if "OLED" in panel_upper:
                continue
            if "LED" in panel_upper or panel_upper in {"IPS", "TN", "VA", "LCD"}:
                return True
            continue
        if panel_upper == selected_upper or selected_upper in panel_upper:
            return True
    return False


def _series_matches_filter(series_name, selected_values):
    if not selected_values:
        return True

    normalized_series = str(series_name or "").strip()
    series_upper = normalized_series.upper()
    compact_series = re.sub(r"[^A-Z0-9]", "", series_upper)

    for selected in selected_values:
        selected_upper = str(selected or "").strip().upper()
        compact_selected = re.sub(r"[^A-Z0-9]", "", selected_upper)

        if selected_upper == "OMEN" and series_upper.startswith("OMEN"):
            return True
        if selected_upper == "HYPERX OMEN" and series_upper.startswith("OMEN"):
            return True
        if selected_upper == "G SERIES" and re.match(r"^G[\s\-]?\d", series_upper):
            return True

        if series_upper == selected_upper:
            return True
        if series_upper.startswith(f"{selected_upper} "):
            return True
        if selected_upper in series_upper:
            return True
        if compact_selected and compact_selected in compact_series:
            return True
    return False


def _ordered_options(values, preferred_order):
    value_set = {value for value in values if value not in (None, "")}
    preferred = list(preferred_order or [])
    ordered = [value for value in preferred if value in value_set]
    for value in sorted(value_set):
        if value not in ordered:
            ordered.append(value)
    return ordered


def _build_finder_options(catalog, filters):
    all_catalog = list(catalog or [])
    selected_brands = list(filters.get("brand") or [])
    selected_series = list(filters.get("series") or [])

    brand_scoped = [item for item in all_catalog if item["brand"] in selected_brands] if selected_brands else list(all_catalog)
    if not brand_scoped:
        brand_scoped = list(all_catalog)

    scoped_catalog = list(brand_scoped)
    if selected_series:
        narrowed = [item for item in scoped_catalog if _series_matches_filter(item["series"], selected_series)]
        if narrowed:
            scoped_catalog = narrowed

    brand_values = _ordered_options(
        {item["brand"] for item in all_catalog}.union(set(selected_brands)),
        FINDER_BRANDS,
    )
    if not brand_values:
        brand_values = list(FINDER_BRANDS)

    brands_for_series = selected_brands if selected_brands else brand_values
    series_by_brand = {}
    for brand in brands_for_series:
        configured = FINDER_SERIES_BY_BRAND.get(brand, [])
        available = {item["series"] for item in all_catalog if item["brand"] == brand}
        selected_for_brand = {value for value in selected_series if value in configured or value in available}
        series_values = _ordered_options(available.union(selected_for_brand).union(set(configured)), configured)
        if series_values:
            series_by_brand[brand] = series_values

    if not series_by_brand:
        for brand in brand_values:
            configured = FINDER_SERIES_BY_BRAND.get(brand, [])
            if configured:
                series_by_brand[brand] = list(configured)

    series_options = _unique([value for values in series_by_brand.values() for value in values])

    available_use_cases = {use_case for item in scoped_catalog for use_case in item.get("use_cases", [])}
    use_case_values = [value for value in FINDER_USE_CASES if value in available_use_cases]
    if filters.get("use_case") and filters["use_case"] not in use_case_values:
        use_case_values.append(filters["use_case"])
    if not use_case_values:
        use_case_values = list(FINDER_USE_CASES)

    cpu_brands = _ordered_options(
        {item["cpu_brand"] for item in scoped_catalog}.union({filters["cpu_brand"]} if filters.get("cpu_brand") else set()),
        FINDER_CPU_BRANDS,
    )
    if not cpu_brands:
        cpu_brands = list(FINDER_CPU_BRANDS)

    cpu_tier_map = {}
    for cpu_brand in cpu_brands:
        available_tiers = {item["cpu_tier"] for item in scoped_catalog if item["cpu_brand"] == cpu_brand}
        preferred_tiers = FINDER_CPU_TIERS.get(cpu_brand, [])
        selected_tiers = {value for value in filters.get("cpu_tier", []) if value in available_tiers or value in preferred_tiers}
        tier_values = _ordered_options(available_tiers.union(selected_tiers).union(set(preferred_tiers)), preferred_tiers)
        cpu_tier_map[cpu_brand] = tier_values

    ram_options = _ordered_options(
        {item["ram_gb"] for item in scoped_catalog}.union(set(filters.get("ram", []))),
        FINDER_RAM_OPTIONS,
    )
    storage_types = _ordered_options(
        {item["storage_type"] for item in scoped_catalog}.union(set(filters.get("storage_type", []))),
        FINDER_STORAGE_TYPES,
    )
    gpu_types = _ordered_options(
        {item["gpu_type"] for item in scoped_catalog}.union({filters["gpu_type"]} if filters.get("gpu_type") else set()),
        FINDER_GPU_TYPES,
    )
    gpu_models = list(FINDER_GPU_MODELS)
    screen_buckets = _ordered_options(
        {_screen_bucket(item["screen_size"]) for item in scoped_catalog}.union(set(filters.get("screen_bucket", []))),
        FINDER_SCREEN_BUCKETS,
    )
    resolutions = list(FINDER_RESOLUTIONS)
    refresh_options = list(FINDER_REFRESH_OPTIONS)
    panels = list(FINDER_PANELS)
    weight_buckets = _ordered_options(
        {_weight_bucket(item["weight_kg"]) for item in scoped_catalog}.union(set(filters.get("weight_bucket", []))),
        FINDER_WEIGHT_BUCKETS,
    )
    battery_buckets = _ordered_options(
        {_battery_bucket(item["battery_hours"]) for item in scoped_catalog}.union(set(filters.get("battery_bucket", []))),
        FINDER_BATTERY_BUCKETS,
    )
    ports = _ordered_options(
        {port for item in scoped_catalog for port in item.get("ports", [])}.union(set(filters.get("port", []))),
        FINDER_PORT_OPTIONS,
    )

    catalog_prices = [int(item.get("price") or 0) for item in all_catalog if int(item.get("price") or 0) > 0]
    if catalog_prices:
        price_min_bound = (min(catalog_prices) // 1000) * 1000
        price_max_bound = int(ceil(max(catalog_prices) / 1000.0) * 1000)
    else:
        price_min_bound = 0
        price_max_bound = 500000
    selected_price_values = [value for value in (filters.get("min_price"), filters.get("max_price")) if value is not None]
    if selected_price_values:
        price_min_bound = min(price_min_bound, min(selected_price_values))
        price_max_bound = max(price_max_bound, max(selected_price_values))
    if price_max_bound <= price_min_bound:
        price_max_bound = price_min_bound + 1000
    price_step = 1000 if price_max_bound <= 300000 else 5000

    extras = []
    for key, label in FINDER_EXTRA_OPTIONS:
        if any(bool(item.get(key)) for item in scoped_catalog) or bool(filters.get(key)):
            extras.append((key, label))
    if not extras:
        extras = list(FINDER_EXTRA_OPTIONS)

    return {
        "use_cases": [(value, value.title()) for value in use_case_values],
        "brands": brand_values or list(FINDER_BRANDS),
        "series_by_brand": series_by_brand,
        "series_options": series_options or list(FINDER_SERIES_OPTIONS),
        "cpu_brands": cpu_brands or list(FINDER_CPU_BRANDS),
        "cpu_tiers": cpu_tier_map,
        "ram_options": ram_options or list(FINDER_RAM_OPTIONS),
        "storage_types": storage_types or list(FINDER_STORAGE_TYPES),
        "storage_min_options": list(FINDER_STORAGE_MIN_OPTIONS),
        "gpu_types": gpu_types or list(FINDER_GPU_TYPES),
        "gpu_models": gpu_models or list(FINDER_GPU_MODELS),
        "screen_buckets": screen_buckets or list(FINDER_SCREEN_BUCKETS),
        "resolutions": resolutions or list(FINDER_RESOLUTIONS),
        "refresh_options": refresh_options or list(FINDER_REFRESH_OPTIONS),
        "panels": panels or list(FINDER_PANELS),
        "weight_buckets": weight_buckets or list(FINDER_WEIGHT_BUCKETS),
        "battery_buckets": battery_buckets or list(FINDER_BATTERY_BUCKETS),
        "ports": ports or list(FINDER_PORT_OPTIONS),
        "price_bounds": {
            "min": price_min_bound,
            "max": price_max_bound,
            "step": price_step,
        },
        "extras": extras,
        "sort_options": list(FINDER_SORT_OPTIONS),
        "per_page_options": list(FINDER_PER_PAGE_OPTIONS),
    }


def _finder_query_map_from_filters(filters, include_page=True):
    params = {}
    if filters["q"]:
        params["q"] = [filters["q"]]
    if filters["use_case"]:
        params["use_case"] = [filters["use_case"]]
    if filters["brand"]:
        params["brand"] = filters["brand"]
    if filters["series"]:
        params["series"] = filters["series"]
    if filters["min_price"] is not None:
        params["min_price"] = [str(filters["min_price"])]
    if filters["max_price"] is not None:
        params["max_price"] = [str(filters["max_price"])]
    if filters["cpu_brand"]:
        params["cpu_brand"] = [filters["cpu_brand"]]
    if filters["cpu_tier"]:
        params["cpu_tier"] = filters["cpu_tier"]
    if filters["ram"]:
        params["ram"] = [str(value) for value in filters["ram"]]
    if filters["storage_type"]:
        params["storage_type"] = filters["storage_type"]
    if filters["storage_min"] is not None:
        params["storage_min"] = [str(filters["storage_min"])]
    if filters["gpu_type"]:
        params["gpu_type"] = [filters["gpu_type"]]
    if filters["gpu_model"]:
        params["gpu_model"] = filters["gpu_model"]
    if filters["screen_bucket"]:
        params["screen_bucket"] = filters["screen_bucket"]
    if filters["resolution"]:
        params["resolution"] = filters["resolution"]
    if filters["refresh"]:
        params["refresh"] = filters["refresh"]
    if filters["panel"]:
        params["panel"] = filters["panel"]
    if filters["weight_bucket"]:
        params["weight_bucket"] = filters["weight_bucket"]
    if filters["battery_bucket"]:
        params["battery_bucket"] = filters["battery_bucket"]
    if filters["port"]:
        params["port"] = filters["port"]

    for extra_key, _ in FINDER_EXTRA_OPTIONS:
        if filters[extra_key]:
            params[extra_key] = ["1"]

    if filters["sort"] != "recommended":
        params["sort"] = [filters["sort"]]
    if filters["per_page"] != FINDER_DEFAULT_PER_PAGE:
        params["per_page"] = [str(filters["per_page"])]
    if include_page and filters["page"] > 1:
        params["page"] = [str(filters["page"])]
    return params


def _finder_url(params):
    flat_params = []
    for key, values in params.items():
        for value in values:
            flat_params.append((key, value))
    if not flat_params:
        return url_for("laptops")
    return f"{url_for('laptops')}?{urlencode(flat_params)}"


def _finder_remove_param(params, key, value=None):
    updated = {param_key: list(param_values) for param_key, param_values in params.items()}
    updated.pop("page", None)

    if value is None:
        updated.pop(key, None)
        return updated

    target_value = str(value)
    if key not in updated:
        return updated
    updated[key] = [entry for entry in updated[key] if entry != target_value]
    if not updated[key]:
        updated.pop(key)
    return updated


def _parse_finder_filters(args):
    use_case_raw = str(args.get("use_case", "")).strip().lower()
    use_case = use_case_raw if use_case_raw in FINDER_USE_CASES else ""

    min_price = _to_int(args.get("min_price"))
    max_price = _to_int(args.get("max_price"))
    if min_price is not None and min_price < 0:
        min_price = None
    if max_price is not None and max_price < 0:
        max_price = None
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    sort = str(args.get("sort", "recommended")).strip().lower()
    if sort not in FINDER_SORT_LABELS:
        sort = "recommended"

    per_page = _to_int(args.get("per_page")) or FINDER_DEFAULT_PER_PAGE
    if per_page not in FINDER_PER_PAGE_OPTIONS:
        per_page = FINDER_DEFAULT_PER_PAGE

    page = _to_int(args.get("page")) or 1
    if page < 1:
        page = 1

    filters = {
        "q": str(args.get("q", "")).strip(),
        "sort": sort,
        "page": page,
        "per_page": per_page,
        "use_case": use_case,
        "brand": _normalize_choices(args.getlist("brand"), FINDER_BRANDS),
        "series": _normalize_choices(args.getlist("series"), FINDER_SERIES_OPTIONS),
        "min_price": min_price,
        "max_price": max_price,
        "cpu_brand": _normalize_choice(args.get("cpu_brand"), FINDER_CPU_BRANDS),
        "cpu_tier": _normalize_choices(args.getlist("cpu_tier"), FINDER_CPU_TIER_SET),
        "ram": _normalize_int_choices(args.getlist("ram"), FINDER_RAM_OPTIONS),
        "storage_type": _normalize_choices(args.getlist("storage_type"), FINDER_STORAGE_TYPES),
        "storage_min": _to_int(args.get("storage_min")),
        "gpu_type": _normalize_choice(args.get("gpu_type"), FINDER_GPU_TYPES),
        "gpu_model": _normalize_choices(args.getlist("gpu_model"), FINDER_GPU_MODELS),
        "screen_bucket": _normalize_choices(args.getlist("screen_bucket"), FINDER_SCREEN_BUCKETS),
        "resolution": _normalize_choices(args.getlist("resolution"), FINDER_RESOLUTIONS),
        "refresh": _normalize_choices(args.getlist("refresh"), FINDER_REFRESH_OPTIONS),
        "panel": _normalize_choices(args.getlist("panel"), FINDER_PANELS),
        "weight_bucket": _normalize_choices(args.getlist("weight_bucket"), FINDER_WEIGHT_BUCKETS),
        "battery_bucket": _normalize_choices(args.getlist("battery_bucket"), FINDER_BATTERY_BUCKETS),
        "port": _normalize_choices(args.getlist("port"), FINDER_PORT_OPTIONS),
    }

    if filters["storage_min"] not in FINDER_STORAGE_MIN_OPTIONS:
        filters["storage_min"] = None

    for extra_key, _ in FINDER_EXTRA_OPTIONS:
        filters[extra_key] = _arg_truthy(args, extra_key)

    if filters["brand"] and filters["series"]:
        allowed_series = set()
        for brand in filters["brand"]:
            allowed_series.update(FINDER_SERIES_BY_BRAND.get(brand, []))
        if allowed_series:
            filters["series"] = [series for series in filters["series"] if series in allowed_series]

    return filters


def _matches_finder_filters(laptop, filters):
    if filters["q"]:
        needle = filters["q"].lower()
        haystack = f"{laptop['brand']} {laptop['model']}".lower()
        if needle not in haystack:
            return False

    if filters["use_case"] and filters["use_case"] not in laptop["use_cases"]:
        return False
    if filters["brand"] and laptop["brand"] not in filters["brand"]:
        return False
    if filters["series"] and not _series_matches_filter(laptop["series"], filters["series"]):
        return False
    if filters["min_price"] is not None and laptop["price"] < filters["min_price"]:
        return False
    if filters["max_price"] is not None and laptop["price"] > filters["max_price"]:
        return False
    if filters["cpu_brand"] and laptop["cpu_brand"] != filters["cpu_brand"]:
        return False
    if filters["cpu_tier"] and laptop["cpu_tier"] not in filters["cpu_tier"]:
        return False
    if filters["ram"] and laptop["ram_gb"] not in filters["ram"]:
        return False
    if filters["storage_type"] and laptop["storage_type"] not in filters["storage_type"]:
        return False
    if filters["storage_min"] is not None and laptop["storage_gb"] < filters["storage_min"]:
        return False
    if filters["gpu_type"] and laptop["gpu_type"] != filters["gpu_type"]:
        return False
    if filters["gpu_model"] and laptop["gpu_model"] not in filters["gpu_model"]:
        return False
    if filters["screen_bucket"] and _screen_bucket(laptop["screen_size"]) not in filters["screen_bucket"]:
        return False
    if filters["resolution"] and not _resolution_matches_filter(laptop["resolution"], filters["resolution"]):
        return False
    if filters["refresh"] and _refresh_bucket(laptop["refresh_hz"]) not in filters["refresh"]:
        return False
    if filters["panel"] and not _panel_matches_filter(laptop["panel"], filters["panel"]):
        return False
    if filters["weight_bucket"] and _weight_bucket(laptop["weight_kg"]) not in filters["weight_bucket"]:
        return False
    if filters["battery_bucket"] and _battery_bucket(laptop["battery_hours"]) not in filters["battery_bucket"]:
        return False
    if filters["port"] and not all(port in laptop["ports"] for port in filters["port"]):
        return False

    for extra_key, _ in FINDER_EXTRA_OPTIONS:
        if filters[extra_key] and not laptop.get(extra_key, False):
            return False

    return True


def _sort_finder_laptops(laptops, sort_key, use_case):
    if sort_key == "price_asc":
        return sorted(laptops, key=lambda item: (item["price"], -item["rating"]))
    if sort_key == "price_desc":
        return sorted(laptops, key=lambda item: (item["price"], item["rating"]), reverse=True)
    if sort_key == "rating_desc":
        return sorted(laptops, key=lambda item: (item["rating"], -item["price"]), reverse=True)
    if sort_key == "battery_desc":
        return sorted(laptops, key=lambda item: (item["battery_hours"], item["rating"]), reverse=True)
    if sort_key == "weight_asc":
        return sorted(laptops, key=lambda item: (item["weight_kg"], -item["rating"]))

    return sorted(
        laptops,
        key=lambda item: (
            1 if use_case and use_case in item["use_cases"] else 0,
            item["rating"],
            item["battery_hours"],
            -item["price"],
        ),
        reverse=True,
    )


def _build_active_chips(filters, query_map):
    chips = []

    def add_chip(label, key, value=None):
        chips.append(
            {
                "label": label,
                "remove_url": _finder_url(_finder_remove_param(query_map, key, value)),
            }
        )

    if filters["q"]:
        add_chip(f'Search: "{filters["q"]}"', "q")
    if filters["use_case"]:
        add_chip(f"Use Case: {filters['use_case'].title()}", "use_case")
    for brand in filters["brand"]:
        add_chip(f"Brand: {brand}", "brand", brand)
    for series in filters["series"]:
        add_chip(f"Series: {series}", "series", series)
    if filters["min_price"] is not None:
        add_chip(f"Min: ${filters['min_price']}", "min_price")
    if filters["max_price"] is not None:
        add_chip(f"Max: ${filters['max_price']}", "max_price")
    if filters["cpu_brand"]:
        add_chip(f"CPU Brand: {filters['cpu_brand']}", "cpu_brand")
    for cpu_tier in filters["cpu_tier"]:
        add_chip(f"CPU Tier: {cpu_tier}", "cpu_tier", cpu_tier)
    for ram in filters["ram"]:
        add_chip(f"RAM: {ram}GB", "ram", ram)
    for storage_type in filters["storage_type"]:
        add_chip(f"Storage: {storage_type}", "storage_type", storage_type)
    if filters["storage_min"] is not None:
        min_label = f"{_format_storage(filters['storage_min'])}+"
        add_chip(f"Storage Min: {min_label}", "storage_min")
    if filters["gpu_type"]:
        add_chip(f"GPU Type: {filters['gpu_type'].title()}", "gpu_type")
    for gpu_model in filters["gpu_model"]:
        add_chip(f"GPU: {gpu_model}", "gpu_model", gpu_model)
    for value in filters["screen_bucket"]:
        add_chip(f"Screen: {value}", "screen_bucket", value)
    for value in filters["resolution"]:
        add_chip(f"Resolution: {value}", "resolution", value)
    for value in filters["refresh"]:
        add_chip(f"Refresh: {value}Hz", "refresh", value)
    for value in filters["panel"]:
        add_chip(f"Panel: {value}", "panel", value)
    for value in filters["weight_bucket"]:
        add_chip(f"Weight: {value}", "weight_bucket", value)
    for value in filters["battery_bucket"]:
        add_chip(f"Battery: {value}", "battery_bucket", value)
    for value in filters["port"]:
        add_chip(f"Port: {value}", "port", value)
    for extra_key, extra_label in FINDER_EXTRA_OPTIONS:
        if filters[extra_key]:
            add_chip(extra_label, extra_key)

    if filters["sort"] != "recommended":
        add_chip(f"Sort: {FINDER_SORT_LABELS[filters['sort']]}", "sort")
    if filters["per_page"] != FINDER_DEFAULT_PER_PAGE:
        add_chip(f"Per Page: {filters['per_page']}", "per_page")

    return chips


def _parse_compare_ids(args):
    raw_ids = []
    for raw_value in args.getlist("ids"):
        raw_ids.extend(str(raw_value).split(","))

    parsed = []
    for value in raw_ids:
        parsed_value = _to_int(value.strip())
        if parsed_value is None:
            continue
        if parsed_value in parsed:
            continue
        parsed.append(parsed_value)
    return parsed[:4]


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_loads(value, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _has_native_configuration(specs):
    if not isinstance(specs, dict):
        return False
    configuration = specs.get("configuration")
    if not isinstance(configuration, dict):
        return False
    categories = configuration.get("categories")
    return isinstance(categories, list) and any(isinstance(category, dict) for category in categories)


def _db_connect():
    connection = sqlite3.connect(HP_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _strip_tags(value):
    cleaned = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_image_url(raw_url, base_url="https://www.hp.com"):
    value = _strip_tags(unescape(raw_url or "")).strip()
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return urljoin(base_url, value)
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return ""


def _extract_card_image_url(card_html):
    image_tag_match = re.search(
        r'<img[^>]*class="[^"]*product-image-photo[^"]*"[^>]*>',
        card_html,
        re.I | re.S,
    )
    image_tag = image_tag_match.group(0) if image_tag_match else ""
    if not image_tag:
        return ""

    for attr in ("src", "data-src", "data-original"):
        attr_match = re.search(rf'{attr}="([^"]+)"', image_tag, re.I)
        if attr_match:
            normalized = _normalize_image_url(attr_match.group(1))
            if normalized:
                return normalized

    srcset_match = re.search(r'srcset="([^"]+)"', image_tag, re.I)
    if srcset_match:
        first_source = srcset_match.group(1).split(",", 1)[0].strip()
        first_url = first_source.split(" ", 1)[0].strip()
        return _normalize_image_url(first_url)
    return ""


def _parse_price_inr(raw_value):
    try:
        return int(float(raw_value))
    except (TypeError, ValueError):
        return 0


def _fetch_html(url, timeout=12):
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _discover_last_listing_page(listing_html, listing_url):
    listing_slug = listing_url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if not listing_slug:
        return 1
    page_matches = re.findall(rf"{re.escape(listing_slug)}\?p=(\d+)", listing_html, flags=re.I)
    if not page_matches:
        return 1
    try:
        return max(int(value) for value in page_matches)
    except ValueError:
        return 1


def _infer_battery_capacity_wh(screen_size, series):
    series_upper = series.upper()
    if "VICTUS" in series_upper:
        return 70 if screen_size < 16 else 83
    if "TRANSCEND" in series_upper:
        return 71
    if screen_size <= 14.2:
        return 71
    if "MAX" in series_upper:
        return 83
    return 83


def _normalize_battery_type_text(raw_value):
    battery_text = _strip_tags(unescape(raw_value or ""))
    if not battery_text:
        return ""

    battery_text = battery_text.replace("\xa0", " ")
    battery_text = re.sub(r"\s+", " ", battery_text).strip(" ,;")
    battery_text = re.sub(r"(?i)\b(\d+)\s*-\s*cell\b", r"\1-cell", battery_text)
    battery_text = re.sub(r"(?i)\b(\d+(?:\.\d+)?)\s*w[h]?\b", r"\1 Wh", battery_text)
    battery_text = re.sub(r"(?i)li[\s-]?ion[\s-]?polymer", "Li-ion polymer", battery_text)
    battery_text = re.sub(r"(?i)li[\s-]?polymer", "Li-polymer", battery_text)
    battery_text = re.sub(r"(?i)\bli[\s-]?ion\b", "Li-ion", battery_text)
    battery_text = re.sub(r"\s*,\s*", ", ", battery_text)
    battery_text = re.sub(r"\s+", " ", battery_text).strip(" ,;")
    return battery_text


def _battery_type_display(battery_type, battery_capacity_wh):
    display_text = _normalize_battery_type_text(battery_type)
    if not display_text:
        return ""

    if battery_capacity_wh:
        display_text = re.sub(
            rf"(?i)\b{int(battery_capacity_wh)}(?:\.0+)?\s*Wh\b",
            "",
            display_text,
        )
        display_text = re.sub(r"\s*,\s*", ", ", display_text)
        display_text = re.sub(r"\s+", " ", display_text).strip(" ,;")
    return display_text


def _extract_battery_info_from_pdp(pdp_html):
    match = re.search(r'<dd[^>]*data-th\s*=\s*"Battery type"[^>]*>(.*?)</dd>', pdp_html, re.I | re.S)
    if not match:
        match = re.search(r"Battery type[\s\S]{0,2000}?<dd[^>]*>(.*?)</dd>", pdp_html, re.I)
    if not match:
        return None, ""

    battery_text = _normalize_battery_type_text(match.group(1))
    capacity_match = re.search(r"([0-9]{2,3})(?:\.[0-9]+)?\s*Wh", battery_text, re.I)
    if not capacity_match:
        return None, battery_text

    return int(capacity_match.group(1)), battery_text


def _infer_cpu_brand_tier(cpu_model):
    normalized = _strip_tags(unescape(cpu_model or "")).lower()
    normalized = normalized.replace("™", " ").replace("®", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if "ryzen ai 9" in normalized or "ryzen 9" in normalized:
        return "AMD", "Ryzen 9"
    if "ryzen ai 7" in normalized or "ryzen 7" in normalized:
        return "AMD", "Ryzen 7"
    if "ryzen 5" in normalized:
        return "AMD", "Ryzen 5"
    if "ultra 9" in normalized:
        return "Intel", "Ultra 9"
    if "ultra 7" in normalized:
        return "Intel", "Ultra 7"
    if "i9" in normalized:
        return "Intel", "i9"
    if "i7" in normalized or "core 7" in normalized:
        return "Intel", "i7"
    if "i5" in normalized or "core 5" in normalized:
        return "Intel", "i5"
    return "Intel", "i7"


def _normalize_gpu_model(raw_gpu):
    if not raw_gpu:
        return "RTX 4050"

    normalized = _strip_tags(unescape(raw_gpu))
    normalized = (
        normalized.replace("™", " ")
        .replace("®", " ")
        .replace("NVIDIA", " ")
        .replace("GeForce", " ")
        .replace("AMD", " ")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()

    rtx_match = re.search(r"RTX\s*([0-9]{3,4})(?:\s*(Ti))?", normalized, re.I)
    if rtx_match:
        gpu = f"RTX {rtx_match.group(1)}"
        if rtx_match.group(2):
            gpu += " Ti"
        return gpu

    radeon_match = re.search(r"Radeon\s+RX\s*([0-9]{4})(M?)", normalized, re.I)
    if radeon_match:
        suffix = "M" if radeon_match.group(2) else ""
        return f"Radeon RX {radeon_match.group(1)}{suffix}".strip()

    arc_match = re.search(r"Intel\s+Arc(?:\s+([A-Z0-9-]+))?", normalized, re.I)
    if arc_match:
        tier = (arc_match.group(1) or "").strip()
        return f"Intel Arc {tier}".strip()

    if re.search(r"(radeon|intel)\s+graphics|integrated", normalized, re.I):
        return "Integrated Graphics"

    return normalized


def _extract_gpu_from_title_or_features(title, feature_rows):
    combined = " | ".join([title] + feature_rows)
    gpu_model = _normalize_gpu_model(combined)
    if gpu_model and gpu_model != "Integrated Graphics":
        if re.search(r"RTX|Radeon RX|Intel Arc", gpu_model, re.I):
            return "dedicated", gpu_model

    for row in feature_rows:
        row_model = _normalize_gpu_model(row)
        if row_model and row_model != "Integrated Graphics":
            if re.search(r"RTX|Radeon RX|Intel Arc", row_model, re.I):
                return "dedicated", row_model

    if re.search(r"radeon|intel|integrated", combined, re.I):
        return "integrated", "Integrated Graphics"
    return "dedicated", "RTX 4050"


def _extract_screen_size_from_title_or_features(title, feature_rows):
    title_match = re.search(r"\((\d{2}(?:\.\d)?)\)", title, re.I)
    if title_match:
        return float(title_match.group(1))

    cm_match = re.search(r"([0-9]{2}(?:\.[0-9])?)\s*cm", title, re.I)
    if cm_match:
        return round(float(cm_match.group(1)) / 2.54, 1)

    model_match = re.search(r"laptop\s+(\d{2})", title, re.I)
    if model_match:
        return float(model_match.group(1))

    for row in feature_rows:
        row_match = re.search(r"\((\d{2}(?:\.\d)?)\)", row, re.I)
        if row_match:
            return float(row_match.group(1))
    return 16.0


def _build_placeholder_benchmarks(gpu_model):
    profiles = {
        "RTX 5090": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 148, "fps_1440p": 109},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 196, "fps_1440p": 146},
                {"title": "Valorant", "preset": "High", "fps_1080p": 415, "fps_1440p": 352},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,920"},
                {"name": "3DMark Time Spy Graphics", "score": "23,900"},
            ],
        },
        "RTX 5080": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 136, "fps_1440p": 97},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 182, "fps_1440p": 134},
                {"title": "Valorant", "preset": "High", "fps_1080p": 380, "fps_1440p": 320},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,820"},
                {"name": "3DMark Time Spy Graphics", "score": "21,400"},
            ],
        },
        "RTX 4090": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 132, "fps_1440p": 95},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 178, "fps_1440p": 130},
                {"title": "Valorant", "preset": "High", "fps_1080p": 365, "fps_1440p": 307},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,780"},
                {"name": "3DMark Time Spy Graphics", "score": "20,700"},
            ],
        },
        "RTX 4080": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 124, "fps_1440p": 88},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 171, "fps_1440p": 126},
                {"title": "Valorant", "preset": "High", "fps_1080p": 349, "fps_1440p": 292},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,700"},
                {"name": "3DMark Time Spy Graphics", "score": "19,800"},
            ],
        },
        "RTX 5070 Ti": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 120, "fps_1440p": 84},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 170, "fps_1440p": 124},
                {"title": "Valorant", "preset": "High", "fps_1080p": 340, "fps_1440p": 285},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,650"},
                {"name": "3DMark Time Spy Graphics", "score": "19,300"},
            ],
        },
        "RTX 5070": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 110, "fps_1440p": 77},
                {"title": "Forza Horizon 5", "preset": "Extreme", "fps_1080p": 157, "fps_1440p": 114},
                {"title": "Valorant", "preset": "High", "fps_1080p": 315, "fps_1440p": 262},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,580"},
                {"name": "3DMark Time Spy Graphics", "score": "17,900"},
            ],
        },
        "RTX 5060": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "High", "fps_1080p": 96, "fps_1440p": 66},
                {"title": "Forza Horizon 5", "preset": "Ultra", "fps_1080p": 141, "fps_1440p": 101},
                {"title": "Valorant", "preset": "High", "fps_1080p": 288, "fps_1440p": 233},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,500"},
                {"name": "3DMark Time Spy Graphics", "score": "15,200"},
            ],
        },
        "RTX 4060": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "High", "fps_1080p": 90, "fps_1440p": 63},
                {"title": "Forza Horizon 5", "preset": "Ultra", "fps_1080p": 134, "fps_1440p": 97},
                {"title": "Valorant", "preset": "High", "fps_1080p": 274, "fps_1440p": 224},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,460"},
                {"name": "3DMark Time Spy Graphics", "score": "13,800"},
            ],
        },
        "RTX 4070": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Ultra", "fps_1080p": 104, "fps_1440p": 72},
                {"title": "Forza Horizon 5", "preset": "Ultra", "fps_1080p": 149, "fps_1440p": 107},
                {"title": "Valorant", "preset": "High", "fps_1080p": 302, "fps_1440p": 248},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,540"},
                {"name": "3DMark Time Spy Graphics", "score": "16,100"},
            ],
        },
        "RTX 5050": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "High", "fps_1080p": 88, "fps_1440p": 58},
                {"title": "Forza Horizon 5", "preset": "High", "fps_1080p": 129, "fps_1440p": 90},
                {"title": "Valorant", "preset": "High", "fps_1080p": 271, "fps_1440p": 214},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,420"},
                {"name": "3DMark Time Spy Graphics", "score": "13,100"},
            ],
        },
        "RTX 4050": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "High", "fps_1080p": 78, "fps_1440p": 53},
                {"title": "Forza Horizon 5", "preset": "High", "fps_1080p": 118, "fps_1440p": 82},
                {"title": "Valorant", "preset": "High", "fps_1080p": 245, "fps_1440p": 195},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,360"},
                {"name": "3DMark Time Spy Graphics", "score": "10,900"},
            ],
        },
        "RTX 3050": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Medium", "fps_1080p": 56, "fps_1440p": 38},
                {"title": "Forza Horizon 5", "preset": "Medium", "fps_1080p": 96, "fps_1440p": 66},
                {"title": "Valorant", "preset": "High", "fps_1080p": 201, "fps_1440p": 158},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,220"},
                {"name": "3DMark Time Spy Graphics", "score": "7,500"},
            ],
        },
        "RTX 2050": {
            "games": [
                {"title": "Cyberpunk 2077", "preset": "Low", "fps_1080p": 44, "fps_1440p": 29},
                {"title": "Forza Horizon 5", "preset": "Medium", "fps_1080p": 72, "fps_1440p": 51},
                {"title": "Valorant", "preset": "High", "fps_1080p": 176, "fps_1440p": 137},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "1,050"},
                {"name": "3DMark Time Spy Graphics", "score": "5,200"},
            ],
        },
        "Integrated Graphics": {
            "games": [
                {"title": "Valorant", "preset": "Low", "fps_1080p": 92, "fps_1440p": 58},
                {"title": "CS2", "preset": "Low", "fps_1080p": 76, "fps_1440p": 48},
                {"title": "Forza Horizon 5", "preset": "Low", "fps_1080p": 38, "fps_1440p": 25},
            ],
            "synthetic": [
                {"name": "Cinebench 2024 Multi", "score": "980"},
                {"name": "3DMark Time Spy Graphics", "score": "2,200"},
            ],
        },
    }
    return profiles.get(gpu_model, profiles["RTX 4050"])


def _mark_included(options, selected_value):
    normalized_selected = str(selected_value or "").lower()
    matched = False
    for option in options:
        token = str(option.get("match", "")).lower()
        option["included"] = bool(token and token in normalized_selected)
        if option["included"]:
            matched = True
    if not matched and options:
        options[0]["included"] = True
    for option in options:
        option.pop("match", None)
    return options


def _lenovo_configurator_url(product_url):
    url = str(product_url or "").strip()
    if not url:
        return ""
    if "cto" in url.lower():
        return url
    bundle_match = re.search(r"/(len[0-9a-z]+)$", url.rstrip("/"), re.I)
    if not bundle_match:
        return ""
    bundle_id = bundle_match.group(1).upper()
    return f"https://www.lenovo.com/in/en/configurator/cto/index.html?bundleId={bundle_id}"


def _normalize_catalog_url(url):
    value = str(url or "").strip()
    if not value:
        return ""
    value = value.split("#", 1)[0].split("?", 1)[0].strip()
    return value.rstrip("/")


def _extract_meta_content(html, meta_name):
    pattern = re.compile(
        rf'<meta[^>]*\bname=["\']{re.escape(meta_name)}["\'][^>]*\bcontent=["\']([^"\']*)["\']',
        re.I,
    )
    match = pattern.search(html or "")
    if not match:
        return ""
    return _strip_tags(unescape(match.group(1))).strip()


def _extract_lenovo_price_inr(html):
    offer_match = re.search(
        r'"offers"\s*:\s*\{[\s\S]{0,400}?"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        html or "",
        re.I,
    )
    if offer_match:
        return int(float(offer_match.group(1)))

    generic_match = re.search(r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)', html or "", re.I)
    if generic_match:
        return int(float(generic_match.group(1)))
    return 0


def _extract_lenovo_specs_from_html(html):
    specs = {}

    for key_raw, value_raw in re.findall(r'"a":"([^"]+)","b":"([^"]+)"', html or ""):
        key = _strip_tags(unescape(key_raw)).strip()
        value = _strip_tags(unescape(value_raw)).strip()
        if key and value and key not in specs:
            specs[key] = value

    fallback_meta = {
        "Processor": "Processor",
        "Operating System": "operating_system",
        "Memory": "memory",
        "Storage": "hard_drive",
        "Display": "display_type",
        "Graphic Card": "graphic_card",
        "Keyboard": "keyboard",
        "Color": "color",
        "WIFI": "wifi",
        "Battery": "series_mktg_battery",
        "Warranty": "warranty",
        "AC Adapter / Power Supply": "power_supply",
        "Software Preload": "software",
    }
    for canonical, meta_name in fallback_meta.items():
        if canonical in specs:
            continue
        meta_value = _extract_meta_content(html, meta_name)
        if meta_value:
            specs[canonical] = meta_value

    return specs


def _extract_lenovo_variant_codes(html):
    combined = ",".join(
        value
        for value in [
            _extract_meta_content(html, "productcodeimpressions"),
            _extract_meta_content(html, "bundleIDimpressions"),
        ]
        if value
    )
    if not combined:
        return []

    codes = []
    for token in combined.split(","):
        code = token.strip().upper()
        if not code:
            continue
        if not re.match(r"^[A-Z0-9]{7,14}$", code):
            continue
        if code.startswith("LEN"):
            continue
        if code not in codes:
            codes.append(code)
    return codes


def _normalize_lenovo_category(raw_name):
    normalized = _strip_tags(unescape(raw_name or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""

    mapping = {
        "Processor": "Processor",
        "Operating System": "Operating System",
        "Graphic Card": "Graphics Card",
        "Graphics": "Graphics Card",
        "Memory": "Memory",
        "Storage": "Storage",
        "Display": "Display",
        "Screen Resolution": "Display",
        "Keyboard": "Keyboard",
        "Color": "Color",
        "WIFI": "Wireless",
        "AC Adapter / Power Supply": "Power Adapter",
        "Battery": "Battery",
        "Warranty": "Warranty & Protection",
        "Services": "Warranty & Protection",
        "Software Preload": "Software",
        "Software": "Software",
    }
    return mapping.get(normalized, "")


def _normalize_lenovo_option_display(category_name, raw_value):
    value = re.sub(r"\s+", " ", _strip_tags(unescape(raw_value or ""))).strip()
    if not value:
        return ""

    if category_name == "Graphics Card":
        # Normalize vendor/model casing to avoid duplicate rows caused by minor text variations.
        value = re.sub(r"\bNvidia\b", "NVIDIA", value, flags=re.I)
        value = re.sub(r"\bGeforce\b", "GeForce", value, flags=re.I)
        value = re.sub(r"\bRtx\b", "RTX", value, flags=re.I)
        value = re.sub(r"\bLaptop Gpu\b", "Laptop GPU", value, flags=re.I)
    return value


def _canonical_lenovo_option_key(category_name, raw_value):
    display = _normalize_lenovo_option_display(category_name, raw_value)
    if not display:
        return ""

    canonical = display.casefold()
    canonical = canonical.replace("®", "").replace("™", "")
    canonical = canonical.replace("\xa0", " ")
    canonical = re.sub(r"[^a-z0-9]+", " ", canonical).strip()
    return canonical


def _extract_lenovo_codes_from_detail(detail):
    if not detail:
        return []
    found = []
    for code in re.findall(r"\b[A-Z0-9]{8,14}\b", str(detail).upper()):
        if not any(ch.isalpha() for ch in code) or not any(ch.isdigit() for ch in code):
            continue
        if code not in found:
            found.append(code)
    return found


def _render_lenovo_variant_detail(codes, fallback_detail=""):
    normalized_codes = []
    for code in codes:
        clean = str(code or "").strip().upper()
        if clean and clean not in normalized_codes:
            normalized_codes.append(clean)

    if normalized_codes:
        shown_codes = ", ".join(normalized_codes[:2])
        extra_codes = len(normalized_codes) - 2
        detail = f"Official variant SKU: {shown_codes}"
        if extra_codes > 0:
            detail += f" (+{extra_codes} more)"
        return detail
    return str(fallback_detail or "").strip()


def _dedupe_lenovo_configuration(configuration):
    if not isinstance(configuration, dict):
        return {}

    categories = configuration.get("categories")
    if not isinstance(categories, list):
        return configuration

    deduped_categories = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        category_name = str(category.get("name") or "").strip()
        options = category.get("options")
        if not isinstance(options, list):
            continue

        options_by_key = {}
        for raw_option in options:
            if not isinstance(raw_option, dict):
                continue

            option_name = _normalize_lenovo_option_display(category_name, raw_option.get("name", ""))
            option_key = _canonical_lenovo_option_key(category_name, option_name)
            if not option_key:
                continue

            incoming_codes = _extract_lenovo_codes_from_detail(raw_option.get("details", ""))
            incoming_price_note = str(raw_option.get("price_note") or "").strip()
            incoming_alt_price_note = str(raw_option.get("alt_price_note") or "").strip()
            incoming_included = bool(raw_option.get("included"))
            incoming_details = str(raw_option.get("details") or "").strip()

            existing = options_by_key.get(option_key)
            if not existing:
                options_by_key[option_key] = {
                    "name": option_name,
                    "details": incoming_details,
                    "price_note": incoming_price_note,
                    "alt_price_note": incoming_alt_price_note,
                    "included": incoming_included,
                    "_codes": list(incoming_codes),
                }
                continue

            existing["included"] = existing["included"] or incoming_included
            for code in incoming_codes:
                if code not in existing["_codes"]:
                    existing["_codes"].append(code)

            if not existing.get("price_note") and incoming_price_note:
                existing["price_note"] = incoming_price_note
            if not existing.get("alt_price_note") and incoming_alt_price_note:
                existing["alt_price_note"] = incoming_alt_price_note
            if len(incoming_details) > len(existing.get("details", "")):
                existing["details"] = incoming_details

        deduped_options = []
        for option in options_by_key.values():
            details = _render_lenovo_variant_detail(option.get("_codes", []), option.get("details", ""))
            deduped_options.append(
                {
                    "name": option["name"],
                    "details": details,
                    "price_note": option.get("price_note", ""),
                    "alt_price_note": option.get("alt_price_note", ""),
                    "included": bool(option.get("included")),
                }
            )

        deduped_options.sort(key=lambda entry: (not entry["included"], entry["name"]))
        if deduped_options and not any(option["included"] for option in deduped_options):
            deduped_options[0]["included"] = True

        deduped_categories.append(
            {
                "name": category_name,
                "options": deduped_options,
            }
        )

    normalized_configuration = dict(configuration)
    normalized_configuration["categories"] = deduped_categories
    return normalized_configuration


def _load_lenovo_customization_cache():
    if not os.path.exists(LENOVO_CUSTOMIZATION_CACHE_PATH):
        return {}
    try:
        with open(LENOVO_CUSTOMIZATION_CACHE_PATH, "r", encoding="utf-8") as cache_file:
            data = json.load(cache_file)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_lenovo_customization_cache(cache):
    try:
        with open(LENOVO_CUSTOMIZATION_CACHE_PATH, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, ensure_ascii=True, indent=2)
    except OSError:
        return


def _is_fresh_lenovo_customization_cache_item(cache_item):
    if not isinstance(cache_item, dict):
        return False
    if cache_item.get("version") != LENOVO_CUSTOMIZATION_CACHE_VERSION:
        return False
    fetched_at = int(cache_item.get("fetched_at") or 0)
    if fetched_at <= 0:
        return False
    return (time.time() - fetched_at) < LENOVO_CUSTOMIZATION_CACHE_TTL_SECONDS


def _fetch_lenovo_official_customization(product_url, fallback_price=0):
    normalized_url = _normalize_catalog_url(product_url)
    if not normalized_url or "lenovo.com" not in normalized_url.lower():
        return None

    try:
        page_html = _fetch_html(normalized_url, timeout=14)
    except (URLError, TimeoutError, ValueError):
        return None

    if "/" not in normalized_url:
        return None
    url_prefix, url_tail = normalized_url.rsplit("/", 1)
    current_tail = url_tail.upper()

    bundle_id = _extract_meta_content(page_html, "subseriesPHcode").upper()
    if not bundle_id:
        bundle_id = _extract_meta_content(page_html, "bundleid").upper()
    if not bundle_id and current_tail.startswith("LEN"):
        bundle_id = current_tail

    current_code = _extract_meta_content(page_html, "productcode").upper() or current_tail

    variant_codes = _extract_lenovo_variant_codes(page_html)
    if current_code and not current_code.startswith("LEN") and current_code not in variant_codes:
        variant_codes.append(current_code)

    # SKU pages often omit the full variant list; use the bundle page to discover all official variants.
    if (not variant_codes or len(variant_codes) < 2) and bundle_id and not current_tail.startswith("LEN"):
        bundle_url = f"{url_prefix}/{bundle_id.lower()}"
        try:
            bundle_html = _fetch_html(bundle_url, timeout=14)
        except (URLError, TimeoutError, ValueError):
            bundle_html = ""
        if bundle_html:
            for code in _extract_lenovo_variant_codes(bundle_html):
                if code not in variant_codes:
                    variant_codes.append(code)

    if not variant_codes and current_code and not current_code.startswith("LEN"):
        variant_codes = [current_code]

    variant_codes = variant_codes[:8]
    current_specs = _extract_lenovo_specs_from_html(page_html)
    current_price = _extract_lenovo_price_inr(page_html) or int(fallback_price or 0)

    variants = []
    for code in variant_codes:
        variant_url = f"{url_prefix}/{code.lower()}"
        try:
            variant_html = page_html if code == current_tail else _fetch_html(variant_url, timeout=14)
        except (URLError, TimeoutError, ValueError):
            continue
        variant_specs = _extract_lenovo_specs_from_html(variant_html)
        if not variant_specs:
            continue
        variants.append(
            {
                "code": code,
                "price": _extract_lenovo_price_inr(variant_html),
                "specs": variant_specs,
            }
        )

    if not variants and current_specs:
        variants = [{"code": current_code, "price": current_price, "specs": current_specs}]
    if not variants:
        return {
            "customization_available": False,
            "customization_options": [],
            "configuration": {},
        }

    if not current_specs:
        current_specs = variants[0]["specs"]
    if not current_price:
        for variant in variants:
            if variant["code"] == current_code and variant.get("price"):
                current_price = int(variant["price"])
                break
        if not current_price:
            for variant in variants:
                if variant.get("price"):
                    current_price = int(variant["price"])
                    break
        if not current_price:
            current_price = int(fallback_price or 0)

    category_order = [
        "Processor",
        "Operating System",
        "Graphics Card",
        "Memory",
        "Storage",
        "Display",
        "Keyboard",
        "Color",
        "Wireless",
        "Battery",
        "Power Adapter",
        "Warranty & Protection",
        "Software",
    ]
    category_values = {name: {} for name in category_order}
    current_selected_keys = {}

    for raw_key, raw_value in current_specs.items():
        category_name = _normalize_lenovo_category(raw_key)
        if not category_name:
            continue
        value = _normalize_lenovo_option_display(category_name, raw_value)
        if value:
            current_selected_keys[category_name] = _canonical_lenovo_option_key(category_name, value)

    for variant in variants:
        variant_price = int(variant.get("price") or 0)
        variant_code = variant.get("code", "")
        for raw_key, raw_value in variant.get("specs", {}).items():
            category_name = _normalize_lenovo_category(raw_key)
            if not category_name:
                continue
            value = _normalize_lenovo_option_display(category_name, raw_value)
            if not value:
                continue

            option_key = _canonical_lenovo_option_key(category_name, value)
            if not option_key:
                continue

            option_pool = category_values.setdefault(category_name, {})
            option = option_pool.get(option_key)
            if not option:
                option = {"key": option_key, "name": value, "prices": [], "codes": []}
                option_pool[option_key] = option
            if variant_price:
                option["prices"].append(variant_price)
            if variant_code and variant_code not in option["codes"]:
                option["codes"].append(variant_code)

    categories = []
    for category_name in category_order:
        options_pool = category_values.get(category_name, {})
        if not options_pool:
            continue
        if len(options_pool) == 1 and category_name not in {
            "Processor",
            "Graphics Card",
            "Memory",
            "Storage",
            "Display",
            "Keyboard",
            "Operating System",
        }:
            continue

        options = []
        for option in options_pool.values():
            min_price = min(option["prices"]) if option["prices"] else 0
            selected_key = current_selected_keys.get(category_name, "")
            included = bool(selected_key) and option.get("key") == selected_key
            delta = (min_price - current_price) if (min_price and current_price and not included) else 0
            price_note = ""
            if delta:
                sign = "+" if delta > 0 else "-"
                price_note = f"{sign}₹{abs(delta):,}"

            detail = _render_lenovo_variant_detail(option["codes"])

            options.append(
                {
                    "name": option["name"],
                    "details": detail,
                    "price_note": price_note,
                    "alt_price_note": "",
                    "included": included,
                }
            )

        options.sort(key=lambda entry: (not entry["included"], entry["name"]))
        if options and not any(option["included"] for option in options):
            options[0]["included"] = True

        categories.append({"name": category_name, "options": options})

    configuration = {}
    if categories:
        configuration = {
            "title": "Configuration",
            "collapse_hint": "Official Lenovo options",
            "warranty_note": (
                "Options synced from official Lenovo India variant listings. "
                "Price differences are estimated from listed variant pricing and may vary at checkout."
            ),
            "categories": categories,
        }
        configuration = _dedupe_lenovo_configuration(configuration)
        categories = configuration.get("categories", []) if isinstance(configuration, dict) else []

    customization_available = any(len(category.get("options", [])) > 1 for category in categories)
    customization_options = []
    for category in categories:
        option_count = len(category.get("options", []))
        if option_count > 1:
            customization_options.append(f"{category['name']}: {option_count} official options")
    if not customization_options:
        customization_options = [f"{category['name']}: official Lenovo spec" for category in categories[:6]]

    return {
        "customization_available": customization_available,
        "customization_options": customization_options,
        "configuration": configuration,
    }


def _apply_lenovo_official_customization(products):
    lenovo_products = [item for item in products if item.get("brand") == "Lenovo"]
    if not lenovo_products:
        return products

    cache = _load_lenovo_customization_cache()
    cache_updated = False
    url_to_data = {}

    for product in lenovo_products:
        product_url = _normalize_catalog_url(product.get("product_url", ""))
        if not product_url:
            continue
        if product_url in url_to_data:
            continue

        cache_item = cache.get(product_url)
        customization_data = None
        if _is_fresh_lenovo_customization_cache_item(cache_item):
            customization_data = cache_item.get("data")
        else:
            customization_data = _fetch_lenovo_official_customization(
                product_url,
                fallback_price=product.get("price_inr", 0),
            )
            if customization_data is not None:
                cache[product_url] = {
                    "version": LENOVO_CUSTOMIZATION_CACHE_VERSION,
                    "fetched_at": int(time.time()),
                    "data": customization_data,
                }
                cache_updated = True
            elif isinstance(cache_item, dict):
                customization_data = cache_item.get("data")

        if isinstance(customization_data, dict):
            url_to_data[product_url] = customization_data

    if cache_updated:
        _save_lenovo_customization_cache(cache)

    for product in lenovo_products:
        product_url = _normalize_catalog_url(product.get("product_url", ""))
        customization_data = url_to_data.get(product_url)
        if not isinstance(customization_data, dict):
            continue
        if customization_data.get("customization_available"):
            deduped_configuration = _dedupe_lenovo_configuration(
                customization_data.get("configuration", product.get("configuration", {}))
            )
            deduped_categories = deduped_configuration.get("categories", []) if isinstance(deduped_configuration, dict) else []
            deduped_customization_options = []
            for category in deduped_categories:
                option_count = len(category.get("options", [])) if isinstance(category, dict) else 0
                if option_count > 1:
                    deduped_customization_options.append(f"{category.get('name', 'Option')}: {option_count} official options")

            fallback_options = list(customization_data.get("customization_options", product.get("customization_options", [])))
            product["customization_options"] = deduped_customization_options or fallback_options
            product["configuration"] = deduped_configuration
        else:
            product["customization_options"] = []
            product["configuration"] = {}

    return products


def _build_lenovo_configuration_block(series, cpu_model, ram_gb, storage_gb, gpu_model, screen_size, resolution, refresh_hz, battery_capacity_wh):
    is_legion = series == "Legion"

    processor_options_loq = _mark_included(
        [
            {
                "name": "14th Generation Intel® Core™ i7-14700HX Processor",
                "details": "(E-cores up to 3.90 GHz P-cores up to 5.50 GHz)",
                "price_note": "+₹11,800",
                "alt_price_note": "-₹8,200",
                "match": "i7-14700hx",
            },
            {
                "name": "13th Generation Intel® Core™ i7-13650HX Processor",
                "details": "(E-cores up to 3.60 GHz P-cores up to 4.90 GHz)",
                "price_note": "+₹3,900",
                "alt_price_note": "-₹3,100",
                "match": "i7-13650hx",
            },
            {
                "name": "13th Generation Intel® Core™ i5-13450HX Processor",
                "details": "(E-cores up to 3.40 GHz P-cores up to 4.60 GHz)",
                "price_note": "",
                "alt_price_note": "",
                "match": "i5-13450hx",
            },
        ],
        cpu_model,
    )
    processor_options_legion = _mark_included(
        [
            {
                "name": "Intel® Core™ Ultra 9 275HX Processor",
                "details": "(Up to 5.4GHz, 24 cores)",
                "price_note": "+₹22,000",
                "alt_price_note": "",
                "match": "ultra 9 275hx",
            },
            {
                "name": "14th Generation Intel® Core™ i9-14900HX Processor",
                "details": "(E-cores up to 4.10 GHz P-cores up to 5.80 GHz)",
                "price_note": "+₹14,500",
                "alt_price_note": "",
                "match": "i9-14900hx",
            },
            {
                "name": "14th Generation Intel® Core™ i7-14700HX Processor",
                "details": "(E-cores up to 3.90 GHz P-cores up to 5.50 GHz)",
                "price_note": "+₹8,900",
                "alt_price_note": "",
                "match": "i7-14700hx",
            },
            {
                "name": "AMD Ryzen™ 9 8945HX Processor",
                "details": "(Up to 5.20 GHz boost clock)",
                "price_note": "+₹9,000",
                "alt_price_note": "",
                "match": "ryzen 9 8945hx",
            },
        ],
        cpu_model,
    )

    processor_options = processor_options_legion if is_legion else processor_options_loq

    if is_legion:
        memory_options = _mark_included(
            [
                {
                    "name": "16 GB DDR5-5600MT/s (SODIMM)",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "16",
                },
                {
                    "name": "32 GB DDR5-5600MT/s (2 x 16 GB)",
                    "details": "",
                    "price_note": "+₹22,500",
                    "alt_price_note": "",
                    "match": "32",
                },
                {
                    "name": "64 GB DDR5-5600MT/s (2 x 32 GB)",
                    "details": "",
                    "price_note": "+₹38,900",
                    "alt_price_note": "",
                    "match": "64",
                },
            ],
            str(64 if ram_gb >= 64 else 32 if ram_gb >= 32 else 16),
        )
        storage_options = _mark_included(
            [
                {
                    "name": "1 TB SSD M.2 PCIe Gen4 TLC",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "1024",
                },
                {
                    "name": "2 TB SSD M.2 PCIe Gen4 TLC",
                    "details": "",
                    "price_note": "+₹18,200",
                    "alt_price_note": "",
                    "match": "2048",
                },
                {
                    "name": "4 TB SSD M.2 PCIe Gen4 TLC (2 x 2TB)",
                    "details": "",
                    "price_note": "+₹42,900",
                    "alt_price_note": "",
                    "match": "4096",
                },
            ],
            str(4096 if storage_gb >= 4096 else 2048 if storage_gb >= 2048 else 1024),
        )
        keyboard_options = _mark_included(
            [
                {
                    "name": "4-zone RGB Backlit, TrueStrike - English (US)",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "4-zone",
                },
                {
                    "name": "Per-key RGB Backlit, TrueStrike - English (US)",
                    "details": "",
                    "price_note": "+₹3,000",
                    "alt_price_note": "",
                    "match": "per-key",
                },
            ],
            "per-key" if gpu_model in {"RTX 5080", "RTX 5090"} else "4-zone",
        )
    else:
        memory_options = _mark_included(
            [
                {
                    "name": "16 GB DDR5-4800MT/s (SODIMM)",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "16",
                },
                {
                    "name": "32 GB DDR5-4800MT/s (SODIMM) - (2 x 16 GB)",
                    "details": "",
                    "price_note": "+₹22,500",
                    "alt_price_note": "",
                    "match": "32",
                },
            ],
            str(32 if ram_gb >= 32 else 16),
        )
        storage_options = _mark_included(
            [
                {
                    "name": "512 GB SSD M.2 2242 PCIe Gen4 TLC",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "512",
                },
                {
                    "name": "1 TB SSD M.2 2242 PCIe Gen4 TLC",
                    "details": "",
                    "price_note": "+₹11,200",
                    "alt_price_note": "",
                    "match": "1024",
                },
            ],
            str(1024 if storage_gb >= 1024 else 512),
        )
        keyboard_options = _mark_included(
            [
                {
                    "name": "White Backlit, Eclipse Black - English (US)",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "white",
                },
                {
                    "name": "24zone RGB Backlit, Eclipse Black - English (US)",
                    "details": "",
                    "price_note": "+₹1,500",
                    "alt_price_note": "",
                    "match": "rgb",
                },
            ],
            "rgb" if ram_gb >= 32 else "white",
        )

    resolution_dimensions = {
        "FHD": "1920 x 1080",
        "QHD": "2560 x 1600",
        "4K": "3840 x 2400",
    }
    panel = "OLED" if resolution == "4K" else "IPS"
    nits = 500 if is_legion else 300
    display_text = (
        f"{screen_size * 2.54:.2f}cms ({screen_size:.1f}) "
        f"{resolution} ({resolution_dimensions.get(resolution, '1920 x 1080')}), {panel}, "
        f"Anti-Glare, Non-Touch, 100%sRGB, {nits} nits, {refresh_hz}Hz"
    )

    graphics_text = f"NVIDIA® GeForce {gpu_model} Laptop GPU" if "RTX" in gpu_model else gpu_model
    gpu_vram_by_model = {
        "RTX 3050": "6GB GDDR6",
        "RTX 4050": "6GB GDDR6",
        "RTX 4060": "8GB GDDR6",
        "RTX 4070": "8GB GDDR6",
        "RTX 4080": "12GB GDDR6",
        "RTX 4090": "16GB GDDR6",
        "RTX 5070": "8GB GDDR7",
        "RTX 5070 Ti": "12GB GDDR7",
        "RTX 5080": "16GB GDDR7",
        "RTX 5090": "24GB GDDR7",
    }
    graphics_details = gpu_vram_by_model.get(gpu_model, "VRAM varies by selected GPU")

    if is_legion:
        if gpu_model == "RTX 5090":
            power_adapter = "400W Slim Tip AC Adapter - India"
        elif gpu_model in {"RTX 5080", "RTX 5070 Ti"}:
            power_adapter = "330W Slim Tip AC Adapter - India"
        else:
            power_adapter = "300W Slim Tip AC Adapter - India"
    else:
        power_adapter = "245W 30% PCC 3pin AC Adapter - India"

    cooling_text = (
        "Legion Coldfront Hyper cooling with vapor chamber and liquid metal"
        if is_legion
        else "LOQ HyperChamber dual-fan cooling system"
    )
    mux_text = "MUX Switch + NVIDIA Advanced Optimus + Lenovo AI Engine+" if is_legion else "MUX Switch + Lenovo AI Engine+"
    wireless_text = "Wi-Fi 7 2x2 BE & Bluetooth® 5.4" if is_legion else "Wi-Fi 6 2x2 AX & Bluetooth® 5.3"
    color_text = "Eclipse Black" if is_legion else "Luna Grey"

    return {
        "title": "Configuration",
        "collapse_hint": "Collapse All Categories",
        "warranty_note": "Configuration price includes 3 Year warranty + Accidental Damage Protection at 4499/- only. You can deselect this option at cart.",
        "categories": [
            {"name": "Processor", "options": processor_options},
            {
                "name": "Operating System",
                "options": [
                    {"name": "Windows 11 Home Single Language 64", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                    {"name": "Windows 11 Pro 64", "details": "", "price_note": "+₹9,000", "alt_price_note": "", "included": False},
                ],
            },
            {
                "name": "Microsoft Productivity Software",
                "options": [
                    {"name": "Microsoft Office Trial", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                    {"name": "Microsoft Office Home 2024 India", "details": "", "price_note": "+₹8,999", "alt_price_note": "+₹2,000", "included": False},
                ],
            },
            {"name": "Memory", "options": memory_options},
            {"name": "Solid State Drive", "options": storage_options},
            {
                "name": "Display",
                "options": [
                    {"name": display_text, "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Graphics Card",
                "options": [
                    {"name": graphics_text, "details": graphics_details, "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Cooling",
                "options": [
                    {"name": cooling_text, "details": "Sustained performance profile and fan curve controls in Lenovo Vantage", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "MUX / AI Features",
                "options": [
                    {"name": mux_text, "details": "Hybrid / discrete mode switching supported", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Camera",
                "options": [
                    {"name": "5MP with Dual Microphone and E-Shutter", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Color",
                "options": [
                    {"name": color_text, "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {"name": "Keyboard", "options": keyboard_options},
            {
                "name": "Wireless",
                "options": [
                    {"name": wireless_text, "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Battery",
                "options": [
                    {"name": f"4 Cell Rechargeable Li-ion {battery_capacity_wh}Wh", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Power Adapter",
                "options": [
                    {"name": power_adapter, "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Warranty & Protection",
                "options": [
                    {"name": "3 Year Warranty + Accidental Damage Protection", "details": "Can be removed at cart", "price_note": "", "alt_price_note": "-₹4,499 if removed", "included": True},
                    {"name": "1 Year Base Warranty", "details": "", "price_note": "-₹4,499", "alt_price_note": "", "included": False},
                ],
            },
            {
                "name": "AI Agent",
                "options": [
                    {"name": "Lenovo AI Now", "details": "On-device productivity and tuning assistant", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
        ],
    }


def _build_lenovo_catalog_variants():
    loq_customization = [
        "Processor options: Intel Core i5/i7 HX",
        "OS options: Windows 11 Home or Pro",
        "Memory options: 16GB or 32GB DDR5",
        "Storage options: 512GB / 1TB PCIe Gen4 SSD",
        "GPU options: RTX 3050 / RTX 4050 / RTX 4060",
        "Display options: FHD/QHD up to 165Hz",
        "Keyboard options: White or 24-zone RGB backlit",
        "MUX switch + Lenovo AI Engine+",
        "Cooling profile controls in Lenovo Vantage",
        "Warranty bundle: 3-year + ADP",
    ]
    legion_customization = [
        "Processor options: Core Ultra 9 / Core i9 / Core i7 / Ryzen 9",
        "GPU options: RTX 5070 / RTX 5070 Ti / RTX 5080 / RTX 5090",
        "Legacy GPU options: RTX 4060 / RTX 4070 / RTX 4080 / RTX 4090",
        "Memory options: 16GB / 32GB / 64GB DDR5",
        "Storage options: 1TB / 2TB / 4TB PCIe NVMe SSD",
        "Display options: QHD 165/240Hz and 4K 120Hz",
        "Cooling: Legion Coldfront Hyper + vapor chamber",
        "MUX + NVIDIA Advanced Optimus",
        "Wireless: Wi-Fi 7 + Bluetooth 5.4",
        "Keyboard: 4-zone or per-key RGB",
        "Warranty bundle: 3-year + ADP",
    ]

    loq_image_url = "https://p1-ofp.static.pub/medias/26612208349_LOQ15IAX9ELG_202407230229581738438439529.png?width=50&height=50"
    legion_image_url = "https://p1-ofp.static.pub/medias/26917906321_Legion_5_15AHP10_Luna_grey_BacklitOLEDHDcamera_202501030959471756811770543.png"

    loq_product_urls = [
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15iax9/83gs00lfin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/83dv00xhin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/len101q0005",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15iax9/len101q0006",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15arp9/83jc00gdin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15arp9/83jc00ehin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-essential-gen-9-15-intel/len101q0010",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irh8/len101q0001",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15arp9/83jc00efin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15aph8/len101q0004",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/83dv0127in",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-16irh8/len101q0002",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15arp9/len101q0009",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15iax9/83gscto1wwin1",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/83dvcto1wwin1",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-essential-gen-9-15-intel/83lk0032in",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15arp9/83jc00egin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-essential-gen-9-15-intel/83lk009vin",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-15irx9/83dv00x6in",
        "https://www.lenovo.com/in/en/p/laptops/loq-laptops/lenovo-loq-iax9i-gen-9-15-inch-intel/len101q0007",
    ]
    legion_product_urls = [
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/lenovo-legion-5i-gen-9-16-inch-intel/len101g0035",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-9-series/legion-9i-16-inch-intel/len101g0031",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/lenovo-legion-slim-5-gen-9-16-inch-amd/len101g0036",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/legion-pro-5i-gen-9-16-inch-intel/len101g0033",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-7-series/legion-7i-gen-9-16-inch-intel/len101g0037",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-pro-series/legion-pro-7i-gen-10-16-inch-intel/len101g0039",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-pro-series/legion-pro-7i-gen-10-16-inch-intel/83f5cto1wwin1",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-7-series/legion-pro-7i-gen-8-16-inch-intel/len101g0023",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/legion-5i-gen-9-15-inch-intel/len101g0038",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/legion-slim-5i-gen-8-(16-inch-intel)/len101g0027",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/legion-pro-5-gen-8-16-inch-amd/len101g0025",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-5-series/legion-slim-5-gen-8-16-inch-amd/len101g0030",
    ]
    legion_fifty_series_urls = [
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-pro-series/legion-pro-7i-gen-10-16-inch-intel/len101g0039",
        "https://www.lenovo.com/in/en/p/laptops/legion-laptops/legion-pro-series/legion-pro-7i-gen-10-16-inch-intel/83f5cto1wwin1",
    ]
    legion_legacy_urls = [url for url in legion_product_urls if url not in legion_fifty_series_urls]

    loq_model_pool = ["LOQ 15IRX9", "LOQ 15APH9", "LOQ 16IRH8", "LOQ 16APH8"]
    loq_cpu_pool = ["Intel Core i5-13450HX", "Intel Core i7-13650HX", "Intel Core i7-14700HX"]
    loq_gpu_pool = ["RTX 3050", "RTX 4050", "RTX 4060"]
    loq_ram_pool = [16, 24, 32]
    loq_storage_pool = [512, 1024, 2048]

    legion_model_pool = ["Legion 5i Gen 9", "Legion Pro 5i Gen 9", "Legion Pro 7i Gen 10", "Legion 7i Gen 9", "Legion Slim 5 Gen 9", "Legion 9i"]
    legion_cpu_pool = ["Intel Core Ultra 9 275HX", "Intel Core i9-14900HX", "Intel Core i7-14700HX", "AMD Ryzen 9 8945HX"]
    legion_fifty_gpu_pool = ["RTX 5070", "RTX 5070 Ti", "RTX 5080", "RTX 5090"]
    legion_legacy_gpu_pool = ["RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090"]
    legion_ram_pool = [16, 32, 64]
    legion_storage_pool = [1024, 2048, 4096]

    products = []

    for index in range(1, 19):
        gpu_model = loq_gpu_pool[(index - 1) % len(loq_gpu_pool)]
        refresh_hz = 165 if index % 3 == 0 else 144
        resolution = "QHD" if refresh_hz == 165 else "FHD"
        screen_size = 16.0 if index % 4 == 0 else 15.6
        battery_capacity_wh = 80 if screen_size >= 16 else 60
        ram_gb = loq_ram_pool[(index - 1) % len(loq_ram_pool)]
        storage_gb = loq_storage_pool[(index - 1) % len(loq_storage_pool)]
        cpu_model = loq_cpu_pool[(index - 1) % len(loq_cpu_pool)]
        use_cases = ["gaming", "student"]
        if gpu_model in {"RTX 4050", "RTX 4060"} and ram_gb >= 24:
            use_cases.append("creator")

        product_url = loq_product_urls[(index - 1) % len(loq_product_urls)]
        configurator_url = _lenovo_configurator_url(product_url)
        price_bonus = {"RTX 3050": 0, "RTX 4050": 12000, "RTX 4060": 22000}[gpu_model]

        products.append(
            {
                "brand": "Lenovo",
                "series": "LOQ",
                "model": f"{loq_model_pool[(index - 1) % len(loq_model_pool)]} (CTO {index:02d})",
                "sku": f"LEN-LOQ-CTO-{index:02d}",
                "price_inr": 77990 + (index * 2800) + price_bonus,
                "product_url": product_url,
                "configurator_url": configurator_url,
                "image_url": loq_image_url,
                "cpu_model": cpu_model,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "gpu_model": gpu_model,
                "screen_size": screen_size,
                "resolution": resolution,
                "refresh_hz": refresh_hz,
                "panel": "IPS",
                "weight_kg": 2.35 if screen_size >= 16 else 2.28,
                "battery_hours": 6.5 if battery_capacity_wh >= 80 else 5.4,
                "battery_capacity_wh": battery_capacity_wh,
                "battery_type": f"4-cell, {battery_capacity_wh} Wh Li-ion",
                "rating": round(4.1 + ((index % 6) * 0.08), 1),
                "use_cases": use_cases,
                "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
                "srgb_100": gpu_model != "RTX 3050",
                "dci_p3": gpu_model == "RTX 4060",
                "good_cooling": True,
                "ram_upgradable": True,
                "extra_ssd_slot": True,
                "backlit_keyboard": True,
                "customization_options": loq_customization,
                "configuration": _build_lenovo_configuration_block(
                    "LOQ",
                    cpu_model,
                    ram_gb,
                    storage_gb,
                    gpu_model,
                    screen_size,
                    resolution,
                    refresh_hz,
                    battery_capacity_wh,
                ),
            }
        )

    for index in range(1, 33):
        if index <= 24:
            gpu_model = legion_fifty_gpu_pool[(index - 1) % len(legion_fifty_gpu_pool)]
            product_url = legion_fifty_series_urls[0]
            if gpu_model == "RTX 5070 Ti" and index % 2 == 0:
                product_url = legion_fifty_series_urls[1]
        else:
            product_url = legion_legacy_urls[(index - 25) % len(legion_legacy_urls)]
            gpu_model = legion_legacy_gpu_pool[(index - 25) % len(legion_legacy_gpu_pool)]

        if gpu_model in {"RTX 5080", "RTX 5090"}:
            resolution = "4K"
            refresh_hz = 120
            panel = "OLED"
        elif gpu_model in {"RTX 5070 Ti", "RTX 4080", "RTX 4090"}:
            resolution = "QHD"
            refresh_hz = 240
            panel = "IPS"
        else:
            resolution = "QHD"
            refresh_hz = 165
            panel = "IPS"

        screen_size = 16.0 if index % 5 else 14.5
        battery_capacity_wh = 99 if screen_size >= 16 else 80
        ram_gb = legion_ram_pool[(index - 1) % len(legion_ram_pool)]
        storage_gb = legion_storage_pool[(index - 1) % len(legion_storage_pool)]
        cpu_model = legion_cpu_pool[(index - 1) % len(legion_cpu_pool)]
        gpu_price_bonus = {
            "RTX 4060": 0,
            "RTX 4070": 18000,
            "RTX 4080": 42000,
            "RTX 4090": 68000,
            "RTX 5070": 32000,
            "RTX 5070 Ti": 50000,
            "RTX 5080": 89000,
            "RTX 5090": 135000,
        }
        price_inr = 149990 + (index * 4200) + gpu_price_bonus.get(gpu_model, 0)
        use_cases = ["gaming", "creator"]
        if screen_size < 15 and gpu_model in {"RTX 4060", "RTX 4070"}:
            use_cases.append("student")

        configurator_url = _lenovo_configurator_url(product_url)

        products.append(
            {
                "brand": "Lenovo",
                "series": "Legion",
                "model": f"{legion_model_pool[(index - 1) % len(legion_model_pool)]} (CTO {index:02d})",
                "sku": f"LEN-LEGION-CTO-{index:02d}",
                "price_inr": price_inr,
                "product_url": product_url,
                "configurator_url": configurator_url,
                "image_url": legion_image_url,
                "cpu_model": cpu_model,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "gpu_model": gpu_model,
                "screen_size": screen_size,
                "resolution": resolution,
                "refresh_hz": refresh_hz,
                "panel": panel,
                "weight_kg": 2.55 if screen_size >= 16 else 2.05,
                "battery_hours": 6.8 if battery_capacity_wh == 99 else 6.1,
                "battery_capacity_wh": battery_capacity_wh,
                "battery_type": f"4-cell, {battery_capacity_wh} Wh Li-ion",
                "rating": round(4.2 + ((index % 7) * 0.08), 1),
                "use_cases": use_cases,
                "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
                "srgb_100": True,
                "dci_p3": gpu_model in {"RTX 4070", "RTX 4080", "RTX 4090", "RTX 5070", "RTX 5070 Ti", "RTX 5080", "RTX 5090"} or resolution == "4K",
                "good_cooling": True,
                "ram_upgradable": True,
                "extra_ssd_slot": True,
                "backlit_keyboard": True,
                "customization_options": legion_customization,
                "configuration": _build_lenovo_configuration_block(
                    "Legion",
                    cpu_model,
                    ram_gb,
                    storage_gb,
                    gpu_model,
                    screen_size,
                    resolution,
                    refresh_hz,
                    battery_capacity_wh,
                ),
            }
        )

    return _apply_lenovo_official_customization(products)


def _build_msi_catalog_variants():
    series_profiles = {
        "Titan": {
            "model_pool": ["Titan 18 HX AI A2X", "Titan 16 HX A2X"],
            "product_url": "https://in.msi.com/Laptop/Titan-18-HX-AI-A2XWX",
            "image_url": "https://storage-asset.msi.com/global/picture/product/product_1737602995c95879e6463325254f810682a141b82d.webp",
            "cpu_pool": ["Intel Core Ultra 9 285HX", "Intel Core i9-14900HX"],
            "gpu_pool": ["RTX 4080", "RTX 5070 Ti"],
            "ram_pool": [32, 64],
            "storage_pool": [2048, 4096],
            "screen_pool": [(18.0, "4K", 120, "IPS"), (18.0, "QHD", 240, "IPS")],
            "weight_kg": 3.55,
            "battery_wh": 99,
            "base_price": 399990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "SD Card", "Headphone jack"],
            "use_cases": ["gaming", "creator"],
            "customization_options": [
                "CPU options: Intel Core i9 / Core Ultra 9 HX",
                "GPU options: RTX 4080 / RTX 5070 Ti",
                "Memory options: 32GB / 64GB DDR5",
                "Storage options: 2TB / 4TB PCIe NVMe SSD",
                "Display options: 18-inch QHD 240Hz or 4K 120Hz",
                "Keyboard options: per-key RGB mechanical-style keyboard",
            ],
        },
        "Raider": {
            "model_pool": ["Raider 18 HX A14V", "Raider 16 HX A14V"],
            "product_url": "https://in.msi.com/Laptop/Raider-18-HX-A14VX",
            "image_url": "https://storage-asset.msi.com/global/picture/product/product_1737450989d93663953d259792385783ca033d4f84.webp",
            "cpu_pool": ["Intel Core i9-14900HX", "Intel Core Ultra 9 185H"],
            "gpu_pool": ["RTX 4070", "RTX 4080", "RTX 5070"],
            "ram_pool": [32, 64],
            "storage_pool": [1024, 2048],
            "screen_pool": [(18.0, "QHD", 240, "IPS"), (16.0, "QHD", 240, "IPS")],
            "weight_kg": 3.05,
            "battery_wh": 99,
            "base_price": 299990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "creator"],
            "customization_options": [
                "CPU options: Intel Core i9 HX / Core Ultra 9",
                "GPU options: RTX 4070 / RTX 4080 / RTX 5070",
                "Memory options: 32GB / 64GB DDR5",
                "Storage options: 1TB / 2TB PCIe NVMe SSD",
                "Display options: 16-inch or 18-inch QHD 240Hz panels",
                "Keyboard options: per-key RGB SteelSeries keyboard",
            ],
        },
        "Stealth": {
            "model_pool": ["Stealth 16 AI Studio A1V", "Stealth 14 AI Studio A1V"],
            "product_url": "https://in.msi.com/Laptop/Stealth-16-AI-Studio-A1VX",
            "image_url": "https://storage-asset.msi.com/global/picture/product/product_17676813904414512bef83fa782f8b3c98eda1f516.webp",
            "cpu_pool": ["Intel Core Ultra 7 155H", "Intel Core Ultra 9 185H"],
            "gpu_pool": ["RTX 4060", "RTX 4070"],
            "ram_pool": [16, 32],
            "storage_pool": [1024, 2048],
            "screen_pool": [(16.0, "QHD", 240, "OLED"), (14.0, "QHD", 120, "OLED")],
            "weight_kg": 1.95,
            "battery_wh": 99,
            "base_price": 189990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
            "use_cases": ["gaming", "creator", "student"],
            "customization_options": [
                "CPU options: Intel Core Ultra 7 / Ultra 9",
                "GPU options: RTX 4060 / RTX 4070",
                "Memory options: 16GB / 32GB LPDDR5X",
                "Storage options: 1TB / 2TB PCIe NVMe SSD",
                "Display options: QHD OLED panels at 120Hz/240Hz",
                "Finish options: Studio-focused portable chassis",
            ],
        },
        "Crosshair": {
            "model_pool": ["Crosshair 16 HX D14V", "Crosshair 15 C13V"],
            "product_url": "https://in.msi.com/Laptop/Crosshair-16-HX-D14VX",
            "image_url": "https://storage-asset.msi.com/global/picture/product/product_174539985060e5b042c3d5e24570cacbcca0c66049.webp",
            "cpu_pool": ["Intel Core i7-14700HX", "Intel Core i7-13620H"],
            "gpu_pool": ["RTX 4050", "RTX 4060", "RTX 4070"],
            "ram_pool": [16, 32],
            "storage_pool": [512, 1024],
            "screen_pool": [(16.0, "QHD", 165, "IPS"), (15.6, "FHD", 144, "IPS")],
            "weight_kg": 2.45,
            "battery_wh": 90,
            "base_price": 139990,
            "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "student"],
            "customization_options": [
                "CPU options: Intel Core i7 H/HX family",
                "GPU options: RTX 4050 / RTX 4060 / RTX 4070",
                "Memory options: 16GB / 32GB DDR5",
                "Storage options: 512GB / 1TB PCIe NVMe SSD",
                "Display options: FHD 144Hz or QHD 165Hz",
                "Keyboard options: 4-zone RGB gaming keyboard",
            ],
        },
    }

    products = []
    for series, profile in series_profiles.items():
        for index in range(1, 7):
            cpu_model = profile["cpu_pool"][(index - 1) % len(profile["cpu_pool"])]
            gpu_model = profile["gpu_pool"][(index - 1) % len(profile["gpu_pool"])]
            ram_gb = profile["ram_pool"][(index - 1) % len(profile["ram_pool"])]
            storage_gb = profile["storage_pool"][(index - 1) % len(profile["storage_pool"])]
            screen_size, resolution, refresh_hz, panel = profile["screen_pool"][(index - 1) % len(profile["screen_pool"])]
            battery_wh = profile["battery_wh"]
            price_inr = profile["base_price"] + (index * 5200) + (9000 if gpu_model == "RTX 4070" else 0)

            products.append(
                {
                    "brand": "MSI",
                    "series": series,
                    "model": f"{profile['model_pool'][(index - 1) % len(profile['model_pool'])]} (Config {index:02d})",
                    "sku": f"MSI-{series.upper()}-CFG-{index:02d}",
                    "price_inr": price_inr,
                    "product_url": profile["product_url"],
                    "configurator_url": profile["product_url"],
                    "image_url": profile["image_url"],
                    "cpu_model": cpu_model,
                    "ram_gb": ram_gb,
                    "storage_gb": storage_gb,
                    "gpu_model": gpu_model,
                    "screen_size": screen_size,
                    "resolution": resolution,
                    "refresh_hz": refresh_hz,
                    "panel": panel,
                    "weight_kg": profile["weight_kg"],
                    "battery_hours": 6.3 if battery_wh >= 99 else 5.5,
                    "battery_capacity_wh": battery_wh,
                    "battery_type": f"4-cell, {battery_wh} Wh Li-polymer",
                    "rating": round(4.2 + ((index % 5) * 0.1), 1),
                    "use_cases": list(profile["use_cases"]),
                    "ports": list(profile["ports"]),
                    "srgb_100": series != "Crosshair",
                    "dci_p3": series in {"Titan", "Raider", "Stealth"},
                    "good_cooling": True,
                    "ram_upgradable": True,
                    "extra_ssd_slot": True,
                    "backlit_keyboard": True,
                    "customization_options": list(profile["customization_options"]),
                }
            )

    return products


def _build_acer_catalog_variants():
    series_profiles = {
        "Predator": {
            "model_pool": ["Predator Helios Neo 16", "Predator Helios 16"],
            "product_url": "https://store.acer.com/en-in/laptops/gaming-laptops/predator",
            "image_url": "https://static-ecpa.acer.com/media/catalog/product/p/r/predator-helios-neo-16-phn16-72-4zone-backlit-on-wallpaper-black-01-1000x1000_nh.qqyaa.002.png?bg-color=255%2C255%2C255&canvas=500%3A500&fit=bounds&format=jpeg&height=500&optimize=high&width=500",
            "cpu_pool": ["Intel Core i7-14700HX", "Intel Core i9-14900HX"],
            "gpu_pool": ["RTX 4060", "RTX 4070", "RTX 4080"],
            "ram_pool": [16, 32],
            "storage_pool": [1024, 2048],
            "screen_pool": [(16.0, "QHD", 165, "IPS"), (16.0, "QHD", 240, "IPS")],
            "weight_kg": 2.65,
            "battery_wh": 90,
            "base_price": 154990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "creator"],
            "customization_options": [
                "CPU options: Intel Core i7 / i9 HX",
                "GPU options: RTX 4060 / RTX 4070 / RTX 4080",
                "Memory options: 16GB / 32GB DDR5",
                "Storage options: 1TB / 2TB PCIe NVMe SSD",
                "Display options: QHD 165Hz or QHD 240Hz IPS",
                "Keyboard options: 4-zone RGB keyboard",
            ],
        },
        "Nitro": {
            "model_pool": ["Nitro V 15", "Nitro 16"],
            "product_url": "https://store.acer.com/en-in/laptops/gaming-laptops/nitro",
            "image_url": "https://static-ecpa.acer.com/media/catalog/product/a/c/acer-nitro-16-an16-41-4-zone-backlit-wallpaper-black-01-1000x1000_nh.qlkaa.002.png?bg-color=255%2C255%2C255&canvas=500%3A500&fit=bounds&format=jpeg&height=500&optimize=high&width=500",
            "cpu_pool": ["Intel Core i5-13420H", "Intel Core i7-13620H", "AMD Ryzen 7 8845HS"],
            "gpu_pool": ["RTX 4050", "RTX 4060", "RTX 3050"],
            "ram_pool": [16, 32],
            "storage_pool": [512, 1024],
            "screen_pool": [(15.6, "FHD", 144, "IPS"), (16.0, "QHD", 165, "IPS")],
            "weight_kg": 2.35,
            "battery_wh": 57,
            "base_price": 94990,
            "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "student"],
            "customization_options": [
                "CPU options: Intel Core i5 / i7 or AMD Ryzen 7",
                "GPU options: RTX 3050 / RTX 4050 / RTX 4060",
                "Memory options: 16GB / 32GB DDR5",
                "Storage options: 512GB / 1TB PCIe NVMe SSD",
                "Display options: FHD 144Hz or QHD 165Hz",
                "Keyboard options: single-zone or 4-zone backlit keyboard",
            ],
        },
    }

    products = []
    for series, profile in series_profiles.items():
        for index in range(1, 14):
            cpu_model = profile["cpu_pool"][(index - 1) % len(profile["cpu_pool"])]
            gpu_model = profile["gpu_pool"][(index - 1) % len(profile["gpu_pool"])]
            ram_gb = profile["ram_pool"][(index - 1) % len(profile["ram_pool"])]
            storage_gb = profile["storage_pool"][(index - 1) % len(profile["storage_pool"])]
            screen_size, resolution, refresh_hz, panel = profile["screen_pool"][(index - 1) % len(profile["screen_pool"])]
            battery_wh = profile["battery_wh"]
            price_inr = profile["base_price"] + (index * 3400) + (8500 if gpu_model == "RTX 4060" else 0)

            use_cases = list(profile["use_cases"])
            if series == "Nitro" and gpu_model == "RTX 4060":
                use_cases = ["gaming", "student", "creator"]

            products.append(
                {
                    "brand": "Acer",
                    "series": series,
                    "model": f"{profile['model_pool'][(index - 1) % len(profile['model_pool'])]} (Config {index:02d})",
                    "sku": f"ACE-{series.upper()}-CFG-{index:02d}",
                    "price_inr": price_inr,
                    "product_url": profile["product_url"],
                    "configurator_url": profile["product_url"],
                    "image_url": profile["image_url"],
                    "cpu_model": cpu_model,
                    "ram_gb": ram_gb,
                    "storage_gb": storage_gb,
                    "gpu_model": gpu_model,
                    "screen_size": screen_size,
                    "resolution": resolution,
                    "refresh_hz": refresh_hz,
                    "panel": panel,
                    "weight_kg": profile["weight_kg"],
                    "battery_hours": 5.8 if battery_wh >= 90 else 5.1,
                    "battery_capacity_wh": battery_wh,
                    "battery_type": f"4-cell, {battery_wh} Wh Li-ion",
                    "rating": round(4.1 + ((index % 6) * 0.1), 1),
                    "use_cases": use_cases,
                    "ports": list(profile["ports"]),
                    "srgb_100": series == "Predator" or gpu_model == "RTX 4060",
                    "dci_p3": series == "Predator",
                    "good_cooling": True,
                    "ram_upgradable": True,
                    "extra_ssd_slot": True,
                    "backlit_keyboard": True,
                    "customization_options": list(profile["customization_options"]),
                }
            )

    return products


def _build_asus_catalog_variants():
    series_profiles = {
        "ROG Strix": {
            "model_pool": ["ROG Strix G16", "ROG Strix Scar 16", "ROG Strix G18"],
            "product_url": "https://www.asus.com/in/laptops/for-gaming/rog/rog-strix-series/",
            "image_url": "https://dlcdnwebimgs.asus.com/gain/86C6E72D-09BC-4B86-A761-CF6FD696363B/w185/fwebp",
            "cpu_pool": ["Intel Core i7-14650HX", "Intel Core i9-14900HX", "Intel Core Ultra 9 275HX"],
            "gpu_pool": ["RTX 4060", "RTX 4070", "RTX 4080"],
            "ram_pool": [16, 32, 64],
            "storage_pool": [1024, 2048],
            "screen_pool": [(16.0, "QHD", 240, "IPS"), (18.0, "QHD", 240, "IPS")],
            "weight_kg": 2.65,
            "count": 14,
            "battery_wh": 90,
            "base_price": 189990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "creator"],
            "customization_options": [
                "CPU options: Intel Core i7 / Core i9 / Core Ultra 9",
                "GPU options: RTX 4060 / RTX 4070 / RTX 4080",
                "Memory options: 16GB / 32GB / 64GB DDR5",
                "Storage options: 1TB / 2TB PCIe NVMe SSD",
                "Display options: 16-inch or 18-inch QHD 240Hz panels",
                "Keyboard options: RGB or per-key Aura Sync keyboard",
            ],
        },
        "ROG Zephyrus": {
            "model_pool": ["ROG Zephyrus G14", "ROG Zephyrus G16"],
            "product_url": "https://www.asus.com/in/laptops/for-gaming/rog/rog-zephyrus-series/",
            "image_url": "https://dlcdnwebimgs.asus.com/gain/101AB8DB-FB2C-4EDD-A62F-86571B7FD236/w185/fwebp",
            "cpu_pool": ["Intel Core Ultra 7 155H", "Intel Core Ultra 9 185H", "AMD Ryzen AI 9 HX 370"],
            "gpu_pool": ["RTX 4060", "RTX 4070", "RTX 4080"],
            "ram_pool": [16, 32],
            "storage_pool": [1024, 2048],
            "screen_pool": [(14.0, "QHD", 120, "OLED"), (16.0, "QHD", 240, "OLED")],
            "weight_kg": 1.85,
            "count": 12,
            "battery_wh": 90,
            "base_price": 194990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
            "use_cases": ["gaming", "creator", "student"],
            "customization_options": [
                "CPU options: Intel Core Ultra 7 / Ultra 9 or AMD Ryzen AI 9",
                "GPU options: RTX 4060 / RTX 4070 / RTX 4080",
                "Memory options: 16GB / 32GB LPDDR5X",
                "Storage options: 1TB / 2TB PCIe NVMe SSD",
                "Display options: 14-inch QHD 120Hz OLED or 16-inch QHD 240Hz OLED",
                "Finish options: Eclipse Gray / Platinum White (varies by SKU)",
            ],
        },
        "ROG Flow": {
            "model_pool": ["ROG Flow X13", "ROG Flow X16", "ROG Flow Z13"],
            "product_url": "https://www.asus.com/in/laptops/for-gaming/rog/rog-flow-series/",
            "image_url": "https://dlcdnwebimgs.asus.com/gain/34C1E26D-F64A-4B4F-8DAC-6C168F7C90E2/w185/fwebp",
            "cpu_pool": ["AMD Ryzen 9 7940HS", "Intel Core i9-13900H", "Intel Core Ultra 7 155H"],
            "gpu_pool": ["RTX 4050", "RTX 4060", "RTX 4070"],
            "ram_pool": [16, 32],
            "storage_pool": [512, 1024],
            "screen_pool": [(13.4, "QHD", 165, "IPS"), (16.0, "QHD", 240, "IPS"), (13.4, "QHD", 120, "IPS")],
            "weight_kg": 1.85,
            "count": 6,
            "battery_wh": 75,
            "base_price": 169990,
            "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
            "use_cases": ["gaming", "creator", "student"],
            "customization_options": [
                "CPU options: AMD Ryzen 9 / Intel Core i9 / Core Ultra 7",
                "GPU options: RTX 4050 / RTX 4060 / RTX 4070",
                "Memory options: 16GB / 32GB LPDDR5X",
                "Storage options: 512GB / 1TB PCIe NVMe SSD",
                "Display options: 13-inch or 16-inch high-refresh touch/non-touch panels",
                "2-in-1 options: detachable keyboard and tablet use (selected Flow models)",
            ],
        },
        "TUF Gaming": {
            "model_pool": ["TUF Gaming A15", "TUF Gaming F15", "TUF Gaming A16"],
            "product_url": "https://www.asus.com/in/laptops/for-gaming/tuf-gaming/",
            "image_url": "https://www.asus.com/media/Odin/Websites/in/ProductLine/20210920052417.png",
            "cpu_pool": ["AMD Ryzen 7 8845HS", "Intel Core i7-13620H", "AMD Ryzen 9 8940H"],
            "gpu_pool": ["RTX 4050", "RTX 4060", "RTX 3050"],
            "ram_pool": [16, 32],
            "storage_pool": [512, 1024],
            "screen_pool": [(15.6, "FHD", 144, "IPS"), (16.0, "QHD", 165, "IPS")],
            "weight_kg": 2.25,
            "battery_wh": 90,
            "base_price": 109990,
            "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
            "use_cases": ["gaming", "student"],
            "customization_options": [
                "CPU options: AMD Ryzen 7/9 or Intel Core i7",
                "GPU options: RTX 3050 / RTX 4050 / RTX 4060",
                "Memory options: 16GB / 32GB DDR5",
                "Storage options: 512GB / 1TB PCIe NVMe SSD",
                "Display options: FHD 144Hz or QHD 165Hz",
                "Keyboard options: single-zone or RGB backlit keyboard",
            ],
        },
    }

    products = []
    rog_series_order = ["ROG Strix", "ROG Zephyrus", "ROG Flow"]
    rog_sku_index = 1

    for series in rog_series_order:
        profile = series_profiles[series]
        for index in range(1, profile["count"] + 1):
            cpu_model = profile["cpu_pool"][(index - 1) % len(profile["cpu_pool"])]
            gpu_model = profile["gpu_pool"][(index - 1) % len(profile["gpu_pool"])]
            ram_gb = profile["ram_pool"][(index - 1) % len(profile["ram_pool"])]
            storage_gb = profile["storage_pool"][(index - 1) % len(profile["storage_pool"])]
            screen_size, resolution, refresh_hz, panel = profile["screen_pool"][(index - 1) % len(profile["screen_pool"])]
            battery_wh = profile["battery_wh"]

            price_inr = profile["base_price"] + (index * 3900) + (15000 if gpu_model == "RTX 4080" else 0)
            if series == "ROG Flow":
                price_inr = profile["base_price"] + (index * 3600) + (9000 if gpu_model == "RTX 4070" else 0)

            use_cases = list(profile["use_cases"])
            if series == "ROG Flow" and gpu_model == "RTX 4050":
                use_cases = ["gaming", "student"]

            if series == "ROG Strix":
                weight_kg = profile["weight_kg"] + (0.20 if screen_size >= 18 else 0.0)
                battery_hours = 6.3
            elif series == "ROG Zephyrus":
                weight_kg = 1.95 if screen_size >= 16 else profile["weight_kg"]
                battery_hours = 7.8
            else:
                weight_kg = profile["weight_kg"] + (0.25 if screen_size >= 16 else 0.0)
                battery_hours = 6.7

            products.append(
                {
                    "brand": "ASUS",
                    "series": series,
                    "model": f"{profile['model_pool'][(index - 1) % len(profile['model_pool'])]} (Config {rog_sku_index:02d})",
                    "sku": f"ASU-ROG-CFG-{rog_sku_index:02d}",
                    "price_inr": price_inr,
                    "product_url": profile["product_url"],
                    "configurator_url": profile["product_url"],
                    "image_url": profile["image_url"],
                    "cpu_model": cpu_model,
                    "ram_gb": ram_gb,
                    "storage_gb": storage_gb,
                    "gpu_model": gpu_model,
                    "screen_size": screen_size,
                    "resolution": resolution,
                    "refresh_hz": refresh_hz,
                    "panel": panel,
                    "weight_kg": weight_kg,
                    "battery_hours": battery_hours,
                    "battery_capacity_wh": battery_wh,
                    "battery_type": f"4-cell, {battery_wh} Wh Li-ion",
                    "rating": round(4.2 + ((rog_sku_index % 6) * 0.09), 1),
                    "use_cases": use_cases,
                    "ports": list(profile["ports"]),
                    "srgb_100": True,
                    "dci_p3": panel == "OLED" or gpu_model in {"RTX 4070", "RTX 4080"},
                    "good_cooling": True,
                    "ram_upgradable": True,
                    "extra_ssd_slot": True,
                    "backlit_keyboard": True,
                    "customization_options": list(profile["customization_options"]),
                }
            )
            rog_sku_index += 1

    for index in range(1, 14):
        profile = series_profiles["TUF Gaming"]
        cpu_model = profile["cpu_pool"][(index - 1) % len(profile["cpu_pool"])]
        gpu_model = profile["gpu_pool"][(index - 1) % len(profile["gpu_pool"])]
        ram_gb = profile["ram_pool"][(index - 1) % len(profile["ram_pool"])]
        storage_gb = profile["storage_pool"][(index - 1) % len(profile["storage_pool"])]
        screen_size, resolution, refresh_hz, panel = profile["screen_pool"][(index - 1) % len(profile["screen_pool"])]
        battery_wh = profile["battery_wh"]
        price_inr = profile["base_price"] + (index * 2900) + (7000 if gpu_model == "RTX 4060" else 0)
        use_cases = ["gaming", "student"]
        if gpu_model == "RTX 4060":
            use_cases.append("creator")

        products.append(
            {
                "brand": "ASUS",
                "series": "TUF Gaming",
                "model": f"{profile['model_pool'][(index - 1) % len(profile['model_pool'])]} (Config {index:02d})",
                "sku": f"ASU-TUF-CFG-{index:02d}",
                "price_inr": price_inr,
                "product_url": profile["product_url"],
                "configurator_url": profile["product_url"],
                "image_url": profile["image_url"],
                "cpu_model": cpu_model,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "gpu_model": gpu_model,
                "screen_size": screen_size,
                "resolution": resolution,
                "refresh_hz": refresh_hz,
                "panel": panel,
                "weight_kg": profile["weight_kg"],
                "battery_hours": 6.9,
                "battery_capacity_wh": battery_wh,
                "battery_type": f"4-cell, {battery_wh} Wh Li-ion",
                "rating": round(4.1 + ((index % 5) * 0.1), 1),
                "use_cases": use_cases,
                "ports": list(profile["ports"]),
                "srgb_100": gpu_model != "RTX 3050",
                "dci_p3": False,
                "good_cooling": True,
                "ram_upgradable": True,
                "extra_ssd_slot": True,
                "backlit_keyboard": True,
                "customization_options": list(profile["customization_options"]),
            }
        )

    return products


def _build_dell_configuration_block(series, cpu_model, ram_gb, storage_gb, gpu_model, screen_size, resolution, refresh_hz, panel, battery_capacity_wh):
    is_alienware = series == "Alienware"

    if is_alienware:
        processor_options = _mark_included(
            [
                {
                    "name": "Intel Core Ultra 9 185H",
                    "details": "Up to 5.10GHz boost clock",
                    "price_note": "+₹18,000",
                    "alt_price_note": "",
                    "match": "ultra 9 185h",
                },
                {
                    "name": "Intel Core i9-14900HX",
                    "details": "24-core gaming and creator class processor",
                    "price_note": "+₹12,000",
                    "alt_price_note": "",
                    "match": "i9-14900hx",
                },
                {
                    "name": "Intel Core i7-14700HX",
                    "details": "Balanced high-performance profile",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "i7-14700hx",
                },
            ],
            cpu_model,
        )
        graphics_options = _mark_included(
            [
                {
                    "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                    "details": "8GB GDDR6",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "rtx 4060",
                },
                {
                    "name": "NVIDIA GeForce RTX 4070 Laptop GPU",
                    "details": "8GB GDDR6",
                    "price_note": "+₹22,000",
                    "alt_price_note": "",
                    "match": "rtx 4070",
                },
                {
                    "name": "NVIDIA GeForce RTX 4080 Laptop GPU",
                    "details": "12GB GDDR6",
                    "price_note": "+₹52,000",
                    "alt_price_note": "",
                    "match": "rtx 4080",
                },
            ],
            gpu_model,
        )
        memory_options = _mark_included(
            [
                {
                    "name": "16GB DDR5",
                    "details": "Dual-channel",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "16",
                },
                {
                    "name": "32GB DDR5",
                    "details": "Dual-channel",
                    "price_note": "+₹16,500",
                    "alt_price_note": "",
                    "match": "32",
                },
                {
                    "name": "64GB DDR5",
                    "details": "Dual-channel",
                    "price_note": "+₹36,000",
                    "alt_price_note": "",
                    "match": "64",
                },
            ],
            str(64 if ram_gb >= 64 else 32 if ram_gb >= 32 else 16),
        )
        storage_options = _mark_included(
            [
                {
                    "name": "1TB PCIe Gen4 NVMe SSD",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "1024",
                },
                {
                    "name": "2TB PCIe Gen4 NVMe SSD",
                    "details": "",
                    "price_note": "+₹17,500",
                    "alt_price_note": "",
                    "match": "2048",
                },
            ],
            str(2048 if storage_gb >= 2048 else 1024),
        )
        display_selection_token = f"{screen_size:.1f}-{resolution}-{refresh_hz}-{panel}".lower()
        display_options = _mark_included(
            [
                {
                    "name": "16.0-inch QHD 240Hz IPS, 300 nits",
                    "details": "Fast refresh gaming panel",
                    "price_note": "+₹8,000",
                    "alt_price_note": "",
                    "match": "16.0-qhd-240-ips",
                },
                {
                    "name": "18.0-inch QHD 165Hz IPS, 300 nits",
                    "details": "Larger display footprint",
                    "price_note": "+₹12,000",
                    "alt_price_note": "",
                    "match": "18.0-qhd-165-ips",
                },
                {
                    "name": "14.0-inch QHD 120Hz IPS, 300 nits",
                    "details": "Portable premium panel",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "14.0-qhd-120-ips",
                },
            ],
            display_selection_token,
        )
        keyboard_options = _mark_included(
            [
                {
                    "name": "Alienware 4-zone RGB keyboard",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "4-zone",
                },
                {
                    "name": "Alienware per-key RGB AlienFX keyboard",
                    "details": "",
                    "price_note": "+₹2,500",
                    "alt_price_note": "",
                    "match": "per-key",
                },
            ],
            "per-key" if gpu_model in {"RTX 4070", "RTX 4080"} or ram_gb >= 32 else "4-zone",
        )
        battery_options = _mark_included(
            [
                {
                    "name": "6-cell 90Wh Li-ion",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "90",
                },
                {
                    "name": "6-cell 99Wh Li-ion",
                    "details": "Subject to model and chassis support",
                    "price_note": "+₹4,500",
                    "alt_price_note": "",
                    "match": "99",
                },
            ],
            str(battery_capacity_wh),
        )
        power_adapter = "330W AC Adapter" if gpu_model == "RTX 4080" else "240W AC Adapter"
        cooling_text = "Alienware Cryo-Tech thermal solution"
        wireless_text = "Intel Killer Wi-Fi 7 + Bluetooth 5.4"
    else:
        processor_options = _mark_included(
            [
                {
                    "name": "Intel Core i5-13450HX",
                    "details": "10-core mainstream gaming option",
                    "price_note": "-₹7,000",
                    "alt_price_note": "",
                    "match": "i5-13450hx",
                },
                {
                    "name": "Intel Core i7-13650HX",
                    "details": "14-core performance option",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "i7-13650hx",
                },
                {
                    "name": "Intel Core i9-13900HX",
                    "details": "24-core upgrade option",
                    "price_note": "+₹16,000",
                    "alt_price_note": "",
                    "match": "i9-13900hx",
                },
            ],
            cpu_model,
        )
        graphics_options = _mark_included(
            [
                {
                    "name": "NVIDIA GeForce RTX 4050 Laptop GPU",
                    "details": "6GB GDDR6",
                    "price_note": "-₹8,000",
                    "alt_price_note": "",
                    "match": "rtx 4050",
                },
                {
                    "name": "NVIDIA GeForce RTX 4060 Laptop GPU",
                    "details": "8GB GDDR6",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "rtx 4060",
                },
            ],
            gpu_model,
        )
        memory_options = _mark_included(
            [
                {
                    "name": "16GB DDR5",
                    "details": "Dual-channel",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "16",
                },
                {
                    "name": "32GB DDR5",
                    "details": "Dual-channel",
                    "price_note": "+₹11,000",
                    "alt_price_note": "",
                    "match": "32",
                },
            ],
            str(32 if ram_gb >= 32 else 16),
        )
        storage_options = _mark_included(
            [
                {
                    "name": "512GB PCIe Gen4 NVMe SSD",
                    "details": "",
                    "price_note": "-₹5,000",
                    "alt_price_note": "",
                    "match": "512",
                },
                {
                    "name": "1TB PCIe Gen4 NVMe SSD",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "1024",
                },
                {
                    "name": "2TB PCIe Gen4 NVMe SSD",
                    "details": "",
                    "price_note": "+₹13,500",
                    "alt_price_note": "",
                    "match": "2048",
                },
            ],
            str(2048 if storage_gb >= 2048 else 1024 if storage_gb >= 1024 else 512),
        )
        display_selection_token = f"{screen_size:.1f}-{resolution}-{refresh_hz}-{panel}".lower()
        display_options = _mark_included(
            [
                {
                    "name": "15.6-inch FHD 120Hz IPS",
                    "details": "",
                    "price_note": "-₹4,000",
                    "alt_price_note": "",
                    "match": "15.6-fhd-120-ips",
                },
                {
                    "name": "15.6-inch FHD 165Hz IPS",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "15.6-fhd-165-ips",
                },
                {
                    "name": "15.6-inch QHD 240Hz IPS",
                    "details": "",
                    "price_note": "+₹9,000",
                    "alt_price_note": "",
                    "match": "15.6-qhd-240-ips",
                },
            ],
            display_selection_token,
        )
        keyboard_options = _mark_included(
            [
                {
                    "name": "Orange backlit keyboard",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "orange",
                },
                {
                    "name": "4-zone RGB backlit keyboard",
                    "details": "",
                    "price_note": "+₹1,200",
                    "alt_price_note": "",
                    "match": "4-zone",
                },
            ],
            "orange" if ram_gb <= 16 else "4-zone",
        )
        battery_options = _mark_included(
            [
                {
                    "name": "6-cell 56Wh Li-ion",
                    "details": "",
                    "price_note": "-₹3,000",
                    "alt_price_note": "",
                    "match": "56",
                },
                {
                    "name": "6-cell 86Wh Li-ion",
                    "details": "",
                    "price_note": "",
                    "alt_price_note": "",
                    "match": "86",
                },
            ],
            str(battery_capacity_wh),
        )
        power_adapter = "240W AC Adapter" if gpu_model == "RTX 4060" else "180W AC Adapter"
        cooling_text = "Dual-fan thermal design with Game Shift mode"
        wireless_text = "Wi-Fi 6E + Bluetooth 5.3"

    return {
        "title": "Dell Configuration",
        "collapse_hint": "Collapse All Categories",
        "warranty_note": "Configuration pricing shown is estimated for Dell India and may vary based on tax, offers, and stock at checkout.",
        "categories": [
            {"name": "Processor", "options": processor_options},
            {
                "name": "Operating System",
                "options": [
                    {"name": "Windows 11 Home Single Language", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                    {"name": "Windows 11 Pro", "details": "", "price_note": "+₹7,500", "alt_price_note": "", "included": False},
                ],
            },
            {
                "name": "Microsoft Productivity Software",
                "options": [
                    {"name": "Microsoft Office Trial", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                    {"name": "Microsoft Office Home and Student 2024", "details": "", "price_note": "+₹8,999", "alt_price_note": "", "included": False},
                ],
            },
            {"name": "Graphics Card", "options": graphics_options},
            {"name": "Memory", "options": memory_options},
            {"name": "Solid State Drive", "options": storage_options},
            {"name": "Display", "options": display_options},
            {
                "name": "Thermals",
                "options": [
                    {"name": cooling_text, "details": "Performance profile controls available in Dell utility software", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {"name": "Keyboard", "options": keyboard_options},
            {
                "name": "Wireless",
                "options": [
                    {"name": wireless_text, "details": "", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {"name": "Battery", "options": battery_options},
            {
                "name": "Power Adapter",
                "options": [
                    {"name": power_adapter, "details": "India compatible", "price_note": "", "alt_price_note": "", "included": True},
                ],
            },
            {
                "name": "Support Services",
                "options": [
                    {"name": "1 Year Base Warranty", "details": "", "price_note": "", "alt_price_note": "", "included": True},
                    {"name": "Premium Support Plus (2 Years)", "details": "Includes accidental damage support", "price_note": "+₹4,999", "alt_price_note": "", "included": False},
                ],
            },
        ],
    }


def _build_dell_catalog_variants():
    alienware_profile = {
        "model_pool": ["Alienware m16 R2", "Alienware x16 R2", "Alienware m18 R2", "Alienware x14 R2"],
        "product_url": "https://www.dell.com/en-in/shop/gaming-and-games/scr/gaming",
        "image_url": "https://i.dell.com/is/image/DellContent/content/dam/ss2/product-images/dell-client-products/notebooks/alienware-notebooks/alienware-m16-r2-intel/media-gallery/laptop-aw-m16r2-nt-bk-gallery-3.psd?chrss=full&fmt=png-alpha&hei=402&pscan=auto&qlt=100%2C1&resMode=sharp2&scl=1&size=510%2C402&wid=510",
        "cpu_pool": ["Intel Core Ultra 9 185H", "Intel Core i9-14900HX", "Intel Core i7-14700HX"],
        "gpu_pool": ["RTX 4070", "RTX 4080", "RTX 4060"],
        "ram_pool": [16, 32, 64],
        "storage_pool": [1024, 2048],
        "screen_pool": [(16.0, "QHD", 240, "IPS"), (18.0, "QHD", 165, "IPS"), (14.0, "QHD", 120, "IPS")],
        "base_price": 219990,
        "battery_wh": 90,
        "ports": ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"],
        "use_cases": ["gaming", "creator"],
        "customization_options": [
            "CPU options: Intel Core Ultra 9 / Core i7 / Core i9 HX",
            "GPU options: RTX 4060 / RTX 4070 / RTX 4080",
            "Memory options: 16GB / 32GB / 64GB",
            "Storage options: 1TB / 2TB PCIe NVMe SSD",
            "Display options: QHD 120Hz / 165Hz / 240Hz",
            "Keyboard options: per-key RGB AlienFX keyboard",
        ],
    }

    products = []
    for index in range(1, 5):
        cpu_model = alienware_profile["cpu_pool"][(index - 1) % len(alienware_profile["cpu_pool"])]
        gpu_model = alienware_profile["gpu_pool"][(index - 1) % len(alienware_profile["gpu_pool"])]
        ram_gb = alienware_profile["ram_pool"][(index - 1) % len(alienware_profile["ram_pool"])]
        storage_gb = alienware_profile["storage_pool"][(index - 1) % len(alienware_profile["storage_pool"])]
        screen_size, resolution, refresh_hz, panel = alienware_profile["screen_pool"][(index - 1) % len(alienware_profile["screen_pool"])]
        price_inr = alienware_profile["base_price"] + (index * 8500) + (16000 if gpu_model == "RTX 4080" else 0)

        products.append(
            {
                "brand": "Dell",
                "series": "Alienware",
                "model": f"{alienware_profile['model_pool'][index - 1]} (Config {index:02d})",
                "sku": f"DEL-ALIENWARE-CFG-{index:02d}",
                "price_inr": price_inr,
                "product_url": alienware_profile["product_url"],
                "configurator_url": alienware_profile["product_url"],
                "image_url": alienware_profile["image_url"],
                "cpu_model": cpu_model,
                "ram_gb": ram_gb,
                "storage_gb": storage_gb,
                "gpu_model": gpu_model,
                "screen_size": screen_size,
                "resolution": resolution,
                "refresh_hz": refresh_hz,
                "panel": panel,
                "weight_kg": 2.75 if screen_size >= 16 else 2.1,
                "battery_hours": 6.0,
                "battery_capacity_wh": alienware_profile["battery_wh"],
                "battery_type": f"6-cell, {alienware_profile['battery_wh']} Wh Li-ion",
                "rating": round(4.3 + ((index % 4) * 0.1), 1),
                "use_cases": list(alienware_profile["use_cases"]),
                "ports": list(alienware_profile["ports"]),
                "srgb_100": True,
                "dci_p3": gpu_model in {"RTX 4070", "RTX 4080"},
                "good_cooling": True,
                "ram_upgradable": True,
                "extra_ssd_slot": True,
                "backlit_keyboard": True,
                "customization_options": list(alienware_profile["customization_options"]),
                "configuration": _build_dell_configuration_block(
                    "Alienware",
                    cpu_model,
                    ram_gb,
                    storage_gb,
                    gpu_model,
                    screen_size,
                    resolution,
                    refresh_hz,
                    panel,
                    alienware_profile["battery_wh"],
                ),
            }
        )

    products.append(
        {
            "brand": "Dell",
            "series": "G Series",
            "model": "G15 5530 (Config 01)",
            "sku": "DEL-GSERIES-CFG-01",
            "price_inr": 129990,
            "product_url": "https://www.dell.com/en-in/shop/gaming-and-games/g15-gaming-laptop/spd/g-series-15-5530-laptop",
            "configurator_url": "https://www.dell.com/en-in/shop/gaming-and-games/g15-gaming-laptop/spd/g-series-15-5530-laptop",
            "image_url": "https://i.dell.com/is/image/DellContent/content/dam/ss2/product-images/dell-client-products/notebooks/g-series/g15-5530/media-gallery/gray/non-touch/4-zone-rgb-kb/notebook-laptop-g15-5530-gray-gallery-1.psd?chrss=full&fmt=png-alpha&hei=402&pscan=auto&qlt=100%2C1&resMode=sharp2&scl=1&size=554%2C402&wid=554",
            "cpu_model": "Intel Core i7-13650HX",
            "ram_gb": 16,
            "storage_gb": 1024,
            "gpu_model": "RTX 4060",
            "screen_size": 15.6,
            "resolution": "FHD",
            "refresh_hz": 165,
            "panel": "IPS",
            "weight_kg": 2.65,
            "battery_hours": 5.2,
            "battery_capacity_wh": 86,
            "battery_type": "6-cell, 86 Wh Li-ion",
            "rating": 4.4,
            "use_cases": ["gaming", "student"],
            "ports": ["USB-C", "HDMI", "Ethernet", "Headphone jack"],
            "srgb_100": False,
            "dci_p3": False,
            "good_cooling": True,
            "ram_upgradable": True,
            "extra_ssd_slot": True,
            "backlit_keyboard": True,
            "customization_options": [
                "CPU options: Intel Core i5 / i7 H/HX",
                "GPU options: RTX 4050 / RTX 4060",
                "Memory options: 16GB / 32GB",
                "Storage options: 512GB / 1TB SSD",
            ],
            "configuration": _build_dell_configuration_block(
                "G Series",
                "Intel Core i7-13650HX",
                16,
                1024,
                "RTX 4060",
                15.6,
                "FHD",
                165,
                "IPS",
                86,
            ),
        }
    )

    return products


def _build_curated_multibrand_products():
    products = []
    curated_items = _merge_catalog_items(
        [item for item in CURATED_MULTI_BRAND_BASE_PRODUCTS if item.get("brand") not in {"Lenovo", "MSI", "Acer", "ASUS", "Dell"}],
        _build_dell_catalog_variants(),
        _build_lenovo_catalog_variants(),
        _build_msi_catalog_variants(),
        _build_acer_catalog_variants(),
        _build_asus_catalog_variants(),
    )
    for item in curated_items:
        cpu_brand, cpu_tier = _infer_cpu_brand_tier(item["cpu_model"])
        gpu_model = _normalize_gpu_model(item["gpu_model"])
        gpu_type = "integrated" if gpu_model == "Integrated Graphics" else "dedicated"
        display_label = f'{item["screen_size"]:.1f}" {item["resolution"]} {item["refresh_hz"]}Hz'
        customization_options = list(item.get("customization_options", []))
        configurator_url = str(item.get("configurator_url", "")).strip()
        configuration = item.get("configuration", {})
        customization_available = _has_native_configuration({"configuration": configuration})

        buy_links = [{"label": f'Buy on {item["brand"]}', "url": item["product_url"]}]
        brand_hub = CURATED_BRAND_HUB_LINKS.get(item["brand"])
        if brand_hub:
            buy_links.append({"label": f'{item["brand"]} Gaming Series', "url": brand_hub})

        products.append(
            {
                "brand": item["brand"],
                "series": item["series"],
                "model": item["model"],
                "sku": item["sku"],
                "price_inr": item["price_inr"],
                "currency": "INR",
                "region": HP_REGION,
                "product_url": item["product_url"],
                "image_url": _normalize_image_url(item.get("image_url", "")),
                "cpu_brand": cpu_brand,
                "cpu_tier": cpu_tier,
                "cpu_model": item["cpu_model"],
                "ram_gb": item["ram_gb"],
                "storage_type": "SSD",
                "storage_gb": item["storage_gb"],
                "gpu_type": gpu_type,
                "gpu_model": gpu_model,
                "screen_size": item["screen_size"],
                "resolution": item["resolution"],
                "refresh_hz": item["refresh_hz"],
                "panel": item["panel"],
                "weight_kg": item["weight_kg"],
                "battery_hours": item["battery_hours"],
                "battery_capacity_wh": item["battery_capacity_wh"],
                "battery_type": item["battery_type"],
                "rating": item["rating"],
                "use_cases": list(item["use_cases"]),
                "ports": list(item["ports"]),
                "srgb_100": bool(item["srgb_100"]),
                "dci_p3": bool(item["dci_p3"]),
                "good_cooling": bool(item["good_cooling"]),
                "ram_upgradable": bool(item["ram_upgradable"]),
                "extra_ssd_slot": bool(item["extra_ssd_slot"]),
                "backlit_keyboard": bool(item["backlit_keyboard"]),
                "customization_available": customization_available,
                "specs": {
                    "display": display_label,
                    "memory_type": "DDR5",
                    "keyboard": "Backlit gaming keyboard",
                    "wireless": "Wi-Fi 6E / Wi-Fi 7 (varies by SKU)",
                    "warranty": "1-year standard warranty (region dependent)",
                    "notes": "Curated catalog entry. Verify exact configuration and availability on the official product page.",
                    "customization_options": customization_options,
                    "configurator_url": configurator_url,
                    "configuration": configuration,
                },
                "benchmarks": _build_placeholder_benchmarks(gpu_model),
                "buy_links": buy_links,
            }
        )
    return products


def _merge_catalog_items(*catalogs):
    merged = []
    seen_skus = set()
    for catalog in catalogs:
        for item in catalog:
            sku = str(item.get("sku", "")).strip()
            if not sku or sku in seen_skus:
                continue
            seen_skus.add(sku)
            merged.append(item)
    return merged


def _extract_storage_gb(feature_rows):
    for row in feature_rows:
        if "ssd" not in row.lower():
            continue
        tb_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*TB", row, re.I)
        if tb_match:
            return int(float(tb_match.group(1)) * 1024)
        gb_match = re.search(r"([0-9]+)\s*GB", row, re.I)
        if gb_match:
            return int(gb_match.group(1))
    return 1024


def _extract_display_from_features(feature_rows):
    resolution = "QHD"
    refresh_hz = 165
    panel = "IPS"

    for row in feature_rows:
        lower = row.lower()
        if "display" not in lower:
            continue
        if "4k" in lower:
            resolution = "4K"
        elif "2k" in lower or "qhd" in lower:
            resolution = "QHD"
        elif "fhd" in lower:
            resolution = "FHD"

        hz_match = re.search(r"(\d{2,3})\s*hz", row, re.I)
        if hz_match:
            refresh_hz = int(hz_match.group(1))

        if "oled" in lower:
            panel = "OLED"
        elif "ips" in lower:
            panel = "IPS"

    return resolution, refresh_hz, panel


def _extract_cpu_from_title_or_features(title, feature_rows):
    cpu_match = re.search(r",\s*([^,]*?(?:Core|Ultra|Ryzen)[^,]*?)\s*,\s*RTX", title, re.I)
    if cpu_match:
        return cpu_match.group(1).strip()

    for row in feature_rows:
        if "processor" not in row.lower():
            continue
        normalized = row.replace("processor", "").replace("Processor", "").strip(" -:")
        if normalized:
            return normalized
    return "Intel Core i7"


def _extract_hp_products_from_listing(listing_html, source, cached_by_sku=None):
    card_pattern = re.compile(
        r"(<li class=\"item product product-item[\s\S]*?)(?=</li><li class=\"item product product-item|</ol>|$)"
    )
    cards = card_pattern.findall(listing_html)
    products = []
    cache = cached_by_sku or {}
    family = str(source.get("family", "")).strip()
    source_label = str(source.get("label", "HP India listing")).strip()
    source_url = str(source.get("url", "")).strip() or HP_OMEN_LISTING_URL

    for card in cards:
        sku_match = re.search(r'data-sku=\"([A-Z0-9]+)\"', card)
        price_match = re.search(r'data-price-amount=\"([0-9.]+)\"', card)
        title_match = re.search(r'<h2 class=\"plp-h2-title[^\"]*\">\s*(.*?)\s*</h2>', card, re.S)
        if not (sku_match and price_match and title_match):
            continue

        sku = sku_match.group(1).strip()
        link_match = re.search(
            r'<a href=\"(https://www\.hp\.com/in-en/shop/[^\"]+)\"[^>]*data-sku=\"' + re.escape(sku) + r'\"',
            card,
        )
        if not link_match:
            link_match = re.search(r'<a href=\"(https://www\.hp\.com/in-en/shop/[^\"]+)\"', card)
        if not link_match:
            continue

        product_url = link_match.group(1).split("#", 1)[0]
        title = _strip_tags(unescape(title_match.group(1)))
        price_inr = _parse_price_inr(price_match.group(1))
        if not title or not price_inr:
            continue

        feature_rows = []
        feature_block_match = re.search(r'<div class=\"product-desc-features[^\"]*\">\s*<ul>(.*?)</ul>', card, re.S)
        if feature_block_match:
            for row in re.findall(r"<li>(.*?)</li>", feature_block_match.group(1), re.S):
                feature_rows.append(_strip_tags(unescape(row)))

        rating_match = re.search(r'data-bv-average-overall-rating=\"([0-9.]+)\"', card)
        rating = float(rating_match.group(1)) if rating_match else 4.4

        title_upper = title.upper()
        family_upper = family.upper()
        if "VICTUS" in title_upper or family_upper == "VICTUS":
            series = "Victus"
        elif "OMEN MAX" in title_upper:
            series = "OMEN MAX"
        elif "TRANSCEND" in title_upper:
            series = "OMEN Transcend"
        else:
            series = "OMEN"

        screen_size = _extract_screen_size_from_title_or_features(title, feature_rows)
        size_label = f"{screen_size:.1f}".rstrip("0").rstrip(".")

        url_config_match = re.search(r"-(\d{2}-[a-z]{2}\d{4}[a-z]{2})-", product_url, re.I)
        if url_config_match:
            config_code = url_config_match.group(1).upper()
            model = f"{series} {size_label} ({config_code})"
        else:
            model = f"{series} {size_label} ({sku})"

        cpu_model = _extract_cpu_from_title_or_features(title, feature_rows)
        cpu_brand, cpu_tier = _infer_cpu_brand_tier(cpu_model)

        gpu_type, gpu_model = _extract_gpu_from_title_or_features(title, feature_rows)

        ram_match = re.search(r"RTX[^,]*,\s*([0-9]{2,3})\s*GB", title, re.I)
        if not ram_match:
            for row in feature_rows:
                row_lower = row.lower()
                if "ram" in row_lower or "ddr" in row_lower:
                    ram_match = re.search(r"([0-9]{2,3})\s*GB", row, re.I)
                    if ram_match:
                        break
        ram_gb = int(ram_match.group(1)) if ram_match else 16

        storage_gb = _extract_storage_gb(feature_rows)
        resolution, refresh_hz, panel = _extract_display_from_features(feature_rows)

        if series == "Victus":
            weight_kg = 2.29 if screen_size < 16 else 2.35
            battery_hours = 5.5 if gpu_type == "dedicated" else 7.2
            ports = ["USB-C", "HDMI", "Ethernet", "Headphone jack"]
            use_cases = ["gaming", "student"] if gpu_type == "dedicated" else ["student"]
        elif screen_size <= 14:
            weight_kg = 1.68
            battery_hours = 7.4
            ports = ["USB-C", "Thunderbolt", "HDMI", "Headphone jack"]
            use_cases = ["gaming", "creator", "student"]
        else:
            weight_kg = 2.38 if series == "OMEN" else 2.55
            battery_hours = 5.8 if series == "OMEN MAX" else 6.2
            ports = ["USB-C", "Thunderbolt", "HDMI", "Ethernet", "Headphone jack"]
            use_cases = ["gaming", "creator"]

        if gpu_model in {"RTX 2050", "RTX 3050", "RTX 5050"}:
            use_cases = ["gaming", "student"]
        elif gpu_model in {"RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090", "RTX 5070", "RTX 5070 Ti", "RTX 5080", "RTX 5090"}:
            if "creator" not in use_cases:
                use_cases.append("creator")

        battery_capacity_wh = _infer_battery_capacity_wh(screen_size, series)
        battery_type = ""
        cached_product = cache.get(sku, {})
        cached_capacity = cached_product.get("battery_capacity_wh")
        cached_type = _normalize_battery_type_text(cached_product.get("battery_type", ""))
        cached_image_url = _normalize_image_url(cached_product.get("image_url", ""))
        image_url = _extract_card_image_url(card) or cached_image_url
        if cached_capacity:
            battery_capacity_wh = int(cached_capacity)
        if cached_type:
            battery_type = cached_type
        if not battery_type:
            try:
                pdp_html = _fetch_html(product_url, timeout=10)
                parsed_capacity, parsed_type = _extract_battery_info_from_pdp(pdp_html)
                if parsed_capacity:
                    battery_capacity_wh = parsed_capacity
                if parsed_type:
                    battery_type = _normalize_battery_type_text(parsed_type)
            except (URLError, TimeoutError, OSError):
                pass

        display_label = f'{screen_size:.1f}" {resolution} {refresh_hz}Hz'
        benchmarks = _build_placeholder_benchmarks(gpu_model)

        products.append(
            {
                "brand": "HP",
                "series": series,
                "model": model,
                "sku": sku,
                "price_inr": price_inr,
                "currency": "INR",
                "region": HP_REGION,
                "product_url": product_url,
                "image_url": image_url,
                "cpu_brand": cpu_brand,
                "cpu_tier": cpu_tier,
                "cpu_model": cpu_model,
                "ram_gb": ram_gb,
                "storage_type": "SSD",
                "storage_gb": storage_gb,
                "gpu_type": gpu_type,
                "gpu_model": gpu_model,
                "screen_size": screen_size,
                "resolution": resolution,
                "refresh_hz": refresh_hz,
                "panel": panel,
                "weight_kg": weight_kg,
                "battery_hours": battery_hours,
                "battery_capacity_wh": battery_capacity_wh,
                "battery_type": battery_type,
                "rating": round(rating, 1),
                "use_cases": use_cases,
                "ports": ports,
                "srgb_100": True,
                "dci_p3": series in {"OMEN MAX", "OMEN Transcend"},
                "good_cooling": True,
                "ram_upgradable": screen_size >= 15,
                "extra_ssd_slot": screen_size >= 15,
                "backlit_keyboard": True,
                "specs": {
                    "display": display_label,
                    "memory_type": "DDR5",
                    "keyboard": "Backlit gaming keyboard",
                    "wireless": "Wi-Fi 6E / Wi-Fi 7 (varies by SKU)",
                    "warranty": "1-year limited warranty (India)",
                    "notes": "Catalog data sourced from HP India listing; exact panel bin and power limits vary by SKU.",
                },
                "benchmarks": benchmarks,
                "buy_links": [
                    {"label": "Buy on HP India", "url": product_url},
                    {
                        "label": source_label,
                        "url": source_url,
                    },
                ],
            }
        )

    deduped = []
    seen_skus = set()
    for item in products:
        if item["sku"] in seen_skus:
            continue
        seen_skus.add(item["sku"])
        deduped.append(item)
    return deduped


def _extract_hp_omen_products_from_listing(listing_html, cached_by_sku=None):
    omen_source = HP_GAMING_LISTING_SOURCES[0]
    return _extract_hp_products_from_listing(
        listing_html,
        omen_source,
        cached_by_sku=cached_by_sku,
    )


def _fetch_live_hp_catalog(cached_by_sku=None):
    all_items = []
    for source in HP_GAMING_LISTING_SOURCES:
        listing_url = source["url"]
        try:
            first_page_html = _fetch_html(listing_url, timeout=12)
        except (URLError, TimeoutError, OSError):
            continue

        all_items.extend(
            _extract_hp_products_from_listing(
                first_page_html,
                source,
                cached_by_sku=cached_by_sku,
            )
        )
        last_page = _discover_last_listing_page(first_page_html, listing_url)

        for page in range(2, last_page + 1):
            page_url = f"{listing_url}?p={page}"
            try:
                page_html = _fetch_html(page_url, timeout=12)
            except (URLError, TimeoutError, OSError):
                continue
            all_items.extend(
                _extract_hp_products_from_listing(
                    page_html,
                    source,
                    cached_by_sku=cached_by_sku,
                )
            )

    deduped = []
    seen_skus = set()
    for item in all_items:
        if item["sku"] in seen_skus:
            continue
        seen_skus.add(item["sku"])
        deduped.append(item)
    return deduped


def _fetch_live_hp_omen_catalog(cached_by_sku=None):
    return _fetch_live_hp_catalog(cached_by_sku=cached_by_sku)


def _load_snapshot_catalog():
    snapshot_paths = [HP_SNAPSHOT_PATH] + HP_LEGACY_SNAPSHOT_PATHS
    for snapshot_path in snapshot_paths:
        if not os.path.exists(snapshot_path):
            continue
        try:
            with open(snapshot_path, "r", encoding="utf-8") as snapshot_file:
                data = json.load(snapshot_file)
                if isinstance(data, list):
                    return data
        except (OSError, ValueError):
            continue
    return []


def _save_snapshot_catalog(catalog):
    target_paths = list(dict.fromkeys([HP_SNAPSHOT_PATH] + HP_LEGACY_SNAPSHOT_PATHS))
    for target_path in target_paths:
        try:
            with open(target_path, "w", encoding="utf-8") as snapshot_file:
                json.dump(catalog, snapshot_file, ensure_ascii=True, indent=2)
        except OSError:
            continue


def _seed_hp_products(connection):
    curated_catalog = _build_curated_multibrand_products()
    snapshot_catalog = _load_snapshot_catalog()
    snapshot_by_sku = {item.get("sku"): item for item in snapshot_catalog if isinstance(item, dict) and item.get("sku")}

    catalog = _fetch_live_hp_catalog(cached_by_sku=snapshot_by_sku)
    if catalog:
        seed_items = _merge_catalog_items(catalog, curated_catalog)
    else:
        base_catalog = snapshot_catalog or HP_PRODUCTS_SEED
        seed_items = _merge_catalog_items(base_catalog, curated_catalog)
    _save_snapshot_catalog(seed_items)

    seed_skus = [item["sku"] for item in seed_items]

    for item in seed_items:
        default_source_label = "HP India OMEN Series"
        default_source_url = HP_OMEN_LISTING_URL
        if str(item.get("series", "")).lower().startswith("victus"):
            default_source_label = "HP India Victus Series"
            default_source_url = HP_VICTUS_LISTING_URL
        buy_links = item.get(
            "buy_links",
            [
                {"label": "Buy on HP India", "url": item["product_url"]},
                {
                    "label": default_source_label,
                    "url": default_source_url,
                },
            ],
        )
        connection.execute(
            """
            INSERT INTO products (
                brand, series, model, sku, price_inr, currency, region, product_url, image_url,
                cpu_brand, cpu_tier, cpu_model, ram_gb, storage_type, storage_gb,
                gpu_type, gpu_model, screen_size, resolution, refresh_hz, panel,
                weight_kg, battery_hours, battery_capacity_wh, battery_type, rating,
                use_cases_json, ports_json, specs_json, benchmarks_json, buy_links_json,
                srgb_100, dci_p3, good_cooling, ram_upgradable, extra_ssd_slot, backlit_keyboard
            ) VALUES (
                :brand, :series, :model, :sku, :price_inr, :currency, :region, :product_url, :image_url,
                :cpu_brand, :cpu_tier, :cpu_model, :ram_gb, :storage_type, :storage_gb,
                :gpu_type, :gpu_model, :screen_size, :resolution, :refresh_hz, :panel,
                :weight_kg, :battery_hours, :battery_capacity_wh, :battery_type, :rating,
                :use_cases_json, :ports_json, :specs_json, :benchmarks_json, :buy_links_json,
                :srgb_100, :dci_p3, :good_cooling, :ram_upgradable, :extra_ssd_slot, :backlit_keyboard
            )
            ON CONFLICT(sku) DO UPDATE SET
                brand = excluded.brand,
                series = excluded.series,
                model = excluded.model,
                price_inr = excluded.price_inr,
                currency = excluded.currency,
                region = excluded.region,
                product_url = excluded.product_url,
                image_url = excluded.image_url,
                cpu_brand = excluded.cpu_brand,
                cpu_tier = excluded.cpu_tier,
                cpu_model = excluded.cpu_model,
                ram_gb = excluded.ram_gb,
                storage_type = excluded.storage_type,
                storage_gb = excluded.storage_gb,
                gpu_type = excluded.gpu_type,
                gpu_model = excluded.gpu_model,
                screen_size = excluded.screen_size,
                resolution = excluded.resolution,
                refresh_hz = excluded.refresh_hz,
                panel = excluded.panel,
                weight_kg = excluded.weight_kg,
                battery_hours = excluded.battery_hours,
                battery_capacity_wh = excluded.battery_capacity_wh,
                battery_type = excluded.battery_type,
                rating = excluded.rating,
                use_cases_json = excluded.use_cases_json,
                ports_json = excluded.ports_json,
                specs_json = excluded.specs_json,
                benchmarks_json = excluded.benchmarks_json,
                buy_links_json = excluded.buy_links_json,
                srgb_100 = excluded.srgb_100,
                dci_p3 = excluded.dci_p3,
                good_cooling = excluded.good_cooling,
                ram_upgradable = excluded.ram_upgradable,
                extra_ssd_slot = excluded.extra_ssd_slot,
                backlit_keyboard = excluded.backlit_keyboard,
                updated_at = CURRENT_TIMESTAMP
            """,
            {
                "brand": item["brand"],
                "series": item["series"],
                "model": item["model"],
                "sku": item["sku"],
                "price_inr": item["price_inr"],
                "currency": item.get("currency", "INR"),
                "region": item.get("region", HP_REGION),
                "product_url": item["product_url"],
                "image_url": _normalize_image_url(item.get("image_url", "")),
                "cpu_brand": item["cpu_brand"],
                "cpu_tier": item["cpu_tier"],
                "cpu_model": item["cpu_model"],
                "ram_gb": item["ram_gb"],
                "storage_type": item["storage_type"],
                "storage_gb": item["storage_gb"],
                "gpu_type": item["gpu_type"],
                "gpu_model": item["gpu_model"],
                "screen_size": item["screen_size"],
                "resolution": item["resolution"],
                "refresh_hz": item["refresh_hz"],
                "panel": item["panel"],
                "weight_kg": item["weight_kg"],
                "battery_hours": item["battery_hours"],
                "battery_capacity_wh": int(item.get("battery_capacity_wh") or _infer_battery_capacity_wh(item["screen_size"], item["series"])),
                "battery_type": _normalize_battery_type_text(item.get("battery_type", "")),
                "rating": item["rating"],
                "use_cases_json": _json_dumps(item.get("use_cases", [])),
                "ports_json": _json_dumps(item.get("ports", [])),
                "specs_json": _json_dumps(item.get("specs", {})),
                "benchmarks_json": _json_dumps(item.get("benchmarks", {})),
                "buy_links_json": _json_dumps(buy_links),
                "srgb_100": int(bool(item.get("srgb_100"))),
                "dci_p3": int(bool(item.get("dci_p3"))),
                "good_cooling": int(bool(item.get("good_cooling"))),
                "ram_upgradable": int(bool(item.get("ram_upgradable"))),
                "extra_ssd_slot": int(bool(item.get("extra_ssd_slot"))),
                "backlit_keyboard": int(bool(item.get("backlit_keyboard"))),
            },
        )

    placeholders = ",".join("?" for _ in seed_skus)
    connection.execute(
        f"DELETE FROM products WHERE sku NOT IN ({placeholders})",
        seed_skus,
    )


def _init_hp_database():
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(HP_SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        schema_sql = schema_file.read()

    with _db_connect() as connection:
        connection.executescript(schema_sql)
        _ensure_products_schema(connection)
        _seed_hp_products(connection)
        connection.commit()


def _ensure_products_schema(connection):
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(products)").fetchall()}
    if "battery_capacity_wh" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN battery_capacity_wh INTEGER")
    if "battery_type" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN battery_type TEXT")
    if "image_url" not in columns:
        connection.execute("ALTER TABLE products ADD COLUMN image_url TEXT")


def _row_to_product(row):
    battery_type = _normalize_battery_type_text(row["battery_type"] or "")
    battery_capacity_wh = row["battery_capacity_wh"]
    specs = _json_loads(row["specs_json"], {})
    return {
        "id": row["id"],
        "brand": row["brand"],
        "series": row["series"],
        "model": row["model"],
        "sku": row["sku"],
        "price": row["price_inr"],
        "currency": row["currency"],
        "region": row["region"],
        "product_url": row["product_url"],
        "image_url": _normalize_image_url(row["image_url"] or ""),
        "cpu_brand": row["cpu_brand"],
        "cpu_tier": row["cpu_tier"],
        "cpu_model": row["cpu_model"],
        "ram_gb": row["ram_gb"],
        "storage_type": row["storage_type"],
        "storage_gb": row["storage_gb"],
        "gpu_type": row["gpu_type"],
        "gpu_model": row["gpu_model"],
        "screen_size": row["screen_size"],
        "resolution": row["resolution"],
        "refresh_hz": row["refresh_hz"],
        "panel": row["panel"],
        "weight_kg": row["weight_kg"],
        "battery_hours": row["battery_hours"],
        "battery_capacity_wh": battery_capacity_wh,
        "battery_type": battery_type,
        "battery_type_display": _battery_type_display(battery_type, battery_capacity_wh),
        "ports": _json_loads(row["ports_json"], []),
        "use_cases": _json_loads(row["use_cases_json"], []),
        "specs": specs,
        "benchmarks": _json_loads(row["benchmarks_json"], {}),
        "buy_links": _json_loads(row["buy_links_json"], []),
        "srgb_100": bool(row["srgb_100"]),
        "dci_p3": bool(row["dci_p3"]),
        "good_cooling": bool(row["good_cooling"]),
        "ram_upgradable": bool(row["ram_upgradable"]),
        "extra_ssd_slot": bool(row["extra_ssd_slot"]),
        "backlit_keyboard": bool(row["backlit_keyboard"]),
        "rating": float(row["rating"] or 0),
        "customization_available": _has_native_configuration(specs),
    }


def _fetch_hp_products():
    with _db_connect() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM products
            ORDER BY
                CASE WHEN gpu_model LIKE '%5080%' THEN 0 ELSE 1 END,
                price_inr DESC,
                id ASC
            """
        ).fetchall()
    return [_row_to_product(row) for row in rows]


def _fetch_hp_product(product_id):
    with _db_connect() as connection:
        row = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return _row_to_product(row) if row else None


def _fetch_products_by_ids(product_ids):
    if not product_ids:
        return []
    placeholders = ",".join("?" for _ in product_ids)
    with _db_connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM products WHERE id IN ({placeholders})",
            product_ids,
        ).fetchall()
    products_by_id = {row["id"]: _row_to_product(row) for row in rows}
    return [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]


def _split_bullet_points(value):
    if value in (None, ""):
        return []
    chunks = []
    for line in str(value).splitlines():
        for bit in line.split(","):
            cleaned = bit.strip(" -\t")
            if cleaned:
                chunks.append(cleaned)
    return chunks


def _extract_price_delta(value):
    if not value:
        return 0
    text = str(value).replace(",", "")
    match = re.search(r"([+-])\s*₹?\s*([0-9]+)", text)
    if not match:
        return 0
    amount = int(match.group(2))
    return -amount if match.group(1) == "-" else amount


def _prepare_native_configuration(product):
    specs = product.get("specs") or {}
    product["customization_available"] = _has_native_configuration(specs)
    configuration = specs.get("configuration")
    if not isinstance(configuration, dict):
        return product

    categories = configuration.get("categories")
    if not isinstance(categories, list):
        return product

    configuration["base_price"] = int(product.get("price") or 0)

    for category_index, category in enumerate(categories):
        if not isinstance(category, dict):
            continue

        category["key"] = f"cfg_{category_index}"
        options = category.get("options") or []
        selected_index = None

        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            if option.get("included"):
                selected_index = option_index

            if option.get("included"):
                option["price_delta"] = 0
            else:
                primary_delta = _extract_price_delta(option.get("price_note", ""))
                fallback_delta = _extract_price_delta(option.get("alt_price_note", ""))
                option["price_delta"] = primary_delta if primary_delta else fallback_delta

        if selected_index is None and options:
            selected_index = 0
            first_option = options[0]
            if isinstance(first_option, dict):
                first_option["included"] = True
                first_option["price_delta"] = 0

        category["selected_option_index"] = selected_index if selected_index is not None else 0

    return product


def _fetch_product_reviews(product_id):
    with _db_connect() as connection:
        rows = connection.execute(
            """
            SELECT id, product_id, name, rating, pros, cons, experience, status, created_at
            FROM reviews
            WHERE product_id = ? AND status = 'approved'
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (product_id,),
        ).fetchall()

    reviews = []
    for row in rows:
        review = dict(row)
        review["pros_points"] = _split_bullet_points(review.get("pros"))
        review["cons_points"] = _split_bullet_points(review.get("cons"))
        reviews.append(review)
    return reviews


def _insert_product_review(product_id, name, rating, pros, cons, experience, status):
    with _db_connect() as connection:
        connection.execute(
            """
            INSERT INTO reviews (product_id, name, rating, pros, cons, experience, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (product_id, name, rating, pros, cons, experience, status),
        )
        connection.commit()


def _format_storage(storage_gb):
    if storage_gb >= 1024 and storage_gb % 1024 == 0:
        return f"{storage_gb // 1024}TB"
    return f"{storage_gb}GB"


_init_hp_database()

BENCHMARKS = {
    "cpu": [
        {"name": "Ryzen 7 7840HS", "score": 28000},
        {"name": "Intel i7-13700H", "score": 25000},
        {"name": "Intel i5-13420H", "score": 18000},
        {"name": "Ryzen 5 7640HS", "score": 22000},
        {"name": "Intel i7-13620H", "score": 23000},
    ],
    "gpu": [
        {"name": "RTX 4070 Laptop", "score": 17500},
        {"name": "RTX 4060 Laptop", "score": 15000},
        {"name": "RTX 4050 Laptop", "score": 12000},
        {"name": "Radeon 780M iGPU", "score": 4500},
        {"name": "Intel Arc A370M", "score": 7000},
    ],
}


@app.route("/")
def home():
    return render_template("index.html", guide=HOME_GUIDE)


@app.route("/benchmarks")
def benchmarks():
    return render_template("benchmarks.html")


@app.route("/laptops")
def laptops():
    return _render_laptop_finder()


@app.route("/finder")
def finder():
    query_string = request.query_string.decode("utf-8").strip()
    target = url_for("laptops")
    if query_string:
        target = f"{target}?{query_string}"
    return redirect(target)


def _render_laptop_finder():
    filters = _parse_finder_filters(request.args)

    catalog = _fetch_hp_products()
    finder_options = _build_finder_options(catalog, filters)
    filtered = [item for item in catalog if _matches_finder_filters(item, filters)]
    ranked = _sort_finder_laptops(filtered, filters["sort"], filters["use_case"])

    total_results = len(ranked)
    total_pages = max(1, ceil(total_results / filters["per_page"])) if total_results else 1
    if filters["page"] > total_pages:
        filters["page"] = total_pages

    start_index = (filters["page"] - 1) * filters["per_page"]
    end_index = start_index + filters["per_page"]
    visible_laptops = ranked[start_index:end_index]

    query_map = _finder_query_map_from_filters(filters, include_page=False)
    active_chips = _build_active_chips(filters, query_map)

    prev_url = None
    if filters["page"] > 1:
        prev_params = {key: list(values) for key, values in query_map.items()}
        prev_page = filters["page"] - 1
        if prev_page > 1:
            prev_params["page"] = [str(prev_page)]
        prev_url = _finder_url(prev_params)

    next_url = None
    if filters["page"] < total_pages:
        next_params = {key: list(values) for key, values in query_map.items()}
        next_params["page"] = [str(filters["page"] + 1)]
        next_url = _finder_url(next_params)

    counts = {
        "total": total_results,
        "shown": len(visible_laptops),
        "from": start_index + 1 if total_results else 0,
        "to": start_index + len(visible_laptops),
    }
    pagination = {
        "page": filters["page"],
        "per_page": filters["per_page"],
        "total_pages": total_pages,
        "has_prev": filters["page"] > 1,
        "has_next": filters["page"] < total_pages,
        "prev_url": prev_url,
        "next_url": next_url,
    }

    return render_template(
        "laptops.html",
        laptops=visible_laptops,
        filters=filters,
        counts=counts,
        active_chips=active_chips,
        pagination=pagination,
        options=finder_options,
    )


@app.route("/laptop/<int:laptop_id>")
def laptop_detail(laptop_id):
    return redirect(url_for("product_detail", product_id=laptop_id))


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = _fetch_hp_product(product_id)
    if not product:
        return render_template("product_detail.html", product=None, reviews=[], product_id=product_id), 404

    product = _prepare_native_configuration(product)
    reviews = _fetch_product_reviews(product_id)
    return render_template("product_detail.html", product=product, reviews=reviews, product_id=product_id)


@app.route("/product/<int:product_id>/review", methods=["POST"])
def product_review(product_id):
    product = _fetch_hp_product(product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("laptops"))

    name = request.form.get("name", "").strip()
    rating_raw = request.form.get("rating", "").strip()
    pros = request.form.get("pros", "").strip()
    cons = request.form.get("cons", "").strip()
    experience = request.form.get("experience", "").strip()

    errors = []
    if len(name) < 2:
        errors.append("Name must be at least 2 characters.")

    try:
        rating = int(rating_raw)
    except ValueError:
        rating = 0
    if rating < 1 or rating > 5:
        errors.append("Rating must be between 1 and 5.")

    if not _split_bullet_points(pros):
        errors.append("Please add at least one pro.")
    if not _split_bullet_points(cons):
        errors.append("Please add at least one con.")
    if len(experience) < 20:
        errors.append("Experience should be at least 20 characters.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(f"{url_for('product_detail', product_id=product_id)}#review-form")

    _insert_product_review(
        product_id=product_id,
        name=name,
        rating=rating,
        pros=pros,
        cons=cons,
        experience=experience,
        status=DEFAULT_REVIEW_STATUS,
    )

    if DEFAULT_REVIEW_STATUS == "pending":
        flash("Review submitted and sent for moderation.", "success")
    else:
        flash("Review submitted successfully.", "success")
    return redirect(f"{url_for('product_detail', product_id=product_id)}#reviews")


@app.route("/compare")
def compare():
    selected_ids = _parse_compare_ids(request.args)
    selected_laptops = _fetch_products_by_ids(selected_ids)
    return render_template("compare.html", laptops=selected_laptops, selected_ids=selected_ids)


@app.route("/api/benchmarks")
def api_benchmarks():
    category = request.args.get("category", "").strip().lower()
    if category:
        if category not in BENCHMARKS:
            return jsonify(
                {
                    "error": "Invalid category. Use one of: cpu, gpu.",
                    "valid_categories": sorted(BENCHMARKS.keys()),
                }
            ), 400
        return jsonify({category: BENCHMARKS[category]})
    return jsonify(BENCHMARKS)


@app.route("/api/laptops")
def api_laptops():
    use_case = request.args.get("use_case", "all").strip().lower()
    legacy_use_case_map = {
        "editing": "creator",
        "coding": "student",
        "professional": "student",
    }
    use_case = legacy_use_case_map.get(use_case, use_case)

    max_price_raw = request.args.get("max_price")
    max_price = None
    if max_price_raw not in (None, ""):
        try:
            max_price = int(max_price_raw)
        except ValueError:
            return jsonify({"error": "max_price must be an integer."}), 400
        if max_price < 0:
            return jsonify({"error": "max_price must be non-negative."}), 400

    filtered = _fetch_hp_products()
    if use_case and use_case != "all":
        filtered = [item for item in filtered if use_case in item["use_cases"]]

    if max_price is not None:
        filtered = [item for item in filtered if item["price"] <= max_price]

    payload = []
    for item in filtered:
        payload.append(
            {
                "id": item["id"],
                "name": f"{item['brand']} {item['model']}",
                "brand": item["brand"],
                "series": item["series"],
                "cpu": item["cpu_model"],
                "gpu": item["gpu_model"],
                "ram_gb": item["ram_gb"],
                "storage": f"{_format_storage(item['storage_gb'])} {item['storage_type']}",
                "display": f"{item['screen_size']}\" {item['resolution']} {item['refresh_hz']}Hz",
                "weight_kg": item["weight_kg"],
                "price_usd": item["price"],
                "image_url": item.get("image_url", ""),
                "battery_capacity_wh": item.get("battery_capacity_wh"),
                "battery_type": item.get("battery_type", ""),
                "use_case": item["use_cases"],
            }
        )

    return jsonify(payload)


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
    use_reloader = os.getenv("FLASK_RELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = os.getenv("PORT", "5000").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 5000
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
