# Lessons

Every one of these was learned by getting it wrong first, from the most general to the most specific.

## 1. Derive rather than synchronise

Two artifacts kept in agreement by discipline will diverge, not because anyone is careless but because the effort is permanent and the failure silent. Producing both from the same data removes the question instead of monitoring it. The test that matters is not "do they agree today" but "could they disagree at all".

Whenever you write a checklist to keep two things in step, look for the one place both could be generated from.

## 2. What has no undo is looked at, not reasoned about

Publishing a package cannot be taken back, and writing an instance's configuration overwrites whatever a colleague changed in the console. For those steps we stopped relying on the order of operations and started reading the current state first: a package is compared with the one the instance holds before anything is uploaded, the submission service with the one configured before anything is written.

An irreversible step reads before it writes, even when the reasoning says it need not.

## 3. A default is one deployment's address baked into every other

No address or credential here has a fallback. A wrong database is caught downstream; **a wrong DS Wizard instance is caught by nothing**, because it accepts the package. Every value is required, and a missing one is named.

## 4. Report, or act

Jobs that report run in parallel and name their own culprit; jobs that act wait for every verdict. A deployment that cannot be sure every check passed should not start.

## 5. A test double that agrees with your code proves nothing

Our guard against overwriting an instance's configuration was right in principle and unreachable in practice: the platform returns more keys than a write carries, so the comparison was never true and every run wrote. The test did not see it because the fake returned exactly what our code produced. Both sides agreed about a shape **neither of them owns**.

Make a double return what the system returns, not what your code sends it.

## 6. Refusing is kinder than silence

Several checks exist because something was being dropped without a word: prose no generator would read, a recommended vocabulary a merge discarded, a chapter description where it means nothing. Each time the fix was to refuse the file and say why. A refusal can be discussed; a silent drop is discovered by whoever reads the output carefully, which is nobody.

## 7. Build the general mechanism early, and say it has no user yet

The merge that stacks profiles supports conflicts, order independence and provenance, and on the standards loaded it performs zero tightenings. Building it first was right, because it makes a future profile a data change. Calling it central today would be false.

## 8. A store that forgets is not a store

A DMP rewritten in place cannot say what it promised last year, nor which rules judged it. The database refuses every update: a change is a new version, beside its assessment and the definitions it was judged by. History is not a feature added later; it is what the table is.

## 9. A cluster is not a laptop

What worked on k3d needed, on a shared cluster, an explicit ingress class, a namespace someone else creates, an account with exactly the rights it needs, an object storage the ingress does not stand in front of, and a wait that survives a cut connection. Each is now a value or a step, tested on a temporary namespace before the real one.

See also the [DS Wizard pitfalls](../guide/dsw.md#pitfalls-we-hit), the ones another pilot deploying DS Wizard will meet first.
