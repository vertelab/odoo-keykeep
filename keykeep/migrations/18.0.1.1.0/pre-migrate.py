# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""Migration script for keykeep 18.0.1.1.0.

- Adds environment field to keykeep.credential (default: 'production')
- Changes unique constraint from (name, subscription_id) to (name, subscription_id, environment)
- Handles existing duplicate (name, subscription_id) pairs by renaming them
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Handle migration to 18.0.1.1.0."""
    if not version:
        return

    _logger.info("keykeep: Running migration to 18.0.1.1.0")

    # 1. Drop old unique constraint
    # The old constraint is named 'keykeep_credential_name_subscription_uniq'
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'keykeep_credential_name_subscription_uniq'
                AND conrelid = 'keykeep_credential'::regclass
            ) THEN
                ALTER TABLE keykeep_credential
                DROP CONSTRAINT keykeep_credential_name_subscription_uniq;
            END IF;
        END
        $$;
    """)

    # 2. Handle duplicate (name, subscription_id) pairs before adding new constraint
    cr.execute("""
        WITH duplicates AS (
            SELECT id, name, subscription_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY name, subscription_id ORDER BY id
                   ) as rn
            FROM keykeep_credential
        )
        UPDATE keykeep_credential
        SET name = name || ' (duplicate-' || (duplicates.rn - 1) || ')'
        FROM duplicates
        WHERE keykeep_credential.id = duplicates.id
        AND duplicates.rn > 1;
    """)

    # 3. Add environment column if not exists
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'keykeep_credential'
                AND column_name = 'environment'
            ) THEN
                ALTER TABLE keykeep_credential
                ADD COLUMN environment VARCHAR;
            END IF;
        END
        $$;
    """)

    # 4. Set default environment for all existing credentials
    cr.execute("""
        UPDATE keykeep_credential
        SET environment = 'production'
        WHERE environment IS NULL;
    """)

    # 5. Add new unique constraint
    cr.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'keykeep_credential_name_subscription_env_uniq'
                AND conrelid = 'keykeep_credential'::regclass
            ) THEN
                ALTER TABLE keykeep_credential
                ADD CONSTRAINT keykeep_credential_name_subscription_env_uniq
                UNIQUE (name, subscription_id, environment);
            END IF;
        END
        $$;
    """)

    _logger.info("keykeep: Migration to 18.0.1.1.0 complete")
