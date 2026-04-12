MessengerApp.prototype.showAuth = function showAuth() {
    this.resetSessionState?.();
    document.getElementById('auth-screen')?.classList.add('active');
    document.getElementById('chat-screen')?.classList.remove('active');
};

MessengerApp.prototype.logout = function logout() {
    api.clearToken();
    wsManager.disconnect();
    this.resetSessionState?.();
    document.getElementById('chat-screen')?.classList.remove('active');
    document.getElementById('auth-screen')?.classList.add('active');
    UI.toast('Вы вышли', 'info');
};

MessengerApp.prototype.enterChat = async function enterChat() {
    document.getElementById('auth-screen')?.classList.remove('active');
    document.getElementById('chat-screen')?.classList.add('active');

    const displayName = this.currentUser.display_name || this.currentUser.username;
    const nameEl = document.getElementById('my-display-name');
    if (nameEl) nameEl.textContent = displayName;

    const avatarEl = document.getElementById('my-avatar');
    if (avatarEl) avatarEl.textContent = UI.getInitials(displayName);

    const idEl = document.getElementById('my-user-id');
    if (idEl) idEl.textContent = `ID: ${this.currentUser.user_id.substring(0, 8)}...`;

    this.syncState?.();
    this.updateMyAvatars();
    wsManager.connect(api.token);
    await this.loadChats();
    UI.toast(`Привет, ${displayName}!`, 'success');
};
