import { createDiscreteApi, darkTheme } from 'naive-ui'

const { message } = createDiscreteApi(['message'], {
  configProviderProps: { theme: darkTheme },
})

export function toastError(content: string): void {
  message.error(content)
}

export function toastSuccess(content: string): void {
  message.success(content)
}
