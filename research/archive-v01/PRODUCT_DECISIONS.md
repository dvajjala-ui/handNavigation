# Product decisions: what HandNavigate should become

**Decision date:** 22 October 2026  
**Status:** Product proposal informed by a bounded local experiment; no customer demand or production reliability has been established.

## 1. The product promise

> Show a recurring task. Review the program it becomes. Let verified execution handle the repetition.

The product should not promise that one demonstration yields an indefinitely correct human replacement. Demonstrations show examples, not a complete specification. Successful teaching must surface what the system did not learn.

A useful automation comprises five things: an input contract, a selected execution environment, approved steps and branches, observable success criteria, and a policy for uncertainty. A recording supplies evidence for some of those things. It does not automatically supply all five.

## 2. The first customer and first job

My recommended initial design partner repeatedly retrieves authorized files or reports from a single business-controlled portal. Start with retrieval rather than consequential external writes. Choose a task with a concrete downloadable result and a repeat frequency high enough that maintenance effort matters.

The synthetic image collector in this pack is a mechanism test, not the market wedge. It resembles the user's daily collection example without making a third-party website's permission, login, ranking, or content-rights policy a hidden dependency.

The first real-site pilot should have the site owner's or authorized operator's approval, an explicit result contract, a representative account, a controlled output folder, and a human responsible for reviewing exceptions. Do not start by promising coverage of every social platform.

## 3. What this experiment changes

The local experiment supports the narrow proposition that browser controls, variable input, bounded iteration, and checked downloads do not inherently require repeated inference.

It does not establish that the hard part of teaching has been solved. The recorder experiment captures fill/click events and binds an explicitly identified example value to a parameter. The collection loop, alternative label, identity attributes, and file verifier are authored by an engineer.

Therefore the next differentiating investment should be **the teaching and review experience**, not model fine-tuning and not adding more click primitives.

## 4. Three independently visible confidence questions

The UI should answer three different questions instead of presenting one unexplained confidence score:

1. **Intent clarity:** Did the user explicitly approve the variables, loop limits, ordering, duplicate policy, and stopping conditions?
2. **Execution qualification:** Has this recipe version been exercised in the specified browser, site, account role, locale, and relevant error cases?
3. **Outcome verification:** What independent evidence confirms the requested result?

A workflow can have a clear intent and an untested environment. A run can execute its steps successfully but fail verification. A safe halt can be correct behavior while still failing to finish the user's task.

## 5. A workflow needs an execution contract

Store a reviewable record with each admitted workflow:

| Field | Example for a future authorized collection workflow |
|---|---|
| Goal | Save up to ten unique eligible files for the chosen topic |
| Input variables | Topic, maximum files, output collection |
| Ranking semantics | First eligible results returned to this account at run time |
| Site and account scope | Exact permitted origins and account role |
| Environment | Supported browser version, desktop runner, locale |
| Permissions | Read portal content; save to one approved directory |
| Verification | Actual file, format, bounded size, stable source association |
| Uncertainty | Halt on ambiguous identity or unknown controls |
| Duplicate semantics | Within this run; cross-day deduplication separately configurable |
| Missed schedule | Skip, run once later, or notify; never silently choose |
| AI policy | Strictly off, or approved diagnosis/repair budget |
| Evidence | Tested cases, outstanding gaps, version and reviewer |

This contract is product metadata, not a guarantee. Its value is making the limits visible and enforceable.

## 6. Teaching design

The first usable teaching flow should be:

**Scope:** Select one tab/site and a task. Show exactly what will be recorded and what will stay local.

**Demonstrate:** Capture relevant actions and interface context, with a visible recording indicator. Support pause and discard. Do not record the whole desktop by default.

**Explain:** Let the person add intent such as "the date changes every morning" or "keep going until ten unique files are saved." Explanation complements the recording; it is not a permission grant.

**Resolve ambiguity:** Ask specific questions at the point of uncertainty. For example: "Do you want the first ten returned results, or only items with a particular property?" Do not ask generic setup questions when the recording already contains the answer.

**Review:** Present the inferred recipe, inputs, outputs, branches, and stop conditions. Distinguish observed facts from proposed generalizations.

**Rehearse:** Use new inputs, then show evidence of the result. Corrections should edit the recipe or add an explicit branch, not merely accumulate an invisible chat history.

**Admit:** Approve an exact version for a bounded environment. Any behavior-changing repair invalidates that admission until rechecked.

## 7. AI should have separate authoring and runtime budgets

A model can propose a draft workflow, identify likely variable values, explain a failure, or suggest a changed target. None of those outputs should directly acquire permission to execute arbitrary code.

For familiar work, the runtime should interpret a constrained representation and make zero inference calls. For new situations, assisted repair should create a proposed patch with a clear before/after diff and associated regression cases.

A lower-cost model is not automatically safe for repair just because the original workflow was authored by a stronger model. Evaluate each role separately. Cache approved structure, not unreviewed guesses.

No model-assisted path is implemented in this pack. The zero-call field is structurally true because there is no model client; it is not a production metering implementation.

## 8. What counts as product success

The primary metric should be verified requested outcomes per admitted run. Report partial completion, safe stops, interventions, and incorrect outcomes separately.

Track teaching time, accepted-versus-rewritten drafts, replay frequency, zero-inference share, maintenance time per supported workflow, repair recurrence, and total cost per verified outcome. Browser runtime and support labor belong in the cost model, not only tokens.

Do not convert this pack's test pass count into a production completion percentage. Fault cases intentionally pass by refusing the task, and the synthetic cases are not a random sample of real environments.

For intuition about evidence, under a highly simplified independent, constant-error-probability model, observing zero errors in n trials gives a one-sided 95% upper bound of `1 - 0.05^(1/n)`. At n=300 that is about 0.994%. Real UI failures are often correlated, so even that simple bound can overstate how well a small pilot generalizes.

## 9. The next pilot gate

Select one permitted real retrieval task and write the manual result oracle first. Prove the same workflow by hand-authored deterministic code before asking an AI system to author it. Otherwise a bad generated recipe and a bad runtime are difficult to distinguish.

Then compare three authoring methods on the same tasks: engineer-authored, user recording plus structured questions, and AI-assisted interpretation plus user review. Measure completion and maintenance on held-out variations rather than only the demonstrated path.

Admission criteria must be set by task risk. For low-risk retrieval, require no silent incorrect files in the qualification set and transparent shortfall reporting. This is an acceptance condition, not evidence of zero future risk. Consequential writes need a different, stronger pilot with independent read-back and uncertainty reconciliation.

## 10. Intentional exclusions

Do not put unrestricted desktop control, autonomous social engagement, payment execution, arbitrary account access, cloud execution, or on-device mobile control into the first release. Those each introduce a different authority and verification problem.

Do not build a workflow marketplace before workflows can declare permissions, provenance, compatibility, and verification rules. Importing a recipe should be treated as importing a program, not as opening a harmless bookmark.

## 11. Packaging and business hypothesis

The proposed initial offer is a small number of maintained, qualified recurring workflows, not "unlimited automation on every website." The commercial unit should reflect support and execution costs. Whether users pay for it is unvalidated and requires design-partner interviews and actual repeated use.

The most valuable potential differentiation is a short path from demonstration to a trustworthy workflow, plus understandable exception handling. A beautiful dashboard helps, but it cannot substitute for that path.

## Owner decision

Proceed to a permitted real-site validation and teaching experiment. Do not begin foundation-model training. Do not claim production readiness from the local lab. Keep the next release small enough that every promised behavior has a corresponding result check and a visible failure mode.
