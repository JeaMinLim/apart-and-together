# AI 등록 및 연동 종합 매뉴얼 (AI Registration Guide)

**따로또같이 (Apart & Together)**는 참여자가 사용하는 AI의 종류나 라이선스 형태에 구애받지 않고 협업할 수 있도록 설계되었습니다.

본인의 AI 사용 환경에 맞춰 **[방법 A: API 키 기반 연동]** 또는 **[방법 B: 구독형 AI MCP 연동]** 중 알맞은 방식을 선택하거나, 두 방식을 함께 사용할 수 있습니다.

---

## 📌 한눈에 보는 연동 방식 비교

| 구분 | [방법 A] API 키 기반 연동 (Multi-AI Hub) | [방법 B] 구독형 AI 연동 (MCP 서버) |
| :--- | :--- | :--- |
| **적합한 사용자** | OpenAI, Claude, Gemini, Grok 등의 API 키를 보유하고 있거나 로컬 Ollama를 사용하는 개발자 | Claude Pro, Cursor Pro 등 웹/앱 구독형으로 사용하여 API 키가 없는 사용자 |
| **사용 인터페이스** | 터미널 CLI (`./bin/multi-ai`) | Claude Desktop 앱 채팅창, Cursor IDE 채팅창 |
| **핵심 기능** | 여러 AI 동시 병렬 질의, 교차 검증, 종합 consensus 도출, 호스트 봇 수명주기 관리 | 자연어 대화로 보안 감사(`audit_code_security`), 공유 우편함 일감 수신 및 결과 제출 |
| **비용** | API 종량제 요금 (Gemini 무료 티어, Ollama 로컬 무료) | 기존 AI 구독료 외 추가 비용 0원 |

---

## 🛠️ 방법 A: API 키 기반 연동 가이드 (Multi-AI Hub)

터미널에서 여러 AI를 묶어 동시에 질문하거나 코드를 검증하고자 할 때 사용합니다.

### 1단계: 환경 설정 파일(`.env`) 생성
프로젝트 루트 디렉토리에서 템플릿 파일(`.env.example`)을 복사하여 `.env`를 생성합니다.

```bash
cp .env.example .env
```

### 2단계: 보유한 AI의 API 키 입력
`.env` 파일을 열고 사용 가능한 AI의 키를 입력합니다. **보유하지 않은 키는 비워두면 자동으로 제외됩니다.**

```ini
# ==========================================
# Apart & Together — Multi-AI API Keys
# ==========================================

# 1. OpenAI (ChatGPT: gpt-4o, gpt-4o-mini 등)
# 발급처: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-...

# 2. Anthropic (Claude: claude-3-5-sonnet 등)
# 발급처: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-...

# 3. Google Gemini (무료 티어 제공)
# 발급처: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIzaSy...

# 4. xAI (Grok)
# 발급처: https://console.x.ai/
XAI_API_KEY=xai-...

# 5. OpenRouter (수백 개 모델 올인원 지원)
# 발급처: https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-...

# 6. 로컬 LLM (Ollama - 완전 무료, 로컬 구동)
# 설치처: https://ollama.com/
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

> [!TIP]
> **API 키가 하나도 없어도 사용할 수 있습니다!**
> 무료 오픈소스 로컬 LLM 도구인 [Ollama](https://ollama.com/)를 설치한 뒤 `ollama run llama3`를 실행해 두면, 비용 없이 로컬에서 완벽하게 작동합니다.

### 3단계: 연동 상태 확인
터미널에서 상태 명령어를 입력하여 정상 등록되었는지 확인합니다:

```bash
./bin/multi-ai status
```

**정상 출력 예시:**
```text
============================================================
  Apart & Together — Multi-AI Hub Status
============================================================
Active Providers: 3 (openai, gemini, ollama)
Configured Providers:
  - openai: ACTIVE (model: gpt-4o-mini)
  - claude: NOT CONFIGURED
  - gemini: ACTIVE (model: gemini-1.5-flash)
  - grok: NOT CONFIGURED
  - openrouter: NOT CONFIGURED
  - ollama: ACTIVE (model: llama3)
```

### 4단계: 터미널 활용 명령어

- **다중 AI 병렬 질의 및 답변 비교**:
  ```bash
  ./bin/multi-ai ask "REST API와 GraphQL의 핵심 차이점과 보안 고려사항을 요약해줘"
  ```
- **다중 AI 답변 종합 (Consensus 도출)**:
  ```bash
  ./bin/multi-ai synth "FastAPI에서 JWT 인증을 구현할 때의 보안 체크리스트"
  ```
- **코드 생성 및 AST 보안 검사**:
  ```bash
  ./bin/multi-ai code "주어진 CSV 텍스트를 파싱하여 딕셔너리 리스트로 변환하는 함수"
  ```

---

## 🔌 방법 B: API 키 없는 구독형 AI 연동 가이드 (MCP 서버)

Claude Pro, Cursor Pro, Windsurf 등 **API 키 없이 구독형 AI GUI/에디터를 사용하는 경우**, 표준 MCP(Model Context Protocol)를 통해 프로젝트 도구들을 연결합니다.

### 1. Claude Desktop 앱 연동 (Claude Pro 사용자)

Claude Desktop 앱의 설정 파일에 `apart-and-together` MCP 서버를 등록합니다.

#### 설정 파일 위치
- **Linux**: `~/.config/Claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### 설정 파일 작성
`claude_desktop_config.json` 파일을 열어 다음 블록을 추가합니다 (저장소 경로는 본인의 실제 절대 경로로 지정):

