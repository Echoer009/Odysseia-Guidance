<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NSpace,
  NSpin,
  NText,
} from 'naive-ui'
import { api } from '../api'
import { toastError, toastSuccess } from '../feedback'

const adjusting = ref(false)

const adjustForm = reactive({
  user_id: null as number | null,
  amount: null as number | null,
  reason: '',
})

const announcementLoading = ref(true)
const announcementSaving = ref(false)
const announcementText = ref('')
let announcementKind: 'string' | 'content' | 'announcement' | 'value' = 'content'

async function loadAnnouncement(): Promise<void> {
  announcementLoading.value = true
  try {
    const data = await api.get<unknown>('shop/announcement')
    if (typeof data === 'string') {
      announcementText.value = data
      announcementKind = 'string'
    } else if (data != null && typeof data === 'object') {
      const record = data as Record<string, unknown>
      if ('content' in record) {
        announcementText.value = record.content == null ? '' : String(record.content)
        announcementKind = 'content'
      } else if ('announcement' in record) {
        announcementText.value = record.announcement == null ? '' : String(record.announcement)
        announcementKind = 'announcement'
      } else {
        announcementText.value = record.value == null ? '' : String(record.value)
        announcementKind = 'value'
      }
    }
  } catch {
  } finally {
    announcementLoading.value = false
  }
}

async function saveAnnouncement(): Promise<void> {
  announcementSaving.value = true
  try {
    if (announcementKind === 'string') await api.put('shop/announcement', announcementText.value)
    else await api.put('shop/announcement', { [announcementKind]: announcementText.value })
    toastSuccess('公告已保存')
  } catch {
  } finally {
    announcementSaving.value = false
  }
}

async function submitAdjust(): Promise<void> {
  if (adjustForm.user_id == null || adjustForm.amount == null || adjustForm.reason.trim().length === 0) {
    toastError('请填写用户 ID、调整金额与原因')
    return
  }
  if (adjustForm.amount === 0) {
    toastError('调整金额不能为零')
    return
  }
  adjusting.value = true
  try {
    const data = await api.post<{ new_balance?: number | string } | null>('economy/adjust', {
      user_id: adjustForm.user_id,
      amount: adjustForm.amount,
      reason: adjustForm.reason.trim(),
    })
    if (data != null && data.new_balance != null) toastSuccess(`已调整，当前余额 ${String(data.new_balance)}`)
    else toastSuccess('金币已调整')
    adjustForm.amount = null
    adjustForm.reason = ''
  } catch {
  } finally {
    adjusting.value = false
  }
}

onMounted(() => void loadAnnouncement())
</script>

<template>
  <n-grid :x-gap="16" :y-gap="16" :cols="1" m="2" responsive="screen">
    <n-grid-item>
      <n-card title="调整金币" size="small">
        <n-form label-placement="top">
          <n-form-item label="用户 ID" required>
            <n-input-number v-model:value="adjustForm.user_id" style="width: 100%" :precision="0" placeholder="user_id" />
          </n-form-item>
          <n-form-item label="调整金额（可为负）" required>
            <n-input-number v-model:value="adjustForm.amount" style="width: 100%" :precision="0" placeholder="正数增加，负数扣除" />
          </n-form-item>
          <n-form-item label="原因" required>
            <n-input v-model:value="adjustForm.reason" type="textarea" :rows="3" placeholder="操作原因，必填" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button type="primary" :loading="adjusting" @click="submitAdjust">提交调整</n-button>
          </n-space>
        </template>
      </n-card>
    </n-grid-item>
    <n-grid-item>
      <n-card title="商店公告" size="small">
        <n-spin :show="announcementLoading">
          <n-input v-model:value="announcementText" type="textarea" class="mono" :rows="12" placeholder="商店公告内容" />
        </n-spin>
        <template #footer>
          <n-space vertical :size="4">
            <n-text depth="3" size="small">支持 {guidance_url} 占位符</n-text>
            <n-space justify="end">
              <n-button type="primary" :loading="announcementSaving" @click="saveAnnouncement">保存</n-button>
            </n-space>
          </n-space>
        </template>
      </n-card>
    </n-grid-item>
  </n-grid>
</template>
