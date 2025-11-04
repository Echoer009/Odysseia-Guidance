import { DiscordSDK } from "@discord/embedded-app-sdk";
import './style.css';

document.addEventListener('DOMContentLoaded', () => {
    // --- Discord SDK 设置 ---
    const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;

    if (!clientId) {
        throw new Error("VITE_DISCORD_CLIENT_ID is not set in the root .env file.");
    }

    async function setupDiscordSdk(clientId: string) {
        const discordSdk = new DiscordSDK(clientId);
        await discordSdk.ready();

        // 请求用户授权，获取用户名等信息
        const { code } = await discordSdk.commands.authorize({
            client_id: discordSdk.clientId,
            response_type: "code",
            state: "",
            prompt: "none",
            scope: ["identify", "guilds"],
        });

        // 使用获取的code换取access_token
        const response = await fetch("/api/token", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                code,
            }),
        });
        const { access_token } = await response.json();

        // 使用token进行最终认证
        const auth = await discordSdk.commands.authenticate({
            access_token,
        });

        if (auth == null) {
            throw new Error("Authenticate command failed");
        }

        // --- 新增：保存token并获取用户信息 ---
        accessToken = access_token;
        const userInfoSuccess = await fetchUserInfo();

        if (userInfoSuccess) {
            updateMessages(`欢迎, ${auth.user.global_name}! 请输入赌注开始游戏。`);
        }
    }


    // --- DOM元素引用 ---
    const bettingView = document.getElementById('betting-view')!;
    const gameView = document.getElementById('game-view')!;
    const dealerScoreEl = document.getElementById('dealer-score')!;
    const playerScoreEl = document.getElementById('player-score')!;
    const dealerHandEl = document.getElementById('dealer-hand')!;
    const playerHandEl = document.getElementById('player-hand')!;
    const hitButton = document.getElementById('hit-button') as HTMLButtonElement;
    const standButton = document.getElementById('stand-button') as HTMLButtonElement;
    const messagesEl = document.getElementById('messages')!;
    const gameMessagesEl = document.getElementById('game-messages')!; // 新的消息区域
    const balanceEl = document.getElementById('balance')!;
    const betAmountInput = document.getElementById('bet-amount') as HTMLInputElement;
    const betButton = document.getElementById('bet-button') as HTMLButtonElement;

    // --- 1. 定义基于图片素材的数据结构 ---
    const suits = ['Club', 'Diamond', 'Heart', 'Spade'];
    const ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];

    type Card = {
        suit: string;
        rank: string;
        image: string;
    };

    // --- 游戏状态变量 ---
    let deck: Card[] = [];
    let playerHand: Card[] = [];
    let dealerHand: Card[] = [];
    let playerScore = 0;
    let dealerScore = 0;
    let gameInProgress = false;
    // --- 新增：金币和下注状态 ---
    let accessToken: string | null = null;
    let currentBalance = 0;
    let currentBet = 0;

    // --- 2. 创建和操作牌堆 ---

    function createDeck(): Card[] {
        const newDeck: Card[] = [];
        for (const suit of suits) {
            for (const rank of ranks) {
                newDeck.push({
                    suit,
                    rank,
                    image: `/cards/${suit}${rank}.png`
                });
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

    // --- 3. 渲染逻辑 ---

    function renderHand(hand: Card[], element: HTMLElement, hideFirstCard: boolean = false): void {
        element.innerHTML = '';
        hand.forEach((card, index) => {
            const cardImg = document.createElement('img');
            if (hideFirstCard && index === 0) {
                cardImg.src = '/cards/Background.png'; // 引用牌背图片
                cardImg.alt = '隐藏的牌';
            } else {
                cardImg.src = card.image;
                cardImg.alt = `${card.rank} of ${card.suit}`;
            }
            cardImg.classList.add('card');
            element.appendChild(cardImg);
        });
    }

    // --- 4. 游戏主逻辑 ---

    function startGame(): void {
        if (currentBet <= 0) {
            updateMessages('请先下注再开始游戏！');
            return;
        }
        gameInProgress = true;
        updateMessages(`你下注了 ${currentBet}。祝你好运！`);

        deck = createDeck();
        shuffleDeck(deck);

        playerHand = [deck.pop()!, deck.pop()!];
        dealerHand = [deck.pop()!, deck.pop()!];

        renderHand(playerHand, playerHandEl);
        renderHand(dealerHand, dealerHandEl, true); // 隐藏庄家第一张牌

        betButton.disabled = true;
        betAmountInput.disabled = true;

        calculateScores(true); // 初始计分
        updateScoreDisplay();

        // 检查玩家是否开局拿到Blackjack
        if (playerScore === 21) {
            updateMessages('Blackjack! 你赢了!');
            // 庄家也需要亮牌
            renderHand(dealerHand, dealerHandEl, false);
            calculateScores(false);
            updateScoreDisplay();
            endGame('blackjack');
        } else {
            hitButton.disabled = false;
            standButton.disabled = false;
        }
    }

    // --- 5. 计算分数 ---

    function getCardValue(card: Card): number {
        if (['J', 'Q', 'K'].includes(card.rank)) {
            return 10;
        }
        if (card.rank === 'A') {
            return 11;
        }
        return parseInt(card.rank);
    }

    function calculateHandScore(hand: Card[]): number {
        let score = 0;
        let aceCount = 0;
        for (const card of hand) {
            score += getCardValue(card);
            if (card.rank === 'A') {
                aceCount++;
            }
        }
        while (score > 21 && aceCount > 0) {
            score -= 10;
            aceCount--;
        }
        return score;
    }

    function calculateScores(isInitialDeal: boolean = false): void {
        playerScore = calculateHandScore(playerHand);
        if (isInitialDeal) {
            dealerScore = getCardValue(dealerHand[1]); // 只计算庄家亮着的牌
        } else {
            dealerScore = calculateHandScore(dealerHand);
        }
    }

    function updateScoreDisplay(): void {
        playerScoreEl.textContent = playerScore.toString();
        dealerScoreEl.textContent = dealerScore.toString();
    }

    // --- 6. 玩家操作 ---

    function hit(): void {
        if (!gameInProgress) return;

        playerHand.push(deck.pop()!);
        renderHand(playerHand, playerHandEl);

        playerScore = calculateHandScore(playerHand);
        updateScoreDisplay();

        if (playerScore > 21) {
            updateMessages('你爆牌了！庄家获胜。');
            determineWinner(); // 改为调用determineWinner来统一处理结束逻辑
        }
    }

    function stand(): void {
        if (!gameInProgress) return;

        hitButton.disabled = true;
        standButton.disabled = true;

        // 揭示庄家的隐藏牌
        renderHand(dealerHand, dealerHandEl, false);
        calculateScores(false);
        updateScoreDisplay();

        // 庄家根据规则自动要牌
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
        }, 800); // 每800毫秒行动一次
    }

    function endGame(gameResult: 'win' | 'loss' | 'push' | 'blackjack'): void {
        gameInProgress = false;
        hitButton.disabled = true;
        standButton.disabled = true;

        // 根据游戏结果处理派奖
        handlePayout(gameResult);
    }

    async function handlePayout(gameResult: 'win' | 'loss' | 'push' | 'blackjack') {
        let payoutAmount = 0;
        let message = '';

        switch (gameResult) {
            case 'win':
                payoutAmount = currentBet * 2;
                message = `你获胜了！赢得 ${payoutAmount} (赔率 2.0x)`;
                break;
            case 'blackjack':
                payoutAmount = Math.floor(currentBet * 2.5);
                message = `Blackjack! 你赢了! 赢得 ${payoutAmount} (赔率 2.5x)`;
                break;
            case 'push':
                payoutAmount = currentBet;
                message = `平局！退还你的赌注 ${currentBet}`;
                break;
            case 'loss':
                payoutAmount = 0;
                message = `你输了。失去了你的赌注 ${currentBet}`;
                break;
        }

        console.log(`--- 游戏结算 ---`);
        console.log(`结果: ${gameResult}, 赌注: ${currentBet}, 派奖金额: ${payoutAmount}`);

        if (!isEmbedded) {
            // --- 浏览器模式模拟 ---
            if (payoutAmount > 0) {
                currentBalance += payoutAmount;
                balanceEl.textContent = currentBalance.toString();
            }
            updateMessages(`${message} | 你的新余额: ${currentBalance}`);
        } else {
            // --- Discord 模式 (真实API调用) ---
            if (payoutAmount > 0) {
                try {
                    const response = await apiCall('/api/game/payout', 'POST', { amount: payoutAmount });
                    if (response.success) {
                        currentBalance = response.new_balance;
                        balanceEl.textContent = currentBalance.toString();
                        updateMessages(`${message} | 你的新余额: ${currentBalance}`);
                    } else {
                        console.error('派奖失败:', response);
                        updateMessages('错误：派奖失败，请联系管理员。');
                    }
                } catch (error) {
                    console.error('派奖API调用失败:', error);
                    updateMessages('错误：派奖API调用失败，请联系管理员。');
                }
            } else {
                updateMessages(`${message} | 你的余额: ${currentBalance}`);
            }
        }

        // 2秒后切换回下注界面
        setTimeout(() => {
            resetGame();
            showView('betting-view');
        }, 2000);
    }


    function determineWinner(): void {
        // 揭示庄家手牌并计算最终分数
        renderHand(dealerHand, dealerHandEl, false);
        calculateScores(false);
        updateScoreDisplay();

        setTimeout(() => {
            if (playerScore > 21) {
                endGame('loss'); // 玩家爆牌
            } else if (dealerScore > 21) {
                endGame('win'); // 庄家爆牌
            } else if (playerScore > dealerScore) {
                endGame('win'); // 玩家点数更高
            } else if (playerScore < dealerScore) {
                endGame('loss'); // 庄家点数更高
            } else {
                endGame('push'); // 平局
            }
        }, 1000);
    }

    // --- 7. 绑定事件监听 ---
    hitButton.addEventListener('click', hit);
    standButton.addEventListener('click', stand);
    betButton.addEventListener('click', handleBet);


    // --- 8. 新增功能函数 ---

    async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object) {
        if (!accessToken) {
            throw new Error("Access Token is not available.");
        }
        const response = await fetch(endpoint, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`,
            },
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
            console.log('获取用户信息和余额...');
            updateMessages('正在获取您的余额...');
            const data = await apiCall('/api/user', 'GET');
            currentBalance = data.balance;
            balanceEl.textContent = currentBalance.toString();
            console.log(`获取余额成功: ${currentBalance}`);
            betButton.disabled = false;
            return true;
        } catch (error: any) {
            console.error("获取用户信息失败:", error);
            const errorMessage = error instanceof Error ? error.message : JSON.stringify(error);
            updateMessages(`无法获取您的余额: ${errorMessage}。请确保后端服务正在运行并可访问。`);
            return false;
        }
    }

    async function handleBet() {
        const amount = parseInt(betAmountInput.value, 10);
        if (isNaN(amount) || amount <= 0) {
            updateMessages('请输入一个有效的下注金额。');
            return;
        }
        if (amount > currentBalance) {
            updateMessages('余额不足！');
            return;
        }

        betButton.disabled = true;
        betAmountInput.disabled = true;
        updateMessages(`正在处理 ${amount} 的下注...`);

        if (!isEmbedded) {
            // --- 浏览器模式模拟 ---
            currentBet = amount;
            currentBalance -= amount;
            balanceEl.textContent = currentBalance.toString();
            updateMessages(`下注 ${currentBet} 成功！正在发牌...`);
            setTimeout(() => {
                showView('game-view');
                startGame();
            }, 1000);
        } else {
            // --- Discord 模式 (真实API调用) ---
            try {
                const response = await apiCall('/api/game/bet', 'POST', { amount });
                if (response.success) {
                    currentBet = amount;
                    currentBalance = response.new_balance;
                    balanceEl.textContent = currentBalance.toString();
                    updateMessages(`下注 ${currentBet} 成功！正在发牌...`);
                    setTimeout(() => {
                        showView('game-view');
                        startGame();
                    }, 1000);
                }
            } catch (error: any) {
                console.error('下注失败:', error);
                updateMessages(`下注失败: ${error.message}`);
                resetGame();
            }
        }
    }

    function resetGame() {
        currentBet = 0;
        betAmountInput.value = '';
        betAmountInput.disabled = false;
        betButton.disabled = false;

        // 清理游戏面板
        playerHand = [];
        dealerHand = [];
        playerScore = 0;
        dealerScore = 0;
        renderHand(playerHand, playerHandEl);
        renderHand(dealerHand, dealerHandEl);
        updateScoreDisplay();
        updateMessages('请输入赌注开始新一轮游戏。');
    }

    function updateMessages(message: string) {
        messagesEl.textContent = message;
        gameMessagesEl.textContent = message;
    }

    function showView(viewId: 'betting-view' | 'game-view') {
        if (viewId === 'betting-view') {
            bettingView.classList.remove('hidden');
            gameView.classList.add('hidden');
        } else {
            bettingView.classList.add('hidden');
            gameView.classList.remove('hidden');
        }
    }

    // --- 环境判断与启动 ---
    const queryParams = new URLSearchParams(window.location.search);
    const isEmbedded = queryParams.get('frame_id') != null;

    // --- 立即显示诊断信息 ---
    updateMessages(`正在初始化...`);

    if (isEmbedded) {
        // 如果URL中有 frame_id, 说明在Discord内, 启动SDK
        if (clientId) {
            updateMessages('在Discord活动中。正在启动SDK...');
            setupDiscordSdk(clientId).catch(err => {
                console.error("SDK 初始化失败:", err);
                // 将错误对象转换为更易读的字符串
                const errorMessage = err instanceof Error ? err.message : JSON.stringify(err);
                updateMessages(`SDK 初始化失败: ${errorMessage}`);
            });
        } else {
            const errorMsg = "错误: VITE_DISCORD_CLIENT_ID 未设置, 无法启动 Discord SDK。";
            console.error(errorMsg);
            updateMessages(errorMsg);
        }
    } else {
        // 否则, 说明在普通浏览器内, 直接启用游戏
        updateMessages('浏览器开发模式。已为您模拟10000余额。');
        // 在浏览器模式下，启用完整的下注流程
        showView('betting-view');
        currentBalance = 10000; // 设置模拟余额
        balanceEl.textContent = currentBalance.toString();
        betButton.disabled = false; // 确保下注按钮可用
    }
});
