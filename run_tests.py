import subprocess
import sys
import os

def main():
    # Run pytest for the entire project with quiet output
    cwd = os.path.abspath(os.path.dirname(__file__))
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=cwd)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
