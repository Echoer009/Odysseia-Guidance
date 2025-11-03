import { DiscordSDK } from "@discord/embedded-app-sdk";
import './style.css';

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

    // 欢迎已认证的用户
    messagesEl.textContent = `欢迎, ${auth.user.global_name}! 请点击“发牌”按钮开始游戏！`;
}


// --- DOM元素引用 ---
const dealerScoreEl = document.getElementById('dealer-score')!;
const playerScoreEl = document.getElementById('player-score')!;
const dealerHandEl = document.getElementById('dealer-hand')!;
const playerHandEl = document.getElementById('player-hand')!;
const dealButton = document.getElementById('deal-button') as HTMLButtonElement;
const hitButton = document.getElementById('hit-button') as HTMLButtonElement;
const standButton = document.getElementById('stand-button') as HTMLButtonElement;
const messagesEl = document.getElementById('messages')!;

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
    gameInProgress = true;
    messagesEl.textContent = '';

    deck = createDeck();
    shuffleDeck(deck);

    playerHand = [deck.pop()!, deck.pop()!];
    dealerHand = [deck.pop()!, deck.pop()!];

    renderHand(playerHand, playerHandEl);
    renderHand(dealerHand, dealerHandEl, true); // 隐藏庄家第一张牌

    dealButton.disabled = true;

    calculateScores(true); // 初始计分
    updateScoreDisplay();

    // 检查玩家是否开局拿到Blackjack
    if (playerScore === 21) {
        messagesEl.textContent = 'Blackjack! 你赢了!';
        // 庄家也需要亮牌
        renderHand(dealerHand, dealerHandEl, false);
        calculateScores(false);
        updateScoreDisplay();
        endGame();
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
        messagesEl.textContent = '你爆牌了！庄家获胜。';
        endGame();
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

function endGame(): void {
    gameInProgress = false;
    hitButton.disabled = true;
    standButton.disabled = true;
    dealButton.disabled = false;
}

function determineWinner(): void {
    setTimeout(() => {
        if (dealerScore > 21) {
            messagesEl.textContent = '庄家爆牌了！你获胜！';
        } else if (playerScore > dealerScore) {
            messagesEl.textContent = '你获胜了！';
        } else if (playerScore < dealerScore) {
            messagesEl.textContent = '庄家获胜。';
        } else {
            messagesEl.textContent = '平局！';
        }
        endGame();
    }, 1000);
}

// --- 7. 绑定事件监听 ---
dealButton.addEventListener('click', startGame);
hitButton.addEventListener('click', hit);
standButton.addEventListener('click', stand);

// --- 环境判断与启动 ---
const queryParams = new URLSearchParams(window.location.search);
const isEmbedded = queryParams.get('frame_id') != null;

if (isEmbedded) {
    // 如果URL中有 frame_id, 说明在Discord内, 启动SDK
    if (clientId) {
        setupDiscordSdk(clientId).catch(console.error);
    } else {
        console.error("VITE_DISCORD_CLIENT_ID is not set, cannot start Discord SDK.");
    }
} else {
    // 否则, 说明在普通浏览器内, 直接启用游戏
    messagesEl.textContent = '在浏览器中进行开发。请点击“发牌”开始游戏！';
    // 注意：在浏览器模式下，dealButton 默认是可用的，无需额外操作
}
