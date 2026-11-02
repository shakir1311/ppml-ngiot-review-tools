import sys

from .gui import main

if __name__ == "__main__":          # the processes of a parallel run import this module too: only the app itself starts the window
    sys.exit(main())
