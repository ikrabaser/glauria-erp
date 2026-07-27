(function () {
    const storageKey = "glauria-theme-preference";

    function resolvedTheme(preference) {
        if (preference === "system") {
            return window.matchMedia(
                "(prefers-color-scheme: dark)"
            ).matches
                ? "dark"
                : "light";
        }

        return preference;
    }

    function applyTheme(preference) {
        document.documentElement.dataset.theme = resolvedTheme(
            preference
        );

        localStorage.setItem(storageKey, preference);
    }

        const savedPreference = localStorage.getItem(storageKey) || "system";

    applyTheme(savedPreference);

    const select = document.querySelector("#theme-preference");

    if (!select) {
        return;
    }

    select.value = savedPreference;

    select.addEventListener("change", function () {
        applyTheme(select.value);
    });
})();

(function () {
    const trigger = document.querySelector("[data-user-menu-trigger]");
    const menu = document.querySelector("[data-user-menu]");

    if (!trigger || !menu) {
        return;
    }

    trigger.addEventListener("click", function () {
        const isOpen = !menu.hidden;

        menu.hidden = isOpen;
        trigger.setAttribute("aria-expanded", String(!isOpen));
    });

    document.addEventListener("click", function (event) {
        if (!event.target.closest(".topbar-account")) {
            menu.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            menu.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
        }
    });
})();