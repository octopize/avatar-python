# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
# ---

# %% [markdown]
# # Tutorial 11 Several databases at once (Beta)
#
# > **⚠️ Not yet runnable.** It needs an API released with database runs, and the client
# > release that follows it. This notebook is the shape of it.
#
# The CRM and the billing system describe the **same people**. A test estate where Alice is
# one fake person in one and a different one in the other is useless.
#
# That is the only reason to use this. If what they share lives inside a single database, use
# Tutorial 10 — it is simpler and does the same thing.

# %%
# NOT_YET_RUNNABLE: needs an API released with database runs, and source databases in the CI stack.
import os

from avatars import Manager, shared_entity

# %%
manager = Manager(api_key=os.environ.get("AVATAR_API_KEY"))
runner = manager.create_runner("full-test-estate")

# %% [markdown]
# ## Why every job reads every database's people
#
# A pseudonym follows the order entities are **collected**, not the value it replaces. Each
# database is copied by jobs of its own, so each of them collects the shared entity from
# **every** database it is found in — reading the other databases' tables, never writing
# them — and resolves it with the entity's own seed. Same people, same order, same seed:
# the same replacement in every job.

# %% [markdown]
# ## Describing it
#
# Name each database, so a shared entity can say which one a table is in — two databases may both
# hold a `customer` table.

# %%
runner.add_databases(
    copies={
        "crm": ("crm_prod", "crm_test"),
        "billing": ("billing_prod", "billing_test"),
    }
)

# %% [markdown]
# ## A plan per database
#
# Each is proposed and reviewed exactly as in Tutorial 10 — discovery twice, review twice.
# Nothing about the plans is cross-database; only the people are.

# %%
plans = {
    "crm": runner.proposed_plan("crm").confirm_all().purge("audit_log"),
    "billing": runner.proposed_plan("billing").confirm_all(),
}

# %% [markdown]
# ## The people who appear in both
#
# This is the only genuinely cross-database decision, and it is one statement: *these tables
# describe the same people, and here is how each database names them.*

# %%
runner.add_databases(
    copies={
        "crm": ("crm_prod", "crm_test"),
        "billing": ("billing_prod", "billing_test"),
    },
    plans=plans,
    shared_entities=[
        shared_entity(
            "rt_person",
            across={
                # The same person is `person_id` in the CRM and `customer_ref` in
                # billing. One shared column name would make most real pairs
                # impossible to express, so each database names its own.
                "crm": ("customer", "person_id"),
                "billing": ("invoice", "customer_ref"),
            },
            replace=["email"],
        )
    ],
)

# %% [markdown]
# ## Check the join before committing to it
#
# The single most useful thing to do first: look at the key values side by side.
#
# ```text
# crm.customer.person_id      : 1001, 1002, 1003
# billing.invoice.customer_ref: 1001, 1002, 1003   ← they line up
# ```
#
# If one side is a UUID and the other an integer, you have the wrong column — and you want
# to know that now rather than after a forty-table copy.

# %%
runner.run()
runner.statuses()

# %% [markdown]
# Every plan is checked and every shared entity resolved before a single row is written.
#
# Each database is written by its own jobs, so one can land while another fails. Retrying
# the failed one is safe: it collects the same entities from every database, in the same
# order, with the same seed, and so gives everyone the replacement the others already did.

# %% [markdown]
# ## The consequence nobody expects
#
# Because identities come from collecting every shared entity and resolving it the same way in every job, **the set of
# databases is part of the identity function**. Add a third database next quarter and every
# fake name changes — in *all* the copies.
#
# That is correct; the alternative is inconsistency. But it means an estate refreshed with
# an extra source shares no people with the previous one. Worth knowing before you promise
# anyone a stable test estate.
