# References and third-party components

The architecture was inspired by men-qingzheng/dsh-bili-creator (MIT), itself based on dsh-bili-scroll and bili-cli. This package is an independent implementation; the reference repository is not vendored into this distribution.

Bilibili integration executes separately installed bili-agent (kukemc/bili-cli, MIT) and its dependencies. Their licenses remain with those distributions.

Speech invokes the user-provided local gpt-sovits skill and GPT-SoVITS installation. No speech model weights, character artwork, or reference audio are distributed in this package. Character names and voices in the local example remain subject to their original source terms. The supplied SVG clapperboard is original artwork for this plugin.

Optional Live2D video export invokes separately installed Playwright (Apache-2.0) and the user's local, versioned MuDuo V2.9 model preview adapter, Cubism Core, PixiJS and pixi-live2d-display. Their licenses and applicable distribution terms remain with those components. This plugin does not redistribute Core, model binaries, textures, character art, or the original preview adapter. Only a local in-memory response adapts the existing viewer's frame clock; the sealed character directory is not modified. Playwright browser binaries are installed or selected separately.
