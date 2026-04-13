import sys

from mp3 import good_data

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.stderr.write(f"{sys.argv[0]}: keep only common frames of two MP3 files to standard output\nusage: {sys.agrv[0]} <file_a> <file_b>\n")

file_a = sys.argv[1]
file_b = sys.argv[2]

# Collect all ID3 blocks and frames from the first file as a set
wanted_chunks = set()

for chunk in good_data(open(file_a, 'rb')):
    wanted_chunks.add(chunk)
sys.stderr.write(f"File {file_a} contains {len(wanted_chunks)} frames and tag blocks\n")

dropped = 0
total = 0
for chunk in good_data(open(file_b, 'rb')):
    total += 1
    if chunk not in wanted_chunks:
        dropped += 1
        continue
    sys.stdout.buffer.write(chunk)

sys.stderr.write(f"File {file_b} contained {dropped}/{total} frames and tag blocks not in file {file_a}\n")
