#!/usr/bin/env python3

from calendar import c
import os
import sys
from hashlib import sha256
import typing
import json
from enum import Enum
from collections import OrderedDict
from unicodedata import name


class RunMode(Enum):
    collectHashes = 1
    compareOriginal = 2
    applyData = 3


class progress:
    def __init__(self, total) -> None:
        self.enabled = False
        try:
            from tqdm import tqdm
            self.enabled = True
            self.bar = tqdm(total=total, unit_scale=True)
        except ImportError:
            pass

    def update(self, value):
        if self.enabled:
            self.bar.update(value)


def printUsage(error: str):
    if error:
        print(error)
    print("Usage: offline_sync.py <file to sync> [Target folder for sync output]")
    sys.exit()

# Handy function from: https://stackoverflow.com/questions/510357/how-to-read-a-single-character-from-the-user
# Thanks


def progressRange(distance):
    try:
        from tqdm import tqdm
        return tqdm(range(distance))
    except:
        return range(distance)


def getChar():
    # figure out which function to use once, and store it in _func
    if "_func" not in getChar.__dict__:
        try:
            # for Windows-based systems
            import msvcrt  # If successful, we are on Windows
            getChar._func = msvcrt.getch

        except ImportError:
            # for POSIX-based systems (with termios & tty support)
            import tty
            import sys
            import termios  # raises ImportError if unsupported

            def _ttyRead():
                fd = sys.stdin.fileno()
                oldSettings = termios.tcgetattr(fd)

                try:
                    tty.setcbreak(fd)
                    answer = sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, oldSettings)
                return answer
            getChar._func = _ttyRead
    return getChar._func()


def yesNoPrompt(prompt: str, defValue=True):
    print(prompt)
    result = getChar()
    if result == 'Y' or result == 'y' or (defValue and result == '\n'):
        return True
    return False


def humanFormat(num):
    magnitude = 0
    while abs(num) >= 1024:
        magnitude += 1
        num /= 1024
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'G', 'T'][magnitude])


def hashFile(inputFile: str, blockSize: int):
    fileHasher = sha256()
    hashes = []
    fileSize = os.path.getsize(inputFile)
    print("Hashing file:", inputFile)

    bar = progress(fileSize)
    with open(inputFile, "rb") as inputData:
        dataRemains = True
        while dataRemains:
            inputBlock = inputData.read(blockSize)
            bar.update(len(inputBlock))
            if len(inputBlock) == 0:
                dataRemains = False
            else:
                blockHash = sha256(inputBlock).hexdigest()
                fileHasher.update(inputBlock)
                hashes.append(blockHash)
    return (fileHasher.hexdigest(), hashes)


def collectHashes(inputFile: str, outputfile: str, blockSize: int = 1024 * 1024):
    fileHasher = sha256()
    fileData = {}
    if not os.path.exists(inputFile):
        print("Input file:", inputFile, "does not exist! Aborting.")
        sys.exit()
    fileData["oldSize"] = os.path.getsize(inputFile)
    fileData["hashSize"] = blockSize
    (fileData["oldFileHash"], fileData["oldHashes"]) = hashFile(inputFile, blockSize)

    print("Split file into", len(fileData["oldHashes"]), "hash blocks. Writing", outputfile, "for comparison with original")
    with open(outputfile, "w") as outputData:
        data = json.dumps(fileData, indent=4)
        outputData.write(data)

    dupHashes = {}
    for hash in fileData["oldHashes"]:
        if hash not in dupHashes:
            dupHashes[hash] = 1
        else:
            dupHashes[hash] += 1
    filteredHashes = filter(lambda x: x[1] > 1, dupHashes.items())
    dict = OrderedDict(sorted(filteredHashes, key=lambda x: x[1]))
    duplicates = []
    # Add a sample for each
    for item in dict.items():
        dup = {}
        dup["Hash"] = item[0]
        dup["Count"] = item[1]
        for a in range(len(fileData["oldHashes"])):
            if fileData["oldHashes"][a] == item[0]:
                dup["SampleBlock"] = a
                break
        duplicates.append(dup)

    with open(outputfile + ".hashFrequency", "w") as dupData:
        output = json.dumps(duplicates, indent=4)
        dupData.write(output)


