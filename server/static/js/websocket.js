class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000;
        this.handlers = {};
        this.token = null;
    }

    connect(token) {
        this.token = token;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('🔌 Подключаюсь к', wsUrl);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('🔌 WebSocket открыт, отправляю токен...');
            this.ws.send(JSON.stringify({ token: token }));
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('📨 WS получено:', data.type, data);

                if (data.type === 'connected') {
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    console.log('✅ Авторизован через WS');
                    this.emit('connected');
                } else if (data.type === 'new_message') {
                    this.emit('new_message', data.message);
                } else if (data.type === 'typing') {
                    this.emit('typing', data);
                } else if (data.type === 'read') {
                    this.emit('read', data);
                } else if (data.type === 'message_edited') {
                    this.emit('message_edited', data);
                }
            } catch (e) {
                console.error('❌ WS parse error:', e);
            }
        };

        this.ws.onclose = () => {
            console.log('🔌 WebSocket закрыт');
            this.isConnected = false;
            this.emit('disconnected');

            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`🔄 Переподключение ${this.reconnectAttempts}/${this.maxReconnectAttempts}...`);
                setTimeout(() => this.connect(this.token), this.reconnectDelay);
            }
        };

        this.ws.onerror = (e) => {
            console.error('❌ WS ошибка:', e);
        };
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }

    sendMessage(chatId, content, options = {}) {
        const data = {
            type: 'message',
            chat_id: chatId,
            content: content || '',
            message_type: options.messageType || 'text',
            reply_to_id: options.replyToId || null,
            file_url: options.fileUrl || null,
            file_name: options.fileName || null,
            file_size: options.fileSize || null,
            mime_type: options.mimeType || null
        };
        console.log('📤 Отправляю:', data);
        this.send(data);
    }

    sendTyping(chatId) {
        this.send({ type: 'typing', chat_id: chatId });
    }

    sendRead(chatId, messageId) {
        this.send({ type: 'read', chat_id: chatId, message_id: messageId });
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        } else {
            console.warn('⚠️ WS не подключён, не могу отправить:', data);
        }
    }

    on(event, callback) {
        if (!this.handlers[event]) this.handlers[event] = [];
        this.handlers[event].push(callback);
    }

    emit(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(cb => cb(data));
        }
    }
}

const wsManager = new WebSocketManager();