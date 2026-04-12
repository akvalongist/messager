class API {
    constructor() {
        this.baseUrl = '/api';
        this.token = localStorage.getItem('token');
    }

    setToken(token) {
        this.token = token;
        localStorage.setItem('token', token);
    }

    clearToken() {
        this.token = null;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }

    buildHeaders(extraHeaders = {}) {
        const headers = { ...extraHeaders };
        if (this.token) {
            headers.Authorization = `Bearer ${this.token}`;
        }
        return headers;
    }

    async parseResponse(response, fallbackMessage) {
        let data = null;
        try {
            data = await response.json();
        } catch (error) {
            data = null;
        }

        if (!response.ok) {
            throw new Error(data?.detail || fallbackMessage);
        }

        return data;
    }

    async request(method, path, body = null) {
        const options = {
            method,
            headers: this.buildHeaders({ 'Content-Type': 'application/json' })
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${path}`, options);
            return await this.parseResponse(response, 'Server error');
        } catch (error) {
            if (error.message === 'Failed to fetch') {
                throw new Error('No connection to server');
            }
            throw error;
        }
    }

    async requestForm(path, formData, fallbackMessage) {
        try {
            const response = await fetch(`${this.baseUrl}${path}`, {
                method: 'POST',
                headers: this.buildHeaders(),
                body: formData
            });
            return await this.parseResponse(response, fallbackMessage);
        } catch (error) {
            if (error.message === 'Failed to fetch') {
                throw new Error('No connection to server');
            }
            throw error;
        }
    }

    async register(username, displayName, password, email = null) {
        const body = { username, display_name: displayName, password };
        if (email) body.email = email;

        const data = await this.request('POST', '/auth/register', body);
        this.setToken(data.token);
        localStorage.setItem('user', JSON.stringify(data));
        return data;
    }

    async login(username, password) {
        const data = await this.request('POST', '/auth/login', { username, password });
        this.setToken(data.token);
        localStorage.setItem('user', JSON.stringify(data));
        return data;
    }

    async getMe() {
        return await this.request('GET', '/auth/me');
    }

    async getChats() {
        return await this.request('GET', '/chats/');
    }

    async createDirectChat(userId) {
        return await this.request('POST', '/chats/direct', { user_id: userId });
    }

    async createGroup(name, description = '', memberIds = []) {
        return await this.request('POST', '/chats/group', {
            name,
            description,
            member_ids: memberIds
        });
    }

    async getChatInfo(chatId) {
        return await this.request('GET', `/chats/${chatId}/info`);
    }

    async addMember(chatId, userId) {
        return await this.request('POST', `/chats/${chatId}/members`, { user_id: userId });
    }

    async removeMember(chatId, userId) {
        return await this.request('DELETE', `/chats/${chatId}/members/${userId}`);
    }

    async leaveChat(chatId) {
        return await this.request('POST', `/chats/${chatId}/leave`);
    }

    async joinByInvite(inviteCode) {
        return await this.request('POST', `/chats/join/${inviteCode}`);
    }

    async getMessages(chatId, limit = 50, before = null) {
        let url = `/messages/${chatId}?limit=${limit}`;
        if (before) url += `&before=${before}`;
        return await this.request('GET', url);
    }

    async deleteMessage(messageId) {
        return await this.request('DELETE', `/messages/${messageId}`);
    }

    async uploadFile(file, chatId = null) {
        const formData = new FormData();
        formData.append('file', file);

        let path = '/files/upload';
        if (chatId) path += `?chat_id=${chatId}`;
        return await this.requestForm(path, formData, 'File upload failed');
    }

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
        return await this.requestForm(
            `/stickers/packs/${packId}/stickers?emoji=${encodeURIComponent(emoji)}`,
            formData,
            'Sticker upload failed'
        );
    }

    async deleteSticker(stickerId) {
        return await this.request('DELETE', `/stickers/stickers/${stickerId}`);
    }

    async uploadAvatar(file) {
        const formData = new FormData();
        formData.append('file', file);
        return await this.requestForm('/auth/me/avatar', formData, 'Avatar upload failed');
    }

    async getNotifications() {
        return await this.request('GET', '/notifications/');
    }

    async markNotificationsRead() {
        return await this.request('POST', '/notifications/read-all');
    }
}

const api = new API();
