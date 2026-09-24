<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { DiscordSDK } from '@discord/embedded-app-sdk';
import { setupChildBridge } from './child-bridge';

// --- Types ---
type View = 'loading' | 'start' | 'play' | 'error';
type FeedbackType = 'success' | 'error' | 'info';

interface RiddleState {
    user_id: string;
    has_riddle: boolean;
    riddle_id: string | null;
    question: string | null;
    wrong_count: number;
    hint: string | null;
    streak: number;
    daily_remaining: number;
    total_solved: number;
    balance: number | null;
}

interface LeaderboardRow {
    user_id: string;
    solved: number;
    streak: number;
}

class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.status = status;
    }
}

// --- Reactive State ---
const currentView = ref<View>('loading');
const loadingMessage = ref('月亮正在升起……');
const fatalError = ref('');
const gameState = ref<RiddleState | null>(null);
const answerText = ref('');
const isRequestInFlight = ref(false);
const feedback = ref<{ type: FeedbackType; text: string } | null>(null);
const showLeaderboard = ref(false);
const leaderboard = ref<LeaderboardRow[]>([]);
const shakeActive = ref(false);
const coinPops = ref<Array<{ id: number; text: string }>>([]);

let accessToken: string | null = null;
let nextCoinId = 0;
let viewSwitchTimer: number | null = null;

// --- Discord SDK & Environment ---
const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
const queryParams = new URLSearchParams(window.location.search);
const isEmbedded = queryParams.get('frame_id') != null;
const baseUrl = import.meta.env.BASE_URL;

const emptyState: RiddleState = {
    user_id: '',
    has_riddle: false,
    riddle_id: null,
    question: null,
    wrong_count: 0,
    hint: null,
    streak: 0,
    daily_remaining: 0,
    total_solved: 0,
    balance: null,
};

const s = computed<RiddleState>(() => gameState.value ?? emptyState);

const startButtonLabel = computed(() => {
    if (s.value.daily_remaining <= 0) return '今日灯谜已猜完';
    return s.value.total_solved > 0 ? '继续猜' : '开始猜谜';
});

// --- Core Logic ---
async function apiCall(endpoint: string, method: 'GET' | 'POST', body?: object) {
    if (!accessToken && isEmbedded) {
        throw new ApiError(401, '登录已过期，请关闭并重新打开活动');
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }

    const response = await fetch(baseUrl + endpoint.replace(/^\//, ''), {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401) {
        throw new ApiError(401, '登录已过期，请关闭并重新打开活动');
    }
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'API请求失败' }));
        throw new ApiError(response.status, errorData.detail || 'API请求失败');
    }
    return response.json();
}

function applyState(state: RiddleState | undefined | null) {
    if (state) gameState.value = state;
}

async function refreshState() {
    const data = await apiCall('/api/riddle/state', 'GET');
    applyState(data.state);
}

async function setupDiscordSdk() {
    const discordSdk = new DiscordSDK(clientId!);
    await discordSdk.ready();
    const { code } = await discordSdk.commands.authorize({
        client_id: discordSdk.clientId,
        response_type: 'code',
        state: '',
        prompt: 'none',
        scope: ['identify', 'guilds'],
    });
    const response = await fetch(baseUrl + 'api/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
    });
    const { access_token } = await response.json();
    const auth = await discordSdk.commands.authenticate({ access_token });
    if (!auth) throw new Error('Authenticate command failed');
    accessToken = access_token;
}

// --- Actions ---
async function startRiddle() {
    if (isRequestInFlight.value) return;
    if (viewSwitchTimer) {
        clearTimeout(viewSwitchTimer);
        viewSwitchTimer = null;
    }
    isRequestInFlight.value = true;
    try {
        const data = await apiCall('/api/riddle/start', 'POST');
        applyState(data.state);
        feedback.value = null;
        answerText.value = '';
        currentView.value = 'play';
    } catch (error: any) {
        feedback.value = { type: 'error', text: error.message };
    } finally {
        isRequestInFlight.value = false;
    }
}

