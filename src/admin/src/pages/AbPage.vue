<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NButton,
  NCard,
  NInput,
  NModal,
  NPopconfirm,
  NSpace,
  NSpin,
  NSwitch,
  NTag,
  NText,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'
import AbArmsEditor from '../components/AbArmsEditor.vue'
import type { AbExperiment, AvailableModel, EditableArm, ModelSelectionSettings } from '../types'
import { formatDateTime, toNumber } from '../utils'

const router = useRouter()
const loading = ref(true)
const experiments = ref<AbExperiment[]>([])
const availableModels = ref<AvailableModel[]>([])
let modelsLoaded = false

const showCreate = ref(false)
const creating = ref(false)
const createForm = reactive({ name: '', note: '' })
const createArms = ref<EditableArm[]>([])

const showMeta = ref(false)
const savingMeta = ref(false)
const metaForm = reactive({ id: 0, name: '', note: '' })

const showArms = ref(false)
const savingArms = ref(false)
const armsExperimentId = ref(0)
const armsEdit = ref<EditableArm[]>([])

async function ensureModels(): Promise<void> {
  if (modelsLoaded) return
  try {
    const data = await api.get<ModelSelectionSettings | null>('settings/models')
    availableModels.value = Array.isArray(data?.available) ? data.available : []
    modelsLoaded = true
  } catch {}
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<AbExperiment[] | null>('ab/experiments')
    experiments.value = (Array.isArray(data) ? data : []).map((experiment) => ({
      ...experiment,
      enabled: !!experiment.enabled,
      arms: (experiment.arms ?? []).map((arm) => ({ ...arm, enabled: !!arm.enabled })),
    }))
  } catch {} finally {
    loading.value = false
  }
}

function openCreate(): void {
  createForm.name = ''
  createForm.note = ''
  createArms.value = [{ label: '', model_full_id: null, traffic_percent: 50, enabled: true }]
  showCreate.value = true
  void ensureModels()
}

async function submitCreate(): Promise<void> {
  if (createForm.name.trim().length === 0) {
    toastError('请填写实验名称')
    return
  }
  if (createArms.value.length === 0) {
    toastError('请至少添加一个分组')
    return
  }
  for (const arm of createArms.value) {
    if (arm.label.trim().length === 0 || arm.model_full_id == null) {
      toastError('每个分组需要填写标签并选择模型')
      return
    }
  }
  creating.value = true
  try {
    await api.post('ab/experiments', {
      name: createForm.name.trim(),
      note: createForm.note.trim(),
      arms: createArms.value.map((arm) => ({
        label: arm.label.trim(),
        model_full_id: arm.model_full_id,
        traffic_percent: arm.traffic_percent ?? 0,
        enabled: arm.enabled,
      })),
    })
    showCreate.value = false
    toastSuccess('已创建')
    await load()
  } catch {} finally {
    creating.value = false
  }
}

function openMeta(experiment: AbExperiment): void {
  metaForm.id = experiment.id
  metaForm.name = experiment.name
  metaForm.note = experiment.note ?? ''
  showMeta.value = true
}

async function saveMeta(): Promise<void> {
  if (metaForm.name.trim().length === 0) {
    toastError('请填写实验名称')
    return
  }
  savingMeta.value = true
  try {
    await api.put(`ab/experiments/${metaForm.id}`, { name: metaForm.name.trim(), note: metaForm.note.trim() })
    showMeta.value = false
    toastSuccess('已保存')
    await load()
  } catch {} finally {
    savingMeta.value = false
  }
}

function openArms(experiment: AbExperiment): void {
  armsExperimentId.value = experiment.id
  armsEdit.value = (Array.isArray(experiment.arms) ? experiment.arms : []).map((arm) => ({
    id: arm.id,
    label: arm.label ?? '',
    model_full_id: arm.model_full_id ?? null,
    traffic_percent: toNumber(arm.traffic_percent),
    enabled: !!arm.enabled,
  }))
  showArms.value = true
  void ensureModels()
}

async function saveArms(): Promise<void> {
  if (armsEdit.value.length === 0) {
    toastError('请至少添加一个分组')
    return
  }
  for (const arm of armsEdit.value) {
    if (arm.label.trim().length === 0 || arm.model_full_id == null) {
      toastError('每个分组需要填写标签并选择模型')
      return
    }
  }
  savingArms.value = true
  try {
    await api.put(`ab/experiments/${armsExperimentId.value}/arms`, {
      arms: armsEdit.value.map((arm) => {
        const out: Record<string, unknown> = {
          label: arm.label.trim(),
          model_full_id: arm.model_full_id,
          traffic_percent: arm.traffic_percent ?? 0,
          enabled: arm.enabled,
        }
        if (arm.id != null) out.id = arm.id
        return out
      }),
    })
    showArms.value = false
    toastSuccess('已保存')
    await load()
  } catch {} finally {
    savingArms.value = false
  }
}

