const btn = document.getElementById("sort_btn");
if (btn) {
    btn.addEventListener("click", function(e) {
        e.preventDefault();
        const sortInput = document.getElementById("sort_input");
        sortInput.value = sortInput.value === "desc" ? "asc" : "desc";
        sortInput.form.submit();
    });
}

/* global dropdown handler */
document.addEventListener('click', (e) => {
    const actionTrigger = e.target.closest('.dropdown-trigger');
    const columnTrigger = e.target.closest('#colSelectorBtn');

    // action dropdown (3 dots)
    if (actionTrigger) {
        e.preventDefault();
        e.stopPropagation();
        const menu = actionTrigger.nextElementSibling;
        const isOpen = menu.classList.contains('open');

        closeAllDropdownsExcept(menu);

        if (isOpen) {
            menu.classList.remove('open');
        } else {
            positionDropdown(menu, actionTrigger);
            menu.classList.add('open');
        }
        return;
    }

    // column selector button
    if (columnTrigger) {
        e.preventDefault();
        e.stopPropagation();
        const dropdown = document.getElementById('colSelectorDropdown');
        const isOpen = dropdown.classList.contains('open');

        closeAllDropdownsExcept(dropdown);

        if (isOpen) {
            dropdown.classList.remove('open');
        } else {
            dropdown.style.position = 'fixed';
            positionDropdown(dropdown, columnTrigger);
            dropdown.classList.add('open');
        }
        return;
    }

    // clicked outside
    if (!isClickInsideAnyDropdown(e.target)) {
        closeAllDropdowns();
    }
});

// helpers
function closeAllDropdownsExcept(except = null) {
    document.querySelectorAll('.dropdown-menu.open, #colSelectorDropdown.open').forEach(el => {
        if (el !== except) el.classList.remove('open');
    });
}

function isClickInsideAnyDropdown(target) {
    return target.closest('.dropdown-menu') ||
           target.closest('#colSelectorDropdown') ||
           target.closest('.column-selector-item');
}

function closeAllDropdowns() {
    document.querySelectorAll('.dropdown-menu.open, #colSelectorDropdown.open').forEach(el => {
        el.classList.remove('open');
    });
}

function positionDropdown(menu, trigger) {
    const triggerRect = trigger.getBoundingClientRect();
    const menuWidth = menu.offsetWidth || 140;
    const menuHeight = menu.offsetHeight || 120;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Align right side of menu to trigger's right side, keeping it inside viewport bounds
    let left = triggerRect.right - menuWidth;
    if (left < 8) {
        left = 8;
    }
    if (left + menuWidth > viewportWidth - 8) {
        left = viewportWidth - menuWidth - 8;
    }

    menu.style.left = `${left}px`;
    menu.style.right = 'auto';

    const spaceBelow = viewportHeight - triggerRect.bottom - 8;
    if (spaceBelow < menuHeight && triggerRect.top > menuHeight) {
        menu.style.top = 'auto';
        menu.style.bottom = `${viewportHeight - triggerRect.top + 4}px`;
    } else {
        menu.style.top = `${triggerRect.bottom + 4}px`;
        menu.style.bottom = 'auto';
    }
}

/* column visibility logic */
document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("tableContainer");
    if (!container) return;

    const btn = document.getElementById("colSelectorBtn");
    const dropdown = document.getElementById("colSelectorDropdown");
    const table = document.getElementById("dataTable");

    if (!btn || !dropdown || !table) return;

    const checkboxes = dropdown.querySelectorAll(".col-toggle");
    const storageKey = "col_visibility_" + window.location.pathname;

    function loadPreferences() {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
            const prefs = JSON.parse(saved);
            checkboxes.forEach(cb => {
                const idx = cb.dataset.colIndex;
                if (idx in prefs) {
                    cb.checked = prefs[idx];
                }
            });
        }
        applyVisibility();
    }

    function savePreferences() {
        const prefs = {};
        checkboxes.forEach(cb => {
            prefs[cb.dataset.colIndex] = cb.checked;
        });
        localStorage.setItem(storageKey, JSON.stringify(prefs));
    }

    function applyVisibility() {
        checkboxes.forEach(cb => {
            const colIndex = cb.dataset.colIndex;
            // Hide/show header
            const header = table.querySelector(`th[data-col="${colIndex}"]`);
            if (header) {
                header.style.display = cb.checked ? "" : "none";
            }
            // Hide/show all cells in that column
            const cells = table.querySelectorAll(`td[data-col="${colIndex}"]`);
            cells.forEach(cell => {
                cell.style.display = cb.checked ? "" : "none";
            });
        });
    }

    // checkbox change
    checkboxes.forEach(cb => {
        cb.addEventListener("change", () => {
            applyVisibility();
            savePreferences();
        });
    });

    // load saved preferences on page load
    loadPreferences();
});

/* other listeners */
// escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllDropdowns();
});

// close on scroll
window.addEventListener('scroll', () => {
    closeAllDropdowns();
}, { passive: true });

// close on resize
window.addEventListener('resize', () => {
    closeAllDropdowns();
});
