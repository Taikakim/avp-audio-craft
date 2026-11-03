with open("eval/render_v7_4track_smoketest_fast.py", "r") as f:
    text = f.read()

bad = "trans_out = bass_out + drums_out + other_out"
good = """
        if other_out.shape[-1] < L:
            other_out = np.pad(other_out, ((0,0), (0, L - other_out.shape[-1])))
        else:
            other_out = other_out[:, :L]
        trans_out = bass_out + drums_out + other_out
"""

text = text.replace(bad, good)

with open("eval/render_v7_4track_smoketest_fast.py", "w") as f:
    f.write(text)
