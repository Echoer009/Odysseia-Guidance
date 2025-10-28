document.addEventListener('DOMContentLoaded', () => {
    // --- DOM 元素获取 ---
    const gameSetupDiv = document.getElementById('game-setup');
    const gameBoardDiv = document.getElementById('game-board');
    const betAmountInput = document.getElementById('bet-amount');
    const startGameBtn = document.getElementById('start-game-btn');

    const dealerHandDiv = document.getElementById('dealer-hand');
    const playerHandsContainer = document.getElementById('player-hands-container'); // 新增容器
    const dealerScoreSpan = document.getElementById('dealer-score');

    const playerActionsDiv = document.getElementById('player-actions'); // 按钮容器
    const hitBtn = document.getElementById('hit-btn');
    const standBtn = document.getElementById('stand-btn');
    const doubleBtn = document.getElementById('double-btn'); // 新增
    const splitBtn = document.getElementById('split-btn');   // 新增

    const insuranceActionsDiv = document.getElementById('insurance-actions'); // 新增
    const insuranceYesBtn = document.getElementById('insurance-yes-btn');
    const insuranceNoBtn = document.getElementById('insurance-no-btn');

    const gameMessageDiv = document.getElementById('game-message');
    const playAgainBtn = document.getElementById('play-again-btn');

    // --- 游戏状态变量 ---
    let currentGameId = null;

    // --- 函数定义 ---

    /**
     * 根据卡牌数据创建卡牌的HTML元素
     */
    const createCardElement = (card) => {
        const cardDiv = document.createElement('div');
        if (card.suit === 'hidden') {
            cardDiv.className = 'card card-back';
            cardDiv.textContent = '?';
            return cardDiv;
        }

        cardDiv.className = 'card';
        const suit = card.suit;
        const rank = card.rank;

        if (suit === '♥️' || suit === '♦️') {
            cardDiv.classList.add('red');
        }

        cardDiv.innerHTML = `
            <span class="rank top">${rank}</span>
            <span class="suit">${suit}</span>
            <span class="rank bottom">${rank}</span>
        `;
        return cardDiv;
    };

    /**
     * 渲染整个游戏状态到UI
     */
    const renderGameState = (gameState) => {
        // 清空旧内容
        dealerHandDiv.innerHTML = '';
        playerHandsContainer.innerHTML = '';
        gameMessageDiv.textContent = '';

        // 渲染庄家手牌和分数
        gameState.dealer_hand.cards.forEach(card => {
            dealerHandDiv.appendChild(createCardElement(card));
        });
        dealerScoreSpan.textContent = gameState.dealer_hand.value;

        // 渲染玩家手牌
        gameState.player_hands.forEach((hand, index) => {
            const handDiv = document.createElement('div');
            handDiv.className = 'hand player-hand';
            if (index === gameState.current_hand_index && gameState.status === 'AWAITING_PLAYER_ACTION') {
                handDiv.classList.add('active-hand');
            }

            const cardsDiv = document.createElement('div');
            cardsDiv.className = 'cards';
            hand.cards.forEach(card => {
                cardsDiv.appendChild(createCardElement(card));
            });

            const scoreSpan = document.createElement('span');
            scoreSpan.className = 'score';
            scoreSpan.textContent = `点数: ${hand.value} | 赌注: ${hand.bet}`;

            const statusSpan = document.createElement('span');
            statusSpan.className = 'status-message';
            statusSpan.textContent = hand.status;

            handDiv.appendChild(cardsDiv);
            handDiv.appendChild(scoreSpan);
            handDiv.appendChild(statusSpan);
            playerHandsContainer.appendChild(handDiv);
        });

        updateGameMessageAndActions(gameState);
    };

    /**
     * 更新游戏消息和按钮可见性
     */
    const updateGameMessageAndActions = (gameState) => {
        const isGameOver = gameState.status === 'GAME_OVER';
        const isPlayerTurn = gameState.status === 'AWAITING_PLAYER_ACTION';

        playerActionsDiv.classList.toggle('hidden', !isPlayerTurn);
        playAgainBtn.classList.toggle('hidden', !isGameOver);
        insuranceActionsDiv.classList.add('hidden'); // 默认隐藏

        if (isPlayerTurn) {
            const currentHand = gameState.player_hands[gameState.current_hand_index];
            hitBtn.disabled = false;
            standBtn.disabled = false;
            doubleBtn.disabled = !currentHand.can_double_down;
            splitBtn.disabled = !currentHand.can_split;

            if (gameState.can_offer_insurance) {
                insuranceActionsDiv.classList.remove('hidden');
                playerActionsDiv.classList.add('hidden');
            }

        } else {
            hitBtn.disabled = true;
            standBtn.disabled = true;
            doubleBtn.disabled = true;
            splitBtn.disabled = true;
        }

        if (isGameOver) {
            let finalMessage = '游戏结束！';
            for (const [index, winnings] of Object.entries(gameState.winnings)) {
                finalMessage += `\n手牌 ${parseInt(index) + 1}: `;
                if (winnings > 0) finalMessage += `赢了 ${winnings}`;
                else if (winnings < 0) finalMessage += `输了 ${-winnings}`;
                else finalMessage += '平局';
            }
            gameMessageDiv.textContent = finalMessage;
        }
    };

    /**
     * 统一处理API请求
     */
    const sendRequest = async (url, method = 'POST', body = null) => {
        try {
            const options = {
                method,
                headers: { 'Content-Type': 'application/json' },
            };
            if (body) {
                options.body = JSON.stringify(body);
            }
            const response = await fetch(url, options);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || '请求失败');
            }
            const data = await response.json();
            currentGameId = data.game_id;
            renderGameState(data);
        } catch (error) {
            console.error('API Error:', error);
            gameMessageDiv.textContent = `错误: ${error.message}`;
        }
    };

    // --- 事件监听器 ---

    startGameBtn.addEventListener('click', () => {
        const bet = parseInt(betAmountInput.value, 10);
        if (isNaN(bet) || bet <= 0) {
            alert('请输入有效的下注金额！');
            return;
        }
        gameSetupDiv.classList.add('hidden');
        gameBoardDiv.classList.remove('hidden');
        sendRequest('/api/game', 'POST', { bet_amount: bet });
    });

    playAgainBtn.addEventListener('click', () => {
        gameBoardDiv.classList.add('hidden');
        gameSetupDiv.classList.remove('hidden');
        gameMessageDiv.textContent = '';
        currentGameId = null;
    });

    hitBtn.addEventListener('click', () => sendRequest(`/api/game/${currentGameId}/hit`));
    standBtn.addEventListener('click', () => sendRequest(`/api/game/${currentGameId}/stand`));
    doubleBtn.addEventListener('click', () => sendRequest(`/api/game/${currentGameId}/double`));
    splitBtn.addEventListener('click', () => sendRequest(`/api/game/${currentGameId}/split`));

    insuranceYesBtn.addEventListener('click', () => {
        insuranceActionsDiv.classList.add('hidden');
        playerActionsDiv.classList.remove('hidden');
        sendRequest(`/api/game/${currentGameId}/insurance`, 'POST', { place_bet: true });
    });

    insuranceNoBtn.addEventListener('click', () => {
        insuranceActionsDiv.classList.add('hidden');
        playerActionsDiv.classList.remove('hidden');
        sendRequest(`/api/game/${currentGameId}/insurance`, 'POST', { place_bet: false });
    });
});