# Learning report contract

`learning_report` records reusable packaging, motion, audio, and handoff
patterns without embedding a project's wording or asset provenance.

The report and source objects have closed field sets. Entries use only `id`,
`area`, `pattern`, `evidence_level`, `generalizability`, `anti_pattern`,
`promotion_status`, and an optional opaque external `case_ref`. A
`project_case` source must carry `source.case_ref`; synthetic and manual-review
sources do not need one. Unknown fields are rejected so exact copy, timing,
layer and asset observations cannot be smuggled into the reusable record.

A project case may contain those observations, but they must remain outside
this Skill package.

Only a human-approved, repeatedly observed pattern may be promoted to generic
packaging guidance or a validator rule.
