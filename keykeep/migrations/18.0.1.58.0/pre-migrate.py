# Copyright 2026 Vertel Sverige AB
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Pre-migrate 18.0.1.54.0 → 18.0.1.58.0 — role separation.

Before this version keykeep leaked accounting rights:

    base.group_system (Settings)
      └→ keykeep.group_admin
           └→ keykeep.group_manager
                └→ account.group_account_invoice

Every Settings user therefore got invoicing rights without opting in. The XML
definitions are fixed in 18.0.1.58.0, but the fix alone is not enough:

Odoo's ``GroupsImplied.write`` runs a recursive SQL that inserts the
*transitively implied* groups as **direct** memberships in
``res_groups_users_rel``. So ``account.group_account_invoice`` (61),
``keykeep.group_manager`` (196) and ``keykeep.group_admin`` (198) sit there as
direct rows for users who only ever had ``base.group_system``. Removing the
implied_ids does not touch those rows.

This migration removes them, but **only where keykeep was the carrier**. Users
who legitimately have ``account.group_account_basic`` (62),
``account.group_account_user`` (63) or ``account.group_account_manager`` (64)
keep their invoicing rights untouched — those are Odoo's own groups and have
nothing to do with keykeep.

Verified against ledningssystem 2026-11-17: of the 56 direct members of 61,
50 had it via Basic/Bookkeeper alone (untouched by this migration), 5 had it
via keykeep as well, and 1 via Basic/Bookkeeper without Accountant.

Idempotent: every step asks which groups actually carry the membership before
deleting the direct row.
"""

import logging

_logger = logging.getLogger(__name__)

ACCOUNT_INVOICE = "account.group_account_invoice"
# Odoo's own invoicing groups. Their presence is never keykeep's business.
ACCOUNT_LEGITIMATE = (
    "account.group_account_readonly",
    "account.group_account_basic",
    "account.group_account_user",
    "account.group_account_manager",
)
KK_MANAGER = "keykeep.group_manager"
KK_DEVOPS = "keykeep.group_devops"
KK_ADMIN = "keykeep.group_admin"
KK_ACCOUNTING = "keykeep.group_accounting"
BASE_SYSTEM = "base.group_system"

_IMPLY_CTE = """
    WITH RECURSIVE group_imply(gid, hid) AS (
        SELECT gid, hid FROM res_groups_implied_rel
         UNION
        SELECT i.gid, r.hid
          FROM res_groups_implied_rel r
          JOIN group_imply i ON (i.hid = r.gid)
    )
