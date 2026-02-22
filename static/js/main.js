const LEVEL_KEYS = ["beginner", "advanced", "enthusiast"];

(function () {
    const root = document.documentElement;
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark") {
        root.setAttribute("data-theme", "dark");
    }

    const themeButton = document.getElementById("themeToggle");
    if (themeButton) {
        themeButton.addEventListener("click", () => {
            const dark = root.getAttribute("data-theme") === "dark";
            if (dark) {
                root.removeAttribute("data-theme");
                localStorage.setItem("theme", "light");
            } else {
                root.setAttribute("data-theme", "dark");
                localStorage.setItem("theme", "dark");
            }
        });
    }

    initTopNavState();
    initPageChrome();
    initResponsiveTableLabels();

    const savedGuideLevel = normalizeLevel(localStorage.getItem("guideLevel"));
    const hasHomePage = Boolean(document.querySelector(".home-page"));
    if (hasHomePage) {
        initUseCaseTabs();
        initBuyingStepper();
        initCharacterShowcase();
        initHomePageMotion();
        initSidebarNavigation();

        lazyInitWhenVisible("#component-deep-dive", () => {
            initLevelCards(savedGuideLevel);
            initGuideLevelToolbar(savedGuideLevel);
            initComponentFilterChips();
            initInlineExpand();
        }, { rootMargin: "240px 0px", fallbackDelay: 900 });

        lazyInitWhenVisible("#red-flags", initSectionSwitchers, { rootMargin: "220px 0px", fallbackDelay: 1000 });
        lazyInitWhenVisible("#methodology", initAccordionToggles, { rootMargin: "180px 0px", fallbackDelay: 1100 });
        lazyInitWhenVisible("#confidence-meter", initConfidenceMeter, { rootMargin: "260px 0px", fallbackDelay: 1300 });
        lazyInitWhenVisible("#final-checklist", initFinalChecklist, { rootMargin: "260px 0px", fallbackDelay: 1400 });
    }

    initLaptopFilters();
    initBenchmarks();
})();

function normalizeLevel(level) {
    return LEVEL_KEYS.includes(level) ? level : "beginner";
}

function initTopNavState() {
    const links = document.querySelectorAll(".site-header nav a[href]");
    if (!links.length) {
        return;
    }

    const currentPath = normalizePath(window.location.pathname || "/");

    links.forEach((link) => {
        const href = link.getAttribute("href") || "";
        if (!href) {
            return;
        }

        let linkPath = href;
        try {
            linkPath = new URL(href, window.location.origin).pathname;
        } catch (error) {
            linkPath = href;
        }

        link.classList.toggle("is-current", normalizePath(linkPath) === currentPath);
    });
}

function normalizePath(path) {
    const trimmed = (path || "/").replace(/\/+$/, "");
    return trimmed || "/";
}

function lazyInitWhenVisible(selector, initFn, options = {}) {
    const target = document.querySelector(selector);
    if (!target || typeof initFn !== "function") {
        return;
    }

    let initialized = false;
    const runInit = () => {
        if (initialized) {
            return;
        }
        initialized = true;
        initFn();
    };

    const fallbackDelay = Number(options.fallbackDelay || 1200);
    if ("requestIdleCallback" in window) {
        window.requestIdleCallback(runInit, { timeout: fallbackDelay });
    } else {
        window.setTimeout(runInit, fallbackDelay);
    }

    if (!("IntersectionObserver" in window)) {
        runInit();
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
                runInit();
                observer.disconnect();
            }
        },
        { rootMargin: String(options.rootMargin || "200px 0px 120px 0px"), threshold: 0.01 }
    );

    observer.observe(target);
}

