from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


REPO_ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_path: Path) -> Config:
    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    return config


def test_revision_ids_fit_default_alembic_version_column():
    config = migration_config(Path("unused.db"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()
    assert all(len(revision.revision) <= 32 for revision in revisions)


def test_application_migration_round_trip_preserves_baseline_data(tmp_path: Path):
    database_path = tmp_path / "migration.db"
    config = migration_config(database_path)
    command.upgrade(config, "0001_persistence_baseline")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO application_cases "
            "(id, case_code, organization_id, citizen_id, procedure_id, procedure_version_id, "
            "status, source_channel, priority, current_submission_version, version, form_data, checklist, created_at, updated_at) "
            "VALUES ('case', 'CASE', 'org', 'citizen', 'p', 'v1', 'draft', 'citizen_portal', 0, 1, 1, '{}', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            "INSERT INTO case_submission_versions "
            "(id, case_id, version, form_data, checklist_snapshot, procedure_version_id, procedure_rule_version, created_at, source) "
            "VALUES ('sv', 'case', 1, '{}', '{}', 'v1', 'r1', CURRENT_TIMESTAMP, 'citizen_portal')"
        ))

    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert "validation_findings" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("application_cases")} >= {
        "classification_confidence", "analysis_completed_at", "returned_at"
    }
    assert {fk["name"] for fk in inspector.get_foreign_keys("validation_findings")} >= {
        "fk_validation_findings_case_id_application_cases",
        "fk_validation_findings_submission",
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT case_code FROM application_cases WHERE id='case'")) == "CASE"

    command.downgrade(config, "0001_persistence_baseline")
    inspector = inspect(engine)
    assert "validation_findings" not in inspector.get_table_names()
    assert "classification_confidence" not in {column["name"] for column in inspector.get_columns("application_cases")}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT case_code FROM application_cases WHERE id='case'")) == "CASE"

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
