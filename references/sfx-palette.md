# Sound-effect palette and selection

Choose a sound in this order:

```text
visible motion family → sound family → reuse cap → semantic special slot
```

The current project default reuse cap is 3 occurrences per asset, configurable in the plan. A cap is a repetition guard, not a quality score.

| Motion family | Sound family | Typical spoken function |
|---|---|---|
| pop/reveal | soft pop, click, restrained prompt | small fact or parameter |
| impact/scale landing | hit or impact | core conclusion or major number |
| sweep/wipe | whoosh/sweep | transition or rapid movement |
| mechanical open/operation | mechanical cue | machine, fixture, equipment |
| typing/character reveal | typing/UI | typed explanation or entry |
| confirmation | ding/prompt | confirmed result or CTA |
| warning pulse/shake | warning cue | genuine risk or warning |

Each audible group records `motion_family`, `sound_family`, spoken function, reason, and source/target locator. The editor verifies the complete audio material closure, path, source range, target range, volume, fades, and overlap. Do not restore a sound the user removed or replaced.