function initPageChrome() {
    const progressBar = document.querySelector("[data-scroll-progress-bar]");
    const backToTop = document.getElementById("backToTop");
    if (!progressBar && !backToTop) {
        return;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let ticking = false;

    function render() {
        const scrollTop = window.scrollY || window.pageYOffset;
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        const progress = maxScroll > 0 ? Math.min(Math.max(scrollTop / maxScroll, 0), 1) : 0;

        if (progressBar) {
            progressBar.style.transform = `scaleX(${progress})`;
        }

        if (backToTop) {
            backToTop.classList.toggle("is-visible", scrollTop > 480);
        }
    }

    function scheduleRender() {
        if (ticking) {
            return;
        }

        ticking = true;
        window.requestAnimationFrame(() => {
            render();
            ticking = false;
        });
    }

    if (backToTop) {
        backToTop.addEventListener("click", () => {
            window.scrollTo({
                top: 0,
                behavior: reduceMotion ? "auto" : "smooth",
            });
        });
    }

    window.addEventListener("scroll", scheduleRender, { passive: true });
    window.addEventListener("resize", scheduleRender);
    render();
}

function initConfidenceMeter() {
    const boxes = document.querySelectorAll("[data-confidence-box]");
    const output = document.querySelector("[data-confidence-output]");
    if (!boxes.length || !output) {
        return;
    }

    function render() {
        const checked = Array.from(boxes).filter((box) => box.checked).length;
        if (checked >= 4) {
            output.textContent = `Safe Purchase Zone (${checked}/5 checks complete).`;
            output.classList.add("is-safe");
        } else {
            output.textContent = `You have ${checked}/5 checks. Complete 4+ for Safe Purchase Zone.`;
            output.classList.remove("is-safe");
        }
    }

    boxes.forEach((box) => {
        box.addEventListener("change", render);
    });

    render();
}

function initFinalChecklist() {
    const boxes = document.querySelectorAll("[data-final-box]");
    const output = document.querySelector("[data-final-output]");
    if (!boxes.length || !output) {
        return;
    }

    const storageKey = "finalChecklistState";
    const savedRaw = localStorage.getItem(storageKey);

    if (savedRaw) {
        try {
            const saved = JSON.parse(savedRaw);
            if (Array.isArray(saved)) {
                boxes.forEach((box, index) => {
                    box.checked = Boolean(saved[index]);
                });
            }
        } catch (error) {
            localStorage.removeItem(storageKey);
        }
    }

    function render() {
        const total = boxes.length;
        const checked = Array.from(boxes).filter((box) => box.checked).length;

        boxes.forEach((box) => {
            const parent = box.closest(".final-check-item");
            if (parent) {
                parent.classList.toggle("is-checked", box.checked);
            }
        });

        if (checked === total) {
            output.textContent = `Final checklist complete (${checked}/${total}). Ready to purchase.`;
            output.classList.add("is-safe");
        } else {
            output.textContent = `Final checklist progress: ${checked}/${total}. Complete all before payment.`;
            output.classList.remove("is-safe");
        }

        localStorage.setItem(storageKey, JSON.stringify(Array.from(boxes, (box) => box.checked)));
    }

    boxes.forEach((box) => {
        box.addEventListener("change", render);
    });

    render();
}

function initUseCaseTabs() {
    const tabs = Array.from(document.querySelectorAll("[data-use-case-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-use-case-panel]"));
    if (!tabs.length || !panels.length) {
        return;
    }

    const tabList = tabs[0].closest("[role='tablist'], .use-case-tabs");
    if (tabList) {
        tabList.setAttribute("role", "tablist");
        tabList.setAttribute("aria-orientation", "horizontal");
    }

    tabs.forEach((tab, index) => {
        const panel = panels[index];
        const tabId = `use-case-tab-${index}`;
        const panelId = `use-case-panel-${index}`;
        tab.id = tabId;
        tab.setAttribute("aria-controls", panelId);
        tab.setAttribute("role", "tab");
        if (panel) {
            panel.id = panelId;
            panel.setAttribute("role", "tabpanel");
            panel.setAttribute("aria-labelledby", tabId);
            panel.tabIndex = 0;
        }
    });

    function activate(index) {
        const targetIndex = String(index);
        tabs.forEach((tab) => {
            const active = tab.dataset.useCaseTab === targetIndex;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", active ? "true" : "false");
            tab.tabIndex = active ? 0 : -1;
        });

        panels.forEach((panel) => {
            const active = panel.dataset.useCasePanel === targetIndex;
            panel.classList.toggle("is-active", active);
            panel.hidden = !active;
            panel.setAttribute("aria-hidden", active ? "false" : "true");
        });
    }

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            activate(tab.dataset.useCaseTab || "0");
        });
    });

    bindHorizontalArrowNavigation(tabs, (nextIndex) => {
        activate(tabs[nextIndex].dataset.useCaseTab || String(nextIndex));
        tabs[nextIndex].focus();
    });

    activate(tabs[0].dataset.useCaseTab || "0");
}

