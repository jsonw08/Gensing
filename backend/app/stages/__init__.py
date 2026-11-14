"""Pipeline stages. Each module owns one stage; JSON-shaped dicts are the hand-offs.

Stage -> owner (see docs/gensing.pdf, "Dividing the work"):
  1 score.py    C   MusicXML -> expected_notes
  2 pitch.py    B   audio -> pitch_track
  3 segment.py  B   pitch_track -> sung_notes
  4 align.py    C   expected_notes + sung_notes -> alignment
  5 grade.py    C   alignment + notes -> results
  6 feedback.py B   results -> feedback
"""
