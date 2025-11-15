<script setup lang="ts">
import { ref, onMounted, computed} from 'vue';
import { DiscordSDK } from "@discord/embedded-app-sdk";
import dialogueConfig from './dialogue.json';

// --- Enums and Types ---
type View = 'loading' | 'betting' | 'game' | 'end-game';
type GameResult = 'win' | 'loss' | 'push' | 'blackjack';
type DialogueKey = keyof typeof dialogueConfig;

// --- Reactive State ---
const currentView = ref<View>('loading');
const loadingMessage = ref('');
const progress = ref(0);
const balance = ref(0);
const betAmount = ref<number | null>(null);
const currentBet = ref(0);
const dealerScore = ref(0);
const playerScore = ref(0);
const dealerHand = ref<string[]>([]);
const playerHand = ref<string[]>([]);
const messages = ref('');
const dealerDialogue = ref('');
const dealerExpression = ref('normal');
const isRequestInFlight = ref(false);
const countdown = ref(10);
const gameEnded = ref(false);
const optimisticCard = ref<string | null>(null);
const screenSize = ref('');
 
let accessToken: string | null = null;
let countdownInterval: number | null = null;
let dialogueTimeout: number | null = null;
let typewriterInterval: number | null = null;

// 优化6: 添加资源缓存，避免重复加载
const assetCache = new Map<string, boolean>();
let assetsPreloaded = false;

// --- Discord SDK & Environment ---
const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
const queryParams = new URLSearchParams(window.location.search);
const isEmbedded = queryParams.get('frame_id') != null;

// --- Computed Properties ---
const canDouble = computed(() => {
    return playerHand.value.length === 2 && balance.value >= currentBet.value;
});

const betOptions = computed(() => {
    const percentages = { small: 0.05, medium: 0.15, large: 0.30 };
    const minimums = { small: 10, medium: 50, large: 100 };
    let options: { [key: string]: number } = {
        small: Math.max(minimums.small, Math.floor(balance.value * percentages.small)),
        medium: Math.max(minimums.medium, Math.floor(balance.value * percentages.medium)),
        large: Math.max(minimums.large, Math.floor(balance.value * percentages.large)),
        all_in: balance.value,
    };
    const uniqueBets: { [key: string]: number } = {};
    for (const key in options) {
        const value = options[key as keyof typeof options];
        if (value > 0 && !Object.values(uniqueBets).includes(value) && value <= balance.value) {
            uniqueBets[key] = value;
        }
    }
    return Object.entries(uniqueBets).sort(([, aValue], [, bValue]) => aValue - bValue);
});

const countdownClass = computed(() => {
    const remaining = countdown.value;
    const classes = [];
    if (remaining <= 3) {
        classes.push('warning', 'shake-strong');
    } else if (remaining <= 6) {
        classes.push('shake-medium');
    }
    return classes.join(' ');
});

const countdownStyle = computed(() => {
    // Scale from 1.0 at 10s to 1.5 at 1s
    const scale = 1 + (10 - countdown.value) * 0.05;
    return {
        transform: `scale(${scale})`,
    };
});

// --- Core Logic ---
async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object, retries = 2) {
    // The mock API has been removed. All requests now go to the backend via the Vite proxy.
    if (isEmbedded && !accessToken) {
        // In embedded mode, we must have an access token.
        throw new Error("Access Token is not available in embedded mode.");
    }

    for (let i = 0; i <= retries; i++) {
        try {
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };

            // Only add the Authorization header if we are in the embedded client and have a token.
            // For local development, the backend should handle unauthenticated requests.
            if (isEmbedded && accessToken) {
                headers['Authorization'] = `Bearer ${accessToken}`;
            }

            const response = await fetch(endpoint, {
                method,
                headers,
                body: body ? JSON.stringify(body) : undefined,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'API请求失败，服务器返回了非预期的响应。' }));
                throw new Error(errorData.detail || 'API请求失败');
            }
            return response.json();
        } catch (error) {
            if (i === retries) {
                if (error instanceof Error) throw error;
                throw new Error('未知错误，请稍后再试');
            }
            await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
        }
    }
}

