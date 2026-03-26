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

        if (!isOwn && msg.sender_name) {
            const chat = this.getCurrentChat();
            if (chat && chat.chat_type === 'group') {
                contentHtml += `<div class="message-sender">${UI.escapeHtml(msg.sender_name)}</div>`;
            }
        }

        if (msg.content) {
            contentHtml += `<div class="message-text">${this.formatMessageText(msg.content)}</div>`;
        }

        if (msg.file_url) {
            if (msg.mime_type && msg.mime_type.startsWith('image/')) {
                contentHtml += `<img class="message-image" src="${msg.file_url}" alt="image" loading="lazy">`;
            } else {
                const icon = UI.getFileIcon(msg.mime_type);
                const size = UI.formatFileSize(msg.file_size);
                contentHtml += `
                    <div class="message-file">
                        <a href="${msg.file_url}" target="_blank" download>
                            ${icon} ${UI.escapeHtml(msg.file_name || 'Файл')} ${size ? `(${size})` : ''}
                        </a>
                    </div>
                `;
            }
        }

        let metaHtml = `<span class="message-time">${UI.formatTime(msg.created_at)}</span>`;
        if (msg.is_edited) {
            metaHtml = `<span class="message-edited">ред.</span>` + metaHtml;
        }
        if (isOwn) {
            metaHtml += `<span class="message-status">✓</span>`;
        }

        return `
            <div class="message ${msgClass}" data-message-id="${msg.id}"
                 oncontextmenu="app.showMessageMenu(event, '${msg.id}')">
                <div class="message-bubble">
                    ${contentHtml}
                    <div class="message-meta">${metaHtml}</div>
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

                wsManager.sendMessage(this.currentChatId, '', {
                    messageType: file.type.startsWith('image/') ? 'image' : 'file',
                    fileUrl: result.url,
                    fileName: file.name,
                    fileSize: result.file_size,
                    mimeType: result.mime_type
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
}

const app = new MessengerApp();