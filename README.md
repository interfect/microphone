# Microphone: tools for blocking ads in Megaphone-hosted podcasts

I was listening to a podcast hosted through Megaphone, and I noticed that it had dynamically-inserted ads show up a few years into the show's run. Right now, for example, it really wants to sell me the Kpop Demon Hunters meal at McDonalds.

I will not be purchasing the Kpop Demon Hunters meal at McDonalds, so I decided to make a tool to drop the dynamic ads from the podcast.

# Usage

Right now, there's nothing to process an RSS feed or host an episode-processing proxy; you can only fetch a single episode at a time from its `https://traffic.megaphone.fm/XXXXXXX.mp3?XXXXXXX` URL.

1. Clone the repo:
```
git clone https://github.com/interfect/microphone
```
2. Enter the directory
```
cd microphone
```
3. Run `fetch.py` on your URL, and redirect output to an MP3 file:
```
python3 fetch.py 'https://traffic.megaphone.fm/XXXXXXX.mp3?XXXXXXX' >clean-episode.mp3
```
4. Listen to the episode in blissful ignorance of the content of dynamic ads

# How It Works

Other podcast ad-removal tools like [MinusPod](https://github.com/ttlequals0/MinusPod) work by using AI transcription and ad-guessing, so they work even on fixed sponsor segments that are part of the "real" episode, but they require expensive language models to function.

Microphone only works on dynamically-inserted ads that change depending on the listener, and (right now) only on Megaphone podcasts, but it uses a much simpler method.

See, MP3 files are composed of "frames" that each represent a snippet of audio. Megaphone is lazy when it inserts ads into a podcast episode: it re-uses all the frames from the original ad-free source episode, and pastes the ad frames into the file alongside them.

Microphone requests several copies of a podcast episode from Megaphone, each of which is a distinct download that gets assigned its own set of ads. Microphone then compares the files, and throws away any MP3 frames that don't appear in *all* versions of the episode. As long as there isn't an ad that got added to all versions of the episode, this results in throwing out all the ads and keeping just a clean copy of the ad-free episode. No fancy AI models needed.

To parse MP3 frames, Microphone uses a slightly modified version of part of https://github.com/kirkeby/python-mp3, by Sune Kirkeby.

# Future Plans

When it is not 3 AM, I plan to wrap this in an RSS proxy that will serve an RSS feed that links to URLs that, when fetched, run this process and serve a clean subset episode dynamically. It *should* be able to take a source RSS feed in a query parameter and work on any Megaphone podcast.