function showDialogue(key: DialogueKey, dynamicData?: { amount?: number, isAllIn?: boolean }) {
    if (dialogueTimeout) clearTimeout(dialogueTimeout);
    if (typewriterInterval) clearInterval(typewriterInterval);

    let dialogues: string[] | undefined;
    const configEntry = (dialogueConfig as any)[key];

    const getRandomDialogue = (arr: string[]) => arr[Math.floor(Math.random() * arr.length)];

    if (Array.isArray(configEntry)) {
        dialogues = configEntry;
    } else if (typeof configEntry === 'object' && configEntry !== null) {
        const amount = dynamicData?.amount ?? 0;
        if (key === 'bet_placed') {
            if (dynamicData?.isAllIn) {
                dialogues = configEntry.all_in;
            } else {
                if (amount > 1000) dialogues = configEntry.high_bet;
                else if (amount > 100) dialogues = configEntry.medium_bet;
                else dialogues = configEntry.low_bet;
            }
        } else if (key === 'win' || key === 'loss') {
            if (amount > 1000) dialogues = configEntry.high_bet;
            else if (amount > 100) dialogues = configEntry.medium_bet;
            else dialogues = configEntry.low_bet;
        } else if (configEntry.any_bet) { // For push, blackjack
            dialogues = configEntry.any_bet;
        }
    }

    if (dialogues) {
        let fullDialogue = getRandomDialogue(dialogues);
        if (dynamicData?.amount) {
            fullDialogue = fullDialogue.replace(/\${amount}/g, dynamicData.amount.toString());
        }
        
        dealerDialogue.value = '';
        let i = 0;
        typewriterInterval = setInterval(() => {
            if (i < fullDialogue.length) {
                dealerDialogue.value += fullDialogue.charAt(i);
                i++;
            } else {
                clearInterval(typewriterInterval!);
                typewriterInterval = null;
                dialogueTimeout = setTimeout(() => {
                    if (currentView.value === 'betting') {
                        showDialogue('welcome');
                    } else if (currentView.value === 'game') {
                        showDialogue('bet_placed', {
                            amount: currentBet.value,
                            isAllIn: currentBet.value === balance.value
                        });
                    } else if (currentView.value === 'end-game') {
                        // Use dealerExpression to determine the dialogue, as it reflects the dealer's outcome.
                        // dealerExpression 'lose' means player won.
                        // dealerExpression 'win' means player lost.
                        const resultKey = dealerExpression.value === 'lose' ? 'loss' : 'win';
                        showDialogue(resultKey, { amount: currentBet.value });
                    }
                }, 4000);
            }
        }, 50); // 50ms typing speed

    } else {
        dealerDialogue.value = '';
    }
}

function updateUIFromGameState(game: any) {
    playerHand.value = game.player_hand;
    dealerHand.value = game.dealer_hand;
    playerScore.value = game.player_score;
    dealerScore.value = game.dealer_score;
}

function endGame(finalGameState: any, newBalance: number) {
    updateUIFromGameState(finalGameState);
    if (newBalance !== undefined) {
        balance.value = newBalance;
    }

    let gameResult: GameResult = 'loss';
    if (finalGameState.game_state === 'finished_win') gameResult = 'win';
    else if (finalGameState.game_state === 'finished_blackjack') gameResult = 'blackjack';
    else if (finalGameState.game_state === 'finished_push') gameResult = 'push';

    dealerExpression.value = gameResult === 'win' || gameResult === 'blackjack' ? 'lose' : 'win';
    let dialogueKey: DialogueKey = gameResult;
    if (gameResult === 'win') {
        dialogueKey = 'loss'; // Player wins, so dealer shows 'loss' dialogue.
    } else if (gameResult === 'loss') {
        dialogueKey = 'win'; // Player loses, so dealer shows 'win' dialogue.
    }
    // 'blackjack' and 'push' have their own specific dialogues and are passed through correctly.
    showDialogue(dialogueKey, { amount: currentBet.value });

    setTimeout(() => {
        currentView.value = 'end-game';
        startEndGameCountdown();
    }, 2000);
}

function startEndGameCountdown() {
    if (countdownInterval) clearInterval(countdownInterval);
    countdown.value = 10;
    countdownInterval = setInterval(() => {
        countdown.value--;
        if (countdown.value === 0) {
            clearInterval(countdownInterval!);
            resetGame();
        }
    }, 1000);
}

