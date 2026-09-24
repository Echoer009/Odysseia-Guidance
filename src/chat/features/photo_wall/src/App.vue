<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { DiscordSDK, Common } from '@discord/embedded-app-sdk'
import { setupChildBridge } from './child-bridge'

interface PhotoEntry {
    id: number
    user_id: string
    display_name: string
    blessing: string
    x_ratio: number
    y_ratio: number
    scale: number
    avatar_url: string | null
    created_at: string | null
}

interface MeInfo {
    user_id: string
    username: string | null
    is_admin: boolean
    entry: PhotoEntry | null
}

type Phase = 'loading' | 'ready' | 'error'

// --- Discord SDK & 环境 ---
const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID
const queryParams = new URLSearchParams(window.location.search)
const isEmbedded = queryParams.get('frame_id') != null
const baseUrl = import.meta.env.BASE_URL

// --- 全局状态 ---
const phase = ref<Phase>('loading')
const errorMsg = ref('')
const title = ref('中秋大合影')
const fullBackgroundUrl = ref('')
const entries = ref<PhotoEntry[]>([])
const exportUrl = baseUrl + 'api/photo/export'
const me = ref<MeInfo | null>(null)

// --- 画布自适应：让画布严格等于图片比例，完整显示不裁切 ---
const stageRef = ref<HTMLElement | null>(null)
const canvasBox = ref<{ w: number; h: number } | null>(null)
let bgRatio = 4 / 3

function recomputeCanvas() {
    const stage = stageRef.value
    if (!stage) return
    const sw = stage.clientWidth
    const sh = stage.clientHeight
    if (sw <= 0 || sh <= 0) return
    let w = sw
    let h = w / bgRatio
    if (h > sh) {
        h = sh
        w = h * bgRatio
    }
    canvasBox.value = { w: Math.floor(w), h: Math.floor(h) }
}

// --- 交互状态 ---
const selected = ref<PhotoEntry | null>(null)
const placing = ref(false)
const panelOpen = ref(false)
const blessingText = ref('')
const submitting = ref(false)
const toast = ref('')
const confirmDelete = ref<PhotoEntry | null>(null)
const canvasRef = ref<HTMLElement | null>(null)

// --- 画笔禁区状态：管理员涂抹，涂过的地方禁止放置 ---
type Pt = [number, number]
interface Stroke {
    radius: number
    points: Pt[]
}
const strokes = ref<Stroke[]>([])
const editZones = ref(false)
const brushSize = ref(0.03)
const painting = ref(false)
const savingZones = ref(false)
const strokeCanvasRef = ref<HTMLCanvasElement | null>(null)
const blessPanelRef = ref<HTMLElement | null>(null)
let currentPoints: Pt[] = []
let bgW = 4
let bgH = 3

function distToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
    const dx = bx - ax
    const dy = by - ay
    if (dx === 0 && dy === 0) return Math.hypot(px - ax, py - ay)
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy))
}

function placementAllowed(x: number, y: number): boolean {
    // 涂过的地方禁止放置；没有笔划时全图可放
    if (strokes.value.length === 0) return true
    const px = x * bgW
    const py = y * bgH
    for (const s of strokes.value) {
        const r = s.radius * bgW
        const pts = s.points
        if (pts.length === 1) {
            if (Math.hypot(px - pts[0][0] * bgW, py - pts[0][1] * bgH) <= r) return false
            continue
        }
        for (let i = 0; i < pts.length - 1; i++) {
            const ax = pts[i][0] * bgW
            const ay = pts[i][1] * bgH
            const bx = pts[i + 1][0] * bgW
            const by = pts[i + 1][1] * bgH
            if (distToSegment(px, py, ax, ay, bx, by) <= r) return false
        }
    }
    return true
}

function avatarRatio(count: number): number {
    // 头像直径（相对图片宽度）随人数自适应，与后端/合成器同一梯度
    if (count < 20) return 0.045
    if (count < 50) return 0.038
    if (count < 100) return 0.031
    if (count < 200) return 0.026
    return 0.022
}

