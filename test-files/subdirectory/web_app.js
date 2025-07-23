/**
 * Modern Web Application Frontend
 * 
 * This file contains various JavaScript utilities and components
 * for a modern single-page application including state management,
 * API interactions, and UI components.
 * 
 * @author AI Assistant
 * @version 2.1.0
 * @license MIT
 */

// ES6 Modules and Modern JavaScript Features
import { debounce, throttle } from './utils/performance.js';
import { apiClient } from './services/api.js';
import { eventBus } from './utils/events.js';

/**
 * Application State Manager
 * Handles global application state using the Observer pattern
 */
class StateManager {
    constructor() {
        this.state = new Map();
        this.observers = new Map();
        this.middleware = [];
    }

    /**
     * Subscribe to state changes for a specific key
     * @param {string} key - The state key to watch
     * @param {Function} callback - Callback function to execute on change
     * @returns {Function} Unsubscribe function
     */
    subscribe(key, callback) {
        if (!this.observers.has(key)) {
            this.observers.set(key, new Set());
        }
        
        this.observers.get(key).add(callback);
        
        // Return unsubscribe function
        return () => {
            const observers = this.observers.get(key);
            if (observers) {
                observers.delete(callback);
                if (observers.size === 0) {
                    this.observers.delete(key);
                }
            }
        };
    }

    /**
     * Set state value and notify observers
     * @param {string} key - State key
     * @param {*} value - New value
     */
    setState(key, value) {
        const previousValue = this.state.get(key);
        
        // Apply middleware
        let newValue = value;
        for (const middleware of this.middleware) {
            newValue = middleware(key, newValue, previousValue);
        }
        
        this.state.set(key, newValue);
        
        // Notify observers
        const observers = this.observers.get(key);
        if (observers) {
            observers.forEach(callback => {
                try {
                    callback(newValue, previousValue);
                } catch (error) {
                    console.error('Observer callback error:', error);
                }
            });
        }
    }

    /**
     * Get current state value
     * @param {string} key - State key
     * @returns {*} Current value
     */
    getState(key) {
        return this.state.get(key);
    }

    /**
     * Add middleware for state changes
     * @param {Function} middlewareFunction - Middleware function
     */
    addMiddleware(middlewareFunction) {
        this.middleware.push(middlewareFunction);
    }
}

/**
 * HTTP Client with modern fetch API
 * Handles authentication, error handling, and request/response interceptors
 */
class HttpClient {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.requestInterceptors = [];
        this.responseInterceptors = [];
        this.defaultHeaders = {
            'Content-Type': 'application/json',
        };
    }

    /**
     * Add request interceptor
     * @param {Function} interceptor - Request interceptor function
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * Add response interceptor
     * @param {Function} interceptor - Response interceptor function
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * Make HTTP request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise} Response promise
     */
    async request(endpoint, options = {}) {
        let url = `${this.baseURL}${endpoint}`;
        let config = {
            headers: { ...this.defaultHeaders, ...options.headers },
            ...options
        };

        // Apply request interceptors
        for (const interceptor of this.requestInterceptors) {
            const result = interceptor(url, config);
            if (result) {
                url = result.url || url;
                config = result.config || config;
            }
        }

        try {
            let response = await fetch(url, config);

            // Apply response interceptors
            for (const interceptor of this.responseInterceptors) {
                response = await interceptor(response) || response;
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('HTTP Request failed:', error);
            throw error;
        }
    }

    // Convenience methods
    get(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'GET' });
    }

    post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    put(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    delete(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'DELETE' });
    }
}

/**
 * Component System for building reusable UI components
 */
class Component {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' 
            ? document.querySelector(element) 
            : element;
        this.options = { ...this.defaultOptions, ...options };
        this.state = new StateManager();
        this.isDestroyed = false;
        
        this.init();
        this.bindEvents();
    }

    get defaultOptions() {
        return {};
    }

    init() {
        // Override in subclasses
    }

    bindEvents() {
        // Override in subclasses
    }

    render() {
        // Override in subclasses
        return this;
    }

    destroy() {
        if (this.isDestroyed) return;
        
        this.unbindEvents();
        this.element = null;
        this.isDestroyed = true;
    }

    unbindEvents() {
        // Override in subclasses
    }

    emit(eventName, data) {
        const event = new CustomEvent(eventName, {
            detail: data,
            bubbles: true
        });
        this.element?.dispatchEvent(event);
    }

    on(eventName, handler) {
        this.element?.addEventListener(eventName, handler);
        return this;
    }

    off(eventName, handler) {
        this.element?.removeEventListener(eventName, handler);
        return this;
    }
}

