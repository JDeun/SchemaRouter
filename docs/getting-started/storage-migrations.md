# Inspecting and migrating SQLite storage

SchemaRouter persists two kinds of long-lived SQLite state:

- `SQLiteRegistry`: ToolSpec contracts and the registry logical version;
- `SQLiteRunTraceStore`: replayable RunEvent history.

Neither store persists live invokers, credentials, HTTP clients, SDK objects, subprocess handles, or
other execution authority.

## Inspect before upgrading

```bash
schemarouter storage inspect ./registry.sqlite3
schemarouter storage inspect ./traces.sqlite3 --json
```

The report shows each detected component, its storage/document format versions, document count,
migration status, and migration history.

Status meanings:

- `current`: readable by this SchemaRouter version;
- `legacy`: supported older format that can be migrated;
- `future`: written by a newer format and intentionally refused;
- `corrupt`: incomplete or invalid format metadata/table shape.

## Migrate with a backup

```bash
schemarouter storage migrate ./registry.sqlite3
```

By default, the command creates:

```text
./registry.sqlite3.schemarouter.bak
```

before applying any required migration. Use an explicit destination when needed:

```bash
schemarouter storage migrate ./registry.sqlite3 \
  --backup-path ./backups/registry-before-upgrade.sqlite3
```

The current legacy v0 -> v1 migration is metadata-only: it validates all stored documents first,
then records explicit format metadata and migration history in a single component transaction.
ToolSpec/RunEvent JSON is not rewritten.

## Automatic legacy migration

Opening a valid v0 `SQLiteRegistry` or `SQLiteRunTraceStore` also performs the same transactional
migration automatically. This preserves existing applications that simply reopen their database
after upgrading.

For production upgrades, explicit `storage inspect` / `storage migrate` is still recommended so
operators have a pre-migration backup and an auditable preflight step.

## Fail-closed cases

SchemaRouter refuses to open or migrate when:

- the storage or document version is newer than supported;
- only part of the required version metadata exists;
- required SQLite tables are missing;
- a legacy ToolSpec cannot be validated;
- a legacy trace violates run identity, sequence, timestamp, or terminal-state invariants.

A failed migration transaction does not stamp the database as current. If a backup was created by
the CLI, recovery is simply to stop the upgraded process and restore that SQLite backup.
