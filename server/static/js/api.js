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

    async request(method, path, body = null) {
        const headers = {
            'Content-Type': 'application/json',
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const options = { method, headers };

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${path}`, options);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка сервера');
            }

            return data;
        } catch (error) {
            if (error.message === 'Failed to fetch') {
                throw new Error('Нет подключения к серверу');
            }
            throw error;
        }
    }

    // ==================== AUTH ====================

    async register(username, displayName, password, email = null) {
        const body = {
            username,
            display_name: displayName,
            password,
        };
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

    // ==================== CHATS ====================

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

    // ==================== MESSAGES ====================

    async getMessages(chatId, limit = 50, before = null) {
        let url = `/messages/${chatId}?limit=${limit}`;
        if (before) url += `&before=${before}`;
        return await this.request('GET', url);
    }

    async deleteMessage(messageId) {
        return await this.request('DELETE', `/messages/${messageId}`);
    }

    // ==================== FILES ====================

    async uploadFile(file, chatId = null) {
        const formData = new FormData();
        formData.append('file', file);

        let url = `${this.baseUrl}/files/upload`;
        if (chatId) url += `?chat_id=${chatId}`;

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка загрузки файла');
        }

        return await response.json();
    }

    // ==================== GROUP MANAGEMENT ====================

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
    // ==================== AVATAR ====================

    async uploadAvatar(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${this.baseUrl}/auth/me/avatar`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка загрузки аватарки');
        }

        return await response.json();
    }
}

const api = new API();