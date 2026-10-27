"""Entry point of the packaged .exe: runs the tray app unless a command is given."""

import sys

from airpods_sync.cli.main import main

main(sys.argv[1:] or ["tray"])
