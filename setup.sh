#!/bin/bash

# Odysseia 部署配置脚本
# 让类脑娘来帮你配置一切吧～

# 颜色定义
PINK='\033[38;5;213m'
SKY='\033[38;5;117m'
CYAN='\033[38;5;159m'
MINT='\033[38;5;120m'
SUN='\033[38;5;220m'
HEART='\033[38;5;204m'

WARM_1='\033[38;5;226m'
WARM_2='\033[38;5;214m'
WARM_3='\033[38;5;209m'
WARM_4='\033[38;5;203m'
WARM_5='\033[38;5;198m'
WARM_6='\033[38;5;163m'
NC='\033[0m'

say_hello() { echo -e "${PINK}💕 $1${NC}"; }
say_success() { echo -e "${MINT}✨ $1${NC}"; }
say_wait() { echo -e "${SKY}🌸 $1${NC}"; }
say_warning() { echo -e "${SUN}💫 $1${NC}"; }
say_oops() { echo -e "${HEART}😅 $1${NC}"; }

print_welcome() {
    clear
    echo ""
    echo ""
    echo -e "   ${WARM_1}██████╗ ██████╗  █████╗ ██╗███╗   ██╗      ██████╗ ██╗██████╗ ██╗${NC}"
    echo -e "   ${WARM_2}██╔══██╗██╔══██╗██╔══██╗██║████╗  ██║     ██╔════╝ ██║██╔══██╗██║${NC}"
    echo -e "   ${WARM_3}██████╔╝██████╔╝███████║██║██╔██╗ ██║     ██║  ███╗██║██████╔╝██║${NC}"
    echo -e "   ${WARM_4}██╔══██╗██╔══██╗██╔══██║██║██║╚██╗██║     ██║   ██║██║██╔══██╗██║${NC}"
    echo -e "   ${WARM_5}██████╔╝██║  ██║██║  ██║██║██║ ╚████║     ╚██████╔╝██║██║  ██║███████╗${NC}"
    echo -e "   ${WARM_6}╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝      ╚═════╝ ╚═╝╚═╝  ╚═╝╚══════╝${NC}"
    echo ""
    echo -e "          ${WARM_4}✨ 欢迎来到类脑娘家！让我来帮你配置一切吧～ ✨${NC}"
    echo ""
    echo ""
}

check_env_file() {
    if [ -f ".env" ]; then
        say_warning "检测到 .env 文件已经存在啦！"
        echo ""
        say_hello "类脑娘可能已经在这里住过了，要重新装修一下吗？"
        local reply=""
        printf "是否重新配置？(y/N): "
        read -r reply < /dev/tty
        echo ""
        if [[ ! "$reply" =~ ^[Yy]$ ]]; then
            say_success "好哒～那就保持现状！"
            return 1
        fi
        say_wait "备份一下旧配置..."
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        say_success "备份完成～"
    fi
    return 0
}

ask_question() {
    local question="$1"
    local default="$2"
    local required="$3"
    local input=""

    echo "" >&2
    if [ -n "$default" ]; then
        echo -e "${PINK}💕 $question [默认: $default]${NC}" >&2
        echo -n "你的回答: " >&2
        read -r input < /dev/tty
        if [ -z "$input" ]; then
            input="$default"
        fi
        printf '%s\n' "$input"
    else
        while true; do
            echo -e "${PINK}💕 $question${NC}" >&2
            echo -n "你的回答: " >&2
            read -r input < /dev/tty
            if [ -n "$input" ]; then
                printf '%s\n' "$input"
                return 0
            fi
            if [ "$required" = "true" ]; then
                echo -e "${HEART}😅 这个必须要填哦～${NC}" >&2
            else
                printf '\n'
                return 0
            fi
        done
    fi
}

configure_required() {
    say_wait "首先来配置一些必要的信息～"
    echo "────────────────────────────────────────"

    DISCORD_TOKEN=$(ask_question "Discord 机器人令牌是什么呢？" "" "true")
}

