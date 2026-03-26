/**
 * API клиент для мессенджера
 */
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

    async joinByInvite(inviteCode) {
        return await this.request('POST', `/chats/join/${inviteCode}`);
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
}

const api = new API();