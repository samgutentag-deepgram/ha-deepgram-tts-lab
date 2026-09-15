# Animated diagrams

Standalone `.svg` files: pure SVG plus CSS keyframes, no JavaScript and no SMIL. Each one reads
correctly frozen on the first frame and pins itself to a resting state under
`prefers-reduced-motion`. Each carries a white rounded background so it sits on a light or a dark
page. Open one directly in a browser to watch it, or embed it with `<img src="...">`.

| File | What it explains | Linked from |
| --- | --- | --- |
| `streaming-vs-batch.svg` | A playhead sweeps a shared 0 to 2 second axis. Batch is silent until 1.6 s, streaming makes sound at 0.25 s. | `docs/eli5-ha-flux-tts.html` section 6 |
| `flush-boundaries.svg` | Tokens flow in continuously, audio flows out continuously, and the three flush boundaries light up inside the server box. | `docs/eli5-ha-flux-tts.html` section 7 |
| `voice-resolution.svg` | A language code enters the resolver. The `en` branch reaches `flux-haley-en`, the `es` branch reaches Aura-2. | `docs/eli5-ha-flux-tts.html` section 4 |

The ELI5 page is self contained and carries its own static, theme-aware version of each of these
three ideas, so it prints without them. These files are the moving versions, kept separate so the
eventual build-log write-up can reuse them.