show_guild_id_guide() {
    echo ""
    say_hello "获取服务器 ID 的方法："
    echo ""
    echo -e "  ${CYAN}1.${NC} 打开 Discord 设置 → 高级 → 开启「开发者模式」"
    echo -e "  ${CYAN}2.${NC} 右键点击你的服务器图标"
    echo -e "  ${CYAN}3.${NC} 点击「复制服务器 ID」"
    echo ""
    echo -e "  ${SUN}💡 服务器 ID 是一串数字，比如 1234567890123456789${NC}"
    echo ""
}

configure_vector_mode() {
    echo ""
    say_wait "接下来选择向量模式～"
    echo "────────────────────────────────────────"
    say_hello "向量模式决定了 RAG 检索功能的工作方式"
    echo ""
    echo -e "  ${CYAN}1) 无向量直接聊天${NC} - 不使用 RAG 检索，类脑娘直接对话哦"
    echo -e "  ${CYAN}2) API 向量${NC}       - 使用 Gemini Embedding API（需要 API 密钥）"
    echo -e "  ${CYAN}3) 本地向量${NC}       - 使用 Ollama 本地模型（推荐，隐私安全）"
    echo ""
    say_warning "注意：本地向量模式需要更多内存（约1GB）"

    local reply=""
    while true; do
        printf "请选择向量模式 [1/2/3] (默认: 1): "
        read -r reply < /dev/tty
        echo ""
        case "$reply" in
            ""|1)
                VECTOR_MODE="none"
                say_success "已选择：无向量直接聊天模式（默认）"
                say_warning "RAG 检索功能将被禁用"
                break
                ;;
            2)
                VECTOR_MODE="api"
                say_success "已选择：API 向量模式"
                configure_gemini_api_keys
                break
                ;;
            3)
                VECTOR_MODE="local"
                say_success "已选择：本地向量模式"
                break
                ;;
            *)
                say_oops "无效的选择，请输入 1、2 或 3"
                ;;
        esac
    done

    if [ "$VECTOR_MODE" = "local" ]; then
        echo ""
        say_hello "本地向量模型选择"
        say_wait "默认使用 qwen3-embedding:0.6b 模型（轻量高效）"
        local custom_model=""
        printf "是否使用自定义模型？(y/N): "
        read -r custom_model < /dev/tty
        echo ""
        if [[ "$custom_model" =~ ^[Yy]$ ]]; then
            OLLAMA_MODEL=$(ask_question "Ollama Embedding 模型名称" "qwen3-embedding:0.6b" "false")
        else
            OLLAMA_MODEL="qwen3-embedding:0.6b"
        fi
        say_success "将使用 Embedding 模型: $OLLAMA_MODEL"

        say_wait "视觉模型用于图片理解功能"
        local custom_vision=""
        printf "是否使用自定义视觉模型？(y/N): "
        read -r custom_vision < /dev/tty
        echo ""
        if [[ "$custom_vision" =~ ^[Yy]$ ]]; then
            OLLAMA_VISION_MODEL=$(ask_question "Ollama 视觉模型名称" "qwen3.5:0.8b" "false")
        else
            OLLAMA_VISION_MODEL="qwen3.5:0.8b"
        fi
        say_success "将使用视觉模型: $OLLAMA_VISION_MODEL"
    fi
}

configure_gemini_api_keys() {
    echo ""
    say_hello "Google Gemini API 密钥（用于 API 向量模式的 RAG 检索）"
    say_wait "可以输入多个密钥哦，每个占一行，输入空行结束"
    say_hello "获取地址: https://makersuite.google.com/app/apikey"

    GOOGLE_API_KEYS=""
    key_count=0
    local key=""
    while true; do
        printf "  密钥 #%d (直接回车跳过): " "$((key_count + 1))" >&2
        read -r key < /dev/tty
        if [ -z "$key" ]; then
            if [ $key_count -eq 0 ]; then
                say_warning "跳过 Gemini API 密钥配置～"
                say_warning "API 向量模式将无法使用，建议重新选择其他模式"
            fi
            break
        fi
        if [ -n "$GOOGLE_API_KEYS" ]; then
            GOOGLE_API_KEYS="$GOOGLE_API_KEYS,$key"
        else
            GOOGLE_API_KEYS="$key"
        fi
        key_count=$((key_count + 1))
    done
}

