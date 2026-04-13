from mp3 import frames

for frame in frames(open('~/Desktop/out.mp3')):
    print(f"Frame length {len(frame)}")
