import { DiscordSDK } from '@discord/embedded-app-sdk'

const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID
const queryParams = new URLSearchParams(window.location.search)
const isEmbedded = queryParams.get('frame_id') != null

let accessToken: string | null = null
let currentUser: { id: string; username?: string } | null = null

const loader = document.getElementById('lobby-loader') as HTMLDivElement
const childFrame = document.getElementById('child-frame') as HTMLIFrameElement

async function setupDiscordSdk() {
  if (!clientId) throw new Error('VITE_DISCORD_CLIENT_ID is not set')
  const discordSdk = new DiscordSDK(clientId)
  await discordSdk.ready()

  const { code } = await discordSdk.commands.authorize({
    client_id: discordSdk.clientId,
    response_type: 'code',
    state: '',
    prompt: 'none',
    scope: ['identify', 'guilds'],
  })

  const response = await fetch('/api/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  if (!response.ok) throw new Error(`Token exchange failed: ${response.status}`)
  const { access_token } = await response.json()

  const auth = await discordSdk.commands.authenticate({ access_token })
  if (!auth) throw new Error('Authenticate command failed')

  accessToken = access_token
  if (auth.user) {
    currentUser = { id: auth.user.id, username: auth.user.username }
  }
}

async function getIntent(userId: string): Promise<string | null> {
  try {
    const resp = await fetch(`/api/intent?user_id=${userId}`)
    if (!resp.ok) return null
    const data = await resp.json()
    return data.module || null
  } catch {
    return null
  }
}

function showChildFrame() {
  loader.classList.add('fade-out')
  childFrame.classList.add('visible')
  setTimeout(() => {
    loader.style.display = 'none'
  }, 300)
}

function createChildIframe(module: string) {
  childFrame.src = `/${module}/`
  window.addEventListener('message', (event: MessageEvent) => {
    if (event.data?.type === 'CHILD_READY') {
      childFrame.contentWindow?.postMessage(
        {
          type: 'AUTH_DATA',
          accessToken,
          user: currentUser,
        },
        '*',
      )
      showChildFrame()
    }
  })
}

async function main() {
  try {
    if (isEmbedded) {
      await setupDiscordSdk()
    }

    let module: string | null = null
    if (currentUser) {
      module = await getIntent(currentUser.id)
    }

    if (!module) {
      module = 'guidance'
    }

    createChildIframe(module)
  } catch (e) {
    console.error('[Lobby] Error:', e)
    createChildIframe('guidance')
  }
}

main()
