from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

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
    return render_template("laptops.html")


@app.route("/api/benchmarks")
def api_benchmarks():
    category = request.args.get("category")
    if category:
        return jsonify({category: BENCHMARKS.get(category, [])})
    return jsonify(BENCHMARKS)


@app.route("/api/laptops")
def api_laptops():
    use_case = request.args.get("use_case", "all").lower()
    max_price = request.args.get("max_price", type=int)

    filtered = LAPTOPS
    if use_case != "all":
        filtered = [l for l in filtered if use_case in l["use_case"]]

    if max_price is not None:
        filtered = [l for l in filtered if l["price_usd"] <= max_price]

    return jsonify(filtered)


if __name__ == "__main__":
    app.run(debug=True)
