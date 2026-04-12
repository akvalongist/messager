MessengerApp.prototype.toggleStickerPanel = async function toggleStickerPanel() {
    const panel = document.getElementById('sticker-panel');
    if (!panel) return;

    if (panel.classList.contains('hidden')) {
        await this.loadStickers();
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
    }
};

MessengerApp.prototype.loadStickers = async function loadStickers() {
    try {
        this.stickerPacks = await api.getMyStickers();
        this.currentPackIndex = 0;
        this.renderStickerTabs();
        if (this.stickerPacks.length > 0) {
            this.selectStickerPack(0);
        } else {
            const grid = document.getElementById('sticker-grid');
            if (grid) {
                grid.innerHTML = '<p style="color: #6b6b80; text-align: center; padding: 20px; grid-column: 1/-1;">Нет стикеров. Создайте или установите пак.</p>';
            }
        }
    } catch (error) {
        console.error('Sticker load failed:', error);
    }
};

MessengerApp.prototype.renderStickerTabs = function renderStickerTabs() {
    const tabs = document.getElementById('sticker-tabs');
    if (!tabs || !this.stickerPacks) return;

    tabs.innerHTML = this.stickerPacks.map((pack, index) => {
        const cover = pack.cover_url
            ? `<img src="${pack.cover_url}" alt="${pack.name}">`
            : '<span class="tab-emoji">📦</span>';

        return `
            <button class="sticker-tab ${index === this.currentPackIndex ? 'active' : ''}"
                    onclick="app.selectStickerPack(${index})"
                    title="${UI.escapeHtml(pack.name)}">
                ${cover}
            </button>
        `;
    }).join('');
};

MessengerApp.prototype.selectStickerPack = function selectStickerPack(index) {
    this.currentPackIndex = index;
    const pack = this.stickerPacks[index];
    if (!pack) return;

    this.renderStickerTabs();
    const grid = document.getElementById('sticker-grid');
    if (!grid) return;

    if (pack.stickers.length === 0) {
        grid.innerHTML = '<p style="color: #6b6b80; text-align: center; padding: 20px; grid-column: 1/-1;">Пак пустой</p>';
        return;
    }

    grid.innerHTML = pack.stickers.map((sticker) => `
        <div class="sticker-item" onclick="app.sendSticker('${sticker.file_url}')" title="${sticker.emoji}">
            <img src="${sticker.file_url}" alt="${sticker.emoji}" loading="lazy">
        </div>
    `).join('');

    if (pack.creator_id === this.currentUser.user_id) {
        grid.innerHTML += `
            <div class="sticker-item" onclick="app.managePack('${pack.id}')"
                 style="border: 2px dashed #2a2a4a; font-size: 24px;"
                 title="Управление">
                ⚙️
            </div>
        `;
    }
};
