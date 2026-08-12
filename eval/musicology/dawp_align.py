#!/usr/bin/env python3
"""dawp_align.py — align Bitwig .dawproject stems <-> tracks <-> clips <-> song sections.

Kim 2026-08-12 (Two Suns in Phrygia, first DAWproject ground-truth). Resolves the flat-stem
naming ambiguity ("which stem is a sub-mix of which group") using the project's explicit track
hierarchy, converts the arrangement to seconds (beats x 60/bpm), pulls track-1's named section
blocks (the song structure), matches each exported stem FLAC to its track/group/send, and cross-
references clips against sections (presence/absence of each element per section).

Run: python3 dawp_align.py <project.xml> <stems_dir> [--json OUT]
Precursor to dawp_to_frames.py (tick-exact 88-key note-grid + gate streams).
"""
import argparse, glob, json, os, re, sys
import xml.etree.ElementTree as ET


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_xml")
    ap.add_argument("stems_dir")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    root = ET.parse(args.project_xml).getroot()

    tr = root.find("Transport")
    bpm = float(tr.find("Tempo").get("value")); ts = tr.find("TimeSignature")
    num, den = int(ts.get("numerator")), int(ts.get("denominator"))
    spb = 60.0 / bpm                          # seconds per beat (quarter)
    def sec(beat): return round(float(beat) * spb, 3)

    # --- track tree: id -> {name,ctype,parent,group(top-level group name)} ---
    tracks, order = {}, []
    def walk(el, parent, top):
        for t in el.findall("Track"):
            tid = t.get("id"); nm = t.get("name", "?"); ct = t.get("contentType", "?")
            mine_top = top if top is not None else (nm if ct == "tracks" else None)
            tracks[tid] = dict(name=nm, ctype=ct, parent=parent, group=top)
            order.append(tid)
            walk(t, tid, mine_top)
    walk(root.find("Structure"), None, None)

    # --- arrangement: track id -> [clips] (name,t0,dur in sec) + note count ---
    lanes_by_track, notes_by_track = {}, {}
    top_lanes = root.find("Arrangement").find("Lanes")
    for ln in top_lanes.findall("Lanes"):
        tref = ln.get("track"); clips_el = ln.find("Clips")
        clips, nnotes = [], 0
        if clips_el is not None:
            for c in clips_el.findall("Clip"):
                t0 = float(c.get("time", 0)); dur = float(c.get("duration", 0))
                clips.append(dict(name=c.get("name", ""), t0b=t0, t0=sec(t0),
                                  durb=dur, dur=sec(dur), endb=t0 + dur))
                nnotes += len(c.findall(".//Note"))
        lanes_by_track[tref] = clips
        notes_by_track[tref] = nnotes

    # --- sections = clips on the top 'Arrangement' (notes) track (id2) ---
    sect_tid = next((tid for tid, t in tracks.items()
                     if t["name"] == "Arrangement" and t["parent"] is None), None)
    sections = sorted(lanes_by_track.get(sect_tid, []), key=lambda c: c["t0b"])

    # --- match stem FLACs to tracks / groups / sends / master ---
    stems = sorted(os.path.basename(p) for p in glob.glob(os.path.join(args.stems_dir, "*.flac")))
    by_name = {}
    for tid, t in tracks.items():
        by_name.setdefault(t["name"], tid)
    stem_map = []
    for s in stems:
        base = s[:-5]
        kind = tid = grp = None
        m = re.match(r"(.+?) GROUP Master$", base)
        mm = re.match(r"(.+?) SEND$", base)
        if base == "Master":
            kind = "master"
        elif m:
            kind, grp = "group", m.group(1)
        elif mm:
            kind, grp = "send", mm.group(1)
        else:
            nm = re.sub(r"^\d+\s+", "", base)             # strip "NN " export prefix
            tid = by_name.get(nm)
            kind = "track" if tid else "unmatched"
            grp = tracks.get(tid, {}).get("group")
        stem_map.append(dict(stem=s, kind=kind, track=tid,
                             track_name=tracks.get(tid, {}).get("name") if tid else None,
                             group=grp, ctype=tracks.get(tid, {}).get("ctype"),
                             n_clips=len(lanes_by_track.get(tid, [])) if tid else None,
                             n_notes=notes_by_track.get(tid) if tid else None))

    # --- section x element: which tracks have a clip overlapping each section ---
    def active_in(a0, a1):
        out = []
        for tid, clips in lanes_by_track.items():
            if tid == sect_tid or not clips:
                continue
            if any(c["t0b"] < a1 and c["endb"] > a0 for c in clips):
                out.append(tracks.get(tid, {}).get("name", tid))
        return out

    # ---------- report ----------
    print(f"=== Two Suns in Phrygia — {bpm:.0f} bpm {num}/{den} | {len(tracks)} tracks | "
          f"{sum(notes_by_track.values())} notes ===")
    print(f"\nSONG SECTIONS (track 'Arrangement', {len(sections)} blocks):")
    print(f"  {'section':<14} {'bars':>5} {'start':>8} {'end':>8}")
    for c in sections:
        bars = c["durb"] / num
        print(f"  {c['name']:<14} {bars:>5.0f} {c['t0']:>7.1f}s {sec(c['endb']):>7.1f}s")

    print(f"\nSTEM -> TRACK -> GROUP ({len(stem_map)} stems):")
    for m in stem_map:
        tag = (f"track '{m['track_name']}'  group={m['group']}  {m['ctype']}  "
               f"{m['n_clips']}clips {m['n_notes']}notes" if m["kind"] == "track"
               else m["kind"].upper() + (f" '{m['group']}'" if m["group"] else ""))
        print(f"  {m['stem']:<48} -> {tag}")

    print("\nELEMENTS ACTIVE PER SECTION (from clip overlap):")
    for c in sections:
        act = active_in(c["t0b"], c["endb"])
        print(f"  {c['name']:<14} ({len(act):2d}): {', '.join(act)}")

    if args.json:
        json.dump(dict(bpm=bpm, time_sig=[num, den], sec_per_beat=spb,
                       sections=sections, tracks=tracks, stem_map=stem_map,
                       lanes_by_track=lanes_by_track, notes_by_track=notes_by_track),
                  open(args.json, "w"), indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
