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
# # Tutorial 10 A test database (Beta)
#
# You want a working copy of a production database: same structure, same row counts, same
# joins, no real people.
#
# The shape of it is three steps and a decision in the middle:
#
# 1. **discovery** reads the source and proposes what to do with each table and column;
# 2. **you review** that proposal — nothing runs until you have;
# 3. **the run** copies the database, one job per group of related tables.

# %%
# NOT_YET_RUNNABLE: needs an API released with database runs, and a source database in the CI stack.
import os

from avatars import Manager, shared_entity

# %%
manager = Manager(api_key=os.environ.get("AVATAR_API_KEY"))
runner = manager.create_runner("crm-test-estate", seed=20260908)

# %% [markdown]
# ## Two things to do first
#
# Neither is done for you, by design.
#
# **The target must already have the schema.** Nothing here invents DDL — getting types,
# constraints and indexes subtly wrong would produce a copy that looks complete and behaves
# differently. Create it first:
#
# ```sh
# pg_dump --schema-only prod | psql test
# ```
#
# **The target must be empty.** A non-empty target is refused, never emptied: emptying it is
# the destructive act this tool does not perform.
#
# And the target must be the **same engine** as the source. PostgreSQL into PostgreSQL —
# nothing translates DDL between two type systems.

# %% [markdown]
# ## Describing the copy
#
# Two **named connections** your deployment holds. Ask your administrator which are
# available — you never write a connection string, and a password never reaches a
# configuration document.
#
# Tutorial 12 shows how to see which connections you have, add your own, test and remove them.

# %%
SOURCE, TARGET = "sample-crm", "sample-crm-test"

runner.add_database(source=SOURCE, target=TARGET)

# %% [markdown]
# ## The plan is proposed, not written
#
# **Schema discovery** reads the source and **classification** proposes what each column
# holds — name rules first (a column called `email` holds an email), then a model for the
# ones no rule settles.
#
# It is a job, and it costs nothing: it reads, proposes, and stops. You get the proposal as
# an object, not a document.

# %%
plan = runner.proposed_plan()

print(plan.summary())
# 1 anonymize, 3 pseudonymize; 6 column(s) awaiting review

print(plan.needs_review())
# {'audit_log': ['actor_email'], 'country': ['name'],
#  'customer': ['address', 'email', 'full_name', 'phone']}

# %% [markdown]
# Read the proposals before deciding anything. `suggested_by` is the field that matters:

# %%
for proposal in plan.proposals():
    print(proposal)

# customer.email: EMAIL (by rules, NOT reviewed)
# customer.full_name: FULL_NAME (by rules, NOT reviewed)
# customer.city: ADDRESS (by rules, NOT reviewed)

# %% [markdown]
# * a **name rule** is deterministic and can be confirmed in bulk;
# * a **model** guess comes with a confidence and deserves reading on its own.
#
# ## What it proposes, column by column
#
# There is no advisor to run first. The avatarization's own advisor reads the *data* to
# suggest parameters, and for a database there is none to read — the tables live in the source
# until the run materialises them. So the proposal is made from what discovery already has:
# the classification, and the type the source declares.
#
# Three answers, and the third is the one people are surprised by:

# %%
for table in plan.tables:
    print(table, plan.column_types(table))

# customer {'id': 'int', 'full_name': 'category', 'email': 'category', 'phone': 'category',
#           'address': 'category', 'country_code': 'category', 'person_id': 'int',
#           'created_at': 'datetime_tz'}
# invoice  {'id': 'int', 'customer_id': 'int', 'amount': 'float',
#           'issued_on': 'datetime', 'contact': 'category'}