function initBuyingStepper() {
    const buttons = Array.from(document.querySelectorAll("[data-step-btn]"));
    const panels = Array.from(document.querySelectorAll("[data-step-panel]"));
    const progress = document.querySelector("[data-step-progress]");
    if (!buttons.length || !panels.length) {
        return;
    }

    const tabList = buttons[0].closest("[role='tablist'], .stepper-nav");
    if (tabList) {
        tabList.setAttribute("role", "tablist");
        tabList.setAttribute("aria-orientation", "horizontal");
    }

    buttons.forEach((button, index) => {
        const panel = panels[index];
        const tabId = `buy-step-tab-${index}`;
        const panelId = `buy-step-panel-${index}`;
        button.id = tabId;
        button.setAttribute("aria-controls", panelId);
        button.setAttribute("role", "tab");
        if (panel) {
            panel.id = panelId;
            panel.setAttribute("role", "tabpanel");
            panel.setAttribute("aria-labelledby", tabId);
            panel.tabIndex = 0;
        }
    });

    function activate(index) {
        const targetIndex = String(index);
        buttons.forEach((button) => {
            const active = button.dataset.stepBtn === targetIndex;
            button.classList.toggle("is-active", active);
            button.setAttribute("aria-selected", active ? "true" : "false");
            button.tabIndex = active ? 0 : -1;
        });

        panels.forEach((panel) => {
            const active = panel.dataset.stepPanel === targetIndex;
            panel.classList.toggle("is-active", active);
            panel.hidden = !active;
            panel.setAttribute("aria-hidden", active ? "false" : "true");
        });

        if (progress) {
            const activeStep = Number(targetIndex) + 1;
            const percent = (activeStep / buttons.length) * 100;
            progress.style.width = `${percent}%`;
        }
    }

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            activate(button.dataset.stepBtn || "0");
        });
    });

    bindHorizontalArrowNavigation(buttons, (nextIndex) => {
        activate(buttons[nextIndex].dataset.stepBtn || String(nextIndex));
        buttons[nextIndex].focus();
    });

    activate(buttons[0].dataset.stepBtn || "0");
}

function initSectionSwitchers() {
    const groups = document.querySelectorAll("[data-segment-group]");
    if (!groups.length) {
        return;
    }

    groups.forEach((group, groupIndex) => {
        const buttons = Array.from(group.querySelectorAll("[data-segment-btn]"));
        const views = Array.from(group.querySelectorAll("[data-segment-view]"));
        if (!buttons.length || !views.length) {
            return;
        }

        const tabList = group.querySelector(".content-switcher-tabs");
        if (tabList) {
            tabList.setAttribute("role", "tablist");
            tabList.setAttribute("aria-orientation", "horizontal");
        }

        const baseNameRaw = group.dataset.segmentGroup || `segment-${groupIndex}`;
        const baseName = String(baseNameRaw).replace(/[^a-z0-9_-]/gi, "-").toLowerCase();

        buttons.forEach((button, index) => {
            const panel = views[index];
            const tabId = `${baseName}-tab-${index}`;
            const panelId = `${baseName}-panel-${index}`;
            button.id = tabId;
            button.setAttribute("role", "tab");
            button.setAttribute("aria-controls", panelId);
            if (panel) {
                panel.id = panelId;
                panel.setAttribute("role", "tabpanel");
                panel.setAttribute("aria-labelledby", tabId);
                panel.tabIndex = 0;
            }
        });

        function activate(key) {
            const targetKey = String(key);

            buttons.forEach((button) => {
                const active = button.dataset.segmentBtn === targetKey;
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", active ? "true" : "false");
                button.tabIndex = active ? 0 : -1;
            });

            views.forEach((view) => {
                const active = view.dataset.segmentView === targetKey;
                view.classList.toggle("is-active", active);
                view.hidden = !active;
                view.setAttribute("aria-hidden", active ? "false" : "true");
            });
        }

        buttons.forEach((button) => {
            button.addEventListener("click", () => {
                activate(button.dataset.segmentBtn || "");
            });
        });

        bindHorizontalArrowNavigation(buttons, (nextIndex) => {
            const next = buttons[nextIndex];
            activate(next.dataset.segmentBtn || "");
            next.focus();
        });

        const initial = buttons.find((button) => button.classList.contains("is-active"));
        activate((initial || buttons[0]).dataset.segmentBtn || "");
    });
}

