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
# # Tutorial 12 Database connections (Beta)
#
# A database job never carries a password. It carries the **name** of a connection, and the
# platform holds the rest. This tutorial is about those connections: what you can connect to,
# how to add one, how to check it, and how to keep it tidy. The last part recaps what happens
# to each column once a connection is in use.
#
# You can do everything here from the web app too (**Settings → Database connections**, or
# **New connection** in the source and target pickers). Use whichever you prefer: they are the
# same connections.
#
# | You want to…                       | Where                                         |
# | ---------------------------------- | --------------------------------------------- |
# | copy a database, step by step      | Tutorial 10                                   |
# | add, test, rename, remove a source | this tutorial                                 |

# %%
# NOT_YET_RUNNABLE: needs an API released with database connections, and a database to connect to in the CI stack.
import os

from avatars import Manager
from avatars.models import ConnectionDraft, ConnectionPatch

# %%
manager = Manager(api_key=os.environ.get("AVATAR_API_KEY"))
connections = manager.auth_client.connections

# %% [markdown]
# ## What can I connect to?
#
# The platform does not open databases itself. A small, separate **connector** service holds
# the drivers, and is the only part that ever sees a password. It is not reachable from outside
# the platform's own network, and your data goes from the database to the platform's storage
# without passing through your machine.
#
# Ask which databases this deployment can reach:

# %%
for engine in connections.list_engines().engines:
    state = "ready" if engine.available else "not on this deployment"
    note = " (preview)" if engine.preview else ""
    print(f"{engine.label:28} {state}{note}")

# PostgreSQL                   ready
# MySQL                        ready
# ...
# Snowflake                    ready (preview)
# IBM Db2                      not on this deployment (preview)

# %% [markdown]
# **Preview** means the connector offers it but it has not been proven against a real server
# yet. Try it on something you can afford to get wrong first.
#
# Each engine describes its own form, so you never assemble a connection string by hand:

# %%
postgres = next(e for e in connections.list_engines().engines if e.engine == "postgresql")
for field in postgres.fields:
    marks = ("required " if field.required else "") + ("secret" if field.secret else "")
    print(f"{field.key:10} {field.label:10} {marks}")

# host       Host       required
# port       Port       required
# database   Database   required
# username   User       required
# password   Password   required secret
# sslmode    SSL mode

# %% [markdown]
# A warehouse asks different things — Snowflake wants an account, a warehouse and a role, and
# BigQuery wants a project, a dataset and a service-account key, with no host at all. That is
# why the form is described by the platform rather than written into this client.

# %% [markdown]
# ## What do I already have?
#
# Connections come from two places. The ones your **operator** declared are read-only. The ones
# **you or your organization** stored are yours to manage.

# %%
for connection in connections.list_connections().connections:
    print(f"{connection.name:20} {connection.engine:11} {connection.scope.value:13}")

# sample-pg            postgresql  deployment
# sample-pg-target     postgresql  deployment

# %% [markdown]
# A listing never contains a connection string. `connection.redacted` shows the host and the
# database, enough to tell two apart, and nothing you could connect with.
#
# ## Adding one
#
# Two things to decide:
#
# * **Who may use it.** `scope="user"` is yours alone: nobody else in your organization sees
#   it, administrators included. `scope="organization"` is for every member, and only an
#   administrator can create one.
# * **The credentials.** They are **write-only**: sent once, stored encrypted, never returned.
#   Not by this API, not by the web app, not in a job.
#
# The tutorial changes nothing on your deployment unless you give it a database to practise
# on. Set `TUTORIAL_DB_HOST` (and the other `TUTORIAL_DB_*` variables) to run the steps below.

# %%
HOST = os.environ.get("TUTORIAL_DB_HOST")
NAME = "tutorial-scratch"

if HOST:
    created = connections.put_connection(
        ConnectionDraft(
            engine="postgresql",
            label="Tutorial scratch database",
            scope="user",
            fields={
                "host": HOST,
                "port": os.environ.get("TUTORIAL_DB_PORT", "5432"),
                "database": os.environ.get("TUTORIAL_DB_NAME", "postgres"),
                "username": os.environ.get("TUTORIAL_DB_USER", "postgres"),
                "password": os.environ.get("TUTORIAL_DB_PASSWORD", ""),
            },
        ),
        NAME,
    )
    print(created.name, created.scope.value, created.redacted)
    # tutorial-scratch  user  postgresql://***@db.internal:5432/postgres
else:
    print("No TUTORIAL_DB_HOST set: reading on, nothing is added.")

# %% [markdown]
# A name is letters, digits, `.`, `_` and `-`. It is the reference a job carries, so it is the
# one thing you cannot change without consequences (see *Renaming*, below).
#
# ## Checking it before you trust it
#
# **Test** opens the connection on the server and reports what it found. It reports facts about
# the database, never about the credential:

