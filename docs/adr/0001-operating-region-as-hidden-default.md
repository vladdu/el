# Operating region is a hidden Default premise

The memo's EL assumes every transistor runs in its active region unless a hint (e.g. `cp`) says otherwise. That assumption is what lets the BE law fix the base-emitter drop. We model it as a Default quantity, `(Q REGION) = ACTIVE`, which is an antecedent of every BE deduction, but we leave it out of `why` output so explanations still match the memo's transcripts. We chose this over an implicit model (the transistor simply has or lacks the BE law) because the memo's planned reductio extension needs to retract exactly this assumption when a contradiction arises. With the region as a premise, that becomes ordinary premise retraction, the same mechanism `change` uses, and the existing dependency records show which deductions to forget.

## Consequences

- The dependency graph contains antecedents that `why` doesn't print. Code that walks justifications must not assume printed and recorded antecedents are the same.
- A `cp` hint sets its transistors' region to unknown rather than removing a law.
