/**
 * UI хелперы
 */
class UI {
    // Показать тост
    static toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // Форматировать время
    static formatTime(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');

        if (date.toDateString() === now.toDateString()) {
            return `${hours}:${minutes}`;
        }

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) {
            return `вчера ${hours}:${minutes}`;
        }

        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        return `${day}.${month} ${hours}:${minutes}`;
    }

    // Форматировать дату для разделителя
    static formatDateSeparator(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();

        if (date.toDateString() === now.toDateString()) return 'Сегодня';

        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.toDateString() === yesterday.toDateString()) return 'Вчера';

        const months = [
            'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
            'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
        ];
        return `${date.getDate()} ${months[date.getMonth()]}`;
    }

    // Получить инициалы
    static getInitials(name) {
        if (!name) return '?';
        return name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
    }

    // Генерировать цвет аватара по имени
    static getAvatarColor(name) {
        const colors = [
            '#7C3AED', '#EC4899', '#3B82F6', '#10B981',
            '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4'
        ];
        let hash = 0;
        for (let i = 0; i < (name || '').length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        return colors[Math.abs(hash) % colors.length];
    }

    // Показать / скрыть модалку
    static showModal(id) {
        document.getElementById(id).classList.add('active');
    }

    static hideModal(id) {
        document.getElementById(id).classList.remove('active');
    }

    static hideAllModals() {
        document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    }

    // Скролл вниз
    static scrollToBottom(container) {
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // Авто-размер textarea
    static autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    // Экранирование HTML
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Определить тип файла по mime
    static getFileIcon(mimeType) {
        if (!mimeType) return '📄';
        if (mimeType.startsWith('image/')) return '🖼️';
        if (mimeType.startsWith('video/')) return '🎬';
        if (mimeType.startsWith('audio/')) return '🎵';
        if (mimeType.includes('pdf')) return '📕';
        if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
        if (mimeType.includes('sheet') || mimeType.includes('excel')) return '📊';
        if (mimeType.includes('zip') || mimeType.includes('rar')) return '📦';
        return '📄';
    }

    // Размер файла
    static formatFileSize(bytes) {
        if (!bytes) return '';
        const units = ['Б', 'КБ', 'МБ', 'ГБ'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) {
            size /= 1024;
            i++;
        }
        return `${size.toFixed(1)} ${units[i]}`;
    }
}