// 类脑娘口气的提示文案（随机展示，与后端同一套语感）
const ZONE_TIPS = [
    '这里不可以放哦，会挡住画面里的大家',
    '这片是保留区域呀，换一边试试嘛',
    '这里被涂掉了啦，往旁边挪一挪～',
    '这里圈起来了呀，别处看看吧～',
]

const OVERLAP_TIPS = [
    '这里不可以放哦，已经有小伙伴啦',
    '这块地方刚被坐下呀，换个位置嘛',
    '慢了一步，这里有人啦～',
    '挤不下啦，旁边找找看哦',
    '这里已经有小伙伴了哦，再挑挑别处吧',
]

function pickTip(pool: string[]): string {
    return pool[Math.floor(Math.random() * pool.length)]
}

function spotFree(x: number, y: number): boolean {
    // 与其他头像保持最小间距（自己的旧位置不算）
    const others = entries.value.filter((e) => e.user_id !== me.value?.user_id)
    if (others.length === 0) return true
    const gap = avatarRatio(others.length + 1) * 1.12 * bgW
    const px = x * bgW
    const py = y * bgH
    return others.every(
        (e) => Math.hypot(e.x_ratio * bgW - px, e.y_ratio * bgH - py) > gap
    )
}

function redrawStrokes() {
    const cv = strokeCanvasRef.value
    const box = canvasBox.value
    if (!cv || !box) return
    cv.width = box.w
    cv.height = box.h
    const ctx = cv.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, box.w, box.h)
    ctx.strokeStyle = '#d4af6a'
    ctx.fillStyle = 'rgba(212, 175, 106, 0.28)'
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    const drawStroke = (s: Stroke) => {
        const w = s.radius * box.w * 2
        if (s.points.length === 1) {
            ctx.beginPath()
            ctx.arc(s.points[0][0] * box.w, s.points[0][1] * box.h, w / 2, 0, Math.PI * 2)
            ctx.fill()
            return
        }
        ctx.lineWidth = w
        ctx.beginPath()
        ctx.moveTo(s.points[0][0] * box.w, s.points[0][1] * box.h)
        for (let i = 1; i < s.points.length; i++) {
            ctx.lineTo(s.points[i][0] * box.w, s.points[i][1] * box.h)
        }
        ctx.stroke()
    }
    for (const s of strokes.value) drawStroke(s)
    if (currentPoints.length > 0) {
        drawStroke({ radius: brushSize.value, points: currentPoints })
    }
}

function canvasPoint(e: PointerEvent): Pt | null {
    const rect = strokeCanvasRef.value?.getBoundingClientRect()
    if (!rect) return null
    return normPoint(rect, e.clientX, e.clientY)
}

// 竖屏触屏时 #app 被 CSS 整体旋转 90°，getBoundingClientRect 拿到的是
// 旋转后的视觉包围盒，必须换算回应用坐标系，否则点击位置会转置错位
const rotatedMedia = window.matchMedia('(orientation: portrait) and (pointer: coarse)')

function normPoint(rect: DOMRect, clientX: number, clientY: number): Pt {
    if (rotatedMedia.matches) {
        return [
            Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)),
            Math.min(1, Math.max(0, (rect.right - clientX) / rect.width)),
        ]
    }
    return [
        Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)),
        Math.min(1, Math.max(0, (clientY - rect.top) / rect.height)),
    ]
}

function onPaintStart(e: PointerEvent) {
    if (!editZones.value) return
    const p = canvasPoint(e)
    if (!p) return
    painting.value = true
    currentPoints = [p]
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
    redrawStrokes()
}

function onPaintMove(e: PointerEvent) {
    if (!painting.value) return
    const p = canvasPoint(e)
    if (!p) return
    currentPoints.push(p)
    redrawStrokes()
}

function onPaintEnd() {
    if (!painting.value) return
    painting.value = false
    if (currentPoints.length > 0) {
        strokes.value.push({ radius: brushSize.value, points: [...currentPoints] })
    }
    currentPoints = []
    redrawStrokes()
}

