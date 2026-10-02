# SQLite 저장소 검사와 마이그레이션

SchemaRouter는 두 종류의 장기 SQLite 상태를 저장합니다.

- `SQLiteRegistry`: ToolSpec contract와 registry logical version
- `SQLiteRunTraceStore`: replay 가능한 RunEvent 이력

어느 저장소도 live invoker, credential, HTTP client, SDK object, subprocess handle 또는 기타 실행 권한을 저장하지 않습니다.

## 업그레이드 전 검사

```bash
schemarouter storage inspect ./registry.sqlite3
schemarouter storage inspect ./traces.sqlite3 --json
```

보고서에는 감지된 각 component, storage/document format version, document 수, migration 상태와 migration 이력이 표시됩니다.

상태의 의미는 다음과 같습니다.

- `current`: 현재 SchemaRouter 버전에서 읽을 수 있음
- `legacy`: migration 가능한 지원 대상 구버전 format
- `future`: 더 새로운 format으로 작성되어 의도적으로 거부됨
- `corrupt`: format metadata 또는 table 구조가 불완전하거나 유효하지 않음

## 백업과 함께 마이그레이션

```bash
schemarouter storage migrate ./registry.sqlite3
```

기본적으로 필요한 migration을 적용하기 전에 다음 백업을 만듭니다.

```text
./registry.sqlite3.schemarouter.bak
```

필요하면 목적지를 직접 지정할 수 있습니다.

```bash
schemarouter storage migrate ./registry.sqlite3 \
  --backup-path ./backups/registry-before-upgrade.sqlite3
```

백업을 건너뛰려면 명시적인 flag가 필요하며 production에서는 권장하지 않습니다.

```bash
schemarouter storage migrate ./registry.sqlite3 --no-backup
```

`--backup-path`와 `--no-backup`은 함께 사용할 수 없습니다. 기존 backup file을 조용히 덮어쓰지도 않습니다.

현재 legacy v0 -> v1 migration은 metadata만 변경합니다. 저장된 모든 document를 먼저 검증한 뒤 하나의 component transaction에서 명시적 format metadata와 migration history를 기록합니다. ToolSpec/RunEvent JSON 자체는 다시 쓰지 않습니다.

## 자동 legacy migration

유효한 v0 `SQLiteRegistry` 또는 `SQLiteRunTraceStore`를 열 때도 동일한 transactional migration이 자동 수행됩니다. 업그레이드 후 데이터베이스를 그대로 다시 여는 기존 애플리케이션의 동작을 유지하기 위한 것입니다.

production 업그레이드에서는 운영자가 migration 전 backup과 감사 가능한 preflight 단계를 확보할 수 있도록 명시적인 `storage inspect` / `storage migrate`를 권장합니다.

동일한 Python API는 `inspect_sqlite_storage(...)`, `migrate_sqlite_storage(...)`, `backup_sqlite_storage(...)`입니다. migration은 전후 inspection과 생성된 경우 backup path를 포함하는 typed `StorageMigrationResult`를 반환합니다.

## Fail-closed 조건

SchemaRouter는 다음 상황에서 저장소를 열거나 migration하지 않습니다.

- storage 또는 document version이 지원 버전보다 새로움
- 필요한 version metadata의 일부만 존재함
- 필수 SQLite table이 없음
- legacy ToolSpec을 검증할 수 없음
- legacy trace가 run identity, sequence, timestamp 또는 terminal-state invariant를 위반함

실패한 migration transaction은 데이터베이스를 current 상태로 표시하지 않습니다. CLI가 backup을 생성했다면 업그레이드된 프로세스를 중지하고 해당 SQLite backup을 복원하면 됩니다.