# %% [markdown]
# | What it saw                    | What it proposes | Why                                       |
# | ------------------------------ | ---------------- | ----------------------------------------- |
# | classified as personal         | pseudonymize     | anonymization *resamples*, so real values survive |
# | a primary or foreign key       | left to the run  | a key is the join, not data               |
# | anything else                  | anonymize        | "ship this verbatim" is a claim only you can make |
#
# Note the third row. A table with no column a rule recognised is proposed for
# **anonymization**, not copying — "no column whose name I know" is a weak claim, and a table
# can identify people through a combination no rule is looking for.
#
# And note what is *not* proposed: freezing and dropping. Whether a consumer depends on a
# column's exact values is not answerable from a schema and a type, so those stay yours.
#
# Only the classifier's verdicts need confirming — six columns here, not all nineteen.
# Anonymizing an ordinary column is the default treatment rather than a guess about content,
# so it asks nothing of anybody.

# %% [markdown]
# ## How many jobs this is
#
# Discovery also works out which tables reference each other. Tables joined by foreign keys
# have to be anonymized **together** — the engine builds a graph over them and requires it
# connected — and tables that reference nothing are separate datasets that happen to share a
# database.
#
# So one group of related tables is one job:

# %%
print(plan.clustered())
# {'cluster-1': ['country', 'customer', 'invoice'], 'cluster-2': ['audit_log']}

# %% [markdown]
# You do not arrange that yourself. Declare the copy and the run works it out — but it is
# worth looking at, because it is the unit everything else is reported in: a status, a
# failure and a re-run are all per group.

# %% [markdown]
# ## Reviewing it
#
# Three kinds of decision, and the plan reads as a sentence:

# %%
plan = (
    plan.confirm_all()  # agree with the classifier
    .reject("customer", "city")  # disagree: this estate needs real cities
    .purge("audit_log")  # keep the table, drop the rows
    .continue_sequence("customer", "id")  # carry on numbering after the copy
)

plan.is_reviewed()  # True — the job will be accepted

# %% [markdown]
# What each of those means:
#
# | Call                   | What it does                                                |
# | ---------------------- | ----------------------------------------------------------- |
# | `confirm_all()`        | agrees with every proposal. A real decision, recorded as one |
# | `reject(t, c)`         | leaves a column alone. **Also** a decision, not a pending item |
# | `purge(t)`             | the table is there, with no rows — for an audit log         |
# | `ignore(t)`            | the table is not in the copy at all                         |
# | `continue_sequence()`  | a copied `SERIAL` keeps numbering, so your first insert does not collide |
#
# `purge` and `ignore` differ on purpose: one leaves a table an application can query and
# find empty, the other leaves nothing. And no classifier can propose either — only you know
# that an audit log should be emptied.
#
# A misspelling is caught immediately, with what does exist:
#
# ```python
# plan.purge("audit_logs")
# # UnknownTableError: this plan has no table 'audit_logs';
# #                    it has: audit_log, country, customer, invoice
# ```

# %% [markdown]
# ## Pseudonymize or anonymize, per column
#
# The two are different and the difference matters. Anonymization **resamples** — it draws
# values from the real distribution, so a real email address ends up in the copy against a
# different person. Pseudonymization **replaces** with a fake value.
#
# Which is why an amount should be anonymized (synthetic, plausible, not somebody's real
# total) and an email address must be pseudonymized. The plan says which per column, and
# `pseudonymize` on a column is what the classifier proposes for personal data.

# %%
print(plan.pseudonymized_columns("customer"))
# {'email': FakeDataStrategy(pii_type=EMAIL), 'full_name': ..., 'phone': ...}

# %% [markdown]
# Four choices per column, and you set them the same way you review anything else:
#
# | Call                          | What happens to the values                     |
# | ----------------------------- | ---------------------------------------------- |
# | `anonymize_columns(t, *cols)` | synthesised from the column's own distribution  |
# | `replace(t, col, strategy)`   | a fake value, consistently                      |
# | `freeze_columns(t, *cols)`    | kept exactly as they are                        |
# | `drop_columns(t, *cols)`      | the column is not in the copy at all            |
#
# A **key** takes none of them, and asking is refused. Freezing a foreign key keeps
# `country_code = 'FR'` while the parent's row for FR has become somebody else — a silently
# broken join, which is the one thing a test database exists to exercise. Rewriting a key so
# parents and children still match is the run's own job.
#
# ```python
# plan.freeze_columns("customer", "country_code")
# # KeyColumnError: customer.country_code is a key, so it cannot be frozen -- the link
# #                 between a parent and its children is what keeps them joinable, and
# #                 rewriting a key is the run's own job.
# ```

