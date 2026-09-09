# Changelog

이 프로젝트는 [Semantic Versioning](https://semver.org/lang/ko/)을 따릅니다. 아직 코드가 없는 설계 단계이므로, 버전은 "구현 명세서/설계 문서" 단위로 매깁니다.

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