```json
{
  "mcpServers": {
    "apart-and-together": {
      "command": "python3",
      "args": [
        "/home/rocky/agents/apart-and-together/src/mcp_server.py"
      ]
    }
  }
}
```

#### 적용 방법
1. 설정 파일을 저장합니다.
2. **Claude Desktop 앱을 완전히 종료 후 다시 실행**합니다.
3. 대화창 오른쪽 아래에 **망치(도구) 아이콘**이 생겼는지 확인합니다.

---

### 2. Cursor IDE 연동 (Cursor Pro 사용자)

Cursor IDE 내에 자체 MCP 연결 기능이 내장되어 있습니다.

#### 등록 순서
1. Cursor 에디터를 실행합니다.
2. 설정 창 열기: 단축키 `Ctrl + Shift + J` (macOS는 `Cmd + Shift + J`)
3. 좌측 메뉴에서 **Features** → **MCP Servers** 선택
4. **+ Add New MCP Server** 버튼 클릭 후 정보 입력:
   - **Name**: `apart-and-together`
   - **Type**: `command`
   - **Command**: `python3 /home/rocky/agents/apart-and-together/src/mcp_server.py`
5. 추가 완료 후 상태 표시줄에 **초록색 불(Connected)**이 켜졌는지 확인합니다.

---

### 3. 구독형 AI 채팅창에서 사용하는 도구 및 프롬프트 예시

연동이 완료되면, 사용자는 평소처럼 자연어로 대화하기만 해도 AI가 알아서 도구를 호출합니다.

#### ① 코드 안전성 검사 (`audit_code_security`)
> **프롬프트 예시:**
> *"내가 작성한 이 파이썬 코드에 `eval`이나 `subprocess` 같은 위험한 코드가 없는지 `audit_code_security` 도구로 검사해줘."*

#### ② 우편함에서 일감 가져오기 (`get_pending_tasks`, `get_task_details`)
> **프롬프트 예시:**
> *"공유 우편함에 내가 처리할 수 있는 일감이 있는지 `get_pending_tasks`로 확인해줘."*  
> *"task-01 과제의 상세 요구사항과 수락 기준을 보여줘."*

#### ③ 작성한 코드나 리뷰 결과 제출 (`submit_task_result`)
> **프롬프트 예시:**
> *"task-01에 대해 작성한 이 코드를 공유 우편함에 `submit_task_result` 도구로 제출해줘."*

---

## 🚀 하이브리드 활용 (방법 A + 방법 B 시너지)

두 방식을 모두 설정하면 다음과 같은 협업이 가능해집니다:

```
[Claude Desktop (구독형)]  ──MCP 호출──>  [src/mcp_server.py]
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 ▼                                                             ▼
       [로컬 공유 우편함 (.mailbox)]                                [Multi-AI Hub (.env)]
   (다른 참여자/에이전트와 코드 교환)                           (GPT-4o, Gemini, Grok 병렬 교차 질의)
```

- Claude Desktop에서 코드를 작성하다가 *"내 로컬에 등록된 다른 AI(Gemini, GPT)들에게도 이 코드 구조에 대한 피드백을 물어봐줘"*라고 하면 `ask_other_ais` 도구를 통해 즉시 교차 리뷰를 수행할 수 있습니다.

---

## ❓ 문제 해결 및 FAQ

### Q1. `./bin/multi-ai status`를 실행했는데 `NOT CONFIGURED`로 나옵니다.
- `.env` 파일의 위치가 프로젝트 최상위 루트(`/home/rocky/agents/apart-and-together/.env`)에 있는지 확인하세요.
- 환경변수명(`OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 등)에 오타가 없는지 확인하세요.

### Q2. Claude Desktop이나 Cursor에서 도구 아이콘이 뜨지 않거나 오류가 납니다.
- `command`에 지정된 `python3`의 경로가 올바른지 확인하세요. (터미널에서 `which python3` 실행 결과 입력 가능)
- `args`에 지정된 `src/mcp_server.py`의 경로가 **반드시 절대 경로**여야 합니다. 상대 경로(`src/mcp_server.py`)는 작동하지 않습니다.

### Q3. 외부 의존성(라이브러리) 설치가 필요한가요?
- **아닙니다.** `apart-and-together`의 모든 기능(Multi-AI Hub, MCP 서버, 공유 우편함, AST 보안 감사기)은 파이썬 3 표준 라이브러리(`urllib`, `sqlite3`, `ast`, `json` 등)만으로 구동되므로 `pip install`이 전혀 필요하지 않습니다.
