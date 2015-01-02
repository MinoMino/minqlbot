from subprocess import check_output

version = check_output(["git", "describe", "--long", "--tags", "--dirty", "--always"]).decode().strip()
print("VERSION:", version)
if "dirty" in version:
    print("Please commit changes before building.")
    exit(1)

with open("common.h", "r+") as f:
    lines = f.readlines()
    f.seek(0)
    fo.truncate()
    for line in lines:
        if line.startswith("#define MINQLBOT_VERSION"):
            f.write('#define MINQLBOT_VERSION "{}"\n'.format(version))
        else:
            f.write(line)