# Copyright 2026 Vertel AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""keykeep.psono.datastore — encrypted vault datastores.

Datastores are opaque encrypted blobs: `data` + `data_nonce` (ciphertext),
`type` (password/settings/...), `description`, a wrapped `secret_key` with
`secret_key_nonce`, and `is_default`. The server never decrypts them.
"""

import uuid

from odoo import fields, models


class KeykeepPsonoDatastore(models.Model):
    _name = "keykeep.psono.datastore"
    _description = "Psono Datastore"
    _order = "is_default desc, create_date"

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
    data = fields.Text(string="Data (ciphertext)")
    data_nonce = fields.Char(string="Data Nonce")
    type = fields.Char(string="Type", default="password")
    description = fields.Char(string="Description", default="Default")
    secret_key = fields.Char(string="Secret Key (wrapped)")
    secret_key_nonce = fields.Char(string="Secret Key Nonce")
    is_default = fields.Boolean(string="Is Default", default=True)

    _sql_constraints = [
        ("psono_id_uniq", "unique (psono_id)", "A datastore with this id already exists."),
    ]

    def to_list_payload(self):
        self.ensure_one()
        return {
            "id": self.psono_id,
            "type": self.type,
            "description": self.description,
            "is_default": self.is_default,
        }

    def to_detail_payload(self):
        self.ensure_one()
        return {
            "data": self.data or "",
            "data_nonce": self.data_nonce or "",
            "type": self.type,
            "description": self.description,
            "secret_key": self.secret_key or "",
            "secret_key_nonce": self.secret_key_nonce or "",
            "is_default": self.is_default,
            "write_date": (self.write_date.isoformat() if self.write_date else ""),
        }
