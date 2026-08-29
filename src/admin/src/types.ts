export type MeInfo = {
  user_id: string
}

export type GlobalSettings = {
  chat_enabled: boolean
  two_stage_enabled: boolean
  api_fallback_enabled: boolean
  feeding_image_enabled: boolean
  feeding_command_enabled: boolean
  warm_up_enabled: boolean
  reply_delay_seconds: number
}

export type AvailableModel = {
  full_id: string
  display_name: string
  provider_name: string
  enabled: boolean
  supports_vision: boolean
  supports_tools: boolean
  supports_thinking: boolean
}

export type ModelSelectionSettings = {
  ai_model: string | null
  tool_model: string | null
  writer_model: string | null
  available: AvailableModel[]
}

export type Provider = {
  id: number
  name: string
  provider_type: string
  display_name: string
  base_url: string
  enabled: boolean
  has_api_key: boolean
}

export type GenerationConfig = {
  temperature: number
  top_p: number
  top_k: number
  max_output_tokens: number
  presence_penalty: number
  frequency_penalty: number
  thinking_budget_tokens: number
}

export type PromptConfig = {
  system_prompt: string
  jailbreak_user_prompt: string
  jailbreak_model_response: string
  jailbreak_final_instruction: string
  use_cache_optimized_build: boolean
}

export type ModelConfig = {
  id: number
  model_name: string
  display_name: string
  provider_id: number
  actual_model: string
  supports_vision: boolean
  supports_tools: boolean
  supports_thinking: boolean
  max_output_tokens: number
  generation_config: GenerationConfig
  prompt_config: PromptConfig
  enabled: boolean
}

export type ToolInfo = {
  name: string
  description: string
  enabled: boolean
  protected: boolean
}

export type EmbeddingOptionSource =
  | string
  | {
      full_id?: string
      id?: string | number
      value?: string
      model?: string
      name?: string
      display_name?: string
      label?: string
    }

export type EmbeddingSettings = {
  embedding_model: string | null
  disabled_embedding_models: string[]
  available: EmbeddingOptionSource[]
}

export type CooldownChannel = {
  guild_id: string | number
  entity_id: string | number
  chat_enabled: boolean
  fixed_cooldown: number
  frequency_cooldown: number
}

export type KeywordFilter = {
  keywords: string[]
  ignore: string[]
}

export type AbArm = {
  id: number
  label: string
  model_full_id: string
  traffic_percent: number
  enabled: boolean
}

export type AbExperiment = {
  id: number
  name: string
  note: string
  enabled: boolean
  created_at: string
  arms: AbArm[]
}

export type AbStatsVotes = {
  better: number
  worse: number
  same: number
  total: number
}

export type AbStatsArm = {
  arm_id: number
  label: string
  model_full_id: string
  traffic_percent: number
  routed_count: number
  votes: AbStatsVotes
  better_rate: number
  worse_rate: number
  net_score: number
}

export type AbDailyPoint = {
  date: string
  arm_id: number
  routed: number
  better: number
  worse: number
  same: number
}

export type AbReasonCount = {
  reason: string
  count: number
}

export type AbStats = {
  experiment: AbExperiment
  arms: AbStatsArm[]
  totals: Record<string, unknown>
  daily: AbDailyPoint[]
  reasons: AbReasonCount[]
}

export type AbFeedback = {
  id: number
  reply_id: number | string | null
  user_id: string | number
  reasons: unknown
  free_text: string | null
  created_at: string
  question_text: string | null
  reply_text: string | null
  arm_id?: number | string | null
  model_full_id?: string | null
}

export type EditableArm = {
  id?: number
  label: string
  model_full_id: string | null
  traffic_percent: number
  enabled: boolean
}

export type DataResourceInfo = {
  name: string
  label?: string | null
}

export type DataField = {
  name: string
  label?: string | null
  type?: string | null
  editable?: boolean | null
}

export type DataListResult = {
  items?: Array<Record<string, unknown>> | null
  total?: number | null
  page?: number | null
  page_size?: number | null
  fields?: DataField[] | null
}

export type AuditEntry = {
  id?: number | string
  created_at?: string | null
  user_id?: string | number | null
  action?: string | null
  target_type?: string | null
  target_id?: string | number | null
  detail?: unknown
  [key: string]: unknown
}

export type AuditListResult = {
  items?: AuditEntry[] | null
  total?: number | null
  page?: number | null
  page_size?: number | null
}

export type PersonaItem = {
  key: string
  label?: string | null
  group?: string | null
  value?: string | null
  overridden?: boolean | null
}

export type PersonaData = {
  texts?: PersonaItem[] | null
  identity?: PersonaItem[] | null
}

export type ConfigOverrideItem = {
  key: string
  group?: string | null
  label?: string | null
  description?: string | null
  default?: unknown
  value?: unknown
  effective?: unknown
}

export type BlacklistEntry = {
  scope?: string | null
  user_id?: string | number | null
  guild_id?: string | number | null
  reason?: string | null
  created_at?: string | null
  [key: string]: unknown
}

export type MutedChannel = {
  guild_id?: string | number | null
  channel_id?: string | number | null
}

export type EventInfo = {
  id: string | number
  name?: string | null
  is_active?: boolean | null
  start_at?: string | null
  end_at?: string | null
  start?: string | null
  end?: string | null
  files?: unknown
}