/**
 * Search Component with debounced input and suggestions
 */
class SearchComponent extends Component {
    get defaultOptions() {
        return {
            debounceDelay: 300,
            minLength: 2,
            maxSuggestions: 10,
            apiEndpoint: '/search',
            placeholder: 'Search...'
        };
    }

    init() {
        this.createElements();
        this.debouncedSearch = debounce(this.performSearch.bind(this), this.options.debounceDelay);
        this.suggestions = [];
        this.selectedIndex = -1;
    }

    createElements() {
        this.element.innerHTML = `
            <div class="search-container">
                <input type="text" 
                       class="search-input" 
                       placeholder="${this.options.placeholder}"
                       autocomplete="off">
                <ul class="search-suggestions" hidden></ul>
                <button class="search-button" type="button">
                    <svg class="search-icon" viewBox="0 0 24 24">
                        <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                    </svg>
                </button>
            </div>
        `;

        this.input = this.element.querySelector('.search-input');
        this.suggestionsContainer = this.element.querySelector('.search-suggestions');
        this.searchButton = this.element.querySelector('.search-button');
    }

    bindEvents() {
        this.input.addEventListener('input', this.handleInput.bind(this));
        this.input.addEventListener('keydown', this.handleKeydown.bind(this));
        this.input.addEventListener('blur', this.handleBlur.bind(this));
        this.searchButton.addEventListener('click', this.handleSearch.bind(this));
        this.suggestionsContainer.addEventListener('click', this.handleSuggestionClick.bind(this));
    }

    handleInput(event) {
        const query = event.target.value.trim();
        
        if (query.length >= this.options.minLength) {
            this.debouncedSearch(query);
        } else {
            this.hideSuggestions();
        }
    }

    handleKeydown(event) {
        const { key } = event;
        
        switch (key) {
            case 'ArrowDown':
                event.preventDefault();
                this.selectedIndex = Math.min(
                    this.selectedIndex + 1, 
                    this.suggestions.length - 1
                );
                this.updateSelection();
                break;
                
            case 'ArrowUp':
                event.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.updateSelection();
                break;
                
            case 'Enter':
                event.preventDefault();
                if (this.selectedIndex >= 0) {
                    this.selectSuggestion(this.suggestions[this.selectedIndex]);
                } else {
                    this.handleSearch();
                }
                break;
                
            case 'Escape':
                this.hideSuggestions();
                this.input.blur();
                break;
        }
    }

    handleBlur() {
        // Delay hiding suggestions to allow for clicks
        setTimeout(() => this.hideSuggestions(), 150);
    }

    handleSearch() {
        const query = this.input.value.trim();
        if (query) {
            this.emit('search', { query });
            this.hideSuggestions();
        }
    }

    handleSuggestionClick(event) {
        const suggestionItem = event.target.closest('.suggestion-item');
        if (suggestionItem) {
            const index = parseInt(suggestionItem.dataset.index);
            this.selectSuggestion(this.suggestions[index]);
        }
    }

    async performSearch(query) {
        try {
            this.emit('search:start', { query });
            
            const response = await apiClient.get(this.options.apiEndpoint, {
                params: { q: query, limit: this.options.maxSuggestions }
            });
            
            this.suggestions = response.suggestions || [];
            this.renderSuggestions();
            this.emit('search:success', { query, suggestions: this.suggestions });
            
        } catch (error) {
            console.error('Search error:', error);
            this.emit('search:error', { query, error });
            this.hideSuggestions();
        }
    }

    renderSuggestions() {
        if (this.suggestions.length === 0) {
            this.hideSuggestions();
            return;
        }

        const html = this.suggestions.map((suggestion, index) => `
            <li class="suggestion-item" data-index="${index}">
                <span class="suggestion-text">${this.highlightQuery(suggestion.text)}</span>
                <span class="suggestion-type">${suggestion.type || ''}</span>
            </li>
        `).join('');

        this.suggestionsContainer.innerHTML = html;
        this.suggestionsContainer.hidden = false;
        this.selectedIndex = -1;
    }

