MessengerApp.prototype.onNewMessage = function onNewMessage(msg) {
    const chatId = msg.chat_id;
    if (!this.messages[chatId]) {
        this.messages[chatId] = [];
    }

    const exists = this.messages[chatId].some((message) => message.id === msg.id);
    if (!exists) {
        this.messages[chatId].push(msg);
    }

    this.syncState?.();

    if (chatId === this.currentChatId) {
        this.renderMessages(chatId);
    }

    const lastMsgEl = document.getElementById(`last-msg-${chatId}`);
    const timeEl = document.getElementById(`chat-time-${chatId}`);
    if (lastMsgEl) lastMsgEl.textContent = (msg.content || msg.file_name || '📎').substring(0, 40);
    if (timeEl) timeEl.textContent = UI.formatTime(msg.created_at);

    if (chatId !== this.currentChatId && msg.sender_id !== this.currentUser.user_id) {
        UI.toast(`${msg.sender_name}: ${(msg.content || '📎').substring(0, 50)}`, 'info');
        this.playNotificationSound();
    }

    document.getElementById('typing-indicator')?.classList.add('hidden');
};