async function submitAnswer() {
    if (isRequestInFlight.value) return;
    const text = answerText.value.trim();
    if (!text) return;

    isRequestInFlight.value = true;
    try {
        const data = await apiCall('/api/riddle/answer', 'POST', { text });
        applyState(data.state);
        if (data.correct) {
            popCoin(`+${data.reward} 类脑币`);
            feedback.value = {
                type: 'success',
                text: `猜对了！谜底是「${data.answer}」，赢得 ${data.reward} 类脑币！`,
            };
            answerText.value = '';
            if (viewSwitchTimer) clearTimeout(viewSwitchTimer);
            viewSwitchTimer = window.setTimeout(() => {
                currentView.value = 'start';
                viewSwitchTimer = null;
            }, 2200);
        } else {
            triggerShake();
            feedback.value = {
                type: 'error',
                text:
                    data.wrong_count >= 3
                        ? `已错 ${data.wrong_count} 次，月亮都替你着急，看看下面的提示吧~`
                        : `不对哦（第 ${data.wrong_count} 次），再想想！`,
            };
        }
    } catch (error: any) {
        feedback.value = { type: 'error', text: error.message };
    } finally {
        isRequestInFlight.value = false;
    }
}

async function giveupRiddle() {
    if (isRequestInFlight.value) return;
    if (viewSwitchTimer) {
        clearTimeout(viewSwitchTimer);
        viewSwitchTimer = null;
    }
    isRequestInFlight.value = true;
    try {
        const data = await apiCall('/api/riddle/giveup', 'POST');
        applyState(data.state);
        feedback.value = {
            type: 'info',
            text: `谜底是「${data.answer}」，连对已清零。下一题加油！`,
        };
        answerText.value = '';
        currentView.value = 'start';
    } catch (error: any) {
        feedback.value = { type: 'error', text: error.message };
    } finally {
        isRequestInFlight.value = false;
    }
}

async function toggleLeaderboard() {
    if (showLeaderboard.value) {
        showLeaderboard.value = false;
        return;
    }
    try {
        const data = await apiCall('/api/riddle/leaderboard', 'GET');
        leaderboard.value = data.leaderboard ?? [];
        showLeaderboard.value = true;
    } catch (error: any) {
        feedback.value = { type: 'error', text: error.message };
    }
}

// --- Animations ---
function triggerShake() {
    shakeActive.value = false;
    requestAnimationFrame(() => {
        shakeActive.value = true;
        setTimeout(() => {
            shakeActive.value = false;
        }, 500);
    });
}

function popCoin(text: string) {
    const id = nextCoinId++;
    coinPops.value.push({ id, text });
    setTimeout(() => {
        coinPops.value = coinPops.value.filter((c) => c.id !== id);
    }, 1700);
}

function rankIcon(idx: number): string {
    return ['#1', '#2', '#3'][idx] ?? `#${idx + 1}`;
}

// --- Initialization ---
async function main() {
    const loadingTexts = ['月亮正在升起……', '灯笼正在点亮……', '谜面正在研磨……', '玉兔正在备题……'];
    let loadingIdx = 0;
    const loadingInterval = setInterval(() => {
        loadingIdx = (loadingIdx + 1) % loadingTexts.length;
        loadingMessage.value = loadingTexts[loadingIdx];
    }, 1500);

    try {
        const bridgeData = await setupChildBridge();
        if (bridgeData) {
            console.log('[Main] Received auth from parent iframe.');
            accessToken = bridgeData.accessToken;
        } else if (isEmbedded) {
            console.log('[Main] Embedded environment detected. Setting up Discord SDK...');
            if (!clientId) throw new Error('VITE_DISCORD_CLIENT_ID is not set.');
            await setupDiscordSdk();
            console.log('[Main] Discord SDK setup complete.');
        } else {
            console.log('[Main] Standalone browser detected, trying anonymous access.');
        }

        await refreshState();
        clearInterval(loadingInterval);
        currentView.value = gameState.value?.has_riddle ? 'play' : 'start';
    } catch (e: any) {
        clearInterval(loadingInterval);
        console.error('[Main] CRITICAL ERROR during initialization:', e);
        if (e instanceof ApiError && e.status === 401) {
            fatalError.value = accessToken
                ? e.message
                : '请从 Discord 的「猜灯谜」活动或大厅中打开本游戏';
        } else {
            fatalError.value = `加载失败: ${e.message}`;
        }
        currentView.value = 'error';
    }
}

onMounted(main);
</script>