function undoStroke() {
    strokes.value.pop()
    redrawStrokes()
}

function clearStrokes() {
    strokes.value = []
    currentPoints = []
    redrawStrokes()
}

function setBrush(r: number) {
    brushSize.value = r
}

async function saveZones() {
    savingZones.value = true
    try {
        await api('api/photo/layout', {
            method: 'PUT',
            body: JSON.stringify({ strokes: strokes.value }),
        })
        showToast('禁区已保存，涂过的地方不可放置')
        editZones.value = false
    } catch (err: any) {
        showToast(err.message || '保存失败')
    } finally {
        savingZones.value = false
    }
}

let accessToken: string | null = null
let toastTimer: number | null = null

const canEdit = computed(() => me.value !== null)
const isAdmin = computed(() => me.value?.is_admin === true)
const myEntry = computed(() => me.value?.entry ?? null)
const isEditing = computed(() => myEntry.value !== null)

// 头像直径（像素）：随画布宽度与人数自适应
const avatarSize = computed(() => {
    if (!canvasBox.value) return 48
    return Math.max(20, Math.round(avatarRatio(entries.value.length) * canvasBox.value.w))
})

function fullUrl(u: string): string {
    return baseUrl + u.replace(/^\//, '')
}

function fmtTime(s: string | null): string {
    if (!s) return ''
    const d = new Date(s.includes('T') ? s : s.replace(' ', 'T') + 'Z')
    if (isNaN(d.getTime())) return s
    return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
}

function showToast(text: string) {
    toast.value = text
    if (toastTimer) clearTimeout(toastTimer)
    toastTimer = window.setTimeout(() => (toast.value = ''), 2600)
}

async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`
    const resp = await fetch(fullUrl(path), { ...init, headers })
    if (!resp.ok) {
        const data = await resp.json().catch(() => null)
        const detail = (data as { detail?: string } | null)?.detail
        throw new Error(detail || `请求失败 (${resp.status})`)
    }
    return resp.json() as Promise<T>
}

// --- 鉴权 ---
async function setupDiscordSdk() {
    const discordSdk = new DiscordSDK(clientId!)
    await discordSdk.ready()
    // 原生锁定横屏（DC 官方 API）：输入法/坐标系全部原生横屏；
    // 不支持的旧客户端会抛错，回退到 CSS 旋转方案
    try {
        await discordSdk.commands.setOrientationLockState({
            lock_state: Common.OrientationLockStateTypeObject.LANDSCAPE,
            picture_in_picture_lock_state: Common.OrientationLockStateTypeObject.LANDSCAPE,
            grid_lock_state: Common.OrientationLockStateTypeObject.UNLOCKED,
        })
    } catch (e) {
        console.warn('setOrientationLockState 不支持，回退 CSS 旋转', e)
    }
    const { code } = await discordSdk.commands.authorize({
        client_id: discordSdk.clientId,
        response_type: 'code',
        state: '',
        prompt: 'none',
        scope: ['identify', 'guilds'],
    })
    const response = await fetch(fullUrl('api/token'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
    })
    if (!response.ok) throw new Error('令牌交换失败')
    const { access_token } = await response.json()
    const auth = await discordSdk.commands.authenticate({ access_token })
    if (!auth) throw new Error('鉴权失败')
    accessToken = access_token
}

// --- 数据 ---
async function loadConfig() {
    const cfg = await api<{
        title: string
        background_url: string
        background_width: number
        background_height: number
        strokes?: Stroke[]
        entries: PhotoEntry[]
    }>('api/photo/config')
    title.value = cfg.title
    fullBackgroundUrl.value = fullUrl(cfg.background_url)
    entries.value = cfg.entries ?? []
    if (cfg.strokes) strokes.value = cfg.strokes
    if (cfg.background_width && cfg.background_height) {
        bgRatio = cfg.background_width / cfg.background_height
        bgW = cfg.background_width
        bgH = cfg.background_height
    }
}

async function loadMe() {
    try {
        me.value = await api<MeInfo>('api/photo/me')
        if (me.value.entry) blessingText.value = me.value.entry.blessing
    } catch {
        me.value = null
    }
}

// --- 留影流程：点 + 填祝福 选位置 提交 ---
function shortName(n: string) {
    return n && n.length > 8 ? n.slice(0, 7) + '…' : n
}

// 输入祝福时暂时解除整页旋转：系统输入法是竖屏的，转着打字体验极差
watch(panelOpen, (open) => {
    document.getElementById('app')?.classList.toggle('no-rotate', open)
    if (open) nextTick(() => blessPanelRef.value?.scrollIntoView({ block: 'center', behavior: 'smooth' }))
})

function blessFocus() {
    blessPanelRef.value?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

function beginPlacing() {
    if (!canEdit.value || submitting.value) return
    placing.value = true
    panelOpen.value = true
    selected.value = null
}

function cancelPlacing() {
    placing.value = false
    panelOpen.value = false
}

function proceedToPlace() {
    if (!blessingText.value.trim()) {
        showToast('先写一句祝福吧')
        return
    }
    panelOpen.value = false
}

function beginEditZones() {
    editZones.value = true
    placing.value = false
    panelOpen.value = false
    selected.value = null
    currentPoints = []
    nextTick(redrawStrokes)
}

async function onCanvasClick(e: MouseEvent) {
    if (editZones.value) return // 编辑禁区时由画笔指针事件接管
    const rect = canvasRef.value?.getBoundingClientRect()
    if (!rect) return
    const [x, y] = normPoint(rect, e.clientX, e.clientY)

    if (!placing.value || panelOpen.value) return
    if (!placementAllowed(x, y)) {
        showToast(pickTip(ZONE_TIPS))
        return
    }
    if (!spotFree(x, y)) {
        showToast(pickTip(OVERLAP_TIPS))
        return
    }
    await submitEntry(x, y)
}

async function submitEntry(x: number, y: number) {
    const blessing = blessingText.value.trim()
    if (!blessing) {
        showToast('先写一句祝福吧')
        return
    }
    submitting.value = true
    try {
        const r = await api<{ entry: PhotoEntry }>('api/photo/entries', {
            method: 'POST',
            body: JSON.stringify({ blessing, x_ratio: x, y_ratio: y }),
        })
        const idx = entries.value.findIndex((it) => it.user_id === r.entry.user_id)
        if (idx >= 0) entries.value[idx] = r.entry
        else entries.value.push(r.entry)
        placing.value = false
        await loadMe()
        showToast(isEditing.value ? '已更新你的留影' : '已把你的祝福留在月宫')
    } catch (err: any) {
        showToast(err.message || '提交失败')
    } finally {
        submitting.value = false
    }
}

async function removeMyEntry() {
    if (!myEntry.value) return
    submitting.value = true
    try {
        await api('api/photo/entries', { method: 'DELETE' })
        entries.value = entries.value.filter((it) => it.user_id !== myEntry.value?.user_id)
        await loadMe()
        blessingText.value = ''
        showToast('已撤下你的留影')
    } catch (err: any) {
        showToast(err.message || '操作失败')
    } finally {
        submitting.value = false
    }
}

// --- 管理员删除 ---
async function adminDelete(entry: PhotoEntry) {
    submitting.value = true
    try {
        await api(`api/photo/entries/${entry.id}`, { method: 'DELETE' })
        entries.value = entries.value.filter((it) => it.id !== entry.id)
        if (selected.value?.id === entry.id) selected.value = null
        confirmDelete.value = null
        showToast('已删除该留影')
    } catch (err: any) {
        showToast(err.message || '删除失败')
    } finally {
        submitting.value = false
    }
}

// --- 入口 ---
async function main() {
    try {
        const bridge = await setupChildBridge()
        if (bridge?.accessToken) {
            accessToken = bridge.accessToken
        } else if (isEmbedded) {
            if (!clientId) throw new Error('缺少 VITE_DISCORD_CLIENT_ID 配置')
            await setupDiscordSdk()
        }
        // 独立浏览器匿名访问：仅浏览（me 接口会 401，忽略）

        await loadConfig()
        await loadMe()
        phase.value = 'ready'
        window.addEventListener('resize', recomputeCanvas)
        requestAnimationFrame(recomputeCanvas)
    } catch (e: any) {
        console.error('[PhotoWall] 初始化失败:', e)
        errorMsg.value = e.message || '加载失败，请稍后再试'
        phase.value = 'error'
    }
}

// 键盘弹出时把实际可视高度写进 CSS 变量，弹窗随之抬到键盘上方，
// 「继续，选择位置」按钮始终可见无需滚动
function trackKeyboard() {
    const vv = window.visualViewport
    if (!vv) return
    const update = () => {
        const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop)
        document.documentElement.style.setProperty('--kb', `${Math.round(kb)}px`)
    }
    vv.addEventListener('resize', update)
    vv.addEventListener('scroll', update)
    update()
}

onMounted(() => {
    trackKeyboard()
    main()
})

// 画布尺寸或禁区状态变化时重绘笔划
watch([canvasBox, editZones, placing], () => nextTick(redrawStrokes))
watch(strokes, () => nextTick(redrawStrokes), { deep: true })
</script>

<template>
    <div class="page">
        <!-- 侧栏：宽视口在左侧（对齐 DC 1367x559 / 752x360 超宽矮比），窄视口在顶部 -->
        <aside class="side">
            <div class="side-actions">
                <template v-if="placing && !panelOpen">
                    <p class="zone-tip">在画面中未被涂抹的区域点击放置</p>
                    <button class="ghost-btn block" @click="cancelPlacing">取消放置</button>
                </template>
                <template v-else-if="canEdit">
                    <div class="btn-row">
                        <button class="primary-btn" :disabled="submitting" @click="beginPlacing">添加</button>
                        <button v-if="isEditing" class="ghost-btn" :disabled="submitting" @click="removeMyEntry">撤下</button>
                    </div>
                </template>
                <p v-else class="guest-tip">公开浏览中 · 从 Discord 进入后可留下祝福</p>
            </div>

            <!-- 参与名单：把超宽视口的剩余空间变成内容 -->
            <div v-if="entries.length" class="side-list">
                <p class="list-count">{{ entries.length }} 位伙伴</p>
                <button
                    v-for="entry in entries"
                    :key="'L' + entry.id"
                    class="member-chip"
                    @click="selected = entry"
                >
                    <img v-if="entry.avatar_url" :src="fullUrl(entry.avatar_url)" alt="" />
                    <span v-else class="chip-fallback">{{ entry.display_name.slice(0, 1) }}</span>
                    <span class="chip-name">{{ entry.display_name }}</span>
                </button>
            </div>
        </aside>

        <!-- 画布（外层 stage 负责按图片比例居中适配，完整显示不裁切） -->
        <div ref="stageRef" class="stage">
            <a class="download-btn" :href="exportUrl" target="_blank" rel="noopener" aria-label="下载大合影">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
                    stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 3v12" /><path d="m7 11 5 5 5-5" /><path d="M4 20h16" />
                </svg>
            </a>
        <main
            ref="canvasRef"
            class="canvas"
            :class="{ placing: placing, 'zones-editing': editZones }"
            :style="canvasBox ? { width: canvasBox.w + 'px', height: canvasBox.h + 'px' } : undefined"
            @click="onCanvasClick"
        >
            <img v-if="fullBackgroundUrl" class="bg" :src="fullBackgroundUrl" alt="" draggable="false" />

            <!-- 画笔禁区层：编辑模式接收涂抹，放置模式弱提示 -->
            <canvas
                ref="strokeCanvasRef"
                class="stroke-canvas"
                :class="{ edit: editZones, hint: placing && !editZones && strokes.length > 0 }"
                @pointerdown.prevent="onPaintStart"
                @pointermove.prevent="onPaintMove"
                @pointerup="onPaintEnd"
                @pointercancel="onPaintEnd"
            ></canvas>

            <!-- 已放置的头像（尺寸随人数自适应，无边框） -->
            <button
                v-for="entry in entries"
                :key="entry.id"
                class="sticker"
                :style="{
                    left: `${entry.x_ratio * 100}%`,
                    top: `${entry.y_ratio * 100}%`,
                }"
                @click.stop="selected = entry"
            >
                <span
                    class="avatar-ring"
                    :style="{ width: avatarSize + 'px', height: avatarSize + 'px' }"
                >
                    <img v-if="entry.avatar_url" :src="fullUrl(entry.avatar_url)" alt="" draggable="false" />
                    <span v-else class="avatar-fallback">{{ entry.display_name.slice(0, 1) }}</span>
                </span>
                <span class="sticker-name" :style="{ fontSize: Math.max(9, avatarSize * 0.19) + 'px' }">
                    {{ shortName(entry.display_name) }}
                </span>
            </button>

            <!-- 放置模式提示（在侧栏，不遮挡画面） -->
        </main>
        </div>

        <!-- 祝福输入面板 -->
        <div v-if="panelOpen" class="overlay" @click.self="cancelPlacing">
            <div ref="blessPanelRef" class="panel">
                <h2 class="panel-title">{{ isEditing ? '调整你的祝福' : '留下一句祝福' }}</h2>
                <p class="panel-sub">头像与名字来自你的 Discord 账号，只需写下祝福</p>
                <textarea
                    v-model="blessingText"
                    class="blessing-input"
                    rows="3"
                    maxlength="100"
                    placeholder="例如：但愿人长久，千里共婵娟"
                    @focus="blessFocus"
                ></textarea>
                <div class="panel-actions">
                    <button class="ghost-btn" @click="cancelPlacing">返回</button>
                    <button class="primary-btn" @click="proceedToPlace">继续，选择位置</button>
                </div>
            </div>
        </div>

        <!-- 祝福详情 -->
        <div v-if="selected" class="overlay" @click.self="selected = null">
            <div class="panel detail">
                <div class="detail-head">
                    <span class="avatar-ring small">
                        <img v-if="selected.avatar_url" :src="fullUrl(selected.avatar_url)" alt="" />
                        <span v-else class="avatar-fallback">{{ selected.display_name.slice(0, 1) }}</span>
                    </span>
                    <div>
                        <h3 class="detail-name">{{ selected.display_name }}</h3>
                        <p class="detail-time">{{ fmtTime(selected.created_at) }}</p>
                    </div>
                </div>
                <p class="detail-blessing">{{ selected.blessing }}</p>
                <div class="panel-actions">
                    <button
                        v-if="isAdmin && selected.user_id !== me?.user_id"
                        class="danger-btn"
                        :disabled="submitting"
                        @click="confirmDelete = selected"
                    >删除该留影</button>
                    <button class="ghost-btn" @click="selected = null">关闭</button>
                </div>
            </div>
        </div>

        <!-- 管理员删除确认 -->
        <div v-if="confirmDelete" class="overlay" @click.self="confirmDelete = null">
            <div class="panel">
                <h2 class="panel-title">确认删除</h2>
                <p class="panel-sub">
                    将删除「{{ confirmDelete.display_name }}」的留影及其祝福，此操作不可撤销。
                </p>
                <div class="panel-actions">
                    <button class="ghost-btn" @click="confirmDelete = null">取消</button>
                    <button class="danger-btn" :disabled="submitting" @click="adminDelete(confirmDelete)">
                        {{ submitting ? '删除中…' : '确认删除' }}
                    </button>
                </div>
            </div>
        </div>

        <!-- 轻提示 -->
        <transition name="fade">
            <div v-if="toast" class="toast">{{ toast }}</div>
        </transition>

        <!-- 加载/错误 -->
        <div v-if="phase !== 'ready'" class="boot">
            <p v-if="phase === 'loading'" class="boot-text">月色正在铺开</p>
            <template v-else>
                <p class="boot-text">{{ errorMsg }}</p>
                <button class="ghost-btn" @click="location.reload()">重新加载</button>
            </template>
        </div>
    </div>
</template>
