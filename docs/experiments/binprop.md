# BinProp commentary experiment

Archived on 2026-11-26. Halogen generated fresh answers for each arm on eight
positions with fixed Stockfish 17.1 lines. One reviewer scored anonymized
answers, prioritizing factual accuracy. The prototype used the released
Opus 5 motif library. [BinProp revision](https://github.com/oripress/BinProp/tree/6c3e1a709dae51adef00b4abd17a1cc2ce90b7ed)

| Minimum fit | Positions with motifs | BinProp wins–losses–ties | Median added time to first text / completion |
| --- | ---: | ---: | ---: |
| 0.75 | 1/8 | 3–2–3 | 7.7 s / 7.2 s |
| 2/3 | 8/8 | 3–4–1 | 43.6 s / 43.9 s |

Seven pairs at 0.75 used identical prompts. At 2/3, grounded explanation scores
rose from 8/16 to 14/16 and answers with a material error rose from 2/8 to 5/8.
Local motif computation took about 2.1 seconds per position. The added detail
came with enough errors and delay to retire the prototype.