def collectData(inputFile: str, hashesFile: str, outputFolder: str):
    fileData = {}
    with open(hashesFile, "r") as hashFileData:
        hashData = hashFileData.read()
        fileData = json.loads(hashData)
    if not "hashSize" in fileData:
        print("Hashsize not found in input hashfile. Aborting.")
        sys.exit()
    fileData["newSize"] = os.path.getsize(inputFile)
    blockSize = int(fileData["hashSize"])
    (fileData["newFileHash"], fileData["newHashes"]) = hashFile(inputFile, blockSize)

    fileData["nonMatching"] = []
    for a in range(len(fileData["newHashes"])):
        if a <= len(fileData["oldHashes"]) and fileData["newHashes"][a] == fileData["oldHashes"][a]:
            continue
        fileData["nonMatching"].append(a)
    diffSize = len(fileData["nonMatching"]) * blockSize

    if fileData["newFileHash"] == fileData["oldFileHash"] and fileData["oldSize"] == fileData["newSize"]:
        print("Files have matching hashes and lengths. Nothing to do")
        sys.exit()

    if len(fileData["nonMatching"]) == 0:
        print("No different blocks found. Nothing to do.")
        sys.exit()

    print("Found", len(fileData["nonMatching"]), "blocks that don't match. Total size of changes will be:", humanFormat(diffSize))
    if not yesNoPrompt("Generate binarydiff files (Y/n)?"):
        sys.exit()

    if not os.path.exists(outputFolder):
        os.makedirs(outputFolder, exist_ok=True)

    if not os.path.isdir(outputFolder):
        print("Error with output folder:", outputFolder, "Please correct. Aborting.")
        sys.exit()

    with open(inputFile, "rb") as inputData:
        for offset in fileData["nonMatching"]:
            inputData.seek(offset * blockSize)
            data = inputData.read(blockSize)
            readHash = sha256(data).hexdigest()
            if readHash != fileData["newHashes"][offset]:
                print("Error with has of block", offset, " Aborting.")
                sys.exit()
            dataFileName = os.path.basename(inputFile) + ".FixBlock" + str(offset)
            with open(os.path.join(outputFolder, dataFileName), "wb") as blockFile:
                blockFile.write(data)
    finalDataFile = os.path.basename(inputFile) + ".FixHashes"
    with open(os.path.join(outputFolder, finalDataFile), "w") as finalData:
        data = json.dumps(fileData, indent=4)
        finalData.write(data)


def applyFixes(inputFile: str, outputFile: str, hashesFolder: str):
    pass


if len(sys.argv) < 2:
    printUsage("No file specified.")

syncFile = sys.argv[1]
targetFolder = os.getcwd()
runMode = RunMode.collectHashes
comparingMode = False

if len(sys.argv) > 2 and os.path.isdir(sys.argv[2]):
    targetFolder = sys.argv[2]

hashOutputFile = os.path.join(targetFolder, os.path.basename(syncFile) + ".hashes")
dataOutputFolder = os.path.join(targetFolder, os.path.basename(syncFile) + ".data")
applyOutputFile = os.path.join(targetFolder, os.path.basename(syncFile) + ".fixed")

if not os.path.exists(syncFile):
    printUsage("File", syncFile, "not found.")

if os.path.exists(hashOutputFile):
    runMode = RunMode.compareOriginal
    if os.path.exists(dataOutputFolder) and os.path.isdir(dataOutputFolder):
        runMode = RunMode.applyData

if runMode == RunMode.applyData:
    if not yesNoPrompt("Apply mode detected, is this correct (y/N)?", False):
        runMode = RunMode.compareOriginal


if runMode == runMode.collectHashes:
    collectHashes(syncFile, hashOutputFile)
elif runMode == runMode.compareOriginal:
    collectData(syncFile, hashOutputFile, dataOutputFolder)
elif runMode == runMode.applyData:
    applyFixes(syncFile, applyOutputFile, dataOutputFolder)
