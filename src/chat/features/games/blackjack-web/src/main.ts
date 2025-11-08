import { DiscordSDK } from "@discord/embedded-app-sdk";
import './style.css';
import { UIManager } from './ui-manager';
import dialogueConfig from './dialogue.json';

document.addEventListener('DOMContentLoaded', () => {
    // --- UI Manager ---
    const uiManager = new UIManager();

    // --- Discord SDK 设置 ---
    const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;

    if (!clientId) {
        throw new Error("VITE_DISCORD_CLIENT_ID is not set in the root .env file.");
    }

    async function setupDiscordSdk(clientId: string) {
        const discordSdk = new DiscordSDK(clientId);
        await discordSdk.ready();

        const { code } = await discordSdk.commands.authorize({
            client_id: discordSdk.clientId,
            response_type: "code",
            state: "",
            prompt: "none",
            scope: ["identify", "guilds"],
        });

        const response = await fetch("/api/token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
        });
        const { access_token } = await response.json();

        const auth = await discordSdk.commands.authenticate({ access_token });

        if (auth == null) {
            throw new Error("Authenticate command failed");
        }

        accessToken = access_token;
    }

    // --- DOM元素引用 ---
    const loadingView = document.getElementById('loading-view')!;
    const appContainer = document.getElementById('app-container')!;
    const dealerScoreEl = document.getElementById('dealer-score')!;
    const playerScoreEl = document.getElementById('player-score')!;
    const dealerHandEl = document.getElementById('dealer-hand')!;
    const playerHandEl = document.getElementById('player-hand')!;
    const hitButton = document.getElementById('hit-button') as HTMLButtonElement;
    const standButton = document.getElementById('stand-button') as HTMLButtonElement;
    const doubleButton = document.getElementById('double-button') as HTMLButtonElement;
    const balanceEl = document.getElementById('balance')!;
    const betAmountInput = document.getElementById('bet-amount') as HTMLInputElement;
    const betButton = document.getElementById('bet-button') as HTMLButtonElement;
    const continueGameButton = document.getElementById('continue-game-button') as HTMLButtonElement;
    const quitGameButton = document.getElementById('quit-game-button') as HTMLButtonElement;
    const betOptionsContainer = document.getElementById('bet-options-container')!;

    // --- Card Data ---
    const suits = ['Club', 'Diamond', 'Heart', 'Spade'];
    const ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
    type Card = { suit: string; rank: string; image: string; };

    // --- Game State ---
    let deck: Card[] = [];
    let playerHand: Card[] = [];
    let dealerHand: Card[] = [];
    let playerScore = 0;
    let dealerScore = 0;
    let gameInProgress = false;
    let accessToken: string | null = null;
    let currentBalance = 0;
    let currentBet = 0;
    let countdownInterval: number | null = null;
    const queryParams = new URLSearchParams(window.location.search);
    const isEmbedded = queryParams.get('frame_id') != null;

    // --- Asset Preloading & Dynamic Loading Messages ---
    const loadingFlavorTexts = (dialogueConfig as any).loading as string[];

    function showDynamicLoadingMessages(element: HTMLElement): number {
        const loadingView = document.getElementById('loading-view');
        if (loadingView) {
            loadingView.style.visibility = 'visible';
        }
        element.textContent = loadingFlavorTexts[Math.floor(Math.random() * loadingFlavorTexts.length)]; // Show first message immediately
        const intervalId = setInterval(() => {
            const randomIndex = Math.floor(Math.random() * loadingFlavorTexts.length);
            element.textContent = loadingFlavorTexts[randomIndex];
        }, 1500);
        return intervalId;
    }

    async function preloadAssets(startPercent: number, endPercent: number) {
        const suits = ['Club', 'Diamond', 'Heart', 'Spade'];
        const ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];
        const characterExpressions = ['normal', 'win', 'lose'];

        const imagePaths = [
            '/cards/Background.png',
            ...characterExpressions.map(e => `/character/${e}.png`)
        ];

        for (const suit of suits) {
            for (const rank of ranks) {
                imagePaths.push(`/cards/${suit}${rank}.png`);
            }
        }

        let loadedCount = 0;
        const totalCount = imagePaths.length;
        if (totalCount === 0) return;

        const promises = imagePaths.map(path => {
            return new Promise((resolve, reject) => {
                const img = new Image();
                img.src = path;
                img.onload = () => {
                    loadedCount++;
                    const assetProgress = loadedCount / totalCount;
                    const totalProgress = startPercent + assetProgress * (endPercent - startPercent);
                    updateProgress(totalProgress);
                    resolve(true);
                };
                img.onerror = reject;
            });
        });

        await Promise.all(promises);
    }


    // --- Game Logic ---
    function createDeck(): Card[] {
        const newDeck: Card[] = [];
        for (const suit of suits) {
            for (const rank of ranks) {
                newDeck.push({ suit, rank, image: `/cards/${suit}${rank}.png` });
            }
        }
        return newDeck;
    }

    function shuffleDeck(deckToShuffle: Card[]): void {
        for (let i = deckToShuffle.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [deckToShuffle[i], deckToShuffle[j]] = [deckToShuffle[j], deckToShuffle[i]];
        }
    }

    function renderHand(hand: Card[], element: HTMLElement, hideFirstCard: boolean = false): void {
        element.innerHTML = '';
        hand.forEach((card, index) => {
            const cardImg = document.createElement('img');
            if (hideFirstCard && index === 0) {
                cardImg.src = '/cards/Background.png';
                cardImg.alt = '隐藏的牌';
            } else {
                cardImg.src = card.image;
                cardImg.alt = `${card.rank} of ${card.suit}`;
            }
            cardImg.classList.add('card');

            // 添加调试尺寸信息
            updateDebugSize(cardImg);

            element.appendChild(cardImg);
        });
    }

    function startGame(): void {
        if (currentBet <= 0) {
            uiManager.showDialogue('bet_required');
            return;
        }
        gameInProgress = true;

        deck = createDeck();
        shuffleDeck(deck);

        playerHand = [deck.pop()!, deck.pop()!];
        dealerHand = [deck.pop()!, deck.pop()!];

        renderHand(playerHand, playerHandEl);
        renderHand(dealerHand, dealerHandEl, true);

        betButton.disabled = true;
        betAmountInput.disabled = true;

        calculateScores(true);
        updateScoreDisplay();

        if (playerScore === 21) {
            // The dialogue for blackjack is handled in the endGame function
            renderHand(dealerHand, dealerHandEl, false);
            calculateScores(false);
            updateScoreDisplay();
            endGame('blackjack');
        } else {
            hitButton.disabled = false;
            standButton.disabled = false;
            doubleButton.disabled = currentBalance < currentBet;
        }
    }

    function getCardValue(card: Card): number {
        if (['J', 'Q', 'K'].includes(card.rank)) return 10;
        if (card.rank === 'A') return 11;
        return parseInt(card.rank);
    }

    function calculateHandScore(hand: Card[]): number {
        let score = 0;
        let aceCount = 0;
        for (const card of hand) {
            score += getCardValue(card);
            if (card.rank === 'A') aceCount++;
        }
        while (score > 21 && aceCount > 0) {
            score -= 10;
            aceCount--;
        }
        return score;
    }

    function calculateScores(isInitialDeal: boolean = false): void {
        playerScore = calculateHandScore(playerHand);
        dealerScore = isInitialDeal ? getCardValue(dealerHand[1]) : calculateHandScore(dealerHand);
    }

    function updateScoreDisplay(): void {
        playerScoreEl.textContent = playerScore.toString();
        dealerScoreEl.textContent = dealerScore.toString();
    }

    function hit(): void {
        if (!gameInProgress) return;
        playerHand.push(deck.pop()!);
        renderHand(playerHand, playerHandEl);
        playerScore = calculateHandScore(playerHand);
        updateScoreDisplay();
        if (playerScore > 21) {
            uiManager.showDialogue('player_bust');
            determineWinner();
        }
        doubleButton.disabled = true; // Can't double after hitting
    }

    function stand(): void {
        if (!gameInProgress) return;
        hitButton.disabled = true;
        standButton.disabled = true;
        doubleButton.disabled = true;
        renderHand(dealerHand, dealerHandEl, false);
        calculateScores(false);
        updateScoreDisplay();

        const dealerTurn = setInterval(() => {
            if (dealerScore < 17) {
                dealerHand.push(deck.pop()!);
                renderHand(dealerHand, dealerHandEl);
                calculateScores();
                updateScoreDisplay();
            } else {
                clearInterval(dealerTurn);
                determineWinner();
            }
        }, 800);
    }

    function endGame(gameResult: 'win' | 'loss' | 'push' | 'blackjack'): void {
        gameInProgress = false;
        hitButton.disabled = true;
        standButton.disabled = true;
        doubleButton.disabled = true;
        handlePayout(gameResult);
    }

    async function handlePayout(gameResult: 'win' | 'loss' | 'push' | 'blackjack') {
        // This local calculation is only for non-embedded mode now.
        // The backend will calculate the final payout.
        let payoutAmount = 0;
        switch (gameResult) {
            case 'win': payoutAmount = currentBet * 2; break;
            case 'blackjack': payoutAmount = Math.floor(currentBet * 2.5); break;
            case 'push': payoutAmount = currentBet; break;
            case 'loss': payoutAmount = 0; break;
        }

        if (!isEmbedded) {
            if (payoutAmount > 0) {
                currentBalance += payoutAmount;
                balanceEl.textContent = currentBalance.toString();
            }
        } else {
            try {
                // Always call the payout endpoint to conclude the game on the server.
                // Send the `result`, not the `amount`. The server calculates the payout.
                const response = await apiCall('/api/game/payout', 'POST', { result: gameResult });
                if (response.success) {
                    currentBalance = response.new_balance;
                    balanceEl.textContent = currentBalance.toString();
                } else {
                    // This case might not be hit if apiCall throws, but it's good practice.
                    uiManager.updateMessages('结算失败了，杂鱼~❤');
                }
            } catch (error) {
                console.error("Payout API call failed:", error);
                uiManager.updateMessages('结算API调用失败了，真是个笨蛋~❤');
            }
        }

        uiManager.updateDealerExpression(gameResult, currentBet, currentBalance, () => {
            // 台词输出完成后等待1.5秒再切换到游戏结束界面
            setTimeout(() => showEndGameSequence(gameResult), 1500);
        });
    }

    function determineWinner(): void {
        renderHand(dealerHand, dealerHandEl, false);
        calculateScores(false);
        updateScoreDisplay();
        setTimeout(() => {
            if (playerScore > 21) endGame('loss');
            else if (dealerScore > 21) endGame('win');
            else if (playerScore > dealerScore) endGame('win');
            else if (playerScore < dealerScore) endGame('loss');
            else endGame('push');
        }, 1000);
    }

    async function doubleDown(): Promise<void> {
        if (!gameInProgress || currentBalance < currentBet) return;

        const additionalBet = currentBet;

        // Disable controls immediately
        hitButton.disabled = true;
        standButton.disabled = true;
        doubleButton.disabled = true;

        const performDoubleDown = () => {
            currentBet *= 2;

            // Player gets one more card
            playerHand.push(deck.pop()!);
            renderHand(playerHand, playerHandEl);
            playerScore = calculateHandScore(playerHand);
            updateScoreDisplay();

            if (playerScore > 21) {
                uiManager.showDialogue('player_bust');
                determineWinner();
            } else {
                // Automatically stand after doubling
                stand();
            }
        };

        if (!isEmbedded) {
            currentBalance -= additionalBet;
            balanceEl.textContent = currentBalance.toString();
            performDoubleDown();
        } else {
            try {
                // The 'bet' endpoint handles deduction, so we just send the additional amount
                const response = await apiCall('/api/game/bet', 'POST', { amount: additionalBet });
                if (response.success) {
                    currentBalance = response.new_balance;
                    balanceEl.textContent = currentBalance.toString();
                    performDoubleDown();
                } else {
                    // Re-enable controls if bet fails
                    hitButton.disabled = false;
                    standButton.disabled = false;
                    doubleButton.disabled = false;
                    uiManager.updateMessages('双倍下注失败了，你个小笨蛋~❤');
                }
            } catch (error) {
                hitButton.disabled = false;
                standButton.disabled = false;
                doubleButton.disabled = false;
                uiManager.updateMessages('双倍下注API调用失败了，真是个笨蛋~❤');
            }
        }
    }

    // --- Event Listeners ---
    hitButton.addEventListener('click', hit);
    standButton.addEventListener('click', stand);
    doubleButton.addEventListener('click', doubleDown);
    betButton.addEventListener('click', () => handleBet(false));
    function continueWithSameBet(): void {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
        // Start new game with the same bet
        handleBet(true);
    }

    continueGameButton.addEventListener('click', continueWithSameBet);

    quitGameButton.addEventListener('click', () => {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
        resetGame();
        uiManager.showView('betting-view');
    });

    // --- API & State Management ---
    async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object) {
        if (!accessToken) throw new Error("Access Token is not available.");
        const response = await fetch(endpoint, {
            method,
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${accessToken}` },
            body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'API request failed');
        }
        return response.json();
    }

    async function fetchUserInfo(): Promise<boolean> {
        try {
            const data = await apiCall('/api/user', 'GET');
            currentBalance = data.balance;
            balanceEl.textContent = currentBalance.toString();
            updateBetOptionsUI();
            betButton.disabled = false;
            return true;
        } catch (error: any) {
            console.error("Failed to fetch user info:", error);
            throw new Error("获取玩家信息失败。");
        }
    }

    async function handleBet(isRetry = false) {
        const amount = isRetry ? currentBet : parseInt(betAmountInput.value, 10);
        if (isNaN(amount) || amount <= 0) {
            uiManager.showDialogue('invalid_bet');
            return;
        }
        if (amount > currentBalance) {
            uiManager.showDialogue('insufficient_funds');
            return;
        }

        betButton.disabled = true;
        betAmountInput.disabled = true;
        const isAllIn = amount === currentBalance;
        uiManager.showBetPlacedDialogue(amount, currentBalance, isAllIn);

        const startAfterBet = () => {
            setTimeout(() => {
                uiManager.showView('game-view');
                startGame();
            }, isRetry ? 100 : 2000);
        };

        if (!isEmbedded) {
            currentBet = amount;
            currentBalance -= amount;
            balanceEl.textContent = currentBalance.toString();
            startAfterBet();
        } else {
            try {
                const response = await apiCall('/api/game/bet', 'POST', { amount });
                if (response.success) {
                    currentBet = amount;
                    currentBalance = response.new_balance;
                    balanceEl.textContent = currentBalance.toString();
                    startAfterBet();
                }
            } catch (error: any) {
                uiManager.updateMessages('下注失败了，你真是个笨蛋~❤');
                resetGame();
            }
        }
    }

    function resetGame() {
        currentBet = 0;
        betAmountInput.value = '';
        betAmountInput.disabled = false;
        betButton.disabled = false;
        playerHand = [];
        dealerHand = [];
        playerScore = 0;
        dealerScore = 0;
        renderHand(playerHand, playerHandEl);
        renderHand(dealerHand, dealerHandEl);
        updateScoreDisplay();
        uiManager.showDialogue('new_round');
        uiManager.resetDealer();
    }

    function showEndGameSequence(gameResult: 'win' | 'loss' | 'push' | 'blackjack') {
        const autoContinue = () => {
            resetGame();
            uiManager.showView('betting-view');
        };

        const { countdownInterval: newInterval } = uiManager.showEndGameView(gameResult, autoContinue);
        if (countdownInterval) {
            clearInterval(countdownInterval);
        }
        countdownInterval = newInterval;
    }

    function calculateBetOptions(balance: number): { [key: string]: number } {
        const percentages = { small: 0.05, medium: 0.15, large: 0.30 };
        const minimums = { small: 10, medium: 50, large: 100 };

        let options: { [key: string]: number } = {
            small: Math.max(minimums.small, Math.floor(balance * percentages.small)),
            medium: Math.max(minimums.medium, Math.floor(balance * percentages.medium)),
            large: Math.max(minimums.large, Math.floor(balance * percentages.large)),
            all_in: balance,
        };

        // 过滤掉无效或重复的选项
        const uniqueBets: { [key: string]: number } = {};
        for (const key in options) {
            const value = options[key as keyof typeof options];
            if (value > 0 && !Object.values(uniqueBets).includes(value)) {
                uniqueBets[key] = value;
            }
        }
        return uniqueBets;
    }

    function updateBetOptionsUI() {
        betOptionsContainer.innerHTML = ''; // 清空现有按钮
        const options = calculateBetOptions(currentBalance);
        const sortedOptions = Object.entries(options).sort(([, aValue], [, bValue]) => aValue - bValue);

        for (const [key, value] of sortedOptions) {
            if (value > currentBalance) continue;

            const button = document.createElement('button');
            button.className = 'bet-option-button';
            let label = '';
            switch (key) {
                case 'small': label = '小'; break;
                case 'medium': label = '中'; break;
                case 'large': label = '大'; break;
                case 'all_in': label = '梭哈'; break;
            }
            button.textContent = `${label} (${value})`;
            button.onclick = () => {
                betAmountInput.value = value.toString();
            };
            betOptionsContainer.appendChild(button);
        }
    }

    function showMainApp() {
        loadingView.classList.add('hidden');
        appContainer.classList.remove('hidden');
    }

    function updateProgress(progress: number) {
        progressBarEl.style.width = `${progress}%`;
    }

    // --- Initialization ---
    const progressBarEl = document.getElementById('progress-bar')!;
    const loadingMessageEl = document.getElementById('loading-message')!;

    async function main() {
        const loadingInterval = showDynamicLoadingMessages(loadingMessageEl);
        updateProgress(5);

        try {
            if (isEmbedded) {
                if (!clientId) {
                    throw new Error("VITE_DISCORD_CLIENT_ID 未设置。");
                }
                await setupDiscordSdk(clientId);
                updateProgress(30);

                const userInfoSuccess = await fetchUserInfo();
                if (!userInfoSuccess) {
                    throw new Error("获取用户信息失败。");
                }
                updateProgress(50);

                await preloadAssets(50, 100);

            } else { // Browser mode
                currentBalance = 10000;
                balanceEl.textContent = currentBalance.toString();
                updateBetOptionsUI();
                betButton.disabled = false;
                await preloadAssets(5, 100);
            }

            // Success path
            clearInterval(loadingInterval);
            loadingMessageEl.textContent = '游戏开始!';
            updateProgress(100);

            setTimeout(() => {
                showMainApp();
                uiManager.showView('betting-view');
                if (!isEmbedded) {
                    uiManager.showDialogue('welcome_browser');
                } else {
                    uiManager.showDialogue('welcome_discord');
                }
            }, 500);

        } catch (e: any) {
            clearInterval(loadingInterval);
            loadingMessageEl.textContent = `加载失败: ${e.message}`;
        }
    }

    main();

    // --- Debug Mode ---
    function toggleDebugMode() {
        document.body.classList.toggle('debug-mode');
        const display = document.getElementById('screen-size-display');
        if (document.body.classList.contains('debug-mode')) {
            // 如果调试模式开启，并且显示元素不存在，则创建它
            if (!display) {
                createScreenSizeDisplay();
            }
        } else {
            // 如果调试模式关闭，并且显示元素存在，则移除它
            if (display) {
                display.remove();
            }
        }
    }
    (window as any).toggleDebugMode = toggleDebugMode;

    // 更新元素调试尺寸信息
    function updateDebugSize(element: HTMLElement) {
        if (document.body.classList.contains('debug-mode')) {
            const rect = element.getBoundingClientRect();
            const width = Math.round(rect.width);
            const height = Math.round(rect.height);
            element.setAttribute('data-debug-size', `${width}×${height}px`);
        }
    }

    // 更新所有关键元素的调试尺寸
    function updateAllDebugSizes() {
        const elementsToUpdate = [
            'betting-view', 'game-view', 'end-game-view', 'game-table',
            'progress-bar-container', 'hit-button', 'stand-button',
            'bet-button', 'continue-game-button', 'quit-game-button',
            'betting-area', 'controls', 'end-game-controls', 'dealer-section',
            'dealer-dialogue-box', 'end-game-dialogue-box', 'dealer-hand', 'player-hand'
        ];

        elementsToUpdate.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                updateDebugSize(element);
            }
        });

        // 更新所有卡片
        document.querySelectorAll('.card').forEach(card => {
            updateDebugSize(card as HTMLElement);
        });

        // 更新所有按钮
        document.querySelectorAll('button').forEach(button => {
            updateDebugSize(button as HTMLElement);
        });

        // 更新所有游戏区域
        document.querySelectorAll('.game-area').forEach(area => {
            updateDebugSize(area as HTMLElement);
        });

        // 更新手牌区域
        document.querySelectorAll('.hand').forEach(hand => {
            updateDebugSize(hand as HTMLElement);
        });
    }

    // 监听窗口大小变化，更新调试信息
    window.addEventListener('resize', () => {
        updateAllDebugSizes();
        updateScreenSizeDisplay();
    });

    // 定期更新调试信息
    setInterval(() => {
        updateAllDebugSizes();
        updateScreenSizeDisplay();
    }, 2000);

    // 默认不开启诊断模式

    // 创建屏幕尺寸显示
    function createScreenSizeDisplay() {
        // 检查是否已存在
        if (document.getElementById('screen-size-display')) {
            return;
        }

        const screenSizeDiv = document.createElement('div');
        screenSizeDiv.id = 'screen-size-display';
        screenSizeDiv.style.cssText = `
            position: fixed;
            top: 10px;
            left: 20px;
            background-color: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 8px 12px;
            border-radius: 5px;
            font-size: 12px;
            font-family: monospace;
            z-index: 10000;
            border: 1px solid #333;
        `;
        document.body.appendChild(screenSizeDiv);
        updateScreenSizeDisplay();
    }

    // 更新屏幕尺寸显示
    function updateScreenSizeDisplay() {
        const display = document.getElementById('screen-size-display');
        if (display) {
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            const documentWidth = document.documentElement.scrollWidth;
            const documentHeight = document.documentElement.scrollHeight;

            let breakpoint = '桌面';
            if (windowWidth <= 480) breakpoint = '手机';
            else if (windowWidth <= 768) breakpoint = '平板';

            display.innerHTML = `
                窗口: ${windowWidth}×${windowHeight}px<br>
                文档: ${documentWidth}×${documentHeight}px<br>
                断点: ${breakpoint}
            `;
        }
    }

    // 初始更新调试尺寸
    setTimeout(() => {
        updateAllDebugSizes();
    }, 1000);
});
