with open("eval/render_v7_4track_smoketest_fast.py", "r") as f:
    lines = f.readlines()
with open("eval/render_v7_4track_smoketest_fast.py", "w") as f:
    for line in lines:
        if "A_start_idx =" in line:
            f.write("        L = int(W_sec * SR)\n")
        if "L = int(W_sec * SR)" in line and "A_start_idx =" not in line:
            continue
        f.write(line)
