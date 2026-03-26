class MessengerApp {
    constructor() {
        this.currentUser = null;
        this.currentChatId = null;
        this.chats = [];
        this.messages = {};
        this.replyTo = null;
        this.typingTimer = null;
        this.typingHideTimer = null;

        this.init();
    }

    async init() {
        this.bindEvents();

        const savedUser = localStorage.getItem('user');
        const savedToken = localStorage.getItem('token');

        if (savedUser && savedToken) {
            try {
                api.token = savedToken;
                this.currentUser = JSON.parse(savedUser);
                await this.enterChat();
            } catch (e) {
                this.showAuth();
            }
        } else {
            this.showAuth();
        }
    }

    bindEvents() {
        const loginForm = document.getElementById('login-form');
        const registerForm = document.getElementById('register-form');

        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        }

        const showRegister = document.getElementById('show-register');
        const showLogin = document.getElementById('show-login');

        if (showRegister) {
            showRegister.addEventListener('click', (e) => {
                e.preventDefault();
                document.getElementById('login-form').classList.remove('active');
                document.getElementById('register-form').classList.add('active');
            });
        }
        if (showLogin) {
            showLogin.addEventListener('click', (e) => {
                e.preventDefault();
                document.getElementById('register-form').classList.remove('active');
                document.getElementById('login-form').classList.add('active');
            });
        }

        this.safeClick('btn-new-chat', () => UI.showModal('modal-new-chat'));
        this.safeClick('btn-new-group', () => UI.showModal('modal-new-group'));
        this.safeClick('btn-logout', () => this.logout());
        this.safeClick('btn-chat-info', () => this.showChatInfo());      // ← ДОБАВЬ
        // СТИКЕРЫ - Кнопки панели
        this.safeClick('btn-emoji', () => this.toggleStickerPanel());
        this.safeClick('btn-create-pack', () => this.showCreatePack());
        this.safeClick('btn-browse-packs', () => this.showBrowsePacks());
        this.safeClick('btn-close-stickers', () => {
            const panel = document.getElementById('sticker-panel');
            if (panel) panel.classList.add('hidden');
        });

        // СТИКЕРЫ - Модалки
        this.safeClick('btn-submit-pack', () => this.createPack());

        document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
            btn.addEventListener('click', () => UI.hideAllModals());
        });
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) UI.hideAllModals();
            });
        });

        this.safeClick('btn-create-direct', () => this.createDirectChat());
        this.safeClick('btn-create-group', () => this.createGroup());

        const input = document.getElementById('message-input');
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            input.addEventListener('input', () => {
                UI.autoResize(input);
                this.handleTyping();
            });
        }

        this.safeClick('btn-send', () => this.sendMessage());

        this.safeClick('btn-attach', () => {
            const fileInput = document.getElementById('file-input');
            if (fileInput) fileInput.click();
        });

        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        }

        this.safeClick('btn-cancel-reply', () => this.cancelReply());
        this.safeClick('btn-back', () => this.showSidebar());

        const searchInput = document.getElementById('search-chats');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.filterChats(e.target.value));
        }

        document.addEventListener('click', () => {
            document.querySelectorAll('.context-menu').forEach(m => m.remove());
        });

        wsManager.on('new_message', (msg) => this.onNewMessage(msg));
        wsManager.on('typing', (data) => this.onTyping(data));
        wsManager.on('read', (data) => this.onRead(data));
        wsManager.on('message_edited', (data) => this.onMessageEdited(data));
        wsManager.on('connected', () => console.log('✅ WS подключён'));
        wsManager.on('disconnected', () => UI.toast('Переподключение...', 'error'));
    }

    safeClick(id, callback) {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', callback);
    }

    // ==================== AUTH ====================

    showAuth() {
        document.getElementById('auth-screen').classList.add('active');
        document.getElementById('chat-screen').classList.remove('active');
    }

    async handleLogin(e) {
        e.preventDefault();
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('auth-error');

        try {
            errorEl.textContent = '';
            this.currentUser = await api.login(username, password);
            await this.enterChat();
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        const username = document.getElementById('reg-username').value.trim();
        const displayName = document.getElementById('reg-display-name').value.trim();
        const email = document.getElementById('reg-email').value.trim();
        const password = document.getElementById('reg-password').value;
        const errorEl = document.getElementById('auth-error');

        try {
            errorEl.textContent = '';
            this.currentUser = await api.register(username, displayName, password, email || null);
            await this.enterChat();
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }

    logout() {
        api.clearToken();
        wsManager.disconnect();
        this.currentUser = null;
        this.currentChatId = null;
        this.chats = [];
        this.messages = {};
        document.getElementById('chat-screen').classList.remove('active');
        document.getElementById('auth-screen').classList.add('active');
        UI.toast('Вы вышли', 'info');
    }

    // ==================== MAIN ====================

    async enterChat() {
        document.getElementById('auth-screen').classList.remove('active');
        document.getElementById('chat-screen').classList.add('active');

        const displayName = this.currentUser.display_name || this.currentUser.username;

        const nameEl = document.getElementById('my-display-name');
        if (nameEl) nameEl.textContent = displayName;

        const avatarEl = document.getElementById('my-avatar');
        if (avatarEl) avatarEl.textContent = UI.getInitials(displayName);

        const idEl = document.getElementById('my-user-id');
        if (idEl) idEl.textContent = `ID: ${this.currentUser.user_id.substring(0, 8)}... 📋`;

        wsManager.connect(api.token);
        await this.loadChats();

        UI.toast(`Привет, ${displayName}! 👋`, 'success');
    }

    copyMyId() {
        const id = this.currentUser.user_id;
        navigator.clipboard.writeText(id);
        UI.toast('ID скопирован! Отправьте его собеседнику', 'success');
    }

    // ==================== SEARCH USERS ====================

    async searchUsers(query) {
        const container = document.getElementById('search-results');
        if (!container) return;

        if (query.length < 2) {
            container.innerHTML = '<p style="color: #6b6b80; font-size: 13px; padding: 8px;">Минимум 2 символа</p>';
            return;
        }

        try {
            const data = await api.request('GET', `/auth/search/${encodeURIComponent(query)}`);
            const users = data.users || [];

            if (users.length === 0) {
                container.innerHTML = '<p style="color: #6b6b80; font-size: 13px; padding: 8px;">Никого не найдено</p>';
                return;
            }

            container.innerHTML = users.map(u => `
                <div class="chat-item" style="padding: 8px 12px; cursor: pointer;"
                     onclick="app.startChatWithUser('${u.user_id}')">
                    <div class="avatar small" style="background: ${UI.getAvatarColor(u.display_name)}">
                        ${UI.getInitials(u.display_name)}
                    </div>
                    <div class="chat-item-info">
                        <div class="chat-item-name">${UI.escapeHtml(u.display_name)}</div>
                        <div class="chat-item-last-message">@${UI.escapeHtml(u.username)}</div>
                    </div>
                    <span style="font-size: 10px; color: ${u.is_online ? '#10B981' : '#6b6b80'}">
                        ${u.is_online ? '🟢' : '⚫'}
                    </span>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '<p style="color: #EF4444; font-size: 13px; padding: 8px;">Ошибка поиска</p>';
        }
    }

    async startChatWithUser(userId) {
        try {
            const chat = await api.createDirectChat(userId);
            UI.hideAllModals();
            await this.loadChats();
            await this.selectChat(chat.id);
            UI.toast('Чат создан!', 'success');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    // ==================== CHATS ====================

    async loadChats() {
        try {
            const data = await api.getChats();
            this.chats = data.chats || [];
            this.renderChatList();
        } catch (error) {
            console.error('Ошибка загрузки чатов:', error);
        }
    }

    renderChatList() {
        const container = document.getElementById('chat-list');
        if (!container) return;

        if (this.chats.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>Нет чатов</p>
                    <p class="hint">Нажмите ✏️ чтобы начать общение</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.chats.map(chat => `
            <div class="chat-item ${chat.id === this.currentChatId ? 'active' : ''}"
                 data-chat-id="${chat.id}"
                 onclick="app.selectChat('${chat.id}')">
                <div class="avatar" style="background: ${UI.getAvatarColor(chat.name)}">
                    ${chat.chat_type === 'group' ? '👥' : UI.getInitials(chat.name)}
                </div>
                <div class="chat-item-info">
                    <div class="chat-item-name">${UI.escapeHtml(chat.name || 'Чат')}</div>
                    <div class="chat-item-last-message" id="last-msg-${chat.id}"></div>
                </div>
                <div class="chat-item-meta">
                    <span class="chat-item-time" id="chat-time-${chat.id}"></span>
                </div>
            </div>
        `).join('');
    }

    async selectChat(chatId) {
        this.currentChatId = chatId;
        const chat = this.chats.find(c => c.id === chatId);
        if (!chat) return;

        const noChat = document.getElementById('no-chat-selected');
        const header = document.getElementById('chat-header');
        const messagesContainer = document.getElementById('messages-container');
        const inputArea = document.getElementById('message-input-area');

        if (noChat) noChat.classList.add('hidden');
        if (header) header.classList.remove('hidden');
        if (messagesContainer) messagesContainer.classList.remove('hidden');
        if (inputArea) inputArea.classList.remove('hidden');

        const chatName = document.getElementById('chat-name');
        const chatAvatar = document.getElementById('chat-avatar');
        const chatStatus = document.getElementById('chat-status');

        if (chatName) chatName.textContent = chat.name || 'Чат';
        if (chatAvatar) {
            chatAvatar.textContent = chat.chat_type === 'group' ? '👥' : UI.getInitials(chat.name);
            chatAvatar.style.background = UI.getAvatarColor(chat.name);
        }
        if (chatStatus) {
            chatStatus.textContent = chat.chat_type === 'group' ? `${chat.members_count} участников` : '';
        }

        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.toggle('active', item.dataset.chatId === chatId);
        });

        await this.loadMessages(chatId);

        const input = document.getElementById('message-input');
        if (input) input.focus();

        if (window.innerWidth <= 768) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) sidebar.classList.add('hidden-mobile');
        }
    }

    showSidebar() {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) sidebar.classList.remove('hidden-mobile');
    }

    filterChats(query) {
        const items = document.querySelectorAll('.chat-item');
        const q = query.toLowerCase();
        items.forEach(item => {
            const name = item.querySelector('.chat-item-name');
            if (name) {
                item.style.display = name.textContent.toLowerCase().includes(q) ? '' : 'none';
            }
        });
    }

    async createDirectChat() {
        const input = document.getElementById('new-chat-user-id');
        if (!input) return;

        const userId = input.value.trim();
        if (!userId) {
            UI.toast('Введите ID или найдите пользователя через поиск', 'error');
            return;
        }

        try {
            const chat = await api.createDirectChat(userId);
            UI.hideAllModals();
            input.value = '';
            await this.loadChats();
            await this.selectChat(chat.id);
            UI.toast('Чат создан!', 'success');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async createGroup() {
        const nameInput = document.getElementById('group-name');
        const descInput = document.getElementById('group-description');
        if (!nameInput) return;

        const name = nameInput.value.trim();
        const description = descInput ? descInput.value.trim() : '';

        if (!name) {
            UI.toast('Введите название группы', 'error');
            return;
        }

        try {
            const chat = await api.createGroup(name, description);
            UI.hideAllModals();
            nameInput.value = '';
            if (descInput) descInput.value = '';
            await this.loadChats();
            await this.selectChat(chat.id);
            UI.toast(`Группа "${name}" создана!`, 'success');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    // ==================== MESSAGES ====================

    async loadMessages(chatId) {
        try {
            const data = await api.getMessages(chatId);
            this.messages[chatId] = data.messages || [];
            this.renderMessages(chatId);
        } catch (error) {
            console.error('Ошибка загрузки сообщений:', error);
        }
    }

    renderMessages(chatId) {
        const container = document.getElementById('messages-list');
        if (!container) return;

        const messages = this.messages[chatId] || [];

        if (messages.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>Нет сообщений</p>
                    <p class="hint">Напишите первое сообщение!</p>
                </div>
            `;
            return;
        }

        let html = '';
        let lastDate = '';

        messages.forEach(msg => {
            const msgDate = new Date(msg.created_at).toDateString();
            if (msgDate !== lastDate) {
                html += `<div class="date-separator">${UI.formatDateSeparator(msg.created_at)}</div>`;
                lastDate = msgDate;
            }
            html += this.renderMessage(msg);
        });

        container.innerHTML = html;

        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) UI.scrollToBottom(messagesContainer);
    }

    renderMessage(msg) {
        const isOwn = msg.sender_id === this.currentUser.user_id;
        const msgClass = msg.message_type === 'system' ? 'system' : (isOwn ? 'own' : 'other');

        if (msg.is_deleted) {
            return `
                <div class="message ${msgClass}" data-message-id="${msg.id}">
                    <div class="message-bubble">
                        <span class="message-deleted">🚫 Сообщение удалено</span>
                    </div>
                </div>
            `;
        }

        let contentHtml = '';

        // Имя отправителя в группах
        if (!isOwn && msg.sender_name) {
            const chat = this.getCurrentChat();
            if (chat && chat.chat_type === 'group') {
                contentHtml += `<div class="message-sender">${UI.escapeHtml(msg.sender_name)}</div>`;
            }
        }

        // Стикер — без фона, просто картинка
        if (msg.file_url && msg.message_type === 'sticker') {
            contentHtml += `
                <div class="sticker-message-container" style="background: transparent !important; padding: 0;">
                    <img class="sticker-message" src="${msg.file_url}" alt="sticker" loading="lazy" style="max-width: 160px; max-height: 160px; filter: drop-shadow(0 2px 5px rgba(0,0,0,0.2));">
                </div>
            `;
        }
        // Картинка — показываем прямо в чате
        else if (msg.file_url && msg.message_type === 'image') {
            contentHtml += `
                <div class="message-image-container">
                    <img class="message-image" 
                         src="${msg.file_url}" 
                         alt="${UI.escapeHtml(msg.file_name || 'Фото')}" 
                         loading="lazy"
                         onclick="window.open('${msg.file_url}', '_blank')"
                         onerror="this.style.display='none'">
                </div>
            `;
            // Если есть подпись
            if (msg.content && msg.content !== msg.file_name) {
                contentHtml += `<div class="message-text">${this.formatMessageText(msg.content)}</div>`;
            }
        }
        // Видео
        else if (msg.file_url && msg.message_type === 'video') {
            contentHtml += `
                <div class="message-video-container">
                    <video class="message-video" controls preload="metadata" style="max-width: 300px; border-radius: 8px;">
                        <source src="${msg.file_url}" type="${msg.mime_type || 'video/mp4'}">
                    </video>
                </div>
            `;
        }
        // Аудио / голосовое
        else if (msg.file_url && (msg.message_type === 'voice' || msg.message_type === 'audio')) {
            contentHtml += `
                <div class="message-audio-container">
                    <audio controls preload="metadata" style="width: 250px;">
                        <source src="${msg.file_url}" type="${msg.mime_type || 'audio/mpeg'}">
                    </audio>
                </div>
            `;
        }
        // Обычный файл
        else if (msg.file_url) {
            const icon = UI.getFileIcon(msg.mime_type);
            const size = UI.formatFileSize(msg.file_size);
            contentHtml += `
                <div class="message-file">
                    <a href="${msg.file_url}" target="_blank" download="${msg.file_name || 'file'}">
                        <div class="file-info">
                            <span class="file-icon">${icon}</span>
                            <div class="file-details">
                                <span class="file-name">${UI.escapeHtml(msg.file_name || 'Файл')}</span>
                                <span class="file-size">${size}</span>
                            </div>
                        </div>
                    </a>
                </div>
            `;
            // Текст к файлу
            if (msg.content && msg.content !== msg.file_name) {
                contentHtml += `<div class="message-text">${this.formatMessageText(msg.content)}</div>`;
            }
        }
        // Обычный текст
        else if (msg.content) {
            contentHtml += `<div class="message-text">${this.formatMessageText(msg.content)}</div>`;
        }

        // Время и статус
        let metaHtml = `<span class="message-time">${UI.formatTime(msg.created_at)}</span>`;
        if (msg.is_edited) {
            metaHtml = `<span class="message-edited">ред.</span>` + metaHtml;
        }
        if (isOwn) {
            metaHtml += `<span class="message-status">✓</span>`;
        }

        // Для стикеров убираем фон пузыря (background: transparent)
        const bubbleStyle = msg.message_type === 'sticker' ? 'background: transparent; box-shadow: none; padding: 0;' : '';

        return `
            <div class="message ${msgClass}" data-message-id="${msg.id}"
                 oncontextmenu="app.showMessageMenu(event, '${msg.id}')">
                <div class="message-bubble" style="${bubbleStyle}">
                    ${contentHtml}
                    <div class="message-meta" style="${msg.message_type === 'sticker' ? 'position: absolute; bottom: 0; right: -40px; background: rgba(0,0,0,0.5); padding: 2px 6px; border-radius: 10px;' : ''}">${metaHtml}</div>
                </div>
            </div>
        `;
    }

    formatMessageText(text) {
        if (!text) return '';
        let html = UI.escapeHtml(text);
        html = html.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" style="color: var(--accent-light)">$1</a>');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        html = html.replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">$1</code>');
        return html;
    }

    // ==================== SEND ====================

    async sendMessage() {
        const input = document.getElementById('message-input');
        if (!input) return;

        const content = input.value.trim();
        if (!content || !this.currentChatId) return;

        // Просто отправляем — сервер сохранит и пришлёт обратно
        wsManager.sendMessage(this.currentChatId, content, {
            replyToId: this.replyTo ? this.replyTo.id : null
        });

        // Очищаем поле
        input.value = '';
        UI.autoResize(input);
        this.cancelReply();
        input.focus();
    }

    onNewMessage(msg) {
        const chatId = msg.chat_id;
        if (!this.messages[chatId]) {
            this.messages[chatId] = [];
        }

        // Не добавляем дубликаты
        const exists = this.messages[chatId].some(m => m.id === msg.id);
        if (!exists) {
            this.messages[chatId].push(msg);
        }

        // Рендерим если текущий чат
        if (chatId === this.currentChatId) {
            this.renderMessages(chatId);
        }

        // Обновляем превью в списке
        const lastMsgEl = document.getElementById(`last-msg-${chatId}`);
        const timeEl = document.getElementById(`chat-time-${chatId}`);
        if (lastMsgEl) lastMsgEl.textContent = (msg.content || msg.file_name || '📎').substring(0, 40);
        if (timeEl) timeEl.textContent = UI.formatTime(msg.created_at);

        // Уведомление если не текущий чат и не своё сообщение
        if (chatId !== this.currentChatId && msg.sender_id !== this.currentUser.user_id) {
            UI.toast(`${msg.sender_name}: ${(msg.content || '📎').substring(0, 50)}`, 'info');
            this.playNotificationSound();
        }

        // Скрываем typing
        const typingEl = document.getElementById('typing-indicator');
        if (typingEl) typingEl.classList.add('hidden');
    }

    // ==================== FILES ====================

    async handleFileUpload(e) {
        const files = e.target.files;
        if (!files.length || !this.currentChatId) return;

        for (const file of files) {
            try {
                UI.toast(`Загрузка ${file.name}...`, 'info');
                const result = await api.uploadFile(file, this.currentChatId);

                // Определяем тип
                let messageType = 'file';
                if (file.type.startsWith('image/')) {
                    messageType = 'image';
                } else if (file.type.startsWith('video/')) {
                    messageType = 'video';
                } else if (file.type.startsWith('audio/')) {
                    messageType = 'voice';
                }

                // Отправляем сообщение с файлом
                wsManager.sendMessage(this.currentChatId, file.name, {
                    messageType: messageType,
                    fileUrl: result.url,
                    fileName: file.name,
                    fileSize: result.file_size,
                    mimeType: result.mime_type || file.type
                });

                UI.toast(`${file.name} отправлен!`, 'success');
            } catch (error) {
                UI.toast(`Ошибка: ${error.message}`, 'error');
            }
        }
        e.target.value = '';
    }

    // ==================== REPLY ====================

    setReply(messageId) {
        const msg = (this.messages[this.currentChatId] || []).find(m => m.id === messageId);
        if (!msg) return;

        this.replyTo = msg;
        const preview = document.getElementById('reply-preview');
        if (preview) {
            preview.classList.remove('hidden');
            const author = preview.querySelector('.reply-author');
            const text = preview.querySelector('.reply-text');
            if (author) author.textContent = msg.sender_name || 'Unknown';
            if (text) text.textContent = (msg.content || '📎 Файл').substring(0, 60);
        }

        const input = document.getElementById('message-input');
        if (input) input.focus();
    }

    cancelReply() {
        this.replyTo = null;
        const preview = document.getElementById('reply-preview');
        if (preview) preview.classList.add('hidden');
    }

    // ==================== CONTEXT MENU ====================

    showMessageMenu(event, messageId) {
        event.preventDefault();
        document.querySelectorAll('.context-menu').forEach(m => m.remove());

        const msg = (this.messages[this.currentChatId] || []).find(m => m.id === messageId);
        if (!msg || msg.is_deleted) return;

        const isOwn = msg.sender_id === this.currentUser.user_id;
        const menu = document.createElement('div');
        menu.className = 'context-menu';

        let items = `
            <div class="context-menu-item" onclick="app.setReply('${messageId}')">↩️ Ответить</div>
            <div class="context-menu-item" onclick="app.copyMessage('${messageId}')">📋 Копировать</div>
        `;

        if (isOwn) {
            items += `<div class="context-menu-item danger" onclick="app.deleteMessage('${messageId}')">🗑️ Удалить</div>`;
        }

        menu.innerHTML = items;
        menu.style.left = `${Math.min(event.clientX, window.innerWidth - 180)}px`;
        menu.style.top = `${Math.min(event.clientY, window.innerHeight - 150)}px`;

        document.body.appendChild(menu);
        setTimeout(() => {
            document.addEventListener('click', () => menu.remove(), { once: true });
        }, 10);
    }

    copyMessage(messageId) {
        const msg = (this.messages[this.currentChatId] || []).find(m => m.id === messageId);
        if (msg && msg.content) {
            navigator.clipboard.writeText(msg.content);
            UI.toast('Скопировано!', 'success');
        }
    }

    async deleteMessage(messageId) {
        try {
            await api.deleteMessage(messageId);
            const msgs = this.messages[this.currentChatId] || [];
            const msg = msgs.find(m => m.id === messageId);
            if (msg) {
                msg.is_deleted = true;
                msg.content = null;
            }
            this.renderMessages(this.currentChatId);
            UI.toast('Сообщение удалено', 'info');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    // ==================== TYPING ====================

    handleTyping() {
        if (!this.currentChatId) return;
        if (this.typingTimer) clearTimeout(this.typingTimer);
        wsManager.sendTyping(this.currentChatId);
        this.typingTimer = setTimeout(() => { this.typingTimer = null; }, 3000);
    }

    // ==================== WS HANDLERS ====================

    onNewMessage(msg) {
        const chatId = msg.chat_id;
        if (!this.messages[chatId]) {
            this.messages[chatId] = [];
        }

        const exists = this.messages[chatId].some(m => m.id === msg.id);
        if (!exists) {
            this.messages[chatId].push(msg);
        }

        if (chatId === this.currentChatId) {
            this.renderMessages(chatId);
        }

        const lastMsgEl = document.getElementById(`last-msg-${chatId}`);
        const timeEl = document.getElementById(`chat-time-${chatId}`);
        if (lastMsgEl) lastMsgEl.textContent = (msg.content || msg.file_name || '📎').substring(0, 40);
        if (timeEl) timeEl.textContent = UI.formatTime(msg.created_at);

        if (chatId !== this.currentChatId) {
            UI.toast(`${msg.sender_name}: ${(msg.content || '📎').substring(0, 50)}`, 'info');
            this.playNotificationSound();
        }

        const typingEl = document.getElementById('typing-indicator');
        if (typingEl) typingEl.classList.add('hidden');
    }

    onTyping(data) {
        if (data.chat_id !== this.currentChatId) return;
        if (data.user_id === this.currentUser.user_id) return;

        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.classList.remove('hidden');
            clearTimeout(this.typingHideTimer);
            this.typingHideTimer = setTimeout(() => {
                indicator.classList.add('hidden');
            }, 3000);
        }
    }

    onRead(data) { }

    onMessageEdited(data) {
        if (!this.currentChatId) return;
        const msgs = this.messages[this.currentChatId] || [];
        const msg = msgs.find(m => m.id === data.message_id);
        if (msg) {
            msg.content = data.content;
            msg.is_edited = true;
            this.renderMessages(this.currentChatId);
        }
    }

    // ==================== GROUP MANAGEMENT ====================

    async showChatInfo() {
        if (!this.currentChatId) return;

        try {
            const info = await api.getChatInfo(this.currentChatId);

            document.getElementById('info-chat-name').textContent = info.name || 'Информация';

            // Инвайт ссылка
            const inviteSection = document.getElementById('invite-section');
            const inviteInput = document.getElementById('invite-link');
            if (info.invite_code) {
                inviteSection.style.display = 'block';
                inviteInput.value = info.invite_code;
            } else {
                inviteSection.style.display = 'none';
            }

            // Количество
            document.getElementById('members-count').textContent = info.members.length;

            // Список участников
            const membersList = document.getElementById('members-list');
            const myRole = info.members.find(m => m.user_id === this.currentUser.user_id)?.role;

            membersList.innerHTML = info.members.map(m => {
                const isMe = m.user_id === this.currentUser.user_id;
                const roleIcon = m.role === 'owner' ? '👑' : m.role === 'admin' ? '⭐' : '';
                const onlineIcon = m.is_online ? '🟢' : '⚫';
                const canRemove = (myRole === 'owner' || myRole === 'admin') && !isMe && m.role !== 'owner';

                return `
                    <div class="chat-item" style="padding: 8px 12px;">
                        <div class="avatar small" style="background: ${UI.getAvatarColor(m.display_name)}">
                            ${UI.getInitials(m.display_name)}
                        </div>
                        <div class="chat-item-info">
                            <div class="chat-item-name">
                                ${roleIcon} ${UI.escapeHtml(m.display_name)} ${isMe ? '(вы)' : ''}
                            </div>
                            <div class="chat-item-last-message">
                                ${onlineIcon} @${UI.escapeHtml(m.username)}
                            </div>
                        </div>
                        ${canRemove ? `
                            <button class="icon-btn" style="color: #EF4444; font-size: 14px;"
                                    onclick="app.removeMember('${m.user_id}')"
                                    title="Удалить из группы">✕</button>
                        ` : ''}
                    </div>
                `;
            }).join('');

            // Очищаем поиск
            document.getElementById('add-member-search').value = '';
            document.getElementById('add-member-results').innerHTML = '';

            UI.showModal('modal-chat-info');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async searchMembersToAdd(query) {
        const container = document.getElementById('add-member-results');
        if (!container) return;

        if (query.length < 2) {
            container.innerHTML = '';
            return;
        }

        try {
            const data = await api.request('GET', `/auth/search/${encodeURIComponent(query)}`);
            const users = data.users || [];

            if (users.length === 0) {
                container.innerHTML = '<p style="color: #6b6b80; font-size: 13px; padding: 4px;">Никого не найдено</p>';
                return;
            }

            container.innerHTML = users.map(u => `
                <div class="chat-item" style="padding: 6px 12px; cursor: pointer;"
                     onclick="app.addMemberToGroup('${u.user_id}', '${UI.escapeHtml(u.display_name)}')">
                    <div class="avatar small" style="background: ${UI.getAvatarColor(u.display_name)}; width: 28px; height: 28px; font-size: 11px;">
                        ${UI.getInitials(u.display_name)}
                    </div>
                    <div class="chat-item-info">
                        <div class="chat-item-name" style="font-size: 13px;">${UI.escapeHtml(u.display_name)}</div>
                    </div>
                    <span style="font-size: 18px; color: #10B981;">+</span>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = '';
        }
    }

    async addMemberToGroup(userId, displayName) {
        if (!this.currentChatId) return;

        try {
            await api.addMember(this.currentChatId, userId);
            UI.toast(`${displayName} добавлен в группу!`, 'success');
            await this.showChatInfo();
            await this.loadChats();
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async removeMember(userId) {
        if (!this.currentChatId) return;

        try {
            await api.removeMember(this.currentChatId, userId);
            UI.toast('Участник удалён', 'info');
            await this.showChatInfo();
            await this.loadChats();
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    copyInviteLink() {
        const input = document.getElementById('invite-link');
        if (input && input.value) {
            navigator.clipboard.writeText(input.value);
            UI.toast('Инвайт-код скопирован! Отправьте его другу', 'success');
        }
    }

    async leaveGroup() {
        if (!this.currentChatId) return;

        if (!confirm('Вы уверены что хотите покинуть группу?')) return;

        try {
            await api.leaveChat(this.currentChatId);
            UI.hideAllModals();
            this.currentChatId = null;

            document.getElementById('no-chat-selected').classList.remove('hidden');
            document.getElementById('chat-header').classList.add('hidden');
            document.getElementById('messages-container').classList.add('hidden');
            document.getElementById('message-input-area').classList.add('hidden');

            await this.loadChats();
            UI.toast('Вы покинули группу', 'info');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async joinByInvite() {
        const input = document.getElementById('join-invite-code');
        if (!input) return;

        const code = input.value.trim();
        if (!code) {
            UI.toast('Введите инвайт-код', 'error');
            return;
        }

        try {
            const chat = await api.joinByInvite(code);
            UI.hideAllModals();
            input.value = '';
            await this.loadChats();
            await this.selectChat(chat.id);
            UI.toast(`Вы присоединились к "${chat.name}"!`, 'success');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    // ==================== STICKERS ====================

    async toggleStickerPanel() {
        const panel = document.getElementById('sticker-panel');
        if (!panel) return;

        if (panel.classList.contains('hidden')) {
            await this.loadStickers();
            panel.classList.remove('hidden');
        } else {
            panel.classList.add('hidden');
        }
    }

    async loadStickers() {
        try {
            this.stickerPacks = await api.getMyStickers();
            this.renderStickerTabs();
            if (this.stickerPacks.length > 0) {
                this.selectStickerPack(0);
            } else {
                const grid = document.getElementById('sticker-grid');
                if (grid) grid.innerHTML = '<p style="color: #6b6b80; text-align: center; padding: 20px; grid-column: 1/-1;">Нет стикеров. Нажмите ➕ чтобы создать пак</p>';
            }
        } catch (error) {
            console.error('Ошибка загрузки стикеров:', error);
        }
    }

    renderStickerTabs() {
        const tabs = document.getElementById('sticker-tabs');
        if (!tabs || !this.stickerPacks) return;

        tabs.innerHTML = this.stickerPacks.map((pack, i) => {
            const cover = pack.cover_url
                ? `<img src="${pack.cover_url}" alt="${pack.name}">`
                : `<span class="tab-emoji">📦</span>`;
            return `
                <button class="sticker-tab ${i === this.currentPackIndex ? 'active' : ''}"
                        onclick="app.selectStickerPack(${i})"
                        title="${UI.escapeHtml(pack.name)}">
                    ${cover}
                </button>
            `;
        }).join('');
    }

    selectStickerPack(index) {
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

        grid.innerHTML = pack.stickers.map(s => `
            <div class="sticker-item" onclick="app.sendSticker('${s.file_url}')" title="${s.emoji}">
                <img src="${s.file_url}" alt="${s.emoji}" loading="lazy">
            </div>
        `).join('');

        // Добавляем кнопку управления если это мой пак
        if (pack.creator_id === this.currentUser.user_id) {
            grid.innerHTML += `
                <div class="sticker-item" onclick="app.managePack('${pack.id}')" 
                     style="border: 2px dashed #2a2a4a; font-size: 24px;" title="Управление">
                    ⚙️
                </div>
            `;
        }
    }

    sendSticker(fileUrl) {
        if (!this.currentChatId) return;

        wsManager.sendMessage(this.currentChatId, '', {
            messageType: 'sticker',
            fileUrl: fileUrl,
            fileName: 'sticker',
            mimeType: 'image/png'
        });

        // Закрываем панель
        const panel = document.getElementById('sticker-panel');
        if (panel) panel.classList.add('hidden');
    }

    showCreatePack() {
        UI.showModal('modal-create-pack');
    }

    async createPack() {
        const nameInput = document.getElementById('pack-name');
        const descInput = document.getElementById('pack-description');
        if (!nameInput) return;

        const name = nameInput.value.trim();
        if (!name) {
            UI.toast('Введите название', 'error');
            return;
        }

        try {
            const pack = await api.createStickerPack(name, descInput?.value?.trim() || '');
            UI.hideAllModals();
            nameInput.value = '';
            if (descInput) descInput.value = '';
            UI.toast(`Пак "${name}" создан!`, 'success');

            // Открываем управление
            this.managePack(pack.id);
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async managePack(packId) {
        this.currentManagePackId = packId;

        try {
            // Загружаем свежие данные
            await this.loadStickers();
            const pack = this.stickerPacks.find(p => p.id === packId);
            if (!pack) {
                UI.toast('Пак не найден', 'error');
                return;
            }

            document.getElementById('manage-pack-title').textContent = `Управление: ${pack.name}`;

            const container = document.getElementById('manage-pack-stickers');
            if (container) {
                container.innerHTML = pack.stickers.map(s => `
                    <div style="position: relative;">
                        <img src="${s.file_url}" style="width: 100%; aspect-ratio: 1; object-fit: contain; border-radius: 8px; background: #1a1a3e;">
                        <button onclick="app.deleteSticker('${s.id}')"
                                style="position: absolute; top: -4px; right: -4px; width: 20px; height: 20px; border-radius: 50%; background: #EF4444; border: none; color: white; cursor: pointer; font-size: 10px;">✕</button>
                    </div>
                `).join('');
            }

            // Привязываем загрузку файла
            const fileInput = document.getElementById('sticker-file-input');
            if (fileInput) {
                fileInput.onchange = async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    const emoji = document.getElementById('sticker-emoji')?.value || '😀';

                    try {
                        UI.toast('Загрузка стикера...', 'info');
                        await api.uploadSticker(packId, file, emoji);
                        UI.toast('Стикер добавлен!', 'success');
                        await this.managePack(packId);
                    } catch (error) {
                        UI.toast(error.message, 'error');
                    }

                    fileInput.value = '';
                };
            }

            UI.showModal('modal-manage-pack');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async deleteSticker(stickerId) {
        try {
            await api.deleteSticker(stickerId);
            UI.toast('Стикер удалён', 'info');
            if (this.currentManagePackId) {
                await this.managePack(this.currentManagePackId);
            }
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async deleteCurrentPack() {
        if (!this.currentManagePackId) return;
        if (!confirm('Удалить этот стикерпак?')) return;

        try {
            await api.deleteStickerPack(this.currentManagePackId);
            UI.hideAllModals();
            UI.toast('Пак удалён', 'info');
            await this.loadStickers();
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async showBrowsePacks() {
        try {
            const packs = await api.browseStickerPacks();
            const container = document.getElementById('browse-packs-list');
            if (!container) return;

            if (packs.length === 0) {
                container.innerHTML = '<p style="color: #6b6b80; text-align: center;">Нет доступных паков</p>';
            } else {
                container.innerHTML = packs.map(pack => `
                    <div class="pack-preview">
                        <div class="pack-preview-stickers">
                            ${pack.stickers.slice(0, 3).map(s => `<img src="${s.file_url}" alt="${s.emoji}">`).join('')}
                        </div>
                        <div class="pack-info">
                            <h4>${UI.escapeHtml(pack.name)}</h4>
                            <span>${pack.sticker_count} стикеров</span>
                        </div>
                        ${pack.is_installed
                        ? '<button class="btn-secondary" style="padding: 4px 12px; font-size: 12px;" disabled>Установлен</button>'
                        : `<button class="btn-primary" style="padding: 4px 12px; font-size: 12px;" onclick="app.installPack('${pack.id}')">Добавить</button>`
                    }
                    </div>
                `).join('');
            }

            UI.showModal('modal-browse-packs');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async installPack(packId) {
        try {
            await api.installStickerPack(packId);
            UI.toast('Пак установлен!', 'success');
            await this.showBrowsePacks();
            await this.loadStickers();
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    getCurrentChat() {
        return this.chats.find(c => c.id === this.currentChatId);
    }

    playNotificationSound() {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            gainNode.gain.value = 0.1;
            oscillator.start();
            oscillator.stop(audioCtx.currentTime + 0.15);
        } catch (e) { }
    }
    // ==================== STICKERS ====================

    async getMyStickers() {
        return await this.request('GET', '/stickers/packs');
    }

    async browseStickerPacks() {
        return await this.request('GET', '/stickers/packs/browse');
    }

    async createStickerPack(name, description = '') {
        return await this.request('POST', '/stickers/packs', { name, description });
    }

    async updateStickerPack(packId, data) {
        return await this.request('PUT', `/stickers/packs/${packId}`, data);
    }

    async deleteStickerPack(packId) {
        return await this.request('DELETE', `/stickers/packs/${packId}`);
    }

    async installStickerPack(packId) {
        return await this.request('POST', `/stickers/packs/${packId}/install`);
    }

    async uninstallStickerPack(packId) {
        return await this.request('DELETE', `/stickers/packs/${packId}/install`);
    }

    async uploadSticker(packId, file, emoji = '😀') {
        const formData = new FormData();
        formData.append('file', file);

        const url = `${this.baseUrl}/stickers/packs/${packId}/stickers?emoji=${encodeURIComponent(emoji)}`;

        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${this.token}` },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка загрузки стикера');
        }

        return await response.json();
    }

    async deleteSticker(stickerId) {
        return await this.request('DELETE', `/stickers/stickers/${stickerId}`);
    }
}

const app = new MessengerApp();