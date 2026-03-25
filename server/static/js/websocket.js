/**
 * WebSocket менеджер
 */
class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000;
        this.handlers = {};
        this.typingTimeout = null;
    }

    connect(token) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('🔌 WebSocket подключён');
            // Отправляем токен для аутентификации
            this.ws.send(JSON.stringify({ token }));
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.emit('connected');
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Ошибка парсинга WS:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('🔌 WebSocket отключён');
            this.isConnected = false;
            this.emit('disconnected');
            this.tryReconnect(token);
        };

        this.ws.onerror = (error) => {
            console.error('WS ошибка:', error);
        };
    }

    tryReconnect(token) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`🔄 Переподключение... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(token), this.reconnectDelay);
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    handleMessage(data) {
        const type = data.type;
        console.log('📨 WS:', type, data);

        switch (type) {
            case 'connected':
                this.emit('authenticated', data);
                break;
            case 'new_message':
                this.emit('new_message', data.message);
                break;
            case 'typing':
                this.emit('typing', data);
                break;
            case 'read':
                this.emit('read', data);
                break;
            case 'message_edited':
                this.emit('message_edited', data);
                break;
            case 'notification':
                this.emit('notification', data.notification);
                break;
            default:
                console.log('Неизвестный тип WS:', type);
        }
    }

    // Отправка сообщения
    sendMessage(chatId, content, options = {}) {
        this.send({
            type: 'message',
            chat_id: chatId,
            content: content,
            message_type: options.messageType || 'text',
            reply_to_id: options.replyToId || null,
            file_url: options.fileUrl || null,
            file_name: options.fileName || null,
            file_size: options.fileSize || null,
            mime_type: options.mimeType || null
        });
    }

    // Индикатор набора
    sendTyping(chatId) {
        this.send({
            type: 'typing',
            chat_id: chatId
        });
    }

    // Прочитано
    sendRead(chatId, messageId) {
        this.send({
            type: 'read',
            chat_id: chatId,
            message_id: messageId
        });
    }

    // Редактирование
    sendEdit(messageId, content) {
        this.send({
            type: 'edit',
            message_id: messageId,
            content: content
        });
    }

    send(data) {
        if (this.ws && this.isConnected) {
            this.ws.send(JSON.stringify(data));
        }
    }

    // Event system
    on(event, callback) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(callback);
    }

    off(event, callback) {
        if (this.handlers[event]) {
            this.handlers[event] = this.handlers[event].filter(cb => cb !== callback);
        }
    }

    emit(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(cb => cb(data));
        }
    }
}

const wsManager = new WebSocketManager();