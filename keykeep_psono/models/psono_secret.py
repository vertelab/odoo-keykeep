# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""keykeep.psono.secret + keykeep.psono.secret.history.

Secrets are opaque encrypted blobs (data + data_nonce + type) belonging to
exactly one parent (a datastore in the MVP). Each secret carries a
client-generated link_id. Creating or updating a secret automatically
snapshots a history entry (encrypted, never plaintext).
"""

import uuid

from odoo import api, fields, models


class KeykeepPsonoSecret(models.Model):
    _name = "keykeep.psono.secret"
    _description = "Psono Secret"
    _order = "create_date desc"

    psono_id = fields.Char(
        string="Psono ID",
        required=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    user_id = fields.Many2one(
        comodel_name="keykeep.psono.user",
        string="Vault User",
        required=True,
        ondelete="cascade",
        index=True,
    )
    parent_datastore_id = fields.Many2one(
        comodel_name="keykeep.psono.datastore",
        string="Parent Datastore",
        ondelete="cascade",
        index=True,
    )
    data = fields.Text(string="Data (ciphertext)")
    data_nonce = fields.Char(string="Data Nonce")
    type = fields.Char(string="Type", default="password")
    link_id = fields.Char(string="Link ID")
    read_count = fields.Integer(string="Read Count", default=0)
    history_ids = fields.One2many(
        comodel_name="keykeep.psono.secret.history",
        inverse_name="secret_id",
        string="History",
    )

    _sql_constraints = [
        ("psono_id_uniq", "unique (psono_id)", "A secret with this id already exists."),
    ]

    # ── lifecycle ──────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._snapshot_history()
        return records

    def write(self, vals):
        changed = any(
            k in vals for k in ("data", "data_nonce", "type", "link_id")
        )
        result = super().write(vals)
        if changed:
            for rec in self:
                rec._snapshot_history()
        return result

    def _snapshot_history(self):
        self.ensure_one()
        return self.env["keykeep.psono.secret.history"].sudo().create(
            {
                "psono_id": str(uuid.uuid4()),
                "secret_id": self.id,
                "data": self.data,
                "data_nonce": self.data_nonce,
                "type": self.type,
                "changed_by": self.env.user.id,
                "changed_at": fields.Datetime.now(),
            }
        )

    def to_read_payload(self):
        self.ensure_one()
        return {
            "create_date": self.create_date.isoformat() if self.create_date else "",
            "write_date": self.write_date.isoformat() if self.write_date else "",
            "data": self.data or "",
            "data_nonce": self.data_nonce or "",
            "type": self.type,
            "read_count": self.read_count,
            "callback_url": "",
            "callback_user": "",
            "callback_pass": "",
        }


class KeykeepPsonoSecretHistory(models.Model):
    _name = "keykeep.psono.secret.history"
    _description = "Psono Secret History"
    _order = "changed_at desc"

    psono_id = fields.Char(
        string="Psono ID",
        required=True,
        index=True,
        default=lambda self: str(uuid.uuid4()),
    )
    secret_id = fields.Many2one(
        comodel_name="keykeep.psono.secret",
        string="Secret",
        required=True,
        ondelete="cascade",
        index=True,
    )
    data = fields.Text(string="Data (ciphertext)")
    data_nonce = fields.Char(string="Data Nonce")
    type = fields.Char(string="Type")
    changed_by = fields.Many2one(comodel_name="res.users", string="Changed By")
    changed_at = fields.Datetime(string="Changed At", default=fields.Datetime.now)
