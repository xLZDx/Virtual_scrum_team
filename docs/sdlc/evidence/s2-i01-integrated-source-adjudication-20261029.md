# I01 bounded integrated SOURCE adjudication — 2026-10-29

Sprint: 39b7cc253f5d

Owner: Codex (implementation/coordination); GPT-PM (architecture/source adjudication).
Request: `c7a8e23e-91f5-489c-a096-c813d84c3b12`; job: `438879ea-c351-483d-8762-bae5dac4e3b4`; correlated reply: `7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`.
Status: `succeeded`; correlated: `true`. Source HEAD supplied: `0cef101ee70be03b0436d82fad459916a79ee65b`.
The exact reply below authorizes bounded integrated source only. It does not authorize actual production keys, runtime signing/activation, E5, final phase8 approval or S2 closure.

## Exact correlated reply

ChatGPT said:

REQUEST_ID: c7a8e23e-91f5-489c-a096-c813d84c3b12

Virtual_scrum_team — S2-MACHINE-ISSUER-I01

GO — bounded integrated SOURCE implementation I01 design implementation-ready Runtime / Production HOLD

Решение: разрешаю переход к реализации ограниченного интегрированного SOURCE-контракта I01, включая код root-Supervisor для подписания, специализированный Store journal/reducer, locked authorization predicates, default-off конфигурацию и интеграцию с существующим v1 issuer callsite.

Это не разрешение генерировать или устанавливать production private keys, включать сервис, выполнять реальные подписания, запускать E5 или закрывать S2 Phase 8.

1. Результат adversarial sweep

Проверены приложенные:

S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md, включая §§4, 5 и 10.

S2_AUTHENTICATED_ASSIGNMENT_BASIS_DESIGN.

Независимые DB/security design rechecks.

Detached dispatch_issuance.py и assignment_basis.py.

Предоставленные snapshots store.py, supervisor.py, supervisor_service.py.

Acceptance ID

	

Проверяемый механизм

	

Вердикт




I01-IDENTITY

	

Полная immutable operation identity, frozen envelope, collision refusal

	

GO




I01-JOURNAL

	

Atomic reserve + INTENT, unique STARTED, durable COMPLETED/UNKNOWN

	

GO




I01-CRYPTO

	

Mandatory exact-domain Ed25519 completion verification

	

GO




I01-RECOVERY

	

UNKNOWN после ambiguous signer outcome, запрет auto-resign

	

GO




I01-CLASS

	

Immutable LEGACY_V1 / DELEGATED_V1 classification, без downgrade

	

GO




I01-ADMISSION

	

Provenance и current authority в одной Store transaction

	

GO




I01-DELIVERY

	

Единый verified snapshot; delivery не является execution authority

	

GO




I01-GRANT

	

Полный повтор predicate при persistence/replay grant

	

GO




I01-RUNNER

	

Повторная проверка при durable claim/reservation

	

GO




I01-ACTIVATION

	

Ключи, root policy, provisioning, enablement, runtime

	

HOLD

Новых подтверждённых design-level BLOCKER или MAJOR, требующих изменения I01 до начала реализации, не выявлено.

Это заключение относится к полноте контракта, а не к корректности ещё не написанной интеграции.

2. Критические интеграционные условия

Следующие требования обязательны для реализации. Их пропуск создаст SOURCE MAJOR.

I01-SRC-01 — Grant provenance binding

Существующий Supervisor.issue_execution_grant() создаёт собственные случайные request_id, grant_id и invocation_id. Поэтому нельзя считать совпадение task/slot/attempt достаточным доказательством происхождения grant.

Реализация обязана:

Связать точные подписанные grant bytes с immutable dispatch_grant operation.

Связать эту операцию с исходным accepted dispatch request и завершённой issuance.

Проверять эту связь при persistence, exact replay, runner claim и reservation.

Отказывать при отсутствии или несоответствии связи.

Существующий wire format execution grant сохраняется.

