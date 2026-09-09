# 구독형 AI를 위한 MCP 연동 가이드

Claude Desktop, Cursor, Windsurf 등 **API 키가 없는 구독형 AI**에서 `apart-and-together`의 도구들을 직접 활용하는 방법입니다.

---

## 1. Claude Desktop 연동 방법 (Claude Pro 구독자)

Claude Desktop은 표준 stdio MCP 프로토콜을 지원합니다.

### 설정 파일 위치
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

### 설정 내용 추가
`claude_desktop_config.json` 파일에 아래 내용을 추가합니다:

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
*(참고: 저장소 경로 `/home/rocky/agents/apart-and-together`는 본인의 실제 저장소 절대 경로로 지정하세요.)*

설정 저장 후 **Claude Desktop을 재시작**하면 우측 하단에 망치(도구) 아이콘이 나타나며 도구들이 활성화됩니다.

---

## 2. Cursor IDE 연동 방법 (Cursor Pro 구독자)

Cursor 에디터 내에서 MCP 서버를 직접 연결할 수 있습니다.

1. Cursor 설정 열기 (`Ctrl + Shift + J` 또는 `Cmd + Shift + J`)
2. **Features** → **MCP Servers** 선택
3. **+ Add New MCP Server** 클릭
   - **Name**: `apart-and-together`
   - **Type**: `command`
   - **Command**: `python3 /home/rocky/agents/apart-and-together/src/mcp_server.py`
4. 저장 후 연결 상태가 녹색(Connected)으로 변하는지 확인합니다.

---

## 3. 사용할 수 있는 MCP 도구 목록

연동이 완료되면, 별도의 API 키 없이도 Claude Desktop이나 Cursor 채팅창에서 자연어로 도구를 실행할 수 있습니다.

### ① `audit_code_security` (코드 보안 감사)
AI가 작성한 코드나 내가 작성한 파이썬 코드에 `eval`, `subprocess`, `os.system` 등 위험 호출이 없는지 Phase 1 AST 감사기로 즉시 검사합니다.
> **프롬프트 예시:**
> *"내가 방금 작성한 이 코드에 보안 취약점이 없는지 audit_code_security 도구로 검사해줘."*

### ② `ask_other_ais` (다른 AI와 교차 비교)
`.env`에 등록된 다른 AI(Gemini 무료키, Grok, OpenRouter 등)에게 동일한 질문을 백그라운드로 던지고 답변을 받아옵니다.
> **프롬프트 예시:**
> *"이 알고리즘에 대해 Gemini와 Grok은 어떻게 생각하는지 ask_other_ais로 물어봐서 비교해줘."*

### ③ `synthesize_with_other_ais` (다중 AI 종합)
여러 AI 모델의 의견을 취합하여 최선의 종합 답변을 생성합니다.
> **프롬프트 예시:**
> *"PostgreSQL과 MongoDB 선택 기준에 대해 synthesize_with_other_ais 도구로 다중 AI 종합 결론을 내줘."*

### ④ `get_multi_ai_status` (허브 상태 점검)
현재 Multi-AI 허브에 활성화된 프로바이더 목록을 확인합니다.
> **프롬프트 예시:**
> *"현재 연동된 AI 모델 상태를 get_multi_ai_status로 확인해줘."*

---

## 4. 💡 API 키 0원으로 구독 AI끼리 협업하기 (공유 우편함)

Grok이나 ChatGPT의 유료 API 키를 구매하지 않고도, **Claude Pro와 Cursor Pro 등 구독 프로그램끼리 로컬 우편함을 통해 코드를 리뷰하고 협업**할 수 있습니다.

### 단계 1: Claude Desktop에서 리뷰 요청 등록
> **Claude 채팅창:**
> *"내가 작성한 이 CSV 파서 코드를 `post_task_to_mailbox` 도구로 코드 리뷰 일감으로 등록해줘."*

### 단계 2: Cursor (또는 다른 창)에서 일감 가져와 리뷰 작성
> **Cursor 채팅창:**
> *"우편함에 올라온 일감이 있는지 `get_pending_tasks`로 확인하고, 있으면 가져와서 코드 리뷰 후 `submit_task_result`로 제출해줘."*
> 
> *(이때 작성된 리뷰 코드에 대해 Phase 1 AST 보안 검사가 자동으로 실행됩니다.)*

### 단계 3: Claude Desktop에서 다른 AI의 리뷰를 수거하여 코드 개선
> **Claude 채팅창:**
> *"우편함에서 내 일감에 대한 다른 AI의 리뷰를 `get_completed_task_results`로 가져와서 코드를 개선해줘."*

