import sys
from subprocess import check_output

def print_usage():
    print("Usage: {} <-set(_debug)|-unset(_debug)>".format(sys.argv[0]))

def set(version):
    with open("common.h", "r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            if line.startswith("#define MINQLBOT_VERSION"):
                f.write('#define MINQLBOT_VERSION "{}"\n'.format(version))
            else:
                f.write(line)

def unset(version):
    with open("common.h", "r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            if line.startswith("#define MINQLBOT_VERSION"):
                f.write('#define MINQLBOT_VERSION "NOT_SET"\n')
            else:
                f.write(line)



if __name__ == "__main__":
    version = check_output(["git", "describe", "--long", "--tags", "--dirty", "--always"]).decode().strip()

    if len(sys.argv) < 2:
        print_usage()
    elif sys.argv[1] == "-set":
        print("Setting to version {}...".format(version))
        if "dirty" in version:
            print("ERROR: Please commit changes before building.")
            exit(1)
        set(version)
        print("Done!")
    elif sys.argv[1] == "-set_debug":
        version += "_debug"
        print("Setting to debug version {}...".format(version))
        set(version)
        print("Done!")
    elif sys.argv[1] == "-unset":
        print("Unsetting version...")
        unset(version)
        print("Done!")
    elif sys.argv[1] == "-unset_debug":
        print("Unsetting debug version...")
        unset(version)
        print("Done!")
    else:
        print_usage()