MessengerApp.prototype.toggleProfileMenu = function toggleProfileMenu() {
    const menu = document.getElementById('profile-menu');
    if (!menu) return;

    if (menu.classList.contains('hidden')) {
        const name = this.currentUser.display_name || this.currentUser.username;
        const nameEl = document.getElementById('profile-name');
        const idEl = document.getElementById('profile-id');
        const avatarEl = document.getElementById('profile-avatar');

        if (nameEl) nameEl.textContent = name;
        if (idEl) idEl.textContent = `ID: ${this.currentUser.user_id}`;
        if (avatarEl) avatarEl.textContent = UI.getInitials(name);

        menu.classList.remove('hidden');
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(event) {
                if (!menu.contains(event.target) && !event.target.closest('.user-info')) {
                    menu.classList.add('hidden');
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 10);
    } else {
        menu.classList.add('hidden');
    }
};

MessengerApp.prototype.updateTheme = function updateTheme() {
    const hue = document.getElementById('theme-hue')?.value || 260;
    const opacity = document.getElementById('theme-opacity')?.value || 15;
    const blur = document.getElementById('theme-blur')?.value || 20;
    const particles = document.getElementById('theme-particles')?.value || 80;

    document.documentElement.style.setProperty('--theme-hue', hue);
    document.documentElement.style.setProperty('--glass-opacity', (opacity / 100).toFixed(2));
    document.documentElement.style.setProperty('--glass-blur', `${blur}px`);
    localStorage.setItem('theme', JSON.stringify({ hue, opacity, blur, particles }));
};

MessengerApp.prototype.loadTheme = function loadTheme() {
    const saved = localStorage.getItem('theme');
    if (!saved) return;

    try {
        const theme = JSON.parse(saved);
        document.documentElement.style.setProperty('--theme-hue', theme.hue);
        document.documentElement.style.setProperty('--glass-opacity', (theme.opacity / 100).toFixed(2));
        document.documentElement.style.setProperty('--glass-blur', `${theme.blur}px`);

        const bindings = {
            'theme-hue': theme.hue,
            'theme-opacity': theme.opacity,
            'theme-blur': theme.blur,
            'theme-particles': theme.particles,
        };

        Object.entries(bindings).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.value = value;
        });
    } catch (error) {
        localStorage.removeItem('theme');
    }
};