<template>
    <div id="app-root">
        <!-- 背景场景：素月 -->
        <div class="scene">
            <div class="moon"></div>
        </div>

        <!-- 加载画面 -->
        <div v-if="currentView === 'loading'" class="center-view">
            <div class="loading-seal">谜</div>
            <h1>{{ loadingMessage }}</h1>
        </div>

        <!-- 错误画面 -->
        <div v-else-if="currentView === 'error'" class="center-view">
            <div class="loading-seal">憾</div>
            <h1>{{ fatalError }}</h1>
            <p>请关闭本次活动窗口后重新打开</p>
        </div>

        <!-- 开始画面 -->
        <div v-else-if="currentView === 'start'" class="panel start-panel">
            <p class="kicker">中秋 · 灯谜</p>
            <h1>月下问谜</h1>
            <p class="subtitle">灯笼之下藏谜语，连对越多奖越多</p>
            <div class="stats">
                <div class="stat-card">
                    <span class="value">{{ s.daily_remaining }}</span>
                    <span class="label">今日剩余题数</span>
                </div>
                <div class="stat-card">
                    <span class="value">{{ s.streak }}</span>
                    <span class="label">当前连对</span>
                </div>
                <div class="stat-card">
                    <span class="value">{{ s.total_solved }}</span>
                    <span class="label">累计猜对</span>
                </div>
                <div class="stat-card">
                    <span class="value">{{ s.balance ?? '—' }}</span>
                    <span class="label">类脑币余额</span>
                </div>
            </div>
            <div v-if="feedback" class="feedback" :class="feedback.type">{{ feedback.text }}</div>
            <p class="rule">答对得 80 类脑币起步，连对每题 +20，封顶 200</p>
            <button class="primary" :disabled="isRequestInFlight || s.daily_remaining <= 0"
                @click="startRiddle">{{ startButtonLabel }}</button>
            <button :disabled="isRequestInFlight" @click="toggleLeaderboard">排行榜</button>
        </div>

        <!-- 答题画面 -->
        <div v-else class="panel play-panel" :class="{ shake: shakeActive }">
            <div class="play-header">
                <span>连对 {{ s.streak }}</span>
                <span class="flames">
                    <i v-for="i in 3" :key="i" class="flame" :class="{ out: s.wrong_count >= i }"></i>
                </span>
                <span>剩 {{ s.daily_remaining }} 题</span>
            </div>
            <p class="flame-hint">每答错一次熄灭一盏灯，三盏全灭后提示自会出现</p>
            <div class="question">{{ s.question }}</div>
            <div v-if="s.hint" class="hint">提示：{{ s.hint }}</div>
            <div v-if="feedback" class="feedback" :class="feedback.type">{{ feedback.text }}</div>
            <input v-model="answerText" type="text" placeholder="输入谜底" maxlength="20"
                :disabled="isRequestInFlight" @keyup.enter="submitAnswer" />
            <div class="controls">
                <button class="primary" :disabled="isRequestInFlight || !answerText.trim()"
                    @click="submitAnswer">提交答案</button>
                <button :disabled="isRequestInFlight || s.daily_remaining <= 0"
                    @click="startRiddle">换一题</button>
                <button class="danger" :disabled="isRequestInFlight" @click="giveupRiddle">放弃</button>
            </div>
            <!-- 奖励飘字层 -->
            <div class="coin-layer">
                <div v-for="c in coinPops" :key="c.id" class="coin-pop">{{ c.text }}</div>
            </div>
        </div>

        <!-- 排行榜浮层 -->
        <div v-if="showLeaderboard" class="overlay" @click.self="showLeaderboard = false">
            <div class="panel lb-panel">
                <h2>灯谜英雄榜</h2>
                <div v-if="leaderboard.length === 0" class="lb-empty">
                    尚无人点亮过灯，快来拔得头筹
                </div>
                <div v-for="(row, idx) in leaderboard" :key="row.user_id" class="lb-row">
                    <span class="lb-rank">{{ rankIcon(idx) }}</span>
                    <span class="lb-user">{{ row.user_id }}</span>
                    <span class="lb-solved">{{ row.solved }} 题</span>
                    <span class="lb-streak">连对 {{ row.streak }}</span>
                </div>
                <button @click="showLeaderboard = false">关闭</button>
            </div>
        </div>
    </div>
</template>