# %% [markdown]
# ## One person, one identity
#
# `customer.email` and an invoice's contact address are the same person. Replacing them
# independently gives that person two identities and breaks every join a test database
# exists to exercise.
#
# Say that they are the same people, and how they are identified:

# %%
runner.add_database(
    source=SOURCE,
    target=TARGET,
    plan=plan,
    shared_entities=[
        shared_entity(
            "rt_person",
            tables=["customer", "invoice"],
            key="customer_id",
            replace=["email"],
        )
    ],
)

# %% [markdown]
# The strategy is inferred from the attribute's name — `email` gets realistic fake emails —
# so the common case needs nothing more. Pass `strategy=` when you want something else.
#
# A shared entity — here a person, but it may as well be a product or a configuration code —
# spans the groups of tables freely. Each job collects it from **every** table it names, not
# just its own group, and resolves it with the run's seed — so all the jobs agree about who
# is who. That is why the runner above was given a `seed`:
# without one, each job would invent its own and the same person would come out different in
# each group.

# %% [markdown]
# ## Parameters, then run
#
# Every table the run works on needs its avatarization parameters, like any other table.
# The plan knows which those are:

# %%
for table in plan.participating():
    runner.set_parameters(table, k=5)

runner.run()

# %% [markdown]
# ## What you get
#
# The target database itself — there is nothing to download.
#
# One job per group of related tables, so a status is per group. They do not depend on each
# other: a group is closed under foreign keys, so no ordering between them is needed, and one
# failing leaves the others' work standing.

# %%
runner.get_all_results()
print(runner.statuses())
# {'cluster-1/standard': 'finished', 'cluster-1/signal_metrics': 'finished',
#  'cluster-1/privacy_metrics': 'finished', 'cluster-1/report': 'finished',
#  'cluster-1/report_pia': 'finished', 'cluster-2/standard': 'finished', ...}

# Each group is its own document set, so its results are read the way any run's are.
print(runner.cluster_sets())
# {'cluster-1': '6acc42e5-...', 'cluster-2': '28ef22bc-...'}

# %% [markdown]
# Each job reports what it wrote: tables, rows, any foreign key a purge left pointing at
# nothing, and any table the plan never mentioned. That last one is worth reading — a table
# the plan says nothing about is **not in the copy at all**, so an application that expects it
# finds it missing rather than finding it stale.
#
# ## One thing to know before you point an application at it
#
# **Primary keys are re-issued.** A key is an identifier, so keeping it would let somebody
# match an avatar back to the person it came from — every primary key is replaced by a
# permutation, and every foreign key pointing at it is remapped to match. Referential
# integrity is exact: the joins all still resolve.
#
# But the *values* change, and for a lookup table that is a nuisance:
#
# ```text
#  code |     name              (the source had)
# ------+--------------        ------+---------
#  0    | Renee Orozco          DE   | Germany
#  1    | Cynthia Wall          ES   | Spain
#  2    | Cheryl Hill           FR   | France
#  3    | Casey Rojas           IT   | Italy
# ```
#
# So anything that says `WHERE country_code = 'FR'` — most applications, and every fixture —
# will not find what it expects. Keeping a domain code verbatim is a real requirement and it
# is not expressible yet: `freeze` is refused on a key, because freezing a *foreign* key while
# its parent moves is a silently broken join. Tracked in
# `docs/avatar/input-workflows.md`, spot 3.