configure_database() {
    echo ""
    say_wait "接下来配置 PostgreSQL 数据库～"
    echo "────────────────────────────────────────"

    POSTGRES_DB=$(ask_question "数据库名称" "braingirl_db" "false")
    POSTGRES_USER=$(ask_question "数据库用户名" "user" "false")
    POSTGRES_PASSWORD=$(ask_question "数据库密码" "password" "false")
    DB_PORT=$(ask_question "数据库端口" "5432" "false")
}

configure_discord() {
    echo ""
    say_wait "配置 Discord 相关设置～"
    echo "────────────────────────────────────────"

    say_hello "开发服务器 ID，用于快速同步命令"
    say_wait "留空则进行全局同步（可能需要一小时）"
    echo ""
    echo -e "  ${CYAN}输入服务器 ID，或输入 ${SUN}?${NC} ${CYAN}查看获取方法${NC}"
    while true; do
        GUILD_ID=$(ask_question "开发服务器 ID" "" "false")
        if [ "$GUILD_ID" = "?" ]; then
            show_guild_id_guide
            GUILD_ID=$(ask_question "开发服务器 ID" "" "false")
        fi
        break
    done

    DEVELOPER_USER_IDS=$(ask_question "开发者用户 ID（多个用逗号分隔）" "" "false")
    ADMIN_ROLE_IDS=$(ask_question "管理员角色 ID（多个用逗号分隔）" "" "false")
}

configure_features() {
    echo ""
    say_wait "配置一些功能开关～"
    echo "────────────────────────────────────────"

    local reply=""
    printf "启用聊天功能？(Y/n): "
    read -r reply < /dev/tty
    echo ""
    if [[ "$reply" =~ ^[Nn]$ ]]; then
        CHAT_ENABLED="False"
        say_warning "聊天功能已关闭～"
    else
        CHAT_ENABLED="True"
        say_success "聊天功能已开启～"
    fi

    printf "记录 AI 完整上下文（用于调试）？(y/N): "
    read -r reply < /dev/tty
    echo ""
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        LOG_AI_FULL_CONTEXT="true"
        say_success "调试日志已开启～"
    else
        LOG_AI_FULL_CONTEXT="false"
    fi
}

configure_other() {
    echo ""
    say_wait "还有一些其他选项～"
    echo "────────────────────────────────────────"

    DISABLED_TOOLS=$(ask_question "禁用的工具（多个用逗号分隔）" "get_yearly_summary" "false")
    say_hello "（可选）论坛搜索频道 ID，用于论坛搜索功能"
    say_wait "留空则不启用论坛搜索"
    FORUM_SEARCH_CHANNEL_IDS=$(ask_question "论坛搜索频道 ID（多个用逗号分隔）" "" "false")
    say_hello "类脑币奖励服务器 ID，用于类脑币奖励功能"
    say_wait "留空则默认使用开发服务器 ID"
    COIN_REWARD_GUILD_IDS=$(ask_question "类脑币奖励服务器 ID（多个用逗号分隔）" "$GUILD_ID" "false")
}

