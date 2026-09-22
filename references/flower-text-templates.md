# Generic flower-text template contract

Flower-text templates are runtime-supplied presentation prototypes. This
reference defines only the reusable contract:

- identify the source closure and preserve all referenced materials;
- declare semantic category, level, motion family, and allowed overrides;
- resolve text from the approved final-subtitle manifest;
- use relative slots and a runtime subtitle anchor instead of fixed canvas coordinates;
- validate font health, text bounds, safe zones, layer order, and collisions;
- keep project-specific template examples and provenance in an external case record.

The reusable Skill does not ship a project catalog or a project's saved text,
track IDs, draft paths, or asset IDs.
