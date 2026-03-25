/**
 * XAM Messenger — Главное приложение
 */
class MessengerApp {
    constructor() {
        this.currentUser = null;
        this.currentChatId = null;
        this.chats = [];
        this.messages = {};
        this.replyTo = null;
        this.typingTimer = null;

        this.init();
    }

    async init() {
        this.bindEvents();

        // Проверяем авторизацию
        const savedUser = localStorage.getItem('user');
        const savedToken = localStorage.getItem('token');

        if (savedUser && savedToken) {
            try {
                api.token = savedToken;
                this.currentUser = JSON.parse(savedUser);
                await this.enterChat();
            } catch (e) {
                console.log('Токен устарел:', e);
                this.showAuth();
            }
        } else {
            this.showAuth();
        }
    }

    // ==================== EVENTS ====================

    bindEvents() {
        // Auth
        document.getElementById('login-form').addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('register-form').addEventListener('submit', (e) => this.handleRegister(e));
        document.getElementById('show-register').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('login-form').classList.remove('active');
            document.getElementById('register-form').classList.add('active');
        });
        document.getElementById('show-login').addEventListener('click', (e) => {
            e.preventDefault();
            document.getElementById('register-form').classList.remove('active');
            document.getElementById('login-form').classList.add('active');
        });

        // Sidebar
        document.getElementById('btn-new-chat').addEventListener('click', () => UI.showModal('modal-new-chat'));
        document.getElementById('btn-new-group').addEventListener('click', () => UI.showModal('modal-new-group'));
        document.getElementById('btn-logout').addEventListener('click', () => this.logout());

        // Modals
        document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
            btn.addEventListener('click', () => UI.hideAllModals());
        });
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) UI.hideAllModals();
            });
        });

        // Create chat/group
        document.getElementById('btn-create-direct').addEventListener('click', () => this.createDirectChat());
        document.getElementById('btn-create-group').addEventListener('click', () => this.createGroup());

        // Message input
        const input = document.getElementById('message-input');
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

        document.getElementById('btn-send').addEventListener('click', () => this.sendMessage());

        // File upload
        document.getElementById('btn-attach').addEventListener('click', () => {
            document.getElementById('file-input').click();
        });
        document.getElementById('file-input').addEventListener('change', (e) => this.handleFileUpload(e));

        // Reply cancel
        document.getElementById('btn-cancel-reply').addEventListener('click', () => this.cancelReply());

        // Mobile back
        document.getElementById('btn-back').addEventListener('click', () => this.showSidebar());

        // Search
        document.getElementById('search-chats').addEventListener('input', (e) => this.filterChats(e.target.value));

        // Context menu close
        document.addEventListener('click', () => {
            document.querySelectorAll('.context-menu').forEach(m => m.remove());
        });

        // WebSocket events
        wsManager.on('new_message', (msg) => this.onNewMessage(msg));
        wsManager.on('typing', (data) => this.onTyping(data));
        wsManager.on('read', (data) => this.onRead(data));
        wsManager.on('message_edited', (data) => this.onMessageEdited(data));
        wsManager.on('connected', () => UI.toast('Подключено', 'success'));
        wsManager.on('disconnected', () => UI.toast('Переподключение...', 'error'));
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
        UI.toast('Вы вышли из аккаунта', 'info');
    }

    // ==================== MAIN SCREEN ====================
    async enterChat() {
        document.getElementById('auth-screen').classList.remove('active');
        document.getElementById('chat-screen').classList.add('active');

        const displayName = this.currentUser.display_name || this.currentUser.username;
        document.getElementById('my-display-name').textContent = displayName;
        document.getElementById('my-avatar').textContent = UI.getInitials(displayName);

        // Показываем ID в сайдбаре
        const idEl = document.getElementById('my-user-id');
        if (idEl) {
            idEl.textContent = `ID: ${this.currentUser.user_id.substring(0, 8)}... 📋`;
        }

        wsManager.connect(api.token);
        await this.loadChats();

        UI.toast(`Привет, ${displayName}! 👋`, 'success');
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

        // Обновляем UI
        document.getElementById('no-chat-selected').classList.add('hidden');
        document.getElementById('chat-header').classList.remove('hidden');
        document.getElementById('messages-container').classList.remove('hidden');
        document.getElementById('message-input-area').classList.remove('hidden');

        // Заголовок
        document.getElementById('chat-name').textContent = chat.name || 'Чат';
        document.getElementById('chat-avatar').textContent =
            chat.chat_type === 'group' ? '👥' : UI.getInitials(chat.name);
        document.getElementById('chat-avatar').style.background = UI.getAvatarColor(chat.name);
        document.getElementById('chat-status').textContent =
            chat.chat_type === 'group' ? `${chat.members_count} участников` : '';

        // Подсвечиваем активный чат
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.toggle('active', item.dataset.chatId === chatId);
        });

        // Загружаем сообщения
        await this.loadMessages(chatId);

        // Фокус на поле ввода
        document.getElementById('message-input').focus();

        // Мобилка: скрываем сайдбар
        if (window.innerWidth <= 768) {
            document.getElementById('sidebar').classList.add('hidden-mobile');
        }
    }

    showSidebar() {
        document.getElementById('sidebar').classList.remove('hidden-mobile');
    }

    filterChats(query) {
        const items = document.querySelectorAll('.chat-item');
        const q = query.toLowerCase();

        items.forEach(item => {
            const name = item.querySelector('.chat-item-name').textContent.toLowerCase();
            item.style.display = name.includes(q) ? '' : 'none';
        });
    }

    async createDirectChat() {
        const userId = document.getElementById('new-chat-user-id').value.trim();
        if (!userId) {
            UI.toast('Введите ID пользователя', 'error');
            return;
        }

        try {
            const chat = await api.createDirectChat(userId);
            UI.hideAllModals();
            document.getElementById('new-chat-user-id').value = '';
            await this.loadChats();
            await this.selectChat(chat.id);
            UI.toast('Чат создан!', 'success');
        } catch (error) {
            UI.toast(error.message, 'error');
        }
    }

    async createGroup() {
        const name = document.getElementById('group-name').value.trim();
        const description = document.getElementById('group-description').value.trim();

        if (!name) {
            UI.toast('Введите название группы', 'error');
            return;
        }

        try {
            const chat = await api.createGroup(name, description);
            UI.hideAllModals();
            document.getElementById('group-name').value = '';
            document.getElementById('group-description').value = '';
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
            // Разделитель дат
            const msgDate = new Date(msg.created_at).toDateString();
            if (msgDate !== lastDate) {
                html += `<div class="date-separator">${UI.formatDateSeparator(msg.created_at)}</div>`;
                lastDate = msgDate;
            }

            html += this.renderMessage(msg);
        });

        container.innerHTML = html;

        // Скролл вниз
        const messagesContainer = document.getElementById('messages-container');
        UI.scrollToBottom(messagesContainer);

        // Обновляем последнее сообщение в списке чатов
        if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            const lastMsgEl = document.getElementById(`last-msg-${chatId}`);
            const timeEl = document.getElementById(`chat-time-${chatId}`);

            if (lastMsgEl) {
                const preview = lastMsg.is_deleted ? 'Сообщение удалено' :
                    (lastMsg.content || lastMsg.file_name || '📎 Файл');
                lastMsgEl.textContent = preview.substring(0, 40);
            }
            if (timeEl) {
                timeEl.textContent = UI.formatTime(lastMsg.created_at);
            }
        }
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

        // Reply
        if (msg.reply_to_id) {
            const replyMsg = (this.messages[this.currentChatId] || []).find(m => m.id === msg.reply_to_id);
            if (replyMsg) {
                contentHtml += `
                    <div class="message-reply">
                        <div class="message-reply-author">${UI.escapeHtml(replyMsg.sender_name || 'Unknown')}</div>
                        <div class="message-reply-text">${UI.escapeHtml((replyMsg.content || '').substring(0, 60))}</div>
                    </div>
                `;
            }
        }

        // Sender name (для групп)
        if (!isOwn && msg.sender_name && this.getCurrentChat()?.chat_type === 'group') {
            contentHtml += `<div class="message-sender">${UI.escapeHtml(msg.sender_name)}</div>`;
        }

        // Content
        if (msg.content) {
            contentHtml += `<div class="message-text">${this.formatMessageText(msg.content)}</div>`;
        }

        // File
        if (msg.file_url) {
            if (msg.mime_type && msg.mime_type.startsWith('image/')) {
                contentHtml += `<img class="message-image" src="${msg.file_url}" alt="${msg.file_name || 'image'}" loading="lazy">`;
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

        // Meta
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

        // Ссылки
        html = html.replace(
            /(https?:\/\/[^\s<]+)/g,
            '<a href="$1" target="_blank" style="color: var(--accent-light)">$1</a>'
        );

        // **жирный**
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // *курсив*
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // `код`
        html = html.replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px;">$1</code>');

        return html;
    }

    // ==================== SEND MESSAGE ====================

    async sendMessage() {
        const input = document.getElementById('message-input');
        const content = input.value.trim();

        if (!content && !this.pendingFile) return;
        if (!this.currentChatId) return;

        // Отправляем через WebSocket
        wsManager.sendMessage(this.currentChatId, content, {
            replyToId: this.replyTo?.id || null
        });

        // Очищаем
        input.value = '';
        UI.autoResize(input);
        this.cancelReply();
        input.focus();
    }

    // ==================== FILE UPLOAD ====================

    async handleFileUpload(e) {
        const files = e.target.files;
        if (!files.length || !this.currentChatId) return;

        for (const file of files) {
            try {
                UI.toast(`Загрузка ${file.name}...`, 'info');
                const result = await api.uploadFile(file, this.currentChatId);

                // Отправляем сообщение с файлом
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

        // Очищаем input
        e.target.value = '';
    }

    // ==================== REPLY ====================

    setReply(messageId) {
        const msg = (this.messages[this.currentChatId] || []).find(m => m.id === messageId);
        if (!msg) return;

        this.replyTo = msg;
        const preview = document.getElementById('reply-preview');
        preview.classList.remove('hidden');
        preview.querySelector('.reply-author').textContent = msg.sender_name || 'Unknown';
        preview.querySelector('.reply-text').textContent = (msg.content || '📎 Файл').substring(0, 60);

        document.getElementById('message-input').focus();
    }

    cancelReply() {
        this.replyTo = null;
        document.getElementById('reply-preview').classList.add('hidden');
    }

    // ==================== CONTEXT MENU ====================

    showMessageMenu(event, messageId) {
        event.preventDefault();

        // Удаляем старые меню
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
            items += `
                <div class="context-menu-item danger" onclick="app.deleteMessage('${messageId}')">🗑️ Удалить</div>
            `;
        }

        menu.innerHTML = items;

        // Позиционирование
        menu.style.left = `${Math.min(event.clientX, window.innerWidth - 180)}px`;
        menu.style.top = `${Math.min(event.clientY, window.innerHeight - 150)}px`;

        document.body.appendChild(menu);

        setTimeout(() => {
            document.addEventListener('click', () => menu.remove(), { once: true });
        }, 10);
    }

    copyMessage(messageId) {
        const msg = (this.messages[this.currentChatId] || []).find(m => m.id === messageId);
        if (msg?.content) {
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

        this.typingTimer = setTimeout(() => {
            this.typingTimer = null;
        }, 3000);
    }

    // ==================== WEBSOCKET HANDLERS ====================

    onNewMessage(msg) {
        const chatId = msg.chat_id;

        // Добавляем в массив сообщений
        if (!this.messages[chatId]) {
            this.messages[chatId] = [];
        }
        this.messages[chatId].push(msg);

        // Если это текущий чат — рендерим
        if (chatId === this.currentChatId) {
            this.renderMessages(chatId);
        }

        // Обновляем список чатов
        const lastMsgEl = document.getElementById(`last-msg-${chatId}`);
        const timeEl = document.getElementById(`chat-time-${chatId}`);

        if (lastMsgEl) {
            lastMsgEl.textContent = (msg.content || msg.file_name || '📎 Файл').substring(0, 40);
        }
        if (timeEl) {
            timeEl.textContent = UI.formatTime(msg.created_at);
        }

        // Уведомление если не текущий чат
        if (chatId !== this.currentChatId) {
            UI.toast(`${msg.sender_name}: ${(msg.content || '📎 Файл').substring(0, 50)}`, 'info');

            // Звук уведомления
            this.playNotificationSound();
        }

        // Скрываем typing
        document.getElementById('typing-indicator').classList.add('hidden');
    }

    onTyping(data) {
        if (data.chat_id !== this.currentChatId) return;
        if (data.user_id === this.currentUser.user_id) return;

        const indicator = document.getElementById('typing-indicator');
        indicator.classList.remove('hidden');

        // Скрываем через 3 секунды
        clearTimeout(this.typingHideTimer);
        this.typingHideTimer = setTimeout(() => {
            indicator.classList.add('hidden');
        }, 3000);
    }

    onRead(data) {
        // Можно обновить галочки сообщений
        console.log('Read:', data);
    }

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

    // ==================== HELPERS ====================

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
        } catch (e) {
            // Ignore audio errors
        }
    }
    copyMyId() {
        const id = this.currentUser.user_id;
        navigator.clipboard.writeText(id);
        UI.toast('ID скопирован! Отправьте его собеседнику', 'success');
    }
}


// ==================== ЗАПУСК ====================
const app = new MessengerApp();