I01-SRC-02 — Atomic admission and replay

В текущем Store.accept_dispatch_intent() ветка существующей idempotent operation возвращает результат раньше проверок live task/lease.

Для delegated v1 обе ветки — новая acceptance и exact replay — должны соблюдать исправленный контракт. Historical replay может возвращать сохранённый факт, но не создавать новую execution authority.

I01-SRC-03 — Verified journal integration

Текущий _verify_supervisor_records() поддерживает generic internal/external operation families.

Новая issuance family требует самостоятельной полной корреляции row/event и проверки:

Единственности INTENT и STARTED.

Допустимого порядка событий.

Неизменности payload и signer identity.

Единственного действительного completion.

Отсутствия смешивания protocol families.

Целостности event chain и anchor.

Cryptographic verification выполняется вне SQL. В транзакцию допускается только trusted context, связанный с точными immutable bytes и fingerprint.

I01-SRC-04 — Snapshot and current authority

Использовать единую connection-taking predicate и повторять её непосредственно на write boundaries. Результат предшествующего read-only вызова не считается разрешением на grant или execution.

Root policy, revocation, generation и key registry должны проверяться через доверенные root-owned providers. При невозможности установить их актуальность операция отказывается.

I01-SRC-05 — Crash-consistent signing

Нельзя использовать execute_external_idempotent() для этой операции. После committed STARTED допускается максимум один вызов OpenSSL для immutable operation identity.

Потерянный completion означает UNKNOWN, а не повторное подписание.

3. Разрешённый implementation scope
SOURCE GO

Codex может реализовать:

Specialized Store issuer journal, reducer, verifier и key-class binding.

Root-Supervisor signing code, остающийся default-off.

Strict optional issuer configuration и fail-closed provider interfaces.

Existing v1 issuer callsite integration.

Delegated admission, delivery, grant, replay и runner locked predicates.

Source-level regression tests и необходимую документацию.

Условия:

Без новых таблиц, schema migration или v2 instruction format.

Без изменения legacy v1 behavior для корректно классифицированных legacy keys.

Без daemon, scheduler или per-task human signature.

Без включения production signing и установки реальных root credentials.

Без выдачи этой SOURCE-санкции за Phase 8 acceptance.

4. Оставшиеся gates

Gate

	

Владелец

	

Статус




I01 architecture/design

	

GPT-PM

	

GO




Bounded integrated implementation

	

Codex

	

Authorized to start




Functional/E2E negative scenarios

	

Codex, после завершения S2 coding

	

NOT_RUN




Independent exact-source security/DB review

	

GPT-PM review

	

Pending




Private-key provisioning / policy installation

	

Operator

	

HOLD




Runtime signing / E5 / production activation

	

Separate authorization

	

HOLD




Final S2 Phase 8 acceptance

	

Separate exact-head gate

	

NOT APPROVED

5. Ограничение доказательств

Приложенные snapshots позволяют оценить заявленные source integration boundaries и обнаружить существующие early-return и grant-binding особенности. Однако я не проверял непосредственно локальный Windows repository D:\Repo\Virtual_scrum_team или полный Git tree на 0cef101ee70be03b0436d82fad459916a79ee65b.

Поэтому это независимое архитектурное решение по предоставленному evidence set, а не утверждение о полной верификации exact HEAD.

Итоговое решение GPT-PM

Decision 1: GO. Реализовать bounded integrated SOURCE I01 в указанном объёме.

Decision 2: IMPLEMENTATION-READY. Исправленный I01 contract достаточно определён для реализации. Два ранее установленных design MAJOR закрыты на уровне требований.

Remaining design BLOCKER/MAJOR: 0 confirmed.

S2 Phase 8: NOT APPROVED.

Следующее действие Codex: завершить интеграцию Store/Supervisor/RPC с перечисленными пятью обязательными source conditions, затем предоставить exact-head diff и результаты предусмотренных проверок на отдельную независимую приёмку.