function resetGame() {
    if (countdownInterval) clearInterval(countdownInterval);
    currentBet.value = 0;
    betAmount.value = null;
    dealerExpression.value = 'normal';
    gameEnded.value = false;
    showDialogue('new_round');
    currentView.value = 'betting';
}

// --- Animation ---
function animateDealerTurn(finalGameState: any): Promise<void> {
    return new Promise(resolve => {
        const finalDealerHand = finalGameState.dealer_hand;

        // This function will be called sequentially to reveal/deal cards
        const dealCardsSequentially = (index: number) => {
            // When all cards are dealt, resolve the promise after a short delay
            if (index >= finalDealerHand.length) {
                setTimeout(resolve, 500);
                return;
            }

            // The first card is already visible. We start by revealing the second.
            if (index === 1) {
                // Replace the hand with the first two real cards
                dealerHand.value = [finalDealerHand[0], finalDealerHand[1]];
                // Calculate and show the score based on the currently visible cards
                updateDealerScore([finalDealerHand[0], finalDealerHand[1]]);
            } else if (index > 1) {
                // For subsequent cards, just push them to the hand
                dealerHand.value.push(finalDealerHand[index]);
                // Update the score after adding each new card
                updateDealerScore(dealerHand.value);
            }

            // Schedule the next card reveal/deal
            setTimeout(() => dealCardsSequentially(index + 1), 750);
        };

        // Start the animation sequence by revealing the second card (index 1)
        // after an initial delay to make the reveal feel deliberate.
        setTimeout(() => dealCardsSequentially(1), 750);
    });
}

// Helper function to calculate and update dealer score
function updateDealerScore(hand: string[]) {
    let score = 0;
    let aceCount = 0;
    
    for (const card of hand) {
        if (card === "Hidden") continue;
        
        // Get card value
        if (card.endsWith("10")) {
            score += 10;
        } else {
            const rankChar = card.slice(-1);
            if (["J", "Q", "K"].includes(rankChar)) {
                score += 10;
            } else if (rankChar === "A") {
                score += 11;
                aceCount++;
            } else {
                score += parseInt(rankChar);
            }
        }
    }
    
    // Adjust for aces if needed
    while (score > 21 && aceCount > 0) {
        score -= 10;
        aceCount--;
    }
    
    dealerScore.value = score;
}

// --- Player Actions ---
async function handleBet() {
    if (isRequestInFlight.value) return;
    const amount = betAmount.value;

    if (!amount || amount <= 0) {
        return showDialogue('invalid_bet');
    }
    if (amount > balance.value) {
        return showDialogue('insufficient_funds');
    }

    isRequestInFlight.value = true;
    gameEnded.value = false; // New game starts, so controls are enabled.
    try {
        const response = await apiCall('/api/game/start', 'POST', { amount });
        if (response.success) {
            currentBet.value = amount;
            balance.value = response.new_balance;
            currentView.value = 'game';
            updateUIFromGameState(response.game);
            showDialogue('bet_placed', { amount, isAllIn: amount === balance.value });
            if (response.game.game_state.startsWith('finished')) {
                gameEnded.value = true; // Game ended on deal, disable controls.
                endGame(response.game, response.new_balance);
            }
        }
    } catch (error: any) {
        messages.value = error.message;
    } finally {
        isRequestInFlight.value = false;
    }
}

async function hit() {
    if (isRequestInFlight.value) return;
    isRequestInFlight.value = true;
    optimisticCard.value = 'Hidden'; // Optimistically add a card back

    try {
        const response = await apiCall('/api/game/hit', 'POST');
        if (response.success) {
            updateUIFromGameState(response.game);
            if (response.game.game_state === 'finished_loss') {
                gameEnded.value = true; // Player busted, disable controls.
                endGame(response.game, response.new_balance);
            }
        }
    } catch (error: any) {
        messages.value = error.message;
    } finally {
        optimisticCard.value = null; // Clear the optimistic card
        isRequestInFlight.value = false;
    }
}

async function stand() {
    if (isRequestInFlight.value) return;
    isRequestInFlight.value = true;
    try {
        const response = await apiCall('/api/game/stand', 'POST');
        if (response.success) {
            gameEnded.value = true; // Game over, disable controls.
            await animateDealerTurn(response.game);
            endGame(response.game, response.new_balance);
        }
    } catch (error: any) {
        messages.value = error.message;
    } finally {
        isRequestInFlight.value = false;
    }
}

