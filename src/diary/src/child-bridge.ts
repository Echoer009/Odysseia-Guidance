export interface BridgeData {
  accessToken: string
  user: { id: string; username?: string } | null
}

export function setupChildBridge(): Promise<BridgeData | null> {
  const isInIframe = window.parent !== window

  if (!isInIframe) {
    return Promise.resolve(null)
  }

  return new Promise<BridgeData | null>((resolve) => {
    const timeout = setTimeout(() => {
      console.warn('[ChildBridge] Timeout waiting for parent auth data, falling back to standalone')
      window.removeEventListener('message', handler)
      resolve(null)
    }, 5000)

    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'AUTH_DATA' && event.data.accessToken) {
        clearTimeout(timeout)
        window.removeEventListener('message', handler)
        console.log('[ChildBridge] Received auth data from parent')
        resolve({
          accessToken: event.data.accessToken,
          user: event.data.user || null,
        })
      }
    }
    window.addEventListener('message', handler)
    window.parent.postMessage({ type: 'CHILD_READY' }, '*')
  })
}
