<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { DiscordSDK } from "@discord/embedded-app-sdk";

// --- 响应式状态定义 ---
const authState = ref("loading"); // loading, authenticating, authenticated, error
const statusMessage = ref("Initializing...");
const userData = ref<any>(null); // 存储用户信息
const errorMessage = ref("");

// --- Discord SDK 配置 ---
// 重要：你需要确保在你的 .env 文件中定义了 VITE_DISCORD_CLIENT_ID
const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
let accessToken: string | null = null;
const discordSdk = new DiscordSDK(clientId);

// --- 核心认证逻辑 ---
async function setupDiscordSdk() {
  try {
    authState.value = "authenticating";
    statusMessage.value = "Waiting for Discord SDK to be ready...";
    await discordSdk.ready();
    console.log("Discord SDK is ready.");

    statusMessage.value = "Authorizing with Discord...";
    const { code } = await discordSdk.commands.authorize({
      client_id: discordSdk.clientId,
      response_type: "code",
      state: "",
      prompt: "none",
      scope: ["identify", "guilds"], // 根据需要调整 scope
    });
    console.log("Authorization code received.");

    statusMessage.value = "Exchanging authorization code for a token...";
    const response = await fetch("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to get access token: ${errorText}`);
    }

    const { access_token } = await response.json();
    accessToken = access_token;
    console.log("Access token received.");

    statusMessage.value = "Authenticating with the received token...";
    const auth = await discordSdk.commands.authenticate({ access_token });

    if (!auth) {
      throw new Error("Discord authentication failed.");
    }
    
    userData.value = auth.user;
    authState.value = "authenticated";
    statusMessage.value = `Welcome, ${auth.user.username}!`;
    console.log("Authentication successful.", auth);

  } catch (e: any) {
    errorMessage.value = e.message || "An unknown error occurred.";
    authState.value = "error";
    statusMessage.value = "Authentication Failed";
    console.error("Authentication Error:", e);
  }
}

// --- Vue 生命周期钩子 ---
onMounted(() => {
  setupDiscordSdk();
});

</script>

<template>
  <div class="container">
    <div class="card">
      <h1>Guidance Web Activity</h1>
      <div class="status-box" :class="authState">
        <h2>{{ statusMessage }}</h2>
        
        <div v-if="authState === 'loading'" class="loader"></div>
        
        <div v-if="authState === 'authenticating'" class="loader"></div>

        <div v-if="authState === 'authenticated'" class="user-info">
          <p><strong>User ID:</strong> {{ userData?.id }}</p>
          <p><strong>Username:</strong> {{ userData?.username }}</p>
          <img :src="`https://cdn.discordapp.com/avatars/${userData?.id}/${userData?.avatar}.png`" alt="User Avatar" class="avatar"/>
        </div>

        <div v-if="authState === 'error'" class="error-details">
          <p><strong>Error:</strong> {{ errorMessage }}</p>
          <p>Please try reloading the activity. If the problem persists, contact support.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #2c2f33;
  color: #ffffff;
  font-family: 'Helvetica Neue', sans-serif;
}

.card {
  background-color: #23272a;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 500px;
  text-align: center;
}

h1 {
  margin-bottom: 1.5rem;
  color: #7289da; /* Discord Blurple */
}

.status-box {
  padding: 1.5rem;
  border-radius: 6px;
  transition: background-color 0.3s ease;
}

.status-box.loading, .status-box.authenticating {
  background-color: #3a3f44;
}

.status-box.authenticated {
  background-color: #43b581; /* Discord Green */
}

.status-box.error {
  background-color: #f04747; /* Discord Red */
}

.loader {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #7289da;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 1rem auto;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.user-info {
  margin-top: 1rem;
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  margin-top: 1rem;
  border: 3px solid #ffffff;
}

.error-details {
  margin-top: 1rem;
  word-wrap: break-word;
}
</style>
