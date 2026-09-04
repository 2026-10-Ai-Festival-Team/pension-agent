# P38-2A — Frozen Semantic-Atom Failure Attribution

P38-2A reads only the already frozen P38-2 execution artifact. It does not
change or execute the parser, candidate Agent, retrieval, HCX, citation, or
policy paths.

## Attribution method

For each non-exact requirement composition, the report stores the raw
component-set difference between gold and prediction. Owners are assigned in
this order:

1. a gold atom absent from the P38-1 development ontology -> `ontology_gap`
2. missing subject -> `subject_miss`
3. missing atoms across two or more non-subject components -> `multi_atom_miss`
4. one action / field / modifier component difference -> that component owner
5. matching atoms but different requirement composition -> `composition_miss`

`semantic_binding_error` remains a distinct owner for a future parser that
binds atom instances to different subject/action scopes. P38-2's flat composer
does not produce such a case.

## Interpretation boundary

The attribution distinguishes vocabulary coverage from representational gaps.
It does not prescribe phrase aliases or a parser patch. `historical` is absent
from the P38-1 development ontology and is reported as an ontology gap rather
than a modifier extraction miss.

The next decision is whether the failure distribution supports a redesigned
typed representation/composer or a separately evaluated structured semantic
planner. This report alone does not authorize either change.

## Frozen result

| Primary owner | Count |
| --- | ---: |
| `subject_miss` | 2 |
| `action_miss` | 0 |
| `field_miss` | 3 |
| `modifier_miss` | 1 |
| `multi_atom_miss` | 7 |
| `composition_miss` | 0 |
| `ontology_gap` | 1 |
| `semantic_binding_error` | 0 |

The 14 failures are evenly distributed across withdrawal/document (3),
contribution/comparison (3), transfer (3), and product field/time (3), with two
other multi-field institutional cases. This rules out the composer as the
primary P38-2 bottleneck: most failures occur while interpreting several atoms
from the raw question, before composition can be tested.