generate_env_file() {
    echo ""
    say_wait "正在生成配置文件..."

    cat > .env << EOF
# Odysseia 环境配置文件
# 由 setup.sh 自动生成

# --- Discord ---
DISCORD_TOKEN="$DISCORD_TOKEN"

# 开发服务器 ID（用于快速同步命令，留空则全局同步）
GUILD_ID="$GUILD_ID"

# 权限控制
DEVELOPER_USER_IDS="$DEVELOPER_USER_IDS"
ADMIN_ROLE_IDS="$ADMIN_ROLE_IDS"

# --- 向量模式配置 ---
# none: 无向量直接聊天（不使用 RAG 检索）
# api: API 向量（使用 Gemini Embedding API，需要下方 GOOGLE_API_KEYS_LIST）
# local: 本地向量（使用 Ollama 本地模型）
VECTOR_MODE=$VECTOR_MODE

# Ollama 模型配置（仅在 VECTOR_MODE=local 时有效）
OLLAMA_MODEL=$OLLAMA_MODEL
OLLAMA_VISION_MODEL=$OLLAMA_VISION_MODEL

# Gemini API 密钥（用于 API 向量模式的 RAG 检索）
GOOGLE_API_KEYS_LIST="$GOOGLE_API_KEYS"

# --- PostgreSQL 数据库 ---
POSTGRES_DB="$POSTGRES_DB"
POSTGRES_USER="$POSTGRES_USER"
POSTGRES_PASSWORD="$POSTGRES_PASSWORD"
DB_PORT=$DB_PORT

# --- 功能开关 ---
CHAT_ENABLED=$CHAT_ENABLED
LOG_AI_FULL_CONTEXT=$LOG_AI_FULL_CONTEXT

# --- 工具配置 ---
DISABLED_TOOLS="$DISABLED_TOOLS"

# --- 类脑币系统 ---
COIN_REWARD_GUILD_IDS="$COIN_REWARD_GUILD_IDS"

# --- 论坛搜索 ---
FORUM_SEARCH_CHANNEL_IDS="$FORUM_SEARCH_CHANNEL_IDS"

# --- SearXNG 联网搜索 ---
SEARXNG_URL="http://searxng:8080"
WEB_SEARCH_MAX_RESULTS=5
WEB_SEARCH_TIMEOUT=10
WEB_SCRAPE_TIMEOUT=15
WEB_SCRAPE_MAX_LENGTH=5000
EOF

    say_success "配置文件生成完成～"
}

ask_start_service() {
    echo ""
    say_hello "配置文件已经准备好啦！"
    say_wait "要不要现在就让类脑娘住进来呢？"
    local reply=""
    printf "现在启动服务吗？(Y/n): "
    read -r reply < /dev/tty
    echo ""
    if [[ ! "$reply" =~ ^[Nn]$ ]]; then
        return 0
    fi
    return 1
}

wait_for_db() {
    local max_attempts=30
    local attempt=1
    local db_host="db"
    local db_port="5432"

    say_wait "等待数据库启动..."
    echo ""

    while [ $attempt -le $max_attempts ]; do
        if docker compose exec -T db pg_isready -h $db_host -p $db_port > /dev/null 2>&1; then
            say_success "数据库已就绪～"
            echo ""
            return 0
        fi

        printf "\r  等待中... ($attempt/$max_attempts)" >&2
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    say_oops "数据库启动超时，请检查 Docker 容器状态"
    docker compose ps db
    exit 1
}

