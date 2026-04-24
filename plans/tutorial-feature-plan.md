# 新手教程 (Tutorial) 功能方案

## 概述

在频道导览 (tour) 完成之后、引导结束 (finish) 之前，插入一个新的 **tutorial** 场景。教程步骤内容完全由配置文件驱动，组件本身不硬编码任何业务内容。

场景流转变为：

```
loading → welcome → selection → tour → tutorial → finish
```

---

## 一、数据模型

### 1.1 新增 `TutorialSlide` 类型 (`types/index.ts`)

```ts
export interface TutorialSlide {
  id: string
  title: string
  description: string
  tip?: string
  expression: Expression
  icon?: string
}
```

- `id` — 唯一标识
- `title` — 步骤标题
- `description` — 详细说明，支持与 tour 一致的富文本语法（`**bold**`、`{{accent}}`、`\n`、`\n\n`）
- `tip` — 可选的小贴士，显示在描述下方（淡灰色斜体）
- `expression` — 类脑娘在当前步骤的表情
- `icon` — 可选的步骤图标（emoji）

### 1.2 扩展 `SceneName` (`types/index.ts`)

```ts
export type SceneName = 'loading' | 'welcome' | 'selection' | 'tour' | 'tutorial' | 'finish' | 'kickout'
```

---

## 二、教程内容配置

### 2.1 新增 `src/data/tutorialConfig.ts`

纯配置文件，定义教程的所有步骤。内容由你决定，组件只负责渲染。

```ts
import type { TutorialSlide } from '../types'

export const tutorialSlides: TutorialSlide[] = [
  // TODO: 由你填写具体教程步骤
]
```

> 编辑此文件即可增删改教程步骤，无需改动组件代码。

### 2.2 新增教程对话 (`src/data/dialogues/tutorial.ts`)

```ts
import type { DialogueEntry } from '../../types'

export const tutorialStartDialogue: DialogueEntry = {
  text: '',   // TODO: 教程开始时的引导语
  expression: 'happy',
}

export const tutorialEndDialogue: DialogueEntry = {
  text: '',   // TODO: 教程结束时的总结语
  expression: 'wave',
}
```

在 `src/data/dialogues/index.ts` 中添加导出：
```ts
export { tutorialStartDialogue, tutorialEndDialogue } from './tutorial'
```

---

## 三、新增组件：`TutorialTour.vue`

### 3.1 设计思路

与 `ChannelTour.vue` 结构高度一致，复用相同的 UI 模式：
- 左右滑动翻页（touch + mouse）
- 打字机效果展示描述文字
- 顶部 `ProgressBar` 显示进度
- 右侧 `CharacterSprite`（使用教程步骤配置的 expression）
- 步骤标题 + 描述 + 可选 tip
- GSAP 入场/退场动画

**与 ChannelTour 的差异：**
- 背景使用统一的暖色渐变（不加载频道背景图）
- 可选的步骤图标
- tip 区域（淡灰色斜体小字）
- 不加载频道角色立绘变体，使用标准 expression sprite

### 3.2 组件结构

```
TutorialTour.vue
  ├── ProgressBar
  ├── CharacterSprite (expression 变化)
  ├── DialogueBox (仅 feedback 时显示)
  ├── 步骤内容区
  │   ├── 图标 (可选)
  │   ├── 标题 (带 GSAP 入场)
  │   ├── 强调线
  │   ├── 描述 (打字机 + 富文本)
  │   └── Tip (可选)
  └── 底部滑动提示
```

### 3.3 复用逻辑

- **富文本解析**：抽取 `ChannelTour.vue` 中的 `parseDescription` / `renderTokens` 到 `src/utils/parser.ts` 共享
- **滑动交互**：与 ChannelTour 相同的 touch/mouse 滑动逻辑
- **打字机**：与 ChannelTour 相同的 character-by-character 揭示
- **动画**：与 ChannelTour 相同的 GSAP 入场/退场时间线

### 3.4 背景方案

使用柔和的暖色渐变背景（区别于 tour 的频道图）：

```css
.tutorial-bg-fallback {
  background: linear-gradient(180deg, #FFF8F0, #FFEDE0);
}
```

可选：在 `assetsConfig.ts` 中添加教程专用背景图 `bg_tutorial.webp`，加载机制与 tour 一致。

---

## 四、类脑娘教程场景专属台词

### 4.1 戳 (Poke) 台词 — `pokeDialogues.ts` 新增 `tutorial` 场景

在 `PokeScene` 类型中添加 `'tutorial'`（`usePoke.ts`）：
```ts
export type PokeScene = 'welcome' | 'selection' | 'tour' | 'tutorial' | 'finish'
```

在 `pokeDialogues.ts` 中新增 `tutorial` 场景的台词池（6个阶段），贴合"教学/上课"语境：

```ts
tutorial: {
  0: [
    // TODO: 轻微反应，惊讶/俏皮
  ],
  1: [
    // TODO: 温和吐槽
  ],
  2: [
    // TODO: 无奈
  ],
  3: [
    // TODO: 生气警告
  ],
  4: [
    // TODO: 暴怒
  ],
  5: [
    '滚出去！！！',
  ],
},
```

### 4.2 拖拽 (Drag) 台词 — `easterEggDialogues.ts` 修改

当前拖拽台词是全局的（不区分场景）。为支持教程场景专属台词，修改 `getDragDialogue` 签名：

```ts
export function getDragDialogue(phase: number, scene?: string): string
```

