MessengerApp.prototype.loadChats = async function loadChats() {
    try {
        const data = await api.getChats();
        this.chats = data.chats || [];
        this.syncState?.();
        this.renderChatList();
    } catch (error) {
        console.error('Chat load failed:', error);
    }
};

MessengerApp.prototype.selectChat = async function selectChat(chatId) {
    this.currentChatId = chatId;
    this.syncState?.();

    const chat = this.chats.find((item) => item.id === chatId);
    if (!chat) return;

    document.getElementById('no-chat-selected')?.classList.add('hidden');
    document.getElementById('chat-header')?.classList.remove('hidden');
    document.getElementById('messages-container')?.classList.remove('hidden');
    document.getElementById('message-input-area')?.classList.remove('hidden');

    const chatName = document.getElementById('chat-name');
    const chatAvatar = document.getElementById('chat-avatar');
    const chatStatus = document.getElementById('chat-status');

    if (chatName) chatName.textContent = chat.name || 'Чат';
    if (chatAvatar) {
        if (chat.avatar_url) {
            chatAvatar.innerHTML = `<img src="${chat.avatar_url}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;">`;
        } else {
            chatAvatar.textContent = chat.chat_type === 'group' ? '👥' : UI.getInitials(chat.name);
            chatAvatar.style.background = UI.getAvatarColor(chat.name);
        }
    }
    if (chatStatus) {
        chatStatus.textContent = chat.chat_type === 'group' ? `${chat.members_count} участников` : '';
    }

    document.querySelectorAll('.chat-item').forEach((item) => {
        item.classList.toggle('active', item.dataset.chatId === chatId);
    });

    await this.loadMessages(chatId);
    document.getElementById('message-input')?.focus();

    if (window.innerWidth <= 768) {
        document.getElementById('sidebar')?.classList.add('hidden-mobile');
    }
};

MessengerApp.prototype.createDirectChat = async function createDirectChat() {
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
        UI.toast('Чат создан', 'success');
    } catch (error) {
        UI.toast(error.message, 'error');
    }
};

MessengerApp.prototype.createGroup = async function createGroup() {
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
        UI.toast(`Группа "${name}" создана`, 'success');
    } catch (error) {
        UI.toast(error.message, 'error');
    }
};