function initComponentFilterChips() {
    const chips = document.querySelectorAll("[data-component-chip]");
    const cards = document.querySelectorAll("[data-component-card]");
    if (!chips.length || !cards.length) {
        return;
    }

    function applyFilter(group) {
        const selectedGroup = group || "all";

        chips.forEach((chip) => {
            const active = chip.dataset.componentChip === selectedGroup;
            chip.classList.toggle("is-active", active);
            chip.setAttribute("aria-pressed", active ? "true" : "false");
        });

        cards.forEach((card) => {
            const show = selectedGroup === "all" || card.dataset.componentGroup === selectedGroup;
            card.hidden = !show;
            card.classList.toggle("is-filtered-out", !show);

            if (!show) {
                const panel = card.querySelector(".inline-expand-body");
                const button = card.querySelector("[data-inline-target]");
                if (panel) {
                    panel.hidden = true;
                }
                if (button) {
                    button.setAttribute("aria-expanded", "false");
                    button.textContent = "Inline Expand";
                }
                card.classList.remove("is-open");
            }
        });
    }

    chips.forEach((chip) => {
        chip.addEventListener("click", () => {
            applyFilter(chip.dataset.componentChip || "all");
        });
    });

    applyFilter("all");
}

function initInlineExpand() {
    const buttons = Array.from(document.querySelectorAll("[data-inline-target]"));
    if (!buttons.length) {
        return;
    }

    function closeButtonPanel(button) {
        const targetId = button.dataset.inlineTarget;
        if (!targetId) {
            return;
        }

        const panel = document.getElementById(targetId);
        if (panel) {
            panel.hidden = true;
        }

        button.setAttribute("aria-expanded", "false");
        button.textContent = "Inline Expand";

        const card = button.closest(".component-card");
        if (card) {
            card.classList.remove("is-open");
        }
    }

    buttons.forEach((button) => {
        const targetId = button.dataset.inlineTarget;
        if (!targetId) {
            return;
        }

        const panel = document.getElementById(targetId);
        if (!panel) {
            return;
        }

        button.addEventListener("click", () => {
            const expanded = button.getAttribute("aria-expanded") === "true";
            const nextState = !expanded;

            if (nextState) {
                buttons.forEach((otherButton) => {
                    if (otherButton !== button) {
                        closeButtonPanel(otherButton);
                    }
                });
            }

            button.setAttribute("aria-expanded", nextState ? "true" : "false");
            button.textContent = nextState ? "Collapse" : "Inline Expand";
            panel.hidden = !nextState;

            const card = button.closest(".component-card");
            if (card) {
                card.classList.toggle("is-open", nextState);
                if (nextState) {
                    // Wait for layout updates so the expanded card can be positioned at eye level.
                    window.setTimeout(() => {
                        scrollElementToEyeLevel(card);
                    }, 90);
                }
            }
        });
    });
}

function bindHorizontalArrowNavigation(items, onSelectIndex) {
    if (!items.length) {
        return;
    }

    items.forEach((item, index) => {
        item.addEventListener("keydown", (event) => {
            const key = event.key;
            let nextIndex = null;

            if (key === "ArrowRight" || key === "ArrowDown") {
                nextIndex = (index + 1) % items.length;
            } else if (key === "ArrowLeft" || key === "ArrowUp") {
                nextIndex = (index - 1 + items.length) % items.length;
            } else if (key === "Home") {
                nextIndex = 0;
            } else if (key === "End") {
                nextIndex = items.length - 1;
            }

            if (nextIndex === null) {
                return;
            }

            event.preventDefault();
            onSelectIndex(nextIndex);
        });
    });
}