新增教程专属拖拽台词池，贴合"上课时被拉扯"的语境：

```ts
const tutorialDragDialogues: Record<number, string[]> = {
  0: [
    // TODO: 惊讶
  ],
  1: [
    // TODO: 吐槽
  ],
  2: [
    // TODO: 无奈
  ],
  3: [
    // TODO: 警告
  ],
  4: [
    // TODO: 暴怒
  ],
  5: [
    '滚出去！！！',
  ],
}
```

在 `getDragDialogue` 中根据 scene 参数选择台词池：

```ts
export function getDragDialogue(phase: number, scene?: string): string {
  let pool: Record<number, string[]> = dragDialogues
  if (scene === 'tutorial') pool = tutorialDragDialogues
  const p = pool[phase]
  if (!p || p.length === 0) return '……'
  return p[Math.floor(Math.random() * p.length)]
}
```

---

## 五、集成改动

### 5.1 `useSceneFeedback.ts` — 支持教程场景

```ts
const hasDialogueBox = currentScene.value === 'welcome' 
  || currentScene.value === 'selection' 
  || currentScene.value === 'tour' 
  || currentScene.value === 'tutorial'  // 新增
  || currentScene.value === 'finish'

const dialogue = type === 'poke'
  ? getPokeDialogue((currentScene.value) as any, result.phase)
  : getDragDialogue(result.phase, currentScene.value)  // 传递 scene
```

### 5.2 `usePoke.ts` — 扩展 PokeScene

```ts
export type PokeScene = 'welcome' | 'selection' | 'tour' | 'tutorial' | 'finish'
```

### 5.3 `App.vue` — 主要集成点

1. **导入** tutorial 相关数据
2. **新增 ref**: `tutorialTourRef`
3. **新增 scene 分支**: `v-else-if="currentScene === 'tutorial'"`
4. **修改流程**:
   - `onTourFinish()` → `transitionTo('tutorial')` 而非直接 `transitionTo('finish')`
   - 新增 `onTutorialFinish()` → `transitionTo('finish')` + 原有 finish 逻辑
5. **getDialogueRef()** 添加 tutorial 分支
6. **教程场景的 HTML**:

```html
<div v-else-if="currentScene === 'tutorial'" class="scene">
  <TutorialTour 
    ref="tutorialTourRef"
    :slides="tutorialSlides"
    :feedback-expression="currentExpression" 
    :is-showing-feedback="isShowingFeedback" 
    @finish="onTutorialFinish" 
    @poke="onPoke" 
    @drag-start="onDragStart" 
  />
</div>
```

### 5.4 `utils/parser.ts` — 抽取共享解析函数

将 `ChannelTour.vue` 中的 `parseDescription`、`tokenCharCount`、`renderTokens` 抽取到 `parser.ts`，供两个 Tour 组件共同使用。

---

## 六、文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **修改** | `src/types/index.ts` | 新增 `TutorialSlide`，扩展 `SceneName` |
| **新增** | `src/data/tutorialConfig.ts` | 教程步骤配置（内容待定） |
| **新增** | `src/data/dialogues/tutorial.ts` | 教程开始/结束对话（内容待定） |
| **修改** | `src/data/dialogues/index.ts` | 导出 tutorial 对话 |
| **修改** | `src/composables/usePoke.ts` | `PokeScene` 添加 `'tutorial'` |
| **修改** | `src/data/pokeDialogues.ts` | 新增 tutorial 场景台词池（内容待定） |
| **修改** | `src/data/easterEggDialogues.ts` | 新增教程拖拽台词池，修改 `getDragDialogue` 签名（内容待定） |
| **修改** | `src/composables/useSceneFeedback.ts` | 支持 tutorial 场景，传递 scene 给 drag |
| **修改** | `src/utils/parser.ts` | 抽取共享富文本解析函数 |
| **修改** | `src/components/ChannelTour.vue` | 改用 parser.ts 中的共享函数 |
| **新增** | `src/components/TutorialTour.vue` | 教程滑动翻页组件 |
| **修改** | `src/App.vue` | 集成 tutorial 场景，调整流程 |

---

## 七、实施顺序

1. **类型定义** — 修改 `types/index.ts`
2. **共享工具** — 抽取 `parser.ts` 中的富文本解析函数
3. **数据配置** — 创建 `tutorialConfig.ts` 和 `dialogues/tutorial.ts`（TODO 占位）
4. **台词系统** — 扩展 `usePoke.ts`、`pokeDialogues.ts`、`easterEggDialogues.ts`（TODO 占位）
5. **反馈系统** — 修改 `useSceneFeedback.ts`
6. **组件开发** — 创建 `TutorialTour.vue`
7. **主流程集成** — 修改 `App.vue`，串联 tour → tutorial → finish
8. **验证** — 场景流转 + poke/drag 台词触发正常

---

## 八、设计一致性保证

- **视觉风格**: 与 ChannelTour 一致的布局（右侧角色立绘 + 左侧内容区 + 顶部进度条 + 底部滑动提示）
- **动画**: 复用 GSAP 入场/退场时间线（相同的 duration、ease、stagger 参数）
- **交互**: 复用相同的滑动翻页 + 打字机 + 点击跳过机制
- **反馈**: 复用 `useSceneFeedback` 的 poke/drag 反馈系统
- **响应式**: 同样的 `@media (max-width: 768px)` 断点处理
- **配置模式**: 与 `channelData.ts`、`tagsConfig.ts` 一致的纯 TS 静态配置文件