"""


def _gid(env, xmlid):
    rec = env.ref(xmlid, raise_if_not_found=False)
    return rec.id if rec else None


def _direct_members(env, group_id):
    env.cr.execute(
        "SELECT uid FROM res_groups_users_rel WHERE gid = %s", (group_id,)
    )
    return {row[0] for row in env.cr.fetchall()}


def _carriers(env, user_id, group_id):
    """Group ids through which user_id reaches group_id (direct groups only)."""
    env.cr.execute(
        _IMPLY_CTE
        + """
        SELECT DISTINCT r.gid
          FROM res_groups_users_rel r
          JOIN group_imply i ON i.gid = r.gid
         WHERE r.uid = %s AND i.hid = %s
        """,
        (user_id, group_id),
    )
    return {row[0] for row in env.cr.fetchall()}


def _log_users(env, user_ids):
    if not user_ids:
        return {}
    env.cr.execute(
        "SELECT id, login FROM res_users WHERE id = ANY(%s)", (list(user_ids),)
    )
    return dict(env.cr.fetchall())


def _remove_direct(env, group_id, user_ids, group_name, reason):
    if not user_ids:
        return 0
    logins = _log_users(env, user_ids)
    env.cr.execute(
        "DELETE FROM res_groups_users_rel WHERE gid = %s AND uid = ANY(%s)",
        (group_id, list(user_ids)),
    )
    removed = env.cr.rowcount or 0
    for uid in sorted(user_ids):
        _logger.info(
            "keykeep 18.0.1.58.0: removed %s from %s (uid %s) — %s",
            group_name,
            logins.get(uid, "?"),
            uid,
            reason,
        )
    return removed


def migrate(cr, version):
    if not version:
        # Fresh install: nothing to clean up.
        return

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    g_invoice = _gid(env, ACCOUNT_INVOICE)
    if not g_invoice:
        _logger.info("keykeep 18.0.1.58.0: account module absent, nothing to do")
        return

    g_manager = _gid(env, KK_MANAGER)
    g_devops = _gid(env, KK_DEVOPS)
    g_admin = _gid(env, KK_ADMIN)
    g_accounting = _gid(env, KK_ACCOUNTING)
    g_system = _gid(env, BASE_SYSTEM)
    legit = {x for x in (_gid(env, i) for i in ACCOUNT_LEGITIMATE) if x}

    # Groups that must never count as a reason to keep invoicing rights.
    keykeep_only = {x for x in (g_manager, g_admin) if x}

    # ── Step 0: drop the implied link in the group definition ──────────────
    # The security groups live in <data noupdate="1">, so the XML change to
    # group_manager.implied_ids is never written on upgrade — only on fresh
    # install. Verified on luke18 2026-11-17: after upgrading to 18.0.1.58.0
    # group_manager still implied account.group_account_invoice. The XML states
    # the intent for new databases; this migration enforces it on existing ones.
    if g_manager and g_invoice:
        env.cr.execute(
            "DELETE FROM res_groups_implied_rel WHERE gid = %s AND hid = %s",
            (g_manager, g_invoice),
        )
        if env.cr.rowcount:
            _logger.info(
                "keykeep 18.0.1.58.0: step 0 — removed %s from "
                "%s.implied_ids",
                ACCOUNT_INVOICE,
                KK_MANAGER,
            )

    # ── Step 0b: drop base.group_system → keykeep links ────────────────────
    # The <data noupdate="1"> wrapper means the rows written by the old
    # `base.group_system → group_admin` record stay in res_groups_implied_rel
    # even after the XML block is deleted: removing a record from XML does not
    # delete the data it once created. Verified on luke18 2026-11-17 — after
    # the upgrade group_system still reached Keykeep Admin/Manager/DevOps/User.
    # Also catches group_devops and group_user, since group_admin implied them
    # transitively and Users would otherwise keep credential access.
    if g_system:
        kk_ids = [
            x for x in (_gid(env, KK_ACCOUNTING), g_admin, g_manager, g_devops)
            if x
        ]
        if kk_ids:
            env.cr.execute(
                "DELETE FROM res_groups_implied_rel "
                "WHERE gid = %s AND hid = ANY(%s)",
                (g_system, kk_ids),
            )
            if env.cr.rowcount:
                _logger.info(
                    "keykeep 18.0.1.58.0: step 0b — removed %s implied "
                    "keykeep link(s) from base.group_system",
                    env.cr.rowcount,
                )

    # ── Step 1: invoicing rights that only keykeep carried ─────────────────
    # A user keeps account.group_account_invoice when at least one carrier is
    # an Odoo invoicing group (62/63/64/60) or keykeep.group_accounting.
    # We only delete when EVERY carrier is a keykeep group.
    keep_carriers = legit | ({g_accounting} if g_accounting else set())
    to_remove = set()
    kept_because_odoo = 0
    for uid in _direct_members(env, g_invoice):
        carriers = _carriers(env, uid, g_invoice)
        if not carriers:
            # Direct membership without any carrier — pre-existing inconsistency.
            # Leave it alone; assuming it is wrong would be guessing.
            continue
        if carriers & keep_carriers:
            kept_because_odoo += 1
            continue
        if g_system and g_system in carriers:
            to_remove.add(uid)
        elif carriers <= keykeep_only:
            # Carried by keykeep alone, even without Settings — still a leak
            # once group_manager stops implying invoicing.
            to_remove.add(uid)

    removed = _remove_direct(
        env,
        g_invoice,
        to_remove,
        ACCOUNT_INVOICE,
        "implied by keykeep only; keykeep no longer grants invoicing "
        "(role separation 18.0.1.58.0)",
    )
    _logger.info(
        "keykeep 18.0.1.58.0: step 1 — %s removed, %s kept via Odoo invoicing groups",
        removed,
        kept_because_odoo,
    )

    # ── Step 2: group_admin / group_manager held only via Settings ─────────
    if g_system:
        for gid, gname in ((g_admin, KK_ADMIN), (g_manager, KK_MANAGER)):
            if not gid:
                continue
            to_remove = set()
            for uid in _direct_members(env, gid):
                carriers = _carriers(env, uid, gid)
                # Keep when a carrier other than base.group_system exists.
                if carriers - {g_system}:
                    continue
                if g_system in carriers:
                    to_remove.add(uid)
            removed = _remove_direct(
                env,
                gid,
                to_remove,
                gname,
                "implied by base.group_system only, which no longer grants "
                "keykeep access (role separation 18.0.1.58.0)",
            )
            _logger.info(
                "keykeep 18.0.1.58.0: step 2 — %s direct %s membership(s) removed",
                removed,
                gname,
            )

    # ── Step 3: do not lose credential access silently ─────────────────────
    # Settings users who just lost group_admin keep group_devops. They can be
    # trimmed manually if they never used keykeep.
    if g_devops and g_system:
        settings_users = _direct_members(env, g_system)
        missing = settings_users - _direct_members(env, g_devops)
        if missing:
            env.cr.execute(
                "INSERT INTO res_groups_users_rel (gid, uid) "
                "SELECT %s, u FROM unnest(%s::int[]) AS u "
                "ON CONFLICT DO NOTHING",
                (g_devops, list(missing)),
            )
            for uid, login in _log_users(env, missing).items():
                _logger.info(
                    "keykeep 18.0.1.58.0: step 3 — kept %s for %s (uid %s) "
                    "so credential access is not lost",
                    KK_DEVOPS,
                    login,
                    uid,
                )

    env.registry.clear_cache("groups")
    _logger.info("keykeep 18.0.1.58.0: role separation migration done")