function scrollElementToEyeLevel(element) {
    if (!element) {
        return;
    }

    const rect = element.getBoundingClientRect();
    const topBound = 112;
    const bottomBound = window.innerHeight - 96;

    if (rect.top >= topBound && rect.bottom <= bottomBound) {
        return;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const eyeLevelOffset = Math.max(120, Math.round(window.innerHeight * 0.23));
    const targetTop = Math.max(0, window.scrollY + rect.top - eyeLevelOffset);

    window.scrollTo({
        top: targetTop,
        behavior: reduceMotion ? "auto" : "smooth",
    });
}

function initAccordionToggles() {
    const buttons = document.querySelectorAll("[data-accordion-target]");
    if (!buttons.length) {
        return;
    }

    buttons.forEach((button) => {
        const targetId = button.dataset.accordionTarget;
        if (!targetId) {
            return;
        }

        const panel = document.getElementById(targetId);
        if (!panel) {
            return;
        }

        button.addEventListener("click", () => {
            const expanded = button.getAttribute("aria-expanded") === "true";
            const nextState = !expanded;
            button.setAttribute("aria-expanded", nextState ? "true" : "false");
            panel.hidden = !nextState;
            button.classList.toggle("is-open", nextState);
        });
    });
}

function initSidebarNavigation() {
    const links = document.querySelectorAll("[data-side-link]");
    if (!links.length) {
        return;
    }

    const items = Array.from(links)
        .map((link) => {
            const href = link.getAttribute("href") || "";
            if (!href.startsWith("#")) {
                return null;
            }

            const target = document.getElementById(href.slice(1));
            if (!target) {
                return null;
            }

            return { link, target };
        })
        .filter(Boolean);

    if (!items.length) {
        return;
    }

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function setActive(targetNode) {
        items.forEach((item) => {
            item.link.classList.toggle("is-active", item.target === targetNode);
        });
    }

    items.forEach((item) => {
        item.link.addEventListener("click", (event) => {
            setActive(item.target);
            if (reduceMotion) {
                return;
            }

            event.preventDefault();
            item.target.scrollIntoView({ behavior: "smooth", block: "start" });
            window.history.replaceState(null, "", `#${item.target.id}`);
        });
    });

    setActive(items[0].target);

    if (!("IntersectionObserver" in window)) {
        return;
    }

    const observer = new IntersectionObserver(
        (entries) => {
            let visible = null;
            entries.forEach((entry) => {
                if (!entry.isIntersecting) {
                    return;
                }

                if (!visible || entry.intersectionRatio > visible.intersectionRatio) {
                    visible = entry;
                }
            });

            if (visible) {
                setActive(visible.target);
            }
        },
        { threshold: [0.2, 0.45, 0.7], rootMargin: "-24% 0px -58% 0px" }
    );

    items.forEach((item) => observer.observe(item.target));
}

function initCharacterShowcase() {
    const cards = document.querySelectorAll("[data-character-card]");
    const dots = document.querySelectorAll("[data-character-dot]");
    const nameTarget = document.querySelector("[data-character-name-target]");
    const tipTarget = document.querySelector("[data-character-tip-target]");
    if (!cards.length || !dots.length || !nameTarget || !tipTarget) {
        return;
    }

    let index = 0;
    let timer = null;

    function activate(nextIndex) {
        const safeIndex = ((nextIndex % cards.length) + cards.length) % cards.length;
        index = safeIndex;

        cards.forEach((card, i) => {
            card.classList.toggle("is-active", i === safeIndex);
        });
        dots.forEach((dot, i) => {
            dot.classList.toggle("is-active", i === safeIndex);
        });

        const active = cards[safeIndex];
        tipTarget.classList.add("is-switching");

        window.setTimeout(() => {
            nameTarget.textContent = active.dataset.characterName || "";
            tipTarget.textContent = active.dataset.characterTip || "";
            tipTarget.classList.remove("is-switching");
        }, 120);
    }

    function startAutoRotate() {
        stopAutoRotate();
        timer = window.setInterval(() => {
            activate(index + 1);
        }, 4200);
    }

    function stopAutoRotate() {
        if (timer) {
            window.clearInterval(timer);
            timer = null;
        }
    }

    dots.forEach((dot) => {
        dot.addEventListener("click", () => {
            const nextIndex = Number(dot.dataset.characterDot || "0");
            activate(nextIndex);
            startAutoRotate();
        });
    });

    const container = document.getElementById("characterLab");
    if (container) {
        container.addEventListener("mouseenter", stopAutoRotate);
        container.addEventListener("mouseleave", startAutoRotate);
    }

    activate(0);
    startAutoRotate();
}

function initHomePageMotion() {
    const homePage = document.querySelector(".home-page");
    if (!homePage) {
        return;
    }

    homePage.classList.add("is-motion-ready");

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const revealItems = Array.from(homePage.querySelectorAll("[data-reveal]"));
    revealItems.forEach((item, index) => {
        const delay = Math.min(index * 70, 420);
        item.style.setProperty("--reveal-delay", `${delay}ms`);
    });

    const markVisible = (node) => node.classList.add("is-visible");

    if (reduceMotion || !("IntersectionObserver" in window)) {
        revealItems.forEach(markVisible);
    } else {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    markVisible(entry.target);
                    observer.unobserve(entry.target);
                });
            },
            { threshold: 0.14, rootMargin: "0px 0px -12% 0px" }
        );

        revealItems.forEach((item, index) => {
            if (index === 0) {
                markVisible(item);
            } else {
                observer.observe(item);
            }
        });
    }

    const heroCard = homePage.querySelector(".hero-pro");
    const stage = homePage.querySelector(".character-stage");
    if (!heroCard || !stage || reduceMotion) {
        return;
    }

    function handlePointerMove(event) {
        const rect = heroCard.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        const rotateX = (-y * 4).toFixed(2);
        const rotateY = (x * 5).toFixed(2);
        stage.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) translate3d(0, 0, 0)`;
    }

    function resetStage() {
        stage.style.transform = "";
    }

    heroCard.addEventListener("pointermove", handlePointerMove);
    heroCard.addEventListener("pointerleave", resetStage);
}

function activateLevelInCard(card, level) {
    const normalized = normalizeLevel(level);
    const buttons = card.querySelectorAll("[data-level-btn]");
    const panels = card.querySelectorAll("[data-level-panel]");

    buttons.forEach((btn) => {
        const active = btn.dataset.levelBtn === normalized;
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-selected", active ? "true" : "false");
    });

    panels.forEach((panel) => {
        const active = panel.dataset.levelPanel === normalized;
        panel.classList.toggle("is-active", active);
        panel.hidden = !active;
    });
}

function applyLevelToAllCards(level) {
    const normalized = normalizeLevel(level);
    const cards = document.querySelectorAll("[data-level-card]");
    cards.forEach((card) => activateLevelInCard(card, normalized));
}

function initLevelCards(defaultLevel) {
    const cards = document.querySelectorAll("[data-level-card]");
    if (!cards.length) {
        return;
    }

    cards.forEach((card) => {
        const buttons = card.querySelectorAll("[data-level-btn]");
        buttons.forEach((btn) => {
            btn.addEventListener("click", () => {
                activateLevelInCard(card, btn.dataset.levelBtn);
            });
        });

        activateLevelInCard(card, defaultLevel);
    });
}

function initGuideLevelToolbar(defaultLevel) {
    const toolbar = document.querySelector("[data-guide-level-toolbar]");
    if (!toolbar) {
        return;
    }

    const buttons = toolbar.querySelectorAll("[data-global-level-btn]");
    if (!buttons.length) {
        return;
    }

    function setToolbarLevel(level) {
        const normalized = normalizeLevel(level);
        buttons.forEach((btn) => {
            const active = btn.dataset.globalLevelBtn === normalized;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("aria-selected", active ? "true" : "false");
        });
    }

    function applyGlobalLevel(level) {
        const normalized = normalizeLevel(level);
        setToolbarLevel(normalized);
        applyLevelToAllCards(normalized);
    }

    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const selected = normalizeLevel(btn.dataset.globalLevelBtn);
            localStorage.setItem("guideLevel", selected);
            applyGlobalLevel(selected);
        });
    });

    applyGlobalLevel(defaultLevel);
}

function initResponsiveTableLabels() {
    const tables = document.querySelectorAll("table");
    if (!tables.length) {
        return;
    }

    tables.forEach((table) => {
        const headers = Array.from(table.querySelectorAll("thead th")).map((header) => {
            return (header.textContent || "").trim();
        });

        if (!headers.length) {
            return;
        }

        const rows = table.querySelectorAll("tbody tr");
        rows.forEach((row) => {
            const cells = Array.from(row.children).filter((node) => node.tagName === "TD");
            cells.forEach((cell, index) => {
                if (!cell.dataset.label) {
                    cell.dataset.label = headers[index] || `Column ${index + 1}`;
                }
            });
        });
    });
}

async function initLaptopFilters() {
    const grid = document.getElementById("laptopGrid");
    const applyBtn = document.getElementById("applyFilters");
    if (!grid || !applyBtn) {
        return;
    }

    async function loadLaptops() {
        const useCase = document.getElementById("useCase").value;
        const maxPrice = document.getElementById("maxPrice").value;
        const params = new URLSearchParams({ use_case: useCase });
        if (maxPrice) {
            params.append("max_price", maxPrice);
        }

        const response = await fetch(`/api/laptops?${params.toString()}`);
        const payload = await response.json();

        if (!response.ok) {
            const message = payload && payload.error ? payload.error : "Unable to load laptops.";
            grid.innerHTML = `<article class="card">${message}</article>`;
            return;
        }

        const laptops = Array.isArray(payload) ? payload : [];

        if (!laptops.length) {
            grid.innerHTML = '<article class="card">No laptops match this filter.</article>';
            return;
        }

        grid.innerHTML = laptops
            .map(
                (laptop) => `
                <article class="card laptop-card">
                    <div class="finder-thumb">
                        <img src="${laptop.image_url || "/static/images/laptop-placeholder.svg"}" alt="${laptop.name}" loading="lazy" onerror="this.onerror=null;this.src='/static/images/laptop-placeholder.svg';">
                    </div>
                    <h3>${laptop.name}</h3>
                    <p class="laptop-meta">${laptop.brand} | ₹${Number(laptop.price_usd || 0).toLocaleString("en-IN")}</p>
                    <p><strong>CPU:</strong> ${laptop.cpu}</p>
                    <p><strong>GPU:</strong> ${laptop.gpu}</p>
                    <p><strong>RAM:</strong> ${laptop.ram_gb}GB | <strong>Storage:</strong> ${laptop.storage}</p>
                    <p><strong>Display:</strong> ${laptop.display} | <strong>Weight:</strong> ${laptop.weight_kg}kg</p>
                </article>`
            )
            .join("");
    }

    applyBtn.addEventListener("click", loadLaptops);
    await loadLaptops();
}

async function initBenchmarks() {
    const cpuCanvas = document.getElementById("cpuChart");
    const gpuCanvas = document.getElementById("gpuChart");
    if (!cpuCanvas || !gpuCanvas) {
        return;
    }

    const response = await fetch("/api/benchmarks");
    const data = await response.json();

    if (window.Chart) {
        renderChart(cpuCanvas, "CPU Comparison", data.cpu);
        renderChart(gpuCanvas, "GPU Comparison", data.gpu);
        return;
    }

    renderFallbackList("cpuFallback", data.cpu);
    renderFallbackList("gpuFallback", data.gpu);
}

function renderChart(canvas, title, series) {
    new Chart(canvas, {
        type: "bar",
        data: {
            labels: series.map((s) => s.name),
            datasets: [
                {
                    label: title,
                    data: series.map((s) => s.score),
                    borderWidth: 1,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
        },
    });
}

function renderFallbackList(targetId, series) {
    const target = document.getElementById(targetId);
    if (!target) {
        return;
    }

    target.innerHTML = "Chart.js not loaded yet. Data preview:<br>" +
        series.map((item) => `${item.name}: ${item.score}`).join("<br>");
}
