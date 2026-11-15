# Alignment Explained: Costs, Dynamic Programming, and DTW

Nov 14, 2026 · @Mehul

> Editable Markdown copy of `Alignment Explained Costs, Dynamic Programming, and DTW.pdf` (8 pages,
> kept unchanged as the original snapshot). Update **this** file, not the PDF. [`DECISIONS.md`](DECISIONS.md) section 4.4 is newer and wins where
> they differ (e.g. every pair carries a `sids` list, not a single `sid`).

Companion to the pipeline notes ([`PIPELINE_NOTES.md`](PIPELINE_NOTES.md)): a step-by-step explanation
of stage 4, built on one small example.

## The problem

Stage 4 gets two lists and must decide which sung note goes with which written note. Example:

```
Written (score):  C   D   E
Sung:             C   E
```

A person sees the singer skipped D. A computer has to consider every possible pairing and pick the one
that makes the most sense:

| Option | Pairing | What it claims happened |
|---|---|---|
| 1 | C=C, D=E, E=nothing | Sang D as E (wrong note), then skipped E |
| 2 | C=C, D=nothing, E=E | Skipped D, everything else correct |
| 3 | Nothing paired; 3 skips + 2 extras | Sang nothing from the score |

Simply pairing the lists in order gives Option 1. That breaks as soon as anything is skipped or added:
every later note gets compared to the wrong target, and the rest of the score turns red.

One rule applies to all options: pairs stay in order. If sung note 2 pairs with written note 3, sung
note 3 can't pair with written note 1. Singers don't go backwards.

## Cost = penalty points

"Cost" just means penalty points. Every claim about what happened gets a penalty, and the best pairing
is the one with the fewest total points.

| Claim | Penalty |
|---|---|
| Sung note X is written note Y (pair them) | semitones apart (0 if identical) |
| Written note was skipped | 3 |
| Sung note was extra | 3 |

Scoring the three options:

| Option | Penalties | Total |
|---|---|---|
| 1 | C=C (0) + D=E (2 semitones) + E skipped (3) | 5 |
| 2 | C=C (0) + D skipped (3) + E=E (0) | **3** |
| 3 | 3 skips (9) + 2 extras (6) | 15 |

Lowest total wins, so Option 2 is chosen.

## Why we need dynamic programming

With 3 notes we can list every option by hand. With 100 written and 100 sung notes there are more
possible pairings than atoms in the universe, so trying them all is impossible.

The trick is to solve small versions of the problem first and reuse their answers. We fill a table
where:

- rows = how many written notes we've handled so far
- columns = how many sung notes we've handled so far
- each cell = the lowest total penalty for handling exactly that many of each

Each cell can only be reached in three ways, from a neighbor that's already filled in:

| Arrow | From | Meaning | Adds |
|---|---|---|---|
| ↖ | the diagonal | pair the current written note with the current sung note | semitones apart |
| ↑ | above | the current written note was skipped | 3 |
| ← | the left | the current sung note was extra | 3 |

For each cell, take the cheapest of the three. That's all dynamic programming means here. A 100 × 100
piece is 10,000 cells, which is instant.

## Filling the table

The completed table for written C D E against sung C E. The arrow shows which move won each cell.

| | nothing sung yet | sung C | sung E |
|---|---|---|---|
| **nothing written yet** | 0 | 3 ← | 6 ← |
| **written C** | 3 ↑ | **0 ↖** | 3 ← |
| **written D** | 6 ↑ | **3 ↑** | 2 ↖ |
| **written E** | 9 ↑ | 6 ↑ | **3 ↖** |

The first row and first column are only skips or only extras, so they just add 3 each step.

Three cells worked out in full:

**Row C, column C**

- pair C with C: 0 (top-left) + 0 = **0** ✓
- skip C: 3 (above) + 3 = 6
- extra C: 3 (left) + 3 = 6

**Row D, column C**

- pair D with C: 3 (top-left) + 2 semitones = 5
- skip D: 0 (above) + 3 = **3** ✓
- extra C: 6 (left) + 3 = 9

**Row E, column E (the final cell)**

- pair E with E: 3 (top-left) + 0 = **3** ✓
- skip E: 2 (above) + 3 = 5
- extra E: 6 (left) + 3 = 9

The bottom-right cell holds the best possible total for the whole problem: **3**.

## Reading off the answer

Start at the bottom-right cell and follow the winning arrows back to the start ("tracing back"):

```
(E, E)  ↖  pair E with E
(D, C)  ↑  D was skipped
(C, C)  ↖  pair C with C
start
```

Result: **C matched, D skipped, E matched.** That's Option 2, found without listing every option.

This trail of arrows is exactly what stage 4 writes to `alignment.json`: a list of matches, skips and
extras that stage 5 then grades.

## The code

Fill the table, remembering which move won each cell, then trace back. `expected` is stage 1's notes
with rests filtered out; `sung` is stage 3's notes after the octave shift is applied.

