with open("eval/render_v7_4track_smoketest_fast.py", "r") as f:
    text = f.read()

bad_line = "chroma_target = (chroma_A * torch.tensor(ramp_down).unsqueeze(0).unsqueeze(0) + chroma_B * torch.tensor(ramp_up).unsqueeze(0).unsqueeze(0)).float()"
good_line = """
        chroma_len = chroma_A.shape[-1]
        ramp_up_chroma = torch.linspace(0, 1, chroma_len)
        ramp_down_chroma = torch.linspace(1, 0, chroma_len)
        chroma_target = (chroma_A * ramp_down_chroma.unsqueeze(0).unsqueeze(0) + chroma_B * ramp_up_chroma.unsqueeze(0).unsqueeze(0)).float()
"""

text = text.replace(bad_line, good_line)

with open("eval/render_v7_4track_smoketest_fast.py", "w") as f:
    f.write(text)
