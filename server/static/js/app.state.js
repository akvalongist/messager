class AppStore {
    constructor() {
        this.currentUser = null;
        this.currentChatId = null;
        this.chats = [];
        this.messages = {};
        this.replyTo = null;
        this.stickerPacks = [];
        this.currentPackIndex = 0;
        this.currentManagePackId = null;
    }
}

MessengerApp.prototype.ensureStore = function ensureStore() {
    if (!this.store) {
        this.store = new AppStore();
    }
    return this.store;
};

MessengerApp.prototype.resetSessionState = function resetSessionState() {
    const store = this.ensureStore();
    store.currentUser = null;
    store.currentChatId = null;
    store.chats = [];
    store.messages = {};
    store.replyTo = null;
    this.currentUser = null;
    this.currentChatId = null;
    this.chats = [];
    this.messages = {};
    this.replyTo = null;
};

MessengerApp.prototype.syncState = function syncState() {
    const store = this.ensureStore();
    store.currentUser = this.currentUser;
    store.currentChatId = this.currentChatId;
    store.chats = this.chats;
    store.messages = this.messages;
    store.replyTo = this.replyTo;
};
