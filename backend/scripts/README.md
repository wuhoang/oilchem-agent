# Scripts

Developer helper scripts for OilChem Agent.

## Available scripts

| Script | Usage | Description |
|--------|-------|-------------|
| `migrate.py` | `python -m scripts.migrate <command>` | Database migration management |

## Migration commands

```bash
# Upgrade to latest
python -m scripts.migrate upgrade

# Downgrade one version
python -m scripts.migrate downgrade

# View current version
python -m scripts.migrate current

# View migration history
python -m scripts.migrate history

# Create a new migration (auto-detect schema changes)
python -m scripts.migrate create "add_new_table"

# Drop all tables (downgrade to base)
python -m scripts.migrate drop

# Stamp current version (mark as applied without running SQL)
python -m scripts.migrate stamp
```
