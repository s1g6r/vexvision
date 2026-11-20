"""Command line.

  python -m vexvision find    URL "Q 12"                 # where match Q 12 starts in a stream
  python -m vexvision analyze URL "Q 12" --weights W.pt  # find + analyse one match -> JSON + map
  python -m vexvision analyze-file match.mp4 --weights W.pt [--start 12.5]
  python -m vexvision frame   image.jpg --weights W.pt   # calibrate + detect + read one frame (debug)
"""
import argparse, json, os, sys

def main(argv=None):
    ap = argparse.ArgumentParser(prog="vexvision")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find"); f.add_argument("url"); f.add_argument("match")
    a = sub.add_parser("analyze"); a.add_argument("url"); a.add_argument("match")
    af = sub.add_parser("analyze-file"); af.add_argument("path"); af.add_argument("--start", type=float, default=0.0)
    fr = sub.add_parser("frame"); fr.add_argument("image")
    for p in (a, af, fr):
        p.add_argument("--weights", default="models/vexvision.pt")
        p.add_argument("--fps", type=float, default=6)
        p.add_argument("--teams", help='JSON like {"red":["1A","2B"],"blue":["3C","4D"]}')
        p.add_argument("--official", help='JSON like {"red":120,"blue":95}')
        p.add_argument("--out", default="out")
    args = ap.parse_args(argv)
    if args.cmd == "find":
        from . import stream
        media, dur, title = stream.resolve(args.url)
        print("stream:", title, f"{dur/3600:.1f} h")
        t, r = stream.find_match(media, dur, args.match)
        print(json.dumps({"start_seconds": t, "overlay": r.as_dict() if r else None}, indent=1))
        return
    from .detect import Detector
    from . import analyze as AN, render, stream
    det = Detector(args.weights)
    teams = json.loads(args.teams) if getattr(args, "teams", None) else None
    official = json.loads(args.official) if getattr(args, "official", None) else None
    os.makedirs(args.out, exist_ok=True)
    if args.cmd == "frame":
        import cv2
        from . import calibrate as C, readers
        img = cv2.imread(args.image)
        dets = det(img)
        cal = AN.Calibrator(det)
        ok = cal.solve(img, dets)
        res = {"detections": dets, "calibrated": ok}
        if ok:
            st, tg = readers.read_frame(img, cal.H, cal.cam)
            res.update({"stacks": st, "toggles": tg, "H": cal.H.tolist()})
            vis = C.draw(img, cal.H)
            for d in dets:
                x0, y0, x1, y1 = map(int, d["box"])
                cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0) if d["cls"] == "robot" else (255, 255, 0), 2)
            cv2.imwrite(os.path.join(args.out, "frame_check.jpg"), vis)
        print(json.dumps({k: v for k, v in res.items() if k != "detections"}, indent=1))
        return
    if args.cmd == "analyze":
        media, dur, title = stream.resolve(args.url)
        t0, r = stream.find_match(media, dur, args.match)
        if t0 is None:
            sys.exit(f"could not find {args.match}")
        frames = stream.frames(media, max(0, t0 - 3), 128, fps=args.fps)
        name = args.match.replace(" ", "")
    else:
        frames = stream.video_frames(args.path, args.start, None, fps=args.fps)
        name = os.path.splitext(os.path.basename(args.path))[0]
    res = AN.analyze(frames, det, teams=teams, official=official)
    jp = os.path.join(args.out, f"{name}.json")
    json.dump(res, open(jp, "w"), indent=1, default=float)
    if "robots" in res:
        render.render_match(res, os.path.join(args.out, f"{name}_map.png"))
    print("wrote", jp)

if __name__ == "__main__":
    main()