async function toggleEnabled(experiment: AbExperiment, value: boolean): Promise<void> {
  const previous = experiment.enabled
  experiment.enabled = value
  try {
    await api.put(`ab/experiments/${experiment.id}/enabled`, { enabled: value })
    toastSuccess(value ? '已启用' : '已停用')
  } catch {
    experiment.enabled = previous
  }
}

async function remove(experiment: AbExperiment): Promise<void> {
  try {
    await api.delete(`ab/experiments/${experiment.id}`)
    toastSuccess('已删除')
    await load()
  } catch {}
}

onMounted(() => void load())
</script>

<template>
  <n-spin :show="loading">
    <n-space vertical :size="16">
      <n-space justify="end">
        <n-button type="primary" @click="openCreate">创建实验</n-button>
      </n-space>
      <n-text v-if="experiments.length === 0" depth="3">暂无实验</n-text>
      <n-card v-for="experiment in experiments" :key="experiment.id" size="small" class="page-card">
        <n-space vertical :size="10">
          <n-space align="center" :size="10" wrap>
            <span class="experiment-name">{{ experiment.name }}</span>
            <n-switch :value="experiment.enabled" size="small" @update:value="(value: boolean) => toggleEnabled(experiment, value)" />
            <n-text depth="3" size="small">创建于 {{ formatDateTime(experiment.created_at) }}</n-text>
          </n-space>
          <n-text v-if="experiment.note" depth="2" size="small">{{ experiment.note }}</n-text>
          <n-space :size="6" wrap>
            <n-tag
              v-for="arm in experiment.arms"
              :key="arm.id"
              size="small"
              :type="arm.enabled ? 'info' : 'default'"
              :bordered="false"
            >
              {{ arm.label }} · {{ arm.model_full_id }}（{{ arm.traffic_percent }}%）
            </n-tag>
          </n-space>
          <n-space :size="8">
            <n-button size="small" @click="openMeta(experiment)">编辑信息</n-button>
            <n-button size="small" @click="openArms(experiment)">配置分组</n-button>
            <n-button size="small" type="primary" secondary @click="router.push({ name: 'ab-stats', params: { id: experiment.id } })">
              查看统计
            </n-button>
            <n-popconfirm @positive-click="remove(experiment)">
              <template #trigger>
                <n-button size="small" type="error" secondary>删除</n-button>
              </template>
              确认删除该实验及全部数据？
            </n-popconfirm>
          </n-space>
        </n-space>
      </n-card>
    </n-space>
  </n-spin>

  <n-modal v-model:show="showCreate" preset="card" title="创建实验" style="width: 720px">
    <n-space vertical :size="16">
      <n-input v-model:value="createForm.name" placeholder="实验名称" />
      <n-input v-model:value="createForm.note" type="textarea" :rows="2" placeholder="备注（可选）" />
      <ab-arms-editor v-model="createArms" :models="availableModels" />
      <n-space justify="end">
        <n-button @click="showCreate = false">取消</n-button>
        <n-button type="primary" :loading="creating" @click="submitCreate">创建</n-button>
      </n-space>
    </n-space>
  </n-modal>

  <n-modal v-model:show="showMeta" preset="card" title="编辑实验信息" style="width: 520px">
    <n-space vertical :size="16">
      <n-input v-model:value="metaForm.name" placeholder="实验名称" />
      <n-input v-model:value="metaForm.note" type="textarea" :rows="2" placeholder="备注" />
      <n-space justify="end">
        <n-button @click="showMeta = false">取消</n-button>
        <n-button type="primary" :loading="savingMeta" @click="saveMeta">保存</n-button>
      </n-space>
    </n-space>
  </n-modal>

  <n-modal v-model:show="showArms" preset="card" title="配置实验分组" style="width: 720px">
    <n-space vertical :size="16">
      <ab-arms-editor v-model="armsEdit" :models="availableModels" />
      <n-space justify="end">
        <n-button @click="showArms = false">取消</n-button>
        <n-button type="primary" :loading="savingArms" @click="saveArms">保存</n-button>
      </n-space>
    </n-space>
  </n-modal>
</template>

<style scoped>
.experiment-name {
  font-size: 16px;
  font-weight: 500;
}
</style>
