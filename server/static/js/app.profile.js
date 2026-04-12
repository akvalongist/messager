const originalBindEvents = MessengerApp.prototype.bindEvents;

MessengerApp.prototype.bindEvents = function bindEventsWithThemeTools() {
    originalBindEvents.call(this);

    const backgroundUrlInput = document.getElementById('theme-background-url');
    const backgroundFileInput = document.getElementById('theme-background-file');
    const clearBackgroundButton = document.getElementById('btn-clear-background');

    if (backgroundUrlInput) {
        backgroundUrlInput.addEventListener('change', () => this.applyBackgroundUrl(backgroundUrlInput.value.trim()));
    }

    if (backgroundFileInput) {
        backgroundFileInput.addEventListener('change', (event) => this.handleBackgroundUpload(event));
    }

    if (clearBackgroundButton) {
        clearBackgroundButton.addEventListener('click', () => this.clearCustomBackground());
    }
};

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
    const hue = document.getElementById('theme-hue')?.value || 212;
    const opacity = document.getElementById('theme-opacity')?.value || 12;
    const blur = document.getElementById('theme-blur')?.value || 24;
    const particles = document.getElementById('theme-particles')?.value || 80;
    const backgroundStrength = document.getElementById('theme-background-strength')?.value || 48;
    const backgroundBlur = document.getElementById('theme-background-blur')?.value || 6;

    document.documentElement.style.setProperty('--theme-hue', hue);
    document.documentElement.style.setProperty('--glass-opacity', (opacity / 100).toFixed(2));
    document.documentElement.style.setProperty('--glass-blur', `${blur}px`);
    document.documentElement.style.setProperty('--bg-media-strength', (backgroundStrength / 100).toFixed(2));
    document.documentElement.style.setProperty('--bg-media-blur', `${backgroundBlur}px`);

    const currentTheme = this.readThemeSettings();
    currentTheme.hue = hue;
    currentTheme.opacity = opacity;
    currentTheme.blur = blur;
    currentTheme.particles = particles;
    currentTheme.backgroundStrength = backgroundStrength;
    currentTheme.backgroundBlur = backgroundBlur;
    this.persistThemeSettings(currentTheme);

    if (window.particleSystem && typeof window.particleSystem.setParticleCount === 'function') {
        window.particleSystem.setParticleCount(particles);
    }
};

MessengerApp.prototype.loadTheme = function loadTheme() {
    const theme = this.readThemeSettings();

    document.documentElement.style.setProperty('--theme-hue', theme.hue ?? 212);
    document.documentElement.style.setProperty('--glass-opacity', ((theme.opacity ?? 12) / 100).toFixed(2));
    document.documentElement.style.setProperty('--glass-blur', `${theme.blur ?? 24}px`);
    document.documentElement.style.setProperty('--bg-media-strength', ((theme.backgroundStrength ?? 48) / 100).toFixed(2));
    document.documentElement.style.setProperty('--bg-media-blur', `${theme.backgroundBlur ?? 6}px`);

    const bindings = {
        'theme-hue': theme.hue ?? 212,
        'theme-opacity': theme.opacity ?? 12,
        'theme-blur': theme.blur ?? 24,
        'theme-particles': theme.particles ?? 80,
        'theme-background-strength': theme.backgroundStrength ?? 48,
        'theme-background-blur': theme.backgroundBlur ?? 6,
        'theme-background-url': theme.backgroundUrl ?? '',
    };

    Object.entries(bindings).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    });

    this.applyBackground(theme.backgroundUrl || null);

    if (window.particleSystem && typeof window.particleSystem.setParticleCount === 'function') {
        window.particleSystem.setParticleCount(theme.particles ?? 80);
    }
};

MessengerApp.prototype.resetTheme = function resetTheme() {
    localStorage.removeItem('theme');
    this.loadTheme();
    UI.toast('Theme reset', 'info');
};

MessengerApp.prototype.readThemeSettings = function readThemeSettings() {
    const saved = localStorage.getItem('theme');
    if (!saved) return {};

    try {
        return JSON.parse(saved);
    } catch (error) {
        localStorage.removeItem('theme');
        return {};
    }
};

MessengerApp.prototype.persistThemeSettings = function persistThemeSettings(theme) {
    localStorage.setItem('theme', JSON.stringify(theme));
};

MessengerApp.prototype.applyBackground = function applyBackground(backgroundUrl) {
    const background = document.getElementById('app-background');
    if (!background) return;

    if (backgroundUrl) {
        background.style.backgroundImage = `url("${backgroundUrl}")`;
        background.classList.add('has-custom-media');
    } else {
        background.style.backgroundImage = '';
        background.classList.remove('has-custom-media');
    }
};

MessengerApp.prototype.applyBackgroundUrl = function applyBackgroundUrl(backgroundUrl) {
    const theme = this.readThemeSettings();
    theme.backgroundUrl = backgroundUrl || null;
    this.persistThemeSettings(theme);
    this.applyBackground(theme.backgroundUrl);
};

MessengerApp.prototype.handleBackgroundUpload = function handleBackgroundUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
        const backgroundUrl = String(reader.result || '');
        const backgroundUrlInput = document.getElementById('theme-background-url');
        if (backgroundUrlInput) backgroundUrlInput.value = '';
        this.applyBackgroundUrl(backgroundUrl);
        UI.toast('Background updated', 'success');
    };
    reader.readAsDataURL(file);
    event.target.value = '';
};

MessengerApp.prototype.clearCustomBackground = function clearCustomBackground() {
    const backgroundUrlInput = document.getElementById('theme-background-url');
    const backgroundFileInput = document.getElementById('theme-background-file');
    if (backgroundUrlInput) backgroundUrlInput.value = '';
    if (backgroundFileInput) backgroundFileInput.value = '';
    this.applyBackgroundUrl(null);
    UI.toast('Custom background cleared', 'info');
};