start_service() {
    echo ""
    say_wait "开始准备类脑娘的新家..."
    echo ""

    if ! docker info > /dev/null 2>&1; then
        say_oops "Docker 好像没启动呢～请先启动 Docker 再试一次"
        exit 1
    fi

    say_wait "清理一下旧环境..."
    docker compose down 2>/dev/null || true

    local compose_profile=""
    case "$VECTOR_MODE" in
        "local")
            say_wait "向量模式：本地向量（将启动 Ollama 服务）"
            compose_profile="--profile ollama"
            ;;
        "api")
            say_wait "向量模式：API 向量（不需要 Ollama 服务）"
            ;;
        "none")
            say_wait "向量模式：无向量直接聊天（不需要 Ollama 服务）"
            ;;
        *)
            say_warning "未知的向量模式 '$VECTOR_MODE'，使用默认配置（无向量）"
            ;;
    esac

    echo ""
    say_wait "选择部署方式："
    echo -e "  ${CYAN}1) 公共镜像${NC} - 直接拉取 Docker Hub 镜像（快速，推荐）"
    echo -e "  ${CYAN}2) 本地构建${NC} - 从源代码构建镜像（适合开发调试）"
    local build_choice=""
    printf "请选择 [1/2] (默认: 1): "
    read -r build_choice < /dev/tty
    echo ""

    case "$build_choice" in
        2)
            say_wait "正在从源代码构建镜像..."
            say_hello "这可能需要几分钟，耐心等待哦～"
            if ! docker compose build; then
                say_oops "构建失败了..."
                exit 1
            fi
            say_success "构建完成～"
            ;;
        ""|1)
            say_wait "使用公共镜像 echoni0n/braingirl:latest"
            say_success "无需构建，直接启动～"
            ;;
        *)
            say_wait "使用公共镜像（默认）"
            ;;
    esac

    say_wait "让类脑娘住进来..."
    local compose_cmd="docker compose $compose_profile up -d"
    if eval "$compose_cmd"; then
        say_success "类脑娘已经住进来了～"
    else
        say_oops "搬家过程出问题了..."
        exit 1
    fi

    wait_for_db

    say_wait "帮类脑娘整理一下房间（初始化数据库）..."
    if docker compose exec -T bot_app alembic upgrade head; then
        say_success "房间整理完毕～"
    else
        say_oops "整理房间出问题了..."
        exit 1
    fi

    echo ""
    say_wait "看看类脑娘的状态～"
    docker compose ps
    echo ""

    echo ""
    echo -e "${PINK}╔══════════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${PINK}║${NC}                                                                                      ${PINK}║${NC}"
    echo -e "${PINK}║${NC}     ${CYAN}🌸 耶！类脑娘已经准备好啦！快去 Discord 里 @类脑娘 打招呼吧～ 🌸${NC}             ${PINK}║${NC}"
    echo -e "${PINK}║${NC}                                                                                      ${PINK}║${NC}"
    echo -e "${PINK}╚══════════════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    say_hello "常用命令："
    echo "  查看日志: docker compose logs -f bot_app"
    echo "  停止服务: docker compose down"
    echo "  重启服务: docker compose restart"
    echo ""
    say_warning "完成部署后，还需要在 Discord 中配置 AI 模型哦："
    echo ""
    echo -e "  ${CYAN}1.${NC} 在 Discord 中使用 ${CYAN}/聊天设置${NC} 命令"
    echo -e "  ${CYAN}2.${NC} 点击 ${CYAN}🔌 Provider管理${NC} → 添加你的 AI 端点（Gemini/DeepSeek/OpenAI 兼容等）"
    echo -e "  ${CYAN}3.${NC} 点击 ${CYAN}🤖 Model管理${NC} → 为 Provider 添加可用的模型"
    echo -e "  ${CYAN}4.${NC} 点击 ${CYAN}更换AI模型${NC} → 选择要使用的模型"
    echo ""
    say_wait "配置完成后类脑娘就可以开始聊天啦～"
    echo ""
}

main() {
    print_welcome

    if ! check_env_file; then
        ask_start_service && start_service
        exit 0
    fi

    VECTOR_MODE="none"
    OLLAMA_MODEL=""
    OLLAMA_VISION_MODEL=""

    configure_required
    configure_vector_mode
    configure_database
    configure_discord
    configure_features
    configure_other

    generate_env_file

    if ask_start_service; then
        start_service
    else
        say_success "配置文件已经准备好啦～"
        echo ""
        say_hello "想找类脑娘的时候，运行这些命令就好："
        echo ""
        if [ "$VECTOR_MODE" = "local" ]; then
            echo -e "${CYAN}  docker compose --profile ollama up -d${NC}"
        else
            echo -e "${CYAN}  docker compose up -d${NC}"
        fi
        echo -e "${CYAN}  docker compose exec bot_app alembic upgrade head${NC}"
        echo ""
        say_warning "启动后记得在 Discord 中配置 AI 模型："
        echo -e "  使用 ${CYAN}/聊天设置${NC} → ${CYAN}🔌 Provider管理${NC} 添加 AI 端点"
        echo -e "  然后用 ${CYAN}🤖 Model管理${NC} 添加模型 → ${CYAN}更换AI模型${NC} 选择要用的模型"
        echo ""
    fi
}

main
