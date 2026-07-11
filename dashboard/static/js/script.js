const btn = document.getElementById("sort_btn");

if (btn) {
    btn.addEventListener("click", function(e) {
        e.preventDefault();

        const sortInput = document.getElementById("sort_input");
        sortInput.value = sortInput.value === "desc" ? "asc" : "desc";

        sortInput.form.submit();
    });
}

/* Dropdown menu for diff. actions */
document.addEventListener('click', (e) => {
    /* Close all open dropdowns if click is outside */
    document.querySelectorAll('.dropdown-menu.open').forEach(menu => {
        if (!menu.dataset.triggerId || !document.querySelector(`[data-dropdown-id="${menu.dataset.triggerId}"]`)) {
            menu.classList.remove('open');
        }
    });

    const trigger = e.target.closest('.dropdown-trigger');

    if (trigger) {
        e.preventDefault();
        e.stopPropagation();

        const menu = trigger.nextElementSibling;
        const wasOpen = menu.classList.contains('open');

        /* Close all other dropdowns first */
        document.querySelectorAll('.dropdown-menu.open').forEach(openMenu => {
            openMenu.classList.remove('open');
        });

        if (!wasOpen) {
            /* Calculate position based on trigger button's viewport position */
            const triggerRect = trigger.getBoundingClientRect();
            const menuHeight = menu.offsetHeight || 120; /* estimate if not rendered yet */
            const viewportHeight = window.innerHeight;
            const spaceBelow = viewportHeight - triggerRect.bottom - 8;

            /* Position horizontally: align right edge of menu with right edge of trigger */
            menu.style.left = 'auto';
            menu.style.right = `${window.innerWidth - triggerRect.right}px`;

            /* Smart flip: open upward if not enough space below */
            if (spaceBelow < menuHeight && triggerRect.top > menuHeight) {
                menu.style.top = 'auto';
                menu.style.bottom = `${viewportHeight - triggerRect.top + 4}px`;
            } else {
                menu.style.top = `${triggerRect.bottom + 4}px`;
                menu.style.bottom = 'auto';
            }

            menu.classList.add('open');
        }
    }
});

// Close dropdown on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.dropdown-menu.open').forEach(menu => {
            menu.classList.remove('open');
        });
    }
});

// Close dropdown on scroll (prevents stale positioning)
window.addEventListener('scroll', () => {
    document.querySelectorAll('.dropdown-menu.open').forEach(menu => {
        menu.classList.remove('open');
    });
}, { passive: true });

// Reposition on window resize
window.addEventListener('resize', () => {
    document.querySelectorAll('.dropdown-menu.open').forEach(menu => {
        menu.classList.remove('open');
    });
});
