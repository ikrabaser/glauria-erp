(function () {
    const storageKey = "glauria-theme-preference";
    const serverPreference = (
        document.documentElement.dataset.themePreference || "system"
    );

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

    applyTheme(serverPreference);

    const select = document.querySelector("#theme-preference");

    if (!select) {
        return;
    }

    select.value = serverPreference;

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

(function () {
    const notificationTrigger = document.querySelector(
        "[data-notification-menu-trigger]"
    );
    const notificationMenu = document.querySelector(
        "[data-notification-menu]"
    );
    const userMenuTrigger = document.querySelector(
        "[data-user-menu-trigger]"
    );
    const userMenu = document.querySelector(
        "[data-user-menu]"
    );

    if (!notificationTrigger || !notificationMenu) {
        return;
    }

    function closeNotificationMenu() {
        notificationMenu.hidden = true;
        notificationTrigger.setAttribute(
            "aria-expanded",
            "false"
        );
    }

    notificationTrigger.addEventListener(
        "click",
        function (event) {
            event.stopPropagation();

            const isOpen = !notificationMenu.hidden;

            notificationMenu.hidden = isOpen;
            notificationTrigger.setAttribute(
                "aria-expanded",
                String(!isOpen)
            );

            if (userMenu && !userMenu.hidden) {
                userMenu.hidden = true;

                if (userMenuTrigger) {
                    userMenuTrigger.setAttribute(
                        "aria-expanded",
                        "false"
                    );
                }
            }
        }
    );

    if (userMenuTrigger) {
        userMenuTrigger.addEventListener(
            "click",
            closeNotificationMenu
        );
    }

    document.addEventListener("click", function (event) {
        if (
            !event.target.closest(
                ".topbar-notification-wrapper"
            )
        ) {
            closeNotificationMenu();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeNotificationMenu();
        }
    });
})();