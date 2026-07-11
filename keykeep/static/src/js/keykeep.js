/** @odoo-module **/
/* Keykeep — SaaS Subscription Manager client logic */
/* Copyright 2026 Vertel AB — License AGPL-3.0 */

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

// Auto-close timer for reveal dialog
patch(FormController.prototype, {
    setup() {
        this._super(...arguments);
        this._keykeepRevealTimer = null;
    },

    async onRecordSaved(record) {
        await this._super(...arguments);
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
        this._super(...arguments);
    },
});

// Copy to clipboard handler
document.addEventListener("click", async (ev) => {
    const copyBtn = ev.target.closest("[data-keykeep-copy]");
    if (!copyBtn) return;

    const value = copyBtn.dataset.keykeepCopy;
    if (!value) return;

    try {
        await navigator.clipboard.writeText(value);
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