    highlightQuery(text) {
        const query = this.input.value.trim();
        if (!query) return text;
        
        const regex = new RegExp(`(${query})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    updateSelection() {
        const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        items.forEach((item, index) => {
            item.classList.toggle('selected', index === this.selectedIndex);
        });
    }

    selectSuggestion(suggestion) {
        this.input.value = suggestion.text;
        this.hideSuggestions();
        this.emit('suggestion:select', { suggestion });
    }

    hideSuggestions() {
        this.suggestionsContainer.hidden = true;
        this.selectedIndex = -1;
    }

    setValue(value) {
        this.input.value = value;
    }

    clear() {
        this.input.value = '';
        this.hideSuggestions();
    }
}

/**
 * Modal Component for displaying overlay content
 */
class ModalComponent extends Component {
    get defaultOptions() {
        return {
            closeOnBackdrop: true,
            closeOnEscape: true,
            showCloseButton: true,
            animation: 'fade',
            size: 'medium' // small, medium, large, fullscreen
        };
    }

    init() {
        this.isOpen = false;
        this.createModal();
    }

    createModal() {
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'modal-backdrop';
        
        this.modal = document.createElement('div');
        this.modal.className = `modal modal-${this.options.size}`;
        
        this.modal.innerHTML = `
            <div class="modal-content">
                ${this.options.showCloseButton ? '<button class="modal-close" aria-label="Close">&times;</button>' : ''}
                <div class="modal-body"></div>
            </div>
        `;
        
        this.backdrop.appendChild(this.modal);
        this.body = this.modal.querySelector('.modal-body');
        this.closeButton = this.modal.querySelector('.modal-close');
    }

    bindEvents() {
        if (this.options.closeOnBackdrop) {
            this.backdrop.addEventListener('click', this.handleBackdropClick.bind(this));
        }
        
        if (this.closeButton) {
            this.closeButton.addEventListener('click', () => this.close());
        }
        
        if (this.options.closeOnEscape) {
            document.addEventListener('keydown', this.handleEscapeKey.bind(this));
        }
    }

    handleBackdropClick(event) {
        if (event.target === this.backdrop) {
            this.close();
        }
    }

    handleEscapeKey(event) {
        if (event.key === 'Escape' && this.isOpen) {
            this.close();
        }
    }

    open(content) {
        if (this.isOpen) return;
        
        if (content) {
            this.setContent(content);
        }
        
        document.body.appendChild(this.backdrop);
        document.body.classList.add('modal-open');
        
        // Trigger animation
        requestAnimationFrame(() => {
            this.backdrop.classList.add('show');
        });
        
        this.isOpen = true;
        this.emit('modal:open');
    }

    close() {
        if (!this.isOpen) return;
        
        this.backdrop.classList.remove('show');
        
        setTimeout(() => {
            if (this.backdrop.parentNode) {
                document.body.removeChild(this.backdrop);
            }
            document.body.classList.remove('modal-open');
        }, 300); // Animation duration
        
        this.isOpen = false;
        this.emit('modal:close');
    }

    setContent(content) {
        if (typeof content === 'string') {
            this.body.innerHTML = content;
        } else {
            this.body.innerHTML = '';
            this.body.appendChild(content);
        }
    }

    toggle(content) {
        if (this.isOpen) {
            this.close();
        } else {
            this.open(content);
        }
    }
}

// Utility Functions
const utils = {
    /**
     * Format file size in human readable format
     * @param {number} bytes - Size in bytes
     * @returns {string} Formatted size string
     */
    formatFileSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    },

    /**
     * Format date in relative time (e.g., "2 hours ago")
     * @param {Date|string} date - Date to format
     * @returns {string} Relative time string
     */
    formatRelativeTime(date) {
        const now = new Date();
        const target = new Date(date);
        const diffMs = now - target;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffSecs < 60) return 'just now';
        if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        
        return target.toLocaleDateString();
    },

    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj);
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === 'object') {
            const cloned = {};
            for (const key in obj) {
                cloned[key] = this.deepClone(obj[key]);
            }
            return cloned;
        }
    }
};

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('Web application initialized');
    
    // Initialize global state manager
    window.appState = new StateManager();
    
    // Initialize HTTP client
    window.apiClient = new HttpClient();
    
    // Add authentication middleware
    window.apiClient.addRequestInterceptor((url, config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return { url, config };
    });
    
    // Initialize search component if element exists
    const searchElement = document.querySelector('.search-component');
    if (searchElement) {
        new SearchComponent(searchElement);
    }
    
    // Set up global error handling
    window.addEventListener('error', (event) => {
        console.error('Global error:', event.error);
        // Could send to error tracking service
    });
    
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        // Could send to error tracking service
    });
});

// Export classes for module usage
export { 
    StateManager, 
    HttpClient, 
    Component, 
    SearchComponent, 
    ModalComponent, 
    utils 
}; 