async function doubleDown() {
    if (isRequestInFlight.value || !canDouble.value) return;
    isRequestInFlight.value = true;
    optimisticCard.value = 'Hidden';
    try {
        const response = await apiCall('/api/game/double', 'POST');
        if (response.success) {
            gameEnded.value = true;
            // Manually update player hand and score right away for responsiveness
            playerHand.value = response.game.player_hand;
            playerScore.value = response.game.player_score;
            optimisticCard.value = null; // Hide placeholder, show real card

            await animateDealerTurn(response.game);
            endGame(response.game, response.new_balance);
        } else {
            // If the API call itself fails but doesn't throw, clear the card.
            optimisticCard.value = null;
        }
    } catch (error: any) {
        messages.value = error.message;
        optimisticCard.value = null;
    } finally {
        isRequestInFlight.value = false;
    }
}

async function continueWithSameBet() {
    if (isRequestInFlight.value) return;
    if (countdownInterval) clearInterval(countdownInterval);
    betAmount.value = currentBet.value;
    await handleBet();
}

function quitGame() {
    resetGame();
}

function setBetOption(value: number) {
    betAmount.value = value;
}

// --- Initialization ---
async function setupDiscordSdk() {
    const discordSdk = new DiscordSDK(clientId!);
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
    if (!auth) throw new Error("Authenticate command failed");
    accessToken = access_token;
}

async function fetchUserInfo() {
    const data = await apiCall('/api/user', 'GET');
    balance.value = data.balance;
}

async function preloadAssets(startPercent: number, endPercent: number) {
    // 优化6: 如果资源已经预加载过，直接更新进度并返回
    if (assetsPreloaded) {
        progress.value = endPercent;
        console.log('[Preload] Assets already cached, skipping preload.');
        return;
    }

    const suits = ['Club', 'Diamond', 'Heart', 'Spade'];
    
    // 优化1: 优先加载关键资源
    const criticalImages = ['/cards/Background.webp', '/character/normal.webp'];
    const secondaryImages = ['/character/win.webp', '/character/lose.webp'];
    
    // 优化2: 将扑克牌分为两批加载，先加载常用牌
    const commonRanks = ['A', 'K', 'Q', 'J', '10'];
    const rareRanks = ['2', '3', '4', '5', '6', '7', '8', '9'];
    
    const commonCards: string[] = [];
    const rareCards: string[] = [];
    
    suits.forEach(suit => {
        commonRanks.forEach(rank => commonCards.push(`/cards/${suit}${rank}.webp`));
        rareRanks.forEach(rank => rareCards.push(`/cards/${suit}${rank}.webp`));
    });
    
    // 按优先级排序: 关键图像 -> 常用扑克牌 -> 次要图像 -> 罕见扑克牌
    const imagePaths = [...criticalImages, ...commonCards, ...secondaryImages, ...rareCards];

    // 优化6: 过滤已缓存的资源
    const uncachedPaths = imagePaths.filter(path => !assetCache.has(path));
    if (uncachedPaths.length === 0) {
        assetsPreloaded = true;
        progress.value = endPercent;
        console.log('[Preload] All assets already cached.');
        return;
    }

    console.log(`[Preload] Loading ${uncachedPaths.length} uncached assets out of ${imagePaths.length} total.`);

    let loadedCount = 0;
    const totalCount = uncachedPaths.length;
    
    // 优化3: 使用更高效的并发控制，限制同时加载的图片数量
    const concurrentLimit = 6; // 限制同时加载的图片数量
    let currentIndex = 0;
    
    const loadNextBatch = async () => {
        const batch = [];
        for (let i = 0; i < concurrentLimit && currentIndex < uncachedPaths.length; i++) {
            batch.push(loadImage(uncachedPaths[currentIndex++]));
        }
        return Promise.all(batch);
    };
    
    const loadImage = (path: string) => new Promise((resolve) => {
        // 优化6: 检查是否已在缓存中
        if (assetCache.has(path)) {
            resolve(true);
            return;
        }

        const img = new Image();
        img.onload = () => {
            assetCache.set(path, true); // 添加到缓存
            loadedCount++;
            progress.value = startPercent + (loadedCount / totalCount) * (endPercent - startPercent);
            // 优化4: 减少日志输出频率，只在每10%进度时记录
            if (loadedCount % Math.ceil(totalCount / 10) === 0) {
                console.log(`[Preload] Progress: ${progress.value.toFixed(2)}%`);
            }
            resolve(true);
        };
        img.onerror = (err) => {
            console.error(`[Preload] FAILED to load: ${path}`, err);
            // 优化5: 不让单个图片加载失败中断整个过程
            resolve(false); // 改为resolve而不是reject
        };
        img.src = path;
    });
    
    // 分批加载图像
    while (currentIndex < uncachedPaths.length) {
        await loadNextBatch();
    }
    
    assetsPreloaded = true;
    console.log('[Preload] All assets loaded and cached.');
}

