# References and third-party components

The architecture was inspired by men-qingzheng/dsh-bili-creator (MIT), itself based on dsh-bili-scroll and bili-cli. This package is an independent implementation; the reference repository is not vendored into this distribution.

Bilibili integration executes separately installed bili-agent (kukemc/bili-cli, MIT) and its dependencies. Their licenses remain with those distributions.

Speech invokes the user-provided local gpt-sovits skill and GPT-SoVITS installation. No speech model weights, character artwork, or reference audio are distributed in this package. Character names and voices in the local example remain subject to their original source terms. The supplied SVG clapperboard is original artwork for this plugin.
