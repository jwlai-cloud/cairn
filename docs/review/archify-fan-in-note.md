# Why the agent topology is not an archify diagram

The topology overlay was criticised for reading as a table of rows rather than a
multi-agent graph, and archify was the named tool. It did not work out, and this records
why so nobody retries it from scratch.

archify's `workflow` type lays nodes on a lane-by-column grid, which models a swimlane
process flow. Four specialists running in parallel and converging on one planner needs
four nodes in four different lanes at the same column, joining a fifth node in a further
column. The renderer routes the vertical leg of a cross-lane edge through the source
column, so every fan-in edge crosses the intervening lanes' nodes.

Three layouts were tried: planner between the specialists, planner below them, and
planner to the right with empty columns left as routing corridors. Error counts went
36, 20, 21. Explicit `fromSide`/`toSide` did not change it. `clean-flow/edge-through-node`
is enforced at `standard` as well as `showcase`, which is correct - it is a correctness
check, not polish.

`node bin/archify.mjs guide` recommends `workflow` for this scenario but at **low**
confidence, matching only the word "planner".

The remaining lever is `channelX`, giving the fan-in edges a shared vertical corridor.
That needs the renderer's column-to-x mapping, and the skill's fast path explicitly says
not to read renderer internals. Two consecutive rounds failed to improve the error count,
which is the skill's own stopping condition.

The attempted specification is kept beside this note. It is valid against the schema and
factually correct about the graph; only its geometry is unacceptable.

**What was done instead:** the overlay is drawn as a real fan-in in SVG, with node cards
and converging curved edges, sized for a video frame. Hand geometry is the right tool
here because the shape is fixed, small, and known in advance.

The detailed system architecture in `docs/architecture/diagrams/cairn-architecture.*`
remains an archify diagram. That one is a component map, which is what the tool is for,
and it validates cleanly.