```python
SKIP = EXTRA = 3

def match_cost(exp, sung):
    return min(abs(exp["midi"] - sung["midi"]), 4)   # semitones apart, capped at 4

def align(expected, sung):
    n, m = len(expected), len(sung)
    table = [[0.0] * (m + 1) for _ in range(n + 1)]
    move = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            options = []
            if i > 0 and j > 0:   # pair (↖)
                options.append((table[i-1][j-1] + match_cost(expected[i-1], sung[j-1]), "match"))
            if i > 0:             # written note skipped (↑)
                options.append((table[i-1][j] + SKIP, "skipped"))
            if j > 0:             # extra sung note (←)
                options.append((table[i][j-1] + EXTRA, "extra"))
            table[i][j], move[i][j] = min(options)

    # trace back from the bottom-right corner
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if move[i][j] == "match":
            pairs.append({"type": "match", "id": expected[i-1]["id"], "sid": sung[j-1]["sid"]})
            i, j = i - 1, j - 1
        elif move[i][j] == "skipped":
            pairs.append({"type": "skipped", "id": expected[i-1]["id"], "sid": None})
            i -= 1
        else:
            pairs.append({"type": "extra", "id": None, "sid": sung[j-1]["sid"]})
            j -= 1
    return pairs[::-1]
```

Running it on the example returns C matched, D skipped, E matched. Good first unit test.

## Choosing the penalties

The penalty sizes decide what kind of mistakes get reported, so they matter more than the code.

**A small pitch error must cost less than skip + extra.** Suppose the singer sings D# instead of D:

| Interpretation | Cost |
|---|---|
| Pair D with D# (1 semitone off) | **1** |
| D skipped + D# extra | 3 + 3 = 6 |

Pairing wins, so stage 5 reports "wrong note: sang D# instead of D", which is the right message. If
skip and extra were cheap (say 0.5 each), the app would report "skipped D, added a random note"
instead.

**The cap at 4 semitones** stops a wildly wrong note from costing so much that the algorithm prefers
to call it a skip plus an extra. Past 4, every wrong note costs the same.

**Timing term (real version):** add a little for being far apart in time, e.g. 0.5 × beats apart.
Pitch still dominates; timing breaks ties and stops a note in bar 2 from pairing with one sung in
bar 9.

**Starting values:** pair = semitones apart (capped at 4) + 0.5 × beats apart; skip = extra = 3. Tune
them on the test recordings with deliberate mistakes.

## DTW: the same table, different moves

DTW (dynamic time warping) also fills a grid and picks the cheapest path. Two things differ.

**1. It compares two curves, not two note lists.** The score is turned into a timeline with one value
per small time step, and compared against stage 2's pitch curve:

```
Score timeline:  C  C  D  D  E  E          (each letter = one time step)
Sung curve:      C  C  C  C  D  E  E  E    (held C long, rushed D)
```

**2. There's no skip or extra move.** Every step on each side must pair with at least one step on the
other. Instead of skipping, DTW stretches and squeezes:

| Arrow | Meaning |
|---|---|
| ↖ | both move forward together |
| ↑ | score moves on, sung stays on the same point (singer rushed) |
| ← | sung moves on, score stays on the same point (singer held longer) |

Each cell's cost is just how different the two pitches are at those points; there's no flat penalty
like our 3. For the example above, the cheapest path pairs:

```
score C C  ↔  sung C C C C   (stretched: held longer)
score D D  ↔  sung D         (squeezed: rushed)
score E E  ↔  sung E E E     (stretched)
```

This handles tempo changes naturally, which is why DTW is popular for free-tempo alignment.

**Its weakness: it can't say "you skipped D."** If D is skipped entirely:

```
Score:  C  C  D  D  E  E
Sung:   C  C  C  E  E  E
```

DTW still has to pair the score's D with something, so it squeezes D onto a sliver of the C-to-E
transition. Detecting the skip needs extra rules afterwards (e.g. "this note got almost no time" or
"the pitch there was nowhere near D"). Likewise an extra note just gets absorbed into a neighboring
stretch.

## Why DTW doesn't need stage 3

Note alignment needs stage 3 because both of its inputs must be lists of notes. The score already is
one, but the recording is just a pitch reading every 10 ms, so stage 3 has to cut it into notes first.

DTW compares like with like:

- The score becomes a curve too: at 80 BPM, a quarter-note C becomes 75 time steps that each say "60".
- The recording is already a curve from stage 2.
- DTW pairs time steps with time steps. No notes are involved on either side.

After DTW runs, each written note "owns" the stretch of sung frames paired with it, and everything
stage 3 would have produced can be read from that stretch:

```
written D (m1-n1)  ↔  sung frames 0.81 s – 1.42 s
   start  = 0.81 s    (first frame paired with it)
   pitch  = median of those frames = 61.71
```

In effect, DTW cuts the curve into notes using the score as a guide. Stage 3 cuts blind, guessing from
the curve alone where notes start and end. Being guided is DTW's strength for timing, and its weakness
for skips and extras: it assumes every written note is there somewhere and nothing else was sung.

## Our choice

We use note alignment as the main approach and keep DTW as a fallback if stage 3 proves unreliable.

| | Note alignment (main) | DTW (fallback) |
|---|---|---|
| Compares | list of notes vs list of notes | curve vs curve, in tiny time steps |
| Moves | pair, skip, extra | pair, stretch, squeeze |
| Skipped / extra notes | reported directly | must be guessed afterwards |
| Needs stage 3 | yes | no |
| Tempo changes | needs tempo scaling first (free mode) | handled naturally |
| Main risk | stage 3 splitting or merging notes | missing skips and extras |

The goal is to report skipped and extra notes explicitly, which note alignment does directly. Its
weakness, dependence on stage 3, is reduced by the split-note merge rule in stage 4.