# %%
if HOST:
    probe = connections.test_connection(NAME)
    print(probe)
    # reachable=True engine='postgresql' has_schema=True is_empty=False table_count=12

# %% [markdown]
# Those three facts — reachable, empty, carries a schema — are exactly what a copy is refused
# on, so a **target** you plan to write to is worth testing before you start: it must have the
# schema and no rows.
#
# When the test fails, the error says *which kind* of failure it was — unreachable, wrong
# credentials, missing database, missing privilege — and never repeats the connection string.
#
# ## Renaming and relabelling
#
# A **label** is only what people see in a picker, and is free to change. A **name** is what
# jobs and saved configurations refer to, so renaming does not touch your running jobs but a
# saved configuration that names the old one will no longer find it.
#
# Neither sends a credential: the platform re-encrypts what it already holds.

# %%
if HOST:
    connections.patch_connection(ConnectionPatch(label="Scratch (practice)"), NAME)
    renamed = connections.patch_connection(ConnectionPatch(name="tutorial-scratch-2"), NAME)
    NAME = renamed.name
    print(NAME)

# %% [markdown]
# ## Changing where it points
#
# To change the host or the password, **replace** the connection: store it again under the same
# name. Replacing needs every field again — the stored credentials are never sent back to
# you, so there is nothing to edit in place.

# %%
if HOST:
    connections.put_connection(
        ConnectionDraft(
            engine="postgresql",
            scope="user",
            fields={
                "host": HOST,
                "port": os.environ.get("TUTORIAL_DB_PORT", "5432"),
                "database": os.environ.get("TUTORIAL_DB_NAME", "postgres"),
                "username": os.environ.get("TUTORIAL_DB_USER", "postgres"),
                "password": os.environ.get("TUTORIAL_DB_PASSWORD", ""),
            },
        ),
        NAME,
    )

# %% [markdown]
# ## Removing it
#
# Deleting forgets the connection and its stored credentials. Jobs that already ran are not
# touched. You can only delete connections you may manage: your own, or — as an administrator
# — your organization's. The operator's cannot be deleted from here.

# %%
if HOST:
    connections.delete_connection(NAME)
    print([c.name for c in connections.list_connections().connections])

# %% [markdown]
# ## Using a connection
#
# A connection is used by name, in a job. The tutorial above is about the thing the name
# stands for; Tutorial 10 uses it:
#
# ```python
# runner.add_database(source="sample-crm", target="sample-crm-test")
# ```
#
# What the platform does with it is worth knowing, because it is why this is safe to hand to
# a team:
#
# * your **worker never holds the password** — it holds a short-lived token good for one
#   connection, and asks the connector to do the reading;
# * the **filtering happens in your database**, so a table of hundreds of millions of rows is
#   not pulled through to be thrown away;
# * the rows travel from the database **straight into the job's storage**, not through the
#   machine you are running this notebook on.

# %% [markdown]
# ## What happens to each column
#
# Once a connection is in use, discovery proposes a **treatment** per column and you review it
# (Tutorial 10 does this end to end). There are four, and a key takes none of them:
#
# | Treatment     | Call on the plan                   | What happens to the values                          |
# | ------------- | ---------------------------------- | --------------------------------------------------- |
# | **anonymize** | `plan.anonymize_columns(t, *cols)` | synthesised from the column's own distribution      |
# | **pseudonymize** | `plan.replace(t, col, strategy)` | replaced by a fake value of the same kind, consistently |
# | **freeze**    | `plan.freeze_columns(t, *cols)`    | kept exactly as they are                            |
# | **skip**      | `plan.drop_columns(t, *cols)`      | the column is not in the copy at all                |
#
# And two at the level of a whole table: `plan.purge(t)` keeps the table with no rows, and
# `plan.ignore(t)` leaves it out of the copy altogether.
#
# **How to choose.** Ask what a consumer of the copy depends on:
#
# * a value that must *look real but belong to nobody* — a name, an email — is
#   **pseudonymized**;
# * a number or a category whose *distribution* matters — an amount, an age — is
#   **anonymized**;
# * a code a consumer filters on (`country = 'FR'`) is **frozen**, and only if it identifies
#   nobody;
# * something nobody needs — a free-text notes column — is **skipped**.
#
# A binary column (a photograph, a scan) is **emptied** in the copy by default: there is
# nothing to synthesise and keeping it would copy the person.
#
# A **key** — a primary or a foreign key — takes none of these. It is re-issued by the run so
# that every join still resolves, and asking to freeze one is refused with the reason.
#
# One last point on choosing: the platform proposes, and **you** decide. A proposal that came
# from a guess has to be confirmed before a job starts, and refusing one is recorded as a
# decision rather than as something nobody looked at.
