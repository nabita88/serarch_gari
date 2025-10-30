// 홈화면 대화창 통합 스크립트
document.addEventListener('DOMContentLoaded', function() {

    // 대화창 CSS 스타일 추가
    function addChatStyles() {
        const chatCSS = `
.chat-container {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 140px);
    max-height: 600px;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.chat-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 0 2px rgba(74, 222, 128, 0.3);
}

.status-dot.online {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% {
        transform: scale(1);
        opacity: 1;
    }
    50% {
        transform: scale(1.1);
        opacity: 0.8;
    }
}

.chat-messages {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: #f8fafc;
}

.message {
    display: flex;
    flex-direction: column;
    max-width: 80%;
}

.message.user {
    align-self: flex-end;
}

.message.bot {
    align-self: flex-start;
}

.message-bubble {
    padding: 12px 16px;
    border-radius: 18px;
    font-size: 14px;
    line-height: 1.5;
    word-wrap: break-word;
}

.message.user .message-bubble {
    background: #667eea;
    color: white;
    border-bottom-right-radius: 6px;
}

.message.bot .message-bubble {
    background: white;
    color: #334155;
    border: 1px solid #e2e8f0;
    border-bottom-left-radius: 6px;
}

.message-time {
    font-size: 11px;
    color: #94a3b8;
    margin-top: 4px;
    align-self: flex-end;
}

.message.bot .message-time {
    align-self: flex-start;
}

.chat-input-container {
    padding: 16px 20px;
    background: white;
    border-top: 1px solid #e2e8f0;
}

.input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
}

.chat-input {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid #d1d5db;
    border-radius: 24px;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}

.chat-input:focus {
    border-color: #667eea;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.send-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    background: #667eea;
    border: none;
    border-radius: 50%;
    color: white;
    cursor: pointer;
    transition: all 0.2s;
}

.send-button:hover {
    background: #5a67d8;
    transform: translateY(-1px);
}

.send-button:active {
    transform: translateY(0);
}

.send-button:disabled {
    background: #9ca3af;
    cursor: not-allowed;
    transform: none;
}

.loading-message {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #6b7280;
    font-size: 14px;
}

.loading-dots {
    display: flex;
    gap: 2px;
}

.loading-dots span {
    width: 4px;
    height: 4px;
    background: #6b7280;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
    0%, 80%, 100% {
        transform: scale(0);
    }
    40% {
        transform: scale(1);
    }
}

.error-message .message-bubble {
    background: #fee2e2;
    border-color: #fecaca;
    color: #dc2626;
}
        `;

        const styleElement = document.createElement('style');
        styleElement.textContent = chatCSS;
        document.head.appendChild(styleElement);
    }

    // 홈 뷰가 활성화될 때 대화창 컴포넌트 로드
    function loadHomeChatComponent() {
        const homeView = document.getElementById('view-home');

        if (!homeView) {
            console.error('홈 뷰를 찾을 수 없습니다.');
            return;
        }

        // CSS 스타일 추가
        addChatStyles();

        // 기존 placeholder 내용을 대화창으로 교체
        homeView.innerHTML = `
            <div class="section">
                <!-- 홈화면 대화창 컴포넌트 -->
                <div class="chat-container">
                    <div class="chat-header">
                        <h3>AI 금융 어시스턴트</h3>
                        <span class="status-dot online"></span>
                    </div>

                    <div class="chat-messages" id="chatMessages">
                        <div class="message bot">
                            <div class="message-bubble">
                                안녕하세요! 궁금한 금융 정보나 기업 정보를 물어보세요.
                            </div>
                            <div class="message-time">방금 전</div>
                        </div>
                    </div>

                    <div class="chat-input-container">
                        <div class="input-wrapper">
                            <input
                                type="text"
                                id="chatInput"
                                class="chat-input"
                                placeholder="예: 삼성전자 2023년 1분기 매출액은?"
                                maxlength="500"
                            />
                            <button id="sendButton" class="send-button">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                                    <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 채팅 기능 초기화
        initHomeChat();
    }

    // 채팅 클래스 및 기능 구현
    function initHomeChat() {
        class HomeChat {
            constructor() {
                this.chatMessages = document.getElementById('chatMessages');
                this.chatInput = document.getElementById('chatInput');
                this.sendButton = document.getElementById('sendButton');
                this.isLoading = false;

                if (!this.chatMessages || !this.chatInput || !this.sendButton) {
                    console.error('채팅 컴포넌트 요소들을 찾을 수 없습니다.');
                    return;
                }

                this.bindEvents();
            }

            bindEvents() {
                this.sendButton.addEventListener('click', () => {
                    this.handleSendMessage();
                });

                this.chatInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.handleSendMessage();
                    }
                });
            }

            async handleSendMessage() {
                const message = this.chatInput.value.trim();

                if (!message || this.isLoading) {
                    return;
                }

                this.addMessage(message, 'user');
                this.chatInput.value = '';
                this.setLoading(true);

                try {
                    const response = await this.sendToAPI(message);
                    this.addMessage(response, 'bot');
                } catch (error) {
                    console.error('API 요청 실패:', error);
                    this.addMessage('죄송합니다. 서버와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.', 'bot', true);
                } finally {
                    this.setLoading(false);
                }
            }

            async sendToAPI(query) {
                const API_URL = "http://211.188.53.220:8000/search";
                console.log("[sendToAPI] 요청 시작:", { query }); // 요청 로그

                const response = await fetch(API_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ question: query })
                });
                console.log("[sendToAPI] HTTP 상태 코드:", response.status);

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                return data.answer || data.response || data.result || '응답을 받을 수 없습니다.';
            }

            addMessage(text, type, isError = false) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}${isError ? ' error-message' : ''}`;

                const bubbleDiv = document.createElement('div');
                bubbleDiv.className = 'message-bubble';
                bubbleDiv.textContent = text;

                const timeDiv = document.createElement('div');
                timeDiv.className = 'message-time';
                timeDiv.textContent = this.getCurrentTime();

                messageDiv.appendChild(bubbleDiv);
                messageDiv.appendChild(timeDiv);

                this.chatMessages.appendChild(messageDiv);
                this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
            }

            setLoading(loading) {
                this.isLoading = loading;
                this.sendButton.disabled = loading;
                this.chatInput.disabled = loading;

                if (loading) {
                    const loadingDiv = document.createElement('div');
                    loadingDiv.className = 'message bot loading-message';
                    loadingDiv.id = 'loading-message';

                    loadingDiv.innerHTML = `
                        <div class="message-bubble">
                            <div class="loading-message">
                                <span>답변을 생성하고 있습니다</span>
                                <div class="loading-dots">
                                    <span></span>
                                    <span></span>
                                    <span></span>
                                </div>
                            </div>
                        </div>
                    `;

                    this.chatMessages.appendChild(loadingDiv);
                    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
                } else {
                    const loadingMessage = document.getElementById('loading-message');
                    if (loadingMessage) {
                        loadingMessage.remove();
                    }
                }
            }

            getCurrentTime() {
                const now = new Date();
                const hours = now.getHours().toString().padStart(2, '0');
                const minutes = now.getMinutes().toString().padStart(2, '0');
                return `${hours}:${minutes}`;
            }
        }

        window.homeChat = new HomeChat();
    }

    // 네비게이션 이벤트 감지 - 개선된 버전
    function handleViewChange() {
        const homeView = document.getElementById('view-home');

        if (!homeView) {
            console.error('홈 뷰를 찾을 수 없습니다.');
            return;
        }

        // MutationObserver를 사용해 홈 뷰가 활성화될 때마다 감지
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (homeView.classList.contains('active') && !homeView.querySelector('.chat-container')) {
                        console.log('홈 뷰 활성화 감지 - 채팅 컴포넌트 로딩');
                        loadHomeChatComponent();
                    }
                }
            });
        });

        // 홈 뷰의 class 변경을 관찰
        observer.observe(homeView, { attributes: true, attributeFilter: ['class'] });

        // 페이지 로드 시 홈이 이미 활성화되어 있다면 로드
        if (homeView.classList.contains('active') && !homeView.querySelector('.chat-container')) {
            loadHomeChatComponent();
        }

        // hashchange 이벤트도 감지 (라우터 동작 보완)
        window.addEventListener('hashchange', function() {
            setTimeout(() => {
                if (location.hash === '#home' && homeView.classList.contains('active') && !homeView.querySelector('.chat-container')) {
                    console.log('Hash 변경으로 홈 뷰 활성화 감지');
                    loadHomeChatComponent();
                }
            }, 50);
        });
    }

    handleViewChange();
});