async function main() {
    // Restore the original logic
    console.log('[Main] Starting initialization...');
    const loadingFlavorTexts = dialogueConfig.loading as string[];
    loadingMessage.value = loadingFlavorTexts[Math.floor(Math.random() * loadingFlavorTexts.length)];
    const loadingInterval = setInterval(() => {
        loadingMessage.value = loadingFlavorTexts[Math.floor(Math.random() * loadingFlavorTexts.length)];
    }, 1500);

    try {
        progress.value = 5;
        if (isEmbedded) {
            console.log('[Main] Embedded environment detected. Setting up Discord SDK...');
            if (!clientId) throw new Error("VITE_DISCORD_CLIENT_ID is not set.");
            await setupDiscordSdk();
            console.log('[Main] Discord SDK setup complete.');
            progress.value = 30;
            console.log('[Main] Fetching user info...');
            await fetchUserInfo();
            console.log('[Main] User info fetched.');
            progress.value = 50;
            console.log('[Main] Preloading assets for embedded...');
            await preloadAssets(50, 100);
            console.log('[Main] Assets preloaded for embedded.');
        } else {
            console.log('[Main] Browser environment detected.');
            // In browser mode, we directly call the backend via Vite's proxy.
            await fetchUserInfo();
            progress.value = 50;
            console.log('[Main] Preloading assets for browser...');
            await preloadAssets(50, 100);
            console.log('[Main] Assets preloaded for browser.');
        }
        clearInterval(loadingInterval);
        loadingMessage.value = '游戏开始!';
        progress.value = 100;
        console.log('[Main] Initialization successful. Preparing to switch view.');

        setTimeout(() => {
            console.log('[Main] setTimeout triggered. Switching view to "betting".');
            currentView.value = 'betting';
            showDialogue('welcome');
        }, 500);

    } catch (e: any) {
        clearInterval(loadingInterval);
        console.error('[Main] CRITICAL ERROR during initialization:', e);
        const errorMessage = `加载失败: ${e.message}`;
        loadingMessage.value = errorMessage;
    }
}

onMounted(main);

onMounted(() => {
    const updateScreenSize = () => {
        screenSize.value = `${window.innerWidth}px x ${window.innerHeight}px`;
    };
    window.addEventListener('resize', updateScreenSize);
    updateScreenSize(); // Initial call
});

// --- Debugging ---
// The debug utilities associated with the second onMounted hook have been removed
// as they were causing conflicts with Vue's reactivity system.

/*
// This second onMounted hook, specifically the MutationObserver, is suspected of
// conflicting with Vue's reactivity system and has been disabled.
onMounted(() => {
    // Also update sizes on resize
    window.addEventListener('resize', () => {
        updateDebugSizes();
        updateScreenSize();
    });
    // Initial update
    updateScreenSize();
    const observer = new MutationObserver(() => {
        requestAnimationFrame(updateDebugSizes);
    });
    observer.observe(document.getElementById('app-root')!, { childList: true, subtree: true, attributes: true });
});
*/
</script>

