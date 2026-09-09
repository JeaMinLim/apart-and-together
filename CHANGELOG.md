# Changelog

이 프로젝트는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다. 아직 코드가 없는 설계 단계이므로, 버전은 "구현 명세서/설계 문서" 단위로 매깁니다.

## [v0.2.0] - 2026-09-09

### 추가됨
- `specs/v0.2.0_multi_ai_hub_spec.md` — Multi-AI Hub 터미널 도구 구현 명세서
- `src/multi_ai/` — 다중 AI 통합 오케스트레이터 패키지 (ChatGPT, Claude, Gemini, Grok, OpenRouter, Ollama 지원)
- `src/multi_ai/cli.py` & `bin/multi-ai` — 터미널 CLI 실행기 (`status`, `ask`, `synth`, `code` 명령 지원)
- `tests/test_multi_ai.py` — Multi-AI 설정, 프로바이더, 동시 질의 및 종합 단위 테스트
- `.env.example` — API 키 설정 템플릿

### 상태
다중 AI 묶음 도구(Multi-AI Hub CLI) 구현 완료.

## [v0.1.0] - 2026-09-09

### 추가됨
- `specs/v0.1.0_phase1_verification_spec.md` — Phase 1 검증 자동화 명세서
- `src/verify/ast_scanner.py` — AST 기반 정적 보안 감사기 (`eval`/`exec`, `os.system`, `subprocess` 등 위험 호출 탐지)
- `tests/test_ast_scanner.py` — AST 보안 스캐너 단위 테스트
- `.github/workflows/verify.yml` — PR 자동 검증 파이프라인 (안전성 AST 검사 + 적합성 테스트 실행 및 Step Summary 리포트)

### 상태
Phase 1(검증 자동화) 구현 완료.

## [v0.0.0] - 2026-09-08

### 추가됨
- `DESIGN.md` — 초대제 협업 워크플로우, 검증/재시도/재할당, git 기반 기여 귀속 등 핵심 설계 결정(§2.1~§2.23)
- `LICENSE` — Apache License 2.0
- `specs/v0.0.0_phase0_scaffolding_spec.md` — Phase 0 구현 명세서(Issue Forms + `CONTRIBUTING.md` 스캐폴딩), 구현 담당(Antigravity)에게 전달

### 상태
아직 코드 없음. 설계 완료, Phase 0(수동 드라이런) 구현 착수 전 단계.
