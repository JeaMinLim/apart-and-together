# 따로또같이 (Apart & Together)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Status](https://img.shields.io/badge/status-Phase_2_Host_AI_Bot-green.svg)](#현재-상태)
[![Version](https://img.shields.io/badge/version-0.5.0-blue.svg)](CHANGELOG.md)

**따로또같이**는 서로 아는 사람들끼리 초대를 받아 각자 자신의 AI로 하위 과제를 맡아 작업하고, 호스트가 검증한 뒤 병합해 하나의 결과물(코드 또는 추론/분석)을 완성해가는 **초대제 AI 협업 플랫폼**입니다.

각자는 **따로**(자기 AI로, 독립적으로) 작업하지만, 검증과 병합을 거쳐 **같이**(하나의 결과물로) 완성됩니다.

---

## 현재 상태

⚡ **v0.5.0 (Phase 2 호스트 AI 봇 + 우편함 + MCP 서버 + Multi-AI Hub + Phase 1 검증)**:
- **AI 등록 및 연동 가이드**: API 키 기반 Multi-AI Hub 및 구독형 AI MCP 연동 상세 안내 ([매뉴얼](docs/AI_REGISTRATION_GUIDE.md))
- **호스트 AI 봇 (`src/host_bot/`)**: 자유 서술 목표로부터 3영역(인터페이스, 테스트, 보안) 수락 기준 자동 초안 생성, Fail-closed 등록자 승인 게이트, 작업자당 재시도 1회 / 과제당 재할당 2회 한도 상태 머신 및 자동 브랜치 체이닝 (`feat/<slug>-<u1>-<u2>`)
- **로컬 공유 우편함 (`src/mailbox/`)**: API 키 없이 Claude Pro, Cursor Pro 등 구독형 AI끼리 로컬 우편함으로 일감 등록 및 교차 코드 리뷰 지원
- **구독형 AI 연동 MCP 서버 (`src/mcp_server.py`)**: Claude Desktop, Cursor 등에서 우편함 및 보안 검사 도구를 직접 호출 ([가이드](docs/MCP_SETUP.md))
- **Multi-AI Hub CLI (`./bin/multi-ai`)**: ChatGPT, Claude, Gemini, Grok, OpenRouter, 로컬 LLM(Ollama)을 묶어 병렬 질의, 종합, 우편함 및 호스트 봇 수명주기 관리
- **Phase 1 자동 검증**: AST 보안 감사기(`src/verify/ast_scanner.py`) 및 PR 자동 검증 워크플로우 구축

## 핵심 아이디어

1. **초대**: 누군가 새 목표를 등록하고, 아는 사람들을 초대한다. 불특정 다수에게 공개되지 않는다.
2. **과제 등록**: 자유 서술로 목표를 적으면, AI가 기계적으로 검증 가능한 수락 기준(테스트 케이스/체크리스트) 초안을 작성하고, 등록자가 확인·승인한 뒤에만 과제가 공개된다.
3. **참여**: 선착순 또는 호스트 지정 방식으로 참여자가 확정된다.
4. **작업 및 제출**: 각자 자신의 AI(벤더 무관)로 작업하고, 완성된 결과물만 브랜치로 제출한다.
5. **검증**: 호스트가 병합 전 반드시 검증한다 — 결정론적 정적 분석(안전성)과 사전에 정한 수락 기준(적합성) 두 층위로.
6. **재시도 및 재할당**: 검증에 실패하면 1회 재시도 기회가 주어지고, 그래도 실패하면 원본 작업 내용을 그대로 공개하며 다른 참여자에게 재할당한다. 재시도/재할당 모두 상한이 있다.
7. **기여 귀속**: 별도의 시스템 없이 git의 커밋 이력(`git blame`)으로 누가 무엇을 기여했는지 자연스럽게 남는다.
8. **보상**: 금전/포인트 같은 인센티브 시스템은 다루지 않는다 — 기여 귀속까지가 이 프로젝트의 책임 범위다.

## 구현 방향

GitHub를 그대로 백엔드로 사용한다(Issue = 과제, Pull Request = 제출, GitHub Actions = 자동 검증, `git blame` = 기여 귀속). 새로 만드는 것은 초대와 일감 배분을 자동화하는 프론트엔드와 AI 봇뿐이다.

자세한 설계 결정과 근거는 [DESIGN.md](DESIGN.md)를 참고하세요. 참여 방법과 협업 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요. 구현 담당(Antigravity)에게 전달하는 작업 지시서는 [`specs/`](specs/) 디렉토리에 버전별로 쌓입니다. 버전 이력은 [CHANGELOG.md](CHANGELOG.md) 참고.

## 라이선스

[Apache License 2.0](LICENSE)
