## OfflineFileSync

### Purpose
I needed a copy of a very large file (>150GB) from a vendor in a country
with poor internet access. They copied the file to an SSD and shipped it to
me. Unfortunately, something was wrong with the copy.

Instead of trying again, waiting for the post and potentially having the
same problem again, I wrote this utility.

### Usage

Run it against the received file. Send the resulting .hashes file and a copy
of the program to the other side. These are both small, so email should be
sufficient.

They then run the program again with the hashes file present in the
directory. A folder "filename.data" will be generated containing the
incorrect blocks and an update hashes file.

This folder can be sent all at once if they have the means to do so, or the
individual files can be sent via email or some other mechanism.

With all the files in hand, run the program again. It will create a new copy
of the file, with the patches applied.