<template>
    <div id="app-root" class="debug-mode">
        <div id="screen-size-debug">{{ screenSize }}</div>
        <!-- Loading View -->
        <div v-if="currentView === 'loading'" id="loading-view">
            <div>
                <h1 id="loading-message">{{ loadingMessage }}</h1>
                <div id="progress-bar-container">
                    <div id="progress-bar" :style="{ width: progress + '%' }"></div>
                </div>
            </div>
        </div>

        <!-- Betting View -->
        <div v-if="currentView === 'betting'" id="betting-view" data-debug-size>
            <div id="betting-content-wrapper">
                <h1>类脑娘的BlackJack</h1>
                <div class="messages">{{ messages }}</div>
                <div id="betting-area" data-debug-size>
                    <p class="balance-text">你的余额: <span>{{ balance }}</span></p>
                    <div id="betting-controls">
                        <div id="manual-bet-container">
                            <input type="number" v-model="betAmount" placeholder="输入赌注" min="1" :disabled="isRequestInFlight">
                            <button @click="handleBet" :disabled="isRequestInFlight || !betAmount || betAmount <= 0">下注</button>
                        </div>
                        <div id="bet-options-container">
                                <button v-for="([key, value]) in betOptions" :key="key" @click="setBetOption(value)" class="bet-option-button" :disabled="isRequestInFlight">
                                {{ key === 'small' ? '小' : key === 'medium' ? '中' : key === 'large' ? '大' : '梭哈' }} ({{ value }})
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <div id="betting-dealer-section" class="dealer-section">
                <img :src="`/character/${dealerExpression}.webp`" alt="荷官" class="dealer-image">
                <div v-if="dealerDialogue" class="dialogue-box">
                    <p>{{ dealerDialogue }}</p>
                </div>
            </div>
        </div>

        <!-- Game View -->
        <div v-if="currentView === 'game'" id="game-view" data-debug-size>
            <div id="game-table" data-debug-size>
                <div class="game-area" data-debug-size>
                    <h2>类脑娘 (<span>{{ dealerScore }}</span>)</h2>
                    <div class="hand" data-debug-size>
                        <img v-for="(card, index) in dealerHand" :key="'dealer-' + index" :src="card === 'Hidden' ? '/cards/Background.webp' : `/cards/${card}.webp`" class="card">
                    </div>
                </div>
                <div class="game-area" data-debug-size>
                    <h2>玩家 (<span>{{ playerScore }}</span>)</h2>
                    <div class="hand" data-debug-size>
                        <img v-for="(card, index) in playerHand" :key="'player-' + index" :src="`/cards/${card}.webp`" class="card">
                        <img v-if="optimisticCard" src="/cards/Background.webp" class="card">
                    </div>
                </div>
                <div class="messages">{{ messages }}</div>
                <div id="controls" data-debug-size>
                    <button @click="hit" :disabled="isRequestInFlight || gameEnded">要牌</button>
                    <button @click="stand" :disabled="isRequestInFlight || gameEnded">停牌</button>
                    <button @click="doubleDown" :disabled="isRequestInFlight || !canDouble || gameEnded">双倍下注</button>
                </div>
            </div>
                <div id="game-dealer-section" class="dealer-section">
                <img :src="`/character/${dealerExpression}.webp`" alt="荷官" class="dealer-image">
                <div v-if="dealerDialogue" class="dialogue-box">
                    <p>{{ dealerDialogue }}</p>
                </div>
            </div>
        </div>

        <!-- End Game View -->
        <div v-if="currentView === 'end-game'" id="end-game-view" data-debug-size :class="countdownClass">
            <div id="end-game-content">
                <div id="countdown-container">
                    <span id="end-game-countdown" :style="countdownStyle">{{ countdown }}</span>
                </div>
                <div id="end-game-dealer-section" class="dealer-section" data-debug-size>
                    <img :src="`/character/${dealerExpression}.webp`" alt="荷官" id="end-game-dealer-image" class="dealer-image">
                    <div v-if="dealerDialogue" id="end-game-dialogue-box" class="dialogue-box">
                        <p>{{ dealerDialogue }}</p>
                    </div>
                </div>
                <div id="end-game-controls" data-debug-size>
                    <button @click="continueWithSameBet">继续挑战</button>
                    <button @click="quitGame">不玩了</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style>
/* Re-importing styles from style.css */
@import './style.css';

/* Global styles from original index.html and style.css */
html, body {
    height: 100%;
    margin: 0;
    padding: 0;
    overflow: hidden;
    font-family: 'Poppins', sans-serif;
    background: radial-gradient(ellipse at center, rgba(0,0,0,0) 50%, rgba(0,0,0,0.4) 100%), #0f3d0f;
    color: white;
    text-align: center;
}

#app-root {
    height: 100%;
    width: 100%;
}

#loading-view {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>