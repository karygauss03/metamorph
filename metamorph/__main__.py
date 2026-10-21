"""Command line entry point.

  metamorph                     start the background drag watcher (single instance)
  metamorph open FILE...        show the wheel for FILEs at the pointer
  metamorph settings            open the settings window
  metamorph list FILE...        print the conversions/tools available for FILEs
  metamorph run OP FILE...      run an operation headlessly, e.g. convert:image:png
  metamorph to EXT FILE...      shorthand: convert FILEs to EXT
  metamorph doctor              show which backends were found
"""

import argparse
import sys
import time


def _headless(args):
    from . import registry, settings, util

    if args.command == "doctor":
        for name, where in util.backends().items():
            print(f"{name:12} {where or 'MISSING'}")
        print(f"\n{registry.conversion_count()} conversions, "
              f"{sum(op.available() for op in registry.TOOLS)} tools, {len(registry.ACTIONS)} actions available")
        return 0
    if args.command == "list":
        for kind in ("convert", "tool"):
            ops = registry.operations_for(args.files, kind)
            print(f"{kind}: " + ", ".join(f"{op.label} [{op.id}]" for op in ops))
        return 0

    if args.command == "to":
        target = args.op.lower().lstrip(".")
        target = registry.ALIASES.get(target, target)
        ops = {op.target: op for op in registry.operations_for(args.files, "convert")}
        if target not in ops:
            print(f"Cannot convert to {target}; available: {', '.join(ops)}", file=sys.stderr)
            return 2
        op = ops[target]
    else:
        op = registry.ALL.get(args.op)
        if not op or op.kind == "action":
            print(f"Unknown operation {args.op}", file=sys.stderr)
            return 2
    params = {p.key: p.default for p in op.params}
    for item in args.param or []:
        key, _, value = item.partition("=")
        params[key] = value
    conf = settings.load()
    ctx = registry.Context(conf, params, args.out)
    start = time.monotonic()
    try:
        outputs = registry.execute(op, args.files, ctx)
    except util.ConversionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for out in outputs:
        print(out)
    print(f"done in {time.monotonic() - start:.1f}s", file=sys.stderr)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in ("list", "run", "to", "doctor"):
        parser = argparse.ArgumentParser(prog="metamorph")
        sub = parser.add_subparsers(dest="command", required=True)
        sub.add_parser("doctor")
        p = sub.add_parser("list")
        p.add_argument("files", nargs="+")
        for name in ("run", "to"):
            p = sub.add_parser(name)
            p.add_argument("op")
            p.add_argument("files", nargs="+")
            p.add_argument("-o", "--out", help="output folder (default: beside the source)")
            p.add_argument("-p", "--param", action="append", help="tool parameter key=value")
        return _headless(parser.parse_args(argv))
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    from .app import run_app
    return run_app(argv)


if __name__ == "__main__":
    sys.exit(main())
