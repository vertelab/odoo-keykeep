/** @odoo-module **/
/* Keykeep — SaaS Subscription Manager client logic */
/* Copyright 2026 Vertel AB — License AGPL-3.0 */

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { FormController } from "@web/views/form/form_controller";
import { ActionDialog } from "@web/webclient/actions/action_dialog";

// Auto-close timer for reveal dialog
patch(FormController.prototype, {
    setup() {
        super.setup();
        this._keykeepRevealTimer = null;
    },

    async onRecordSaved(record) {
        await super.onRecordSaved(record);
        // Check if this is the reveal dialog
        if (this.props.resModel === "keykeep.credential.reveal") {
            this._startRevealTimer();
        }
    },

    _startRevealTimer() {
        if (this._keykeepRevealTimer) {
            clearTimeout(this._keykeepRevealTimer);
        }
        const timeoutField = this.model.root.data.reveal_timeout;
        if (!timeoutField) return;
        const seconds = timeoutField.value || 0;
        if (seconds <= 0) return;
        this._keykeepRevealTimer = setTimeout(() => {
            this.props.close();
        }, seconds * 1000);
    },

    onWillDestroy() {
        if (this._keykeepRevealTimer) {
            clearTimeout(this._keykeepRevealTimer);
        }
        super.onWillDestroy();
    },
});

// Fullscreen / expand support for target="new" dialogs (ActionDialog).
// Odoo's own FormViewDialog (calendar events, m2o edits) shows the expand
// icon; ActionDialog does not wire onExpand, so wizards/reveal dialogs
// lack it. We add the same icon for act_window form dialogs and re-open the
// record as a main-area form action (keeping a reveal-specific view when
// the action carries keykeep_reveal_view_id in its context).
patch(ActionDialog.prototype, {
    setup() {
        super.setup();
        this.actionService = useService("action");
    },

    async onExpand() {
        const { resModel, resId, context } = this.props.actionProps || {};
        if (!resModel || this.props.actionType !== "ir.actions.act_window") {
            return;
        }
        const viewId = context?.keykeep_reveal_view_id || false;
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: resModel,
            res_id: resId,
            views: [[viewId, "form"]],
            context: { ...(context || {}) },
        });
        this.props.close();
    },
});

// Server-side copy (action_copy_field): copies the value returned by the
// server into the clipboard and shows a notification. The server logs the
// copy in the audit log + credential chatter before returning the value.
registry.category("actions").add("keykeep_copy_value", async (env, action) => {
    try {
        await keykeepCopyToClipboard(action.params.value);
        env.services.notification.add("Copied to clipboard", { type: "success" });
    } catch (err) {
        console.warn("Keykeep: Clipboard copy failed", err);
        env.services.notification.add("Copy failed — check clipboard permissions", {
            type: "danger",
        });
    }
});

// Copy to clipboard — prefers the async Clipboard API (secure context),
// falls back to a hidden textarea + execCommand (HTTP / intranet hosts).
async function keykeepCopyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand("copy");
    } finally {
        document.body.removeChild(ta);
    }
}

// Copy to clipboard handler.
// data-keykeep-copy names the form field whose VALUE should be copied
// (e.g. "api_key", "password", "email"). An explicit
// data-keykeep-copy-value attribute wins when present.
document.addEventListener("click", async (ev) => {
    const copyBtn = ev.target.closest("[data-keykeep-copy]");
    if (!copyBtn) return;
    ev.preventDefault();

    const fieldName = copyBtn.dataset.keykeepCopy;
    if (!fieldName) return;

    let value = copyBtn.dataset.keykeepCopyValue;
    if (value === undefined) {
        // Resolve the actual value from the form field with that name.
        // Odoo 18 renders every field inside a <div name="..."> wrapper:
        // editable fields contain an <input>/<textarea>/<select> whose
        // .value holds the data, while readonly fields render a <span>
        // whose textContent holds the formatted value. Reading .value on
        // the wrapper itself always yields undefined.
        const root =
            copyBtn.closest(".o_form_renderer, .modal-content, .o_dialog") ||
            document;
        const fieldEls = root.querySelectorAll(`[name="${fieldName}"]`);
        const fieldEl = fieldEls[fieldEls.length - 1];
        if (fieldEl) {
            const inputEl = fieldEl.matches("input, textarea, select")
                ? fieldEl
                : fieldEl.querySelector("input, textarea, select");
            if (inputEl) {
                value = inputEl.value ?? "";
            } else {
                value = fieldEl.textContent?.trim() ?? "";
            }
        } else {
            value = "";
        }
    }
    if (!value) {
        console.warn("Keykeep: nothing to copy for", fieldName);
        return;
    }

    try {
        await keykeepCopyToClipboard(value);
        const originalText = copyBtn.textContent;
        copyBtn.textContent = "Copied!";
        copyBtn.classList.add("btn-success");
        copyBtn.classList.remove("btn-outline-secondary");
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.classList.remove("btn-success");
            copyBtn.classList.add("btn-outline-secondary");
        }, 2000);
    } catch (err) {
        console.warn("Keykeep: Clipboard copy failed", err);
    }
});

// Key type auto-detection patterns
const KEY_PATTERNS = {
    stripe: { pattern: /^sk_(live|test)_/, label: "Stripe Secret Key" },
    github: { pattern: /^ghp_/, label: "GitHub Personal Access Token" },
    github_pat: { pattern: /^github_pat_/, label: "GitHub Fine-grained PAT" },
    sentry: { pattern: /^sntrys_/, label: "Sentry Auth Token" },
    aws_access: { pattern: /^AKIA[0-9A-Z]{16}$/, label: "AWS Access Key ID" },
    aws_secret: { pattern: /^[0-9a-zA-Z/+]{40}$/, label: "Possible AWS Secret Key" },
    openai: { pattern: /^sk-[A-Za-z0-9]{32,}$/, label: "OpenAI API Key" },
};

document.addEventListener("input", (ev) => {
    const field = ev.target.closest("textarea, input[type='text']");
    if (!field) return;

    // Look for the detect badge in the wizard
    const detectBadge = field.closest(".o_form_sheet")?.querySelector("#key_detect");
    if (!detectBadge) return;

    const value = field.value?.trim();
    if (!value) {
        detectBadge.textContent = "";
        return;
    }

    for (const [name, {pattern, label}] of Object.entries(KEY_PATTERNS)) {
        if (pattern.test(value)) {
            detectBadge.textContent = `🔍 Detected: ${label}`;
            return;
        }
    }
    detectBadge.textContent = "